from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from ffmpeg_audio import AudioExtractResult, normalize_to_wav
from format_md import SpeakerTurn, save_transcript_markdown
from media_probe import probe_media


class OpenAINotInstalledError(RuntimeError):
    pass


class OpenAIKeyMissingError(RuntimeError):
    pass


# OpenAI 25 MB upload limit for the audio transcriptions endpoint
_OPENAI_MAX_BYTES = 25 * 1024 * 1024


def _ensure_openai() -> None:
    try:
        import openai  # noqa: F401
    except ImportError:
        raise OpenAINotInstalledError(
            "openai package not installed. Run: uv pip install --python .venv/bin/python openai"
        )


def _ensure_api_key() -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise OpenAIKeyMissingError(
            "OPENAI_API_KEY environment variable not set. "
            "Add it to your .env file or export it in your shell."
        )
    return key


def transcribe_with_openai(
    audio_path: str | Path,
    *,
    model: str = "gpt-4o-mini-transcribe",
    language_code: Optional[str] = None,
) -> list[SpeakerTurn]:
    """
    Transcribe audio using the OpenAI audio transcriptions API.

    Models:
      gpt-4o-mini-transcribe  — $0.003/min, fast, good quality (default)
      gpt-4o-transcribe       — $0.006/min, best quality
      whisper-1               — $0.006/min, classic Whisper model

    Limitations:
      - No speaker diarization (all speech attributed to one speaker).
      - 25 MB upload limit. Use AssemblyAI or Deepgram for longer files.

    Returns:
        List of SpeakerTurn objects.
    """
    _ensure_openai()
    api_key = _ensure_api_key()

    from openai import OpenAI

    audio_path = Path(audio_path).expanduser().resolve()
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    file_size = audio_path.stat().st_size
    if file_size > _OPENAI_MAX_BYTES:
        raise ValueError(
            f"File is {file_size / 1024 / 1024:.1f} MB — exceeds OpenAI's 25 MB limit. "
            "Use AssemblyAI or Deepgram for longer recordings."
        )

    client = OpenAI(api_key=api_key)

    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model=model,
            file=f,
            language=language_code or None,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    turns: list[SpeakerTurn] = []
    segments = getattr(response, "segments", None) or []

    for seg in segments:
        text = (getattr(seg, "text", None) or "").strip()
        if text:
            turns.append(
                SpeakerTurn(
                    speaker_label="A",  # OpenAI API has no diarization
                    start_seconds=float(getattr(seg, "start", 0)),
                    end_seconds=float(getattr(seg, "end", 0)),
                    text=text,
                )
            )

    # Fallback when verbose_json returns no segments
    if not turns:
        full_text = (getattr(response, "text", None) or "").strip()
        if full_text:
            turns.append(
                SpeakerTurn(
                    speaker_label="A",
                    start_seconds=0.0,
                    end_seconds=0.0,
                    text=full_text,
                )
            )

    return turns


def transcribe_openai_pipeline(
    input_file: str | Path,
    output_md: str | Path,
    *,
    model: str = "gpt-4o-mini-transcribe",
    language_code: Optional[str] = None,
    title: Optional[str] = None,
    keep_wav: bool = False,
) -> tuple[Path, AudioExtractResult]:
    """
    Full pipeline: probe → normalize → transcribe via OpenAI → save markdown.
    """
    input_path = Path(input_file).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    print(f"Processing: {input_path.name}")
    try:
        media_info = probe_media(input_path)
    except Exception as e:
        raise ValueError(f"Invalid audio/video file: {input_path.name}\n{e}")

    if not media_info.has_audio:
        non_media = {".md", ".txt", ".json", ".pdf", ".doc", ".docx", ".html"}
        if input_path.suffix.lower() in non_media:
            raise ValueError(
                f"Invalid file type: {input_path.suffix}. Provide an audio or video file."
            )
        raise ValueError(f"No audio stream found in: {input_path.name}")

    if media_info.duration_seconds:
        print(f"Duration: {media_info.duration_seconds / 60:.1f} minutes")

    temp_dir = None
    wav_output_dir = Path.cwd() if keep_wav else None
    if not keep_wav:
        temp_dir = tempfile.mkdtemp()
        wav_output_dir = Path(temp_dir)

    try:
        print("Normalizing audio to 16 kHz mono WAV…")
        audio_result = normalize_to_wav(input_path, wav_output_dir)

        print(f"Transcribing with OpenAI ({model})…")
        turns = transcribe_with_openai(
            audio_result.output_wav_path,
            model=model,
            language_code=language_code,
        )
        print(f"Transcription complete. Segments: {len(turns)}")

        md_path = save_transcript_markdown(
            turns, output_md, title=title or input_path.stem
        )
        print(f"Transcript saved: {md_path}")

        return md_path, audio_result

    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
