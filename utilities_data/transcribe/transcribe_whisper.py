from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Optional

from ffmpeg_audio import AudioExtractResult, normalize_to_wav
from format_md import SpeakerTurn, save_transcript_markdown
from media_probe import probe_media


class WhisperNotInstalledError(RuntimeError):
    pass


def _ensure_faster_whisper() -> None:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        raise WhisperNotInstalledError(
            "faster-whisper not installed. Run: uv pip install --python .venv/bin/python faster-whisper"
        )


def transcribe_with_whisper(
    audio_path: str | Path,
    *,
    model_size: str = "base",
    language_code: Optional[str] = None,
    device: str = "cpu",
    compute_type: str = "int8",
) -> list[SpeakerTurn]:
    """
    Transcribe audio using faster-whisper (local, free, no API key required).

    Note: Does not perform speaker diarization — all speech is attributed to 'Speaker 1'.
    For multi-speaker diarization, use the AssemblyAI backend instead.

    Args:
        audio_path: Path to audio file (WAV recommended)
        model_size: Whisper model size — tiny, base, small, medium, large-v3, large-v3-turbo
        language_code: Language code (e.g. 'en', 'es'). Auto-detects if None.
        device: Compute device ('cpu', 'cuda', 'auto')
        compute_type: Quantization type ('int8', 'float16', 'float32')

    Returns:
        List of SpeakerTurn objects (all attributed to 'Speaker 1')
    """
    _ensure_faster_whisper()
    from faster_whisper import WhisperModel

    audio_path = Path(audio_path).expanduser().resolve()
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    print(f"Loading Whisper model '{model_size}' (downloads on first use)...")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    print("Transcribing locally with Whisper (no API key required)...")
    segments, info = model.transcribe(
        str(audio_path),
        language=language_code,
        beam_size=5,
        vad_filter=True,
    )

    print(
        f"Detected language: {info.language} (confidence: {info.language_probability:.1%})"
    )

    turns = []
    for segment in segments:
        text = (segment.text or "").strip()
        if text:
            turns.append(
                SpeakerTurn(
                    # Single-letter label → maps to "Speaker 1" via is_detected_name
                    speaker_label="A",
                    start_seconds=segment.start,
                    end_seconds=segment.end,
                    text=text,
                )
            )

    return turns


def transcribe_whisper_pipeline(
    input_file: str | Path,
    output_md: str | Path,
    *,
    model_size: str = "base",
    language_code: Optional[str] = None,
    title: Optional[str] = None,
    keep_wav: bool = False,
    device: str = "cpu",
) -> tuple[Path, AudioExtractResult]:
    """
    Complete free transcription pipeline: normalize audio, transcribe with Whisper, save markdown.

    Args:
        input_file: Path to audio/video file (any format)
        output_md: Path to save markdown transcript
        model_size: Whisper model size (tiny/base/small/medium/large-v3)
        language_code: Optional language code. Auto-detects if None.
        title: Optional title for the transcript
        keep_wav: If True, keep the normalized WAV file
        device: Compute device ('cpu' or 'cuda')

    Returns:
        Tuple of (markdown_path, audio_extract_result)
    """
    input_path = Path(input_file).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    print(f"Processing: {input_path.name}")
    try:
        media_info = probe_media(input_path)
    except Exception as e:
        raise ValueError(
            f"Invalid audio/video file: {input_path.name}\n"
            f"Please provide a valid audio or video file (e.g., MP3, MP4, WAV, M4A, etc.)\n"
            f"Error: {e}"
        )

    if not media_info.has_audio:
        non_media_extensions = {
            ".md",
            ".txt",
            ".json",
            ".pdf",
            ".doc",
            ".docx",
            ".html",
        }
        if input_path.suffix.lower() in non_media_extensions:
            raise ValueError(
                f"Invalid file type: {input_path.name}\n"
                f"Please provide an audio or video file (e.g., MP3, MP4, WAV, M4A, FLAC, etc.)\n"
                f"You provided a {input_path.suffix} file, which cannot be transcribed."
            )
        raise ValueError(
            f"No audio stream found in file: {input_path.name}\n"
            f"The file must contain an audio track to be transcribed."
        )

    if media_info.duration_seconds:
        print(f"Duration: {media_info.duration_seconds / 60:.1f} minutes")

    temp_dir = None
    if keep_wav:
        wav_output_dir = Path.cwd()
    else:
        temp_dir = tempfile.mkdtemp()
        wav_output_dir = temp_dir

    try:
        print("Normalizing audio to 16kHz mono WAV...")
        audio_result = normalize_to_wav(input_path, wav_output_dir)
        print(f"Normalized: {audio_result.output_wav_path}")

        speaker_turns = transcribe_with_whisper(
            audio_result.output_wav_path,
            model_size=model_size,
            language_code=language_code,
            device=device,
        )
        print(f"Transcription complete! Segments: {len(speaker_turns)}")

        md_path = save_transcript_markdown(
            speaker_turns,
            output_md,
            title=title or f"Transcript: {input_path.stem}",
        )
        print(f"Transcript saved: {md_path}")

        return md_path, audio_result

    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
