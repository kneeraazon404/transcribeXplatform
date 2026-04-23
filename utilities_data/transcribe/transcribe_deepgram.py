from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import httpx

from ffmpeg_audio import AudioExtractResult, normalize_to_wav
from format_md import SpeakerTurn, save_transcript_markdown
from media_probe import probe_media


class DeepgramKeyMissingError(RuntimeError):
    pass


_DEEPGRAM_LISTEN_URL = "https://api.deepgram.com/v1/listen"


def _ensure_api_key() -> str:
    key = os.getenv("DEEPGRAM_API_KEY")
    if not key:
        raise DeepgramKeyMissingError(
            "DEEPGRAM_API_KEY environment variable not set. "
            "Add it to your .env file or export it in your shell."
        )
    return key


def transcribe_with_deepgram(
    audio_path: str | Path,
    *,
    model: str = "nova-3",
    language_code: Optional[str] = None,
) -> list[SpeakerTurn]:
    """
    Transcribe audio using the Deepgram REST API.

    Models:
      nova-3    — latest, best quality, $0.0043/min (default)
      nova-2    — reliable, $0.0043/min
      enhanced  — general purpose
      base      — budget tier

    Free tier: 12,000 min/year (~200 hrs) — no card required at deepgram.com.
    Supports speaker diarization (multi-speaker output with labels).

    Returns:
        List of SpeakerTurn objects.
    """
    api_key = _ensure_api_key()

    audio_path = Path(audio_path).expanduser().resolve()
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    params: dict[str, str] = {
        "model": model,
        "smart_format": "true",
        "diarize": "true",
        "punctuate": "true",
        "utterances": "true",
    }
    if language_code:
        params["language"] = language_code

    audio_bytes = audio_path.read_bytes()

    response = httpx.post(
        _DEEPGRAM_LISTEN_URL,
        params=params,
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": "audio/wav",
        },
        content=audio_bytes,
        timeout=300.0,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Deepgram API returned {response.status_code}: {response.text[:400]}"
        )

    data = response.json()
    turns: list[SpeakerTurn] = []

    utterances = (data.get("results") or {}).get("utterances") or []
    if utterances:
        for utt in utterances:
            text = (utt.get("transcript") or "").strip()
            if text:
                turns.append(
                    SpeakerTurn(
                        speaker_label=str(utt.get("speaker", 0)),
                        start_seconds=float(utt.get("start", 0)),
                        end_seconds=float(utt.get("end", 0)),
                        text=text,
                    )
                )
    else:
        # Fallback: channel transcript without diarization
        try:
            alt = data["results"]["channels"][0]["alternatives"][0]
            text = (alt.get("transcript") or "").strip()
            if text:
                turns.append(
                    SpeakerTurn(
                        speaker_label="A",
                        start_seconds=0.0,
                        end_seconds=0.0,
                        text=text,
                    )
                )
        except (KeyError, IndexError, TypeError):
            pass

    return turns


def transcribe_deepgram_pipeline(
    input_file: str | Path,
    output_md: str | Path,
    *,
    model: str = "nova-3",
    language_code: Optional[str] = None,
    title: Optional[str] = None,
    keep_wav: bool = False,
) -> tuple[Path, AudioExtractResult]:
    """
    Full pipeline: probe → normalize → transcribe via Deepgram → save markdown.
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

        print(f"Transcribing with Deepgram ({model})…")
        turns = transcribe_with_deepgram(
            audio_result.output_wav_path,
            model=model,
            language_code=language_code,
        )
        speaker_count = len({t.speaker_label for t in turns})
        print(f"Transcription complete. {speaker_count} speaker(s), {len(turns)} segment(s).")

        md_path = save_transcript_markdown(
            turns, output_md, title=title or input_path.stem
        )
        print(f"Transcript saved: {md_path}")

        return md_path, audio_result

    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
