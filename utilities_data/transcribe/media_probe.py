from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class FFprobeNotInstalledError(RuntimeError):
    pass


class FFprobeProcessError(RuntimeError):
    pass


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    duration_seconds: Optional[float]
    has_audio: bool
    has_video: bool
    audio_codec: Optional[str]
    video_codec: Optional[str]


def _ensure_ffprobe_installed() -> None:
    if shutil.which("ffprobe") is None:
        raise FFprobeNotInstalledError(
            "ffprobe not found in PATH. Install ffmpeg (mac: brew install ffmpeg; ubuntu: sudo apt-get install ffmpeg)."
        )


def probe_media(path: str | Path) -> MediaInfo:
    """
    Uses ffprobe to detect streams/codecs and duration.
    """
    _ensure_ffprobe_installed()

    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(p),
    ]

    proc = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.splitlines()[-25:])
        raise FFprobeProcessError(
            f"ffprobe failed (exit={proc.returncode}). Last stderr lines:\n{tail}"
        )

    data = json.loads(proc.stdout)

    duration = None
    try:
        duration_str = data.get("format", {}).get("duration")
        if duration_str is not None:
            duration = float(duration_str)
    except Exception:
        duration = None

    has_audio = False
    has_video = False
    audio_codec = None
    video_codec = None

    for s in data.get("streams", []) or []:
        codec_type = s.get("codec_type")
        codec_name = s.get("codec_name")
        if codec_type == "audio":
            has_audio = True
            audio_codec = audio_codec or codec_name
        elif codec_type == "video":
            has_video = True
            video_codec = video_codec or codec_name

    return MediaInfo(
        path=p,
        duration_seconds=duration,
        has_audio=has_audio,
        has_video=has_video,
        audio_codec=audio_codec,
        video_codec=video_codec,
    )
