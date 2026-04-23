from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Path setup — resolve utilities before any local imports
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT / "utilities_data" / "transcribe"))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from jobs import Job, JobStatus, create_job, get_job

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Transcribe API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev
        "http://127.0.0.1:3000",  # Next.js dev (127.0.0.1)
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "app://.",  # Electron production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_executor = ThreadPoolExecutor(max_workers=4)

VALID_BACKENDS = {"assemblyai", "openai", "deepgram", "whisper"}

# ---------------------------------------------------------------------------
# Health / capability check
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health():
    """Report which backends are available based on installed packages and env vars."""
    assemblyai_ready = bool(os.getenv("ASSEMBLYAI_API_KEY"))
    openai_ready = bool(os.getenv("OPENAI_API_KEY"))
    deepgram_ready = bool(os.getenv("DEEPGRAM_API_KEY"))

    whisper_ready = False
    try:
        import faster_whisper  # noqa: F401

        whisper_ready = True
    except ImportError:
        pass

    return {
        "status": "ok",
        "backends": {
            "assemblyai": assemblyai_ready,
            "openai": openai_ready,
            "deepgram": deepgram_ready,
            "whisper": whisper_ready,
        },
    }


# ---------------------------------------------------------------------------
# Transcription job runner (runs in thread pool)
# ---------------------------------------------------------------------------


def _run_job(
    job: Job,
    input_path: Path,
    output_path: Path,
    backend: str,
    model: str,
    language_code: Optional[str],
    title: Optional[str],
) -> None:
    from ffmpeg_audio import normalize_to_wav
    from format_md import save_transcript_markdown
    from media_probe import probe_media

    wav_path: Optional[Path] = None
    try:
        job.status = JobStatus.PROCESSING
        job.add_message(f"Processing: {input_path.name}")

        # --- Probe ---
        media_info = probe_media(input_path)
        if not media_info.has_audio:
            raise ValueError("File has no audio stream.")

        if media_info.duration_seconds:
            job.add_message(f"Duration: {media_info.duration_seconds / 60:.1f} minutes")

        # --- Normalize to 16 kHz mono WAV ---
        job.add_message("Normalizing audio to 16 kHz mono WAV…")
        wav_dir = output_path.parent / "wav"
        wav_dir.mkdir(parents=True, exist_ok=True)
        audio_result = normalize_to_wav(input_path, wav_dir)
        wav_path = audio_result.output_wav_path
        job.add_message("Audio normalized.")

        # --- Transcribe ---
        turns = _transcribe(job, backend, model, wav_path, language_code)

        speaker_count = len({t.speaker_label for t in turns})
        job.add_message(
            f"Detected {speaker_count} speaker(s), {len(turns)} segment(s)."
        )

        # --- Save markdown ---
        md_path = save_transcript_markdown(
            turns,
            output_path,
            title=title or input_path.stem,
        )
        job.transcript = md_path.read_text(encoding="utf-8")
        job.status = JobStatus.COMPLETED
        job.add_message("Done!")

    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)
        job.add_message(f"Error: {exc}")

    finally:
        if wav_path and wav_path.exists():
            try:
                wav_path.unlink()
                wav_path.parent.rmdir()
            except Exception:
                pass


