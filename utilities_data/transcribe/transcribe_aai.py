from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

import assemblyai as aai
from dotenv import load_dotenv
from ffmpeg_audio import AudioExtractResult, normalize_to_wav
from format_md import assemblyai_to_speaker_turns, save_transcript_markdown
from media_probe import probe_media

# Load environment variables
load_dotenv()


class AssemblyAIError(RuntimeError):
    pass


def _ensure_api_key() -> str:
    """
    Ensure AssemblyAI API key is available.

    Returns:
        API key string

    Raises:
        AssemblyAIError if API key is not found
    """
    api_key = os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise AssemblyAIError(
            "ASSEMBLYAI_API_KEY environment variable not set. "
            "Please add it to your .env file or set it in your environment."
        )
    return api_key


def transcribe_audio_file(
    audio_path: str | Path,
    *,
    language_code: Optional[str] = None,
    speaker_labels: bool = True,
    punctuate: bool = True,
    format_text: bool = True,
) -> aai.Transcript:
    """
    Transcribe an audio file using AssemblyAI.

    Args:
        audio_path: Path to audio file (WAV recommended, but other formats supported)
        language_code: Optional language code (e.g., 'en', 'es'). Auto-detect if None.
        speaker_labels: Enable speaker diarization (default: True)
        punctuate: Add punctuation (default: True)
        format_text: Format text properly (default: True)

    Returns:
        AssemblyAI Transcript object

    Raises:
        AssemblyAIError if transcription fails
    """
    import warnings

    # Suppress Pydantic serialization warning for speech_understanding
    warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

    api_key = _ensure_api_key()
    aai.settings.api_key = api_key

    # Configure transcription
    config = aai.TranscriptionConfig(
        speaker_labels=speaker_labels,
        punctuate=punctuate,
        format_text=format_text,
        speech_models=["universal-2"],
    )
    config.speech_understanding = {
        "request": {
            "speaker_identification": {
                "speaker_type": "name",
                "known_values": [],
            }
        }
    }

    if language_code:
        config.language_code = language_code

    # Transcribe
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(str(audio_path), config)

    if transcript.status == aai.TranscriptStatus.error:
        raise AssemblyAIError(f"Transcription failed: {transcript.error}")

    if not transcript.utterances:
        raise AssemblyAIError(
            "No utterances returned. The audio may be unclear or speaker_labels may not be supported for this audio."
        )

    return transcript


def _extract_speaker_names(transcript: aai.Transcript) -> dict[str, str]:
    """Extract speaker label → detected name mapping from AssemblyAI speech_understanding result."""

    def _parse(su: object) -> dict[str, str]:
        if not isinstance(su, dict):
            return {}
        speakers = (
            su.get("result", {}).get("speaker_identification", {}).get("speakers", [])
        )
        if not isinstance(speakers, list):
            return {}
        return {
            s["speaker_label"]: s["name"]
            for s in speakers
            if isinstance(s, dict) and s.get("speaker_label") and s.get("name")
        }

    try:
        su = getattr(transcript, "speech_understanding", None)
        if su:
            names = _parse(su)
            if names:
                return names
    except Exception:
        pass

    try:
        jr = getattr(transcript, "json_response", None)
        if isinstance(jr, dict):
            su = jr.get("speech_understanding")
            if su:
                names = _parse(su)
                if names:
                    return names
    except Exception:
        pass

    return {}


def transcribe_with_normalization(
    input_file: str | Path,
    output_md: str | Path,
    *,
    language_code: Optional[str] = None,
    title: Optional[str] = None,
    keep_wav: bool = False,
) -> tuple[Path, AudioExtractResult]:
    """
    Complete transcription pipeline: normalize audio, transcribe, save markdown.

    Args:
        input_file: Path to audio/video file (any format)
        output_md: Path to save markdown transcript
        language_code: Optional language code for transcription
        title: Optional title for the transcript
        keep_wav: If True, keep the normalized WAV file (default: False)

    Returns:
        Tuple of (markdown_path, audio_extract_result)
    """
    input_path = Path(input_file).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Probe media info
    print(f"Processing: {input_path.name}")
    try:
        media_info = probe_media(input_path)
    except Exception as e:
        raise ValueError(
            f"Invalid audio/video file: {input_path.name}\n"
            f"Please provide a valid audio or video file (e.g., MP3, MP4, WAV, M4A, etc.)\n"
            f"Error: {e}"
        )

    # Check if file has audio stream
    if not media_info.has_audio:
        # Check if it's obviously not a media file
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
        else:
            raise ValueError(
                f"No audio stream found in file: {input_path.name}\n"
                f"The file must contain an audio track to be transcribed."
            )

    if media_info.duration_seconds:
        duration_mins = media_info.duration_seconds / 60
        print(f"Duration: {duration_mins:.1f} minutes")

    # Create temp directory or use current working directory
    temp_dir = None
    if keep_wav:
        # Save to current working directory (same as MD file behavior)
        wav_output_dir = Path.cwd()
    else:
        # Use temporary directory
        temp_dir = tempfile.mkdtemp()
        wav_output_dir = temp_dir

    try:
        # Normalize audio to WAV
        print("Normalizing audio to 16kHz mono WAV...")
        audio_result = normalize_to_wav(input_path, wav_output_dir)
        print(f"Normalized: {audio_result.output_wav_path}")

        # Transcribe with AssemblyAI
        print("Transcribing with AssemblyAI (this may take a few minutes)...")
        transcript = transcribe_audio_file(
            audio_result.output_wav_path,
            language_code=language_code,
        )
        print(f"Transcription complete! Word count: {len(transcript.words or [])}")

        # Extract speaker names from speech_understanding, then build turns
        speaker_names = _extract_speaker_names(transcript)
        speaker_turns = assemblyai_to_speaker_turns(
            transcript.utterances, speaker_names=speaker_names
        )
        print(f"Detected {len(set(t.speaker_label for t in speaker_turns))} speakers")

        # Save as markdown
        md_path = save_transcript_markdown(
            speaker_turns,
            output_md,
            title=title or f"Transcript: {input_path.stem}",
        )
        print(f"Transcript saved: {md_path}")

        return md_path, audio_result

    finally:
        # Cleanup temp directory if used
        if temp_dir:
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)
