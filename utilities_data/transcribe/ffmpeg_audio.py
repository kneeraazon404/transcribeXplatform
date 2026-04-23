from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from media_probe import MediaInfo, probe_media


class FFmpegNotInstalledError(RuntimeError):
    pass


class FFmpegProcessError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioExtractResult:
    input_path: Path
    media_info: MediaInfo
    output_wav_path: Path
    stderr_tail: str


def _ensure_ffmpeg_installed() -> None:
    if shutil.which("ffmpeg") is None:
        raise FFmpegNotInstalledError(
            "ffmpeg not found in PATH. Install it (mac: brew install ffmpeg; ubuntu: sudo apt-get install ffmpeg)."
        )


def normalize_to_wav(
    input_file: str | Path,
    output_dir: str | Path,
    *,
    sample_rate_hz: int = 16000,
    mono: bool = True,
    overwrite: bool = True,
) -> AudioExtractResult:
    """
    Convert any supported audio/video file to WAV suitable for STT:
    - PCM 16-bit (pcm_s16le)
    - 16kHz by default
    - mono by default
    """
    _ensure_ffmpeg_installed()

    in_path = Path(input_file).expanduser().resolve()
    if not in_path.exists():
        raise FileNotFoundError(
            f"Input file does not exist: {in_path}"
        )

    out_dir = Path(output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    media = probe_media(in_path)
    if not media.has_audio:
        raise ValueError(f"No audio stream found in file: {in_path}")

    out_wav = out_dir / f"{in_path.stem}_normalized.wav"

    cmd = ["ffmpeg", "-hide_banner"]
    cmd += ["-y" if overwrite else "-n"]
    cmd += ["-i", str(in_path)]

    # Choose first audio stream explicitly (helps with files that have multiple audio tracks)
    cmd += ["-map", "0:a:0"]

    # Drop video
    cmd += ["-vn"]

    if mono:
        cmd += ["-ac", "1"]
    cmd += ["-ar", str(sample_rate_hz)]

    # Output: PCM 16-bit WAV
    cmd += ["-c:a", "pcm_s16le", str(out_wav)]

    proc = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.splitlines()[-25:])
        raise FFmpegProcessError(
            f"ffmpeg failed (exit={proc.returncode}). Last stderr lines:\n{tail}"
        )

    stderr_tail = "\n".join(proc.stderr.splitlines()[-10:])

    return AudioExtractResult(
        input_path=in_path,
        media_info=media,
        output_wav_path=out_wav,
        stderr_tail=stderr_tail,
    )