def _transcribe(
    job: Job, backend: str, model: str, wav_path: Path, language_code: Optional[str]
):
    """Dispatch to the correct provider and return a list of SpeakerTurn objects."""

    if backend == "assemblyai":
        from format_md import assemblyai_to_speaker_turns
        from transcribe_aai import _extract_speaker_names, transcribe_audio_file

        job.add_message("Uploading to AssemblyAI…")
        transcript = transcribe_audio_file(
            wav_path, language_code=language_code or None
        )
        job.add_message(f"AssemblyAI complete. Words: {len(transcript.words or [])}")
        speaker_names = _extract_speaker_names(transcript)
        return assemblyai_to_speaker_turns(
            transcript.utterances, speaker_names=speaker_names
        )

    if backend == "openai":
        from transcribe_openai import transcribe_with_openai

        _model = model or "gpt-4o-mini-transcribe"
        job.add_message(f"Uploading to OpenAI ({_model})…")
        turns = transcribe_with_openai(
            wav_path, model=_model, language_code=language_code or None
        )
        job.add_message(f"OpenAI complete. Segments: {len(turns)}")
        return turns

    if backend == "deepgram":
        from transcribe_deepgram import transcribe_with_deepgram

        _model = model or "nova-3"
        job.add_message(f"Uploading to Deepgram ({_model})…")
        turns = transcribe_with_deepgram(
            wav_path, model=_model, language_code=language_code or None
        )
        job.add_message(f"Deepgram complete. Segments: {len(turns)}")
        return turns

    if backend == "whisper":
        from transcribe_whisper import transcribe_with_whisper

        _model = model or "base"
        job.add_message(f"Transcribing locally with Whisper ({_model})…")
        turns = transcribe_with_whisper(
            wav_path, model_size=_model, language_code=language_code or None
        )
        job.add_message(f"Whisper complete. Segments: {len(turns)}")
        return turns

    raise ValueError(f"Unknown backend: {backend!r}")


# ---------------------------------------------------------------------------
# POST /api/transcribe — upload file and start job
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".flac",
    ".ogg",
    ".aac",
    ".m4a",
    ".wma",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".flv",
    ".webm",
    ".wmv",
}


@app.post("/api/transcribe", status_code=202)
async def start_transcription(
    file: UploadFile = File(...),
    backend: str = Form("assemblyai"),
    model: str = Form(""),
    language: str = Form(""),
    title: str = Form(""),
):
    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Provide an audio or video file.",
        )

    if backend not in VALID_BACKENDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown backend '{backend}'. Choose from: {', '.join(sorted(VALID_BACKENDS))}",
        )

    temp_dir = Path(tempfile.mkdtemp(prefix="transcribe_"))
    input_path = temp_dir / (file.filename or f"upload{suffix}")
    output_path = temp_dir / (Path(file.filename or "transcript").stem + ".md")

    try:
        with open(input_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {exc}")

    job = create_job(filename=file.filename or "upload", temp_dir=temp_dir)

    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        _executor,
        _run_job,
        job,
        input_path,
        output_path,
        backend,
        model or "",
        language or None,
        title or None,
    )

    return {"job_id": job.id}


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id} — poll status
# ---------------------------------------------------------------------------


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.snapshot()


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}/events — SSE live progress stream
# ---------------------------------------------------------------------------


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def _stream():
        sent = 0
        while True:
            snapshot = job.snapshot()
            new_msgs = snapshot["messages"][sent:]
            for msg in new_msgs:
                yield f"data: {json.dumps({'type': 'message', 'text': msg})}\n\n"
            sent += len(new_msgs)

            if snapshot["status"] in (JobStatus.COMPLETED, JobStatus.FAILED):
                yield f"data: {json.dumps({'type': 'done', 'status': snapshot['status'], 'error': snapshot['error']})}\n\n"
                return

            await asyncio.sleep(0.3)

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}/transcript — get transcript content
# ---------------------------------------------------------------------------


@app.get("/api/jobs/{job_id}/transcript")
def download_transcript(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=409, detail=f"Job is {job.status}, not completed yet"
        )
    if not job.transcript:
        raise HTTPException(status_code=404, detail="Transcript not available")

    return JSONResponse(
        content={
            "transcript": job.transcript,
            "filename": f"{Path(job.filename).stem}.md",
        }
    )


# ---------------------------------------------------------------------------
# DELETE /api/jobs/{job_id} — clean up temp files
# ---------------------------------------------------------------------------


@app.delete("/api/jobs/{job_id}", status_code=204)
def delete_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job._temp_dir and job._temp_dir.exists():
        shutil.rmtree(job._temp_dir, ignore_errors=True)
    return None


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
