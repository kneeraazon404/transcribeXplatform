"""Tests for media_probe.py — ffprobe wrapper and MediaInfo parsing."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from media_probe import (
    MediaInfo,
    probe_media,
    FFprobeNotInstalledError,
    FFprobeProcessError,
)

AUDIO_ONLY_OUTPUT = json.dumps({
    "format": {"duration": "120.5"},
    "streams": [
        {"codec_type": "audio", "codec_name": "aac"},
    ],
})

VIDEO_AND_AUDIO_OUTPUT = json.dumps({
    "format": {"duration": "300.0"},
    "streams": [
        {"codec_type": "video", "codec_name": "h264"},
        {"codec_type": "audio", "codec_name": "aac"},
    ],
})

VIDEO_ONLY_OUTPUT = json.dumps({
    "format": {"duration": "60.0"},
    "streams": [
        {"codec_type": "video", "codec_name": "h264"},
    ],
})

NO_STREAMS_OUTPUT = json.dumps({
    "format": {},
    "streams": [],
})

MULTIPLE_AUDIO_OUTPUT = json.dumps({
    "format": {"duration": "90.0"},
    "streams": [
        {"codec_type": "audio", "codec_name": "aac"},
        {"codec_type": "audio", "codec_name": "mp3"},
    ],
})


def _make_proc(returncode=0, stdout="", stderr=""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


class TestProbeMedia:
    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            probe_media(tmp_path / "nonexistent.mp4")

    def test_ffprobe_not_installed(self, tmp_path):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        with patch("shutil.which", return_value=None):
            with pytest.raises(FFprobeNotInstalledError):
                probe_media(audio)

    def test_ffprobe_process_error(self, tmp_path):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        with patch("shutil.which", return_value="/usr/bin/ffprobe"):
            with patch("subprocess.run", return_value=_make_proc(returncode=1, stderr="Invalid data")):
                with pytest.raises(FFprobeProcessError):
                    probe_media(audio)

    def test_audio_only_file(self, tmp_path):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        with patch("shutil.which", return_value="/usr/bin/ffprobe"):
            with patch("subprocess.run", return_value=_make_proc(stdout=AUDIO_ONLY_OUTPUT)):
                info = probe_media(audio)
        assert info.has_audio is True
        assert info.has_video is False
        assert info.audio_codec == "aac"
        assert info.video_codec is None
        assert info.duration_seconds == pytest.approx(120.5)

    def test_video_and_audio_file(self, tmp_path):
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake")
        with patch("shutil.which", return_value="/usr/bin/ffprobe"):
            with patch("subprocess.run", return_value=_make_proc(stdout=VIDEO_AND_AUDIO_OUTPUT)):
                info = probe_media(video)
        assert info.has_audio is True
        assert info.has_video is True
        assert info.audio_codec == "aac"
        assert info.video_codec == "h264"
        assert info.duration_seconds == pytest.approx(300.0)

    def test_video_only_no_audio(self, tmp_path):
        video = tmp_path / "silent.mp4"
        video.write_bytes(b"fake")
        with patch("shutil.which", return_value="/usr/bin/ffprobe"):
            with patch("subprocess.run", return_value=_make_proc(stdout=VIDEO_ONLY_OUTPUT)):
                info = probe_media(video)
        assert info.has_audio is False
        assert info.has_video is True

    def test_no_streams(self, tmp_path):
        f = tmp_path / "empty.mp4"
        f.write_bytes(b"fake")
        with patch("shutil.which", return_value="/usr/bin/ffprobe"):
            with patch("subprocess.run", return_value=_make_proc(stdout=NO_STREAMS_OUTPUT)):
                info = probe_media(f)
        assert info.has_audio is False
        assert info.has_video is False
        assert info.duration_seconds is None

    def test_duration_not_present(self, tmp_path):
        output = json.dumps({"format": {}, "streams": [{"codec_type": "audio", "codec_name": "mp3"}]})
        f = tmp_path / "nodur.mp3"
        f.write_bytes(b"fake")
        with patch("shutil.which", return_value="/usr/bin/ffprobe"):
            with patch("subprocess.run", return_value=_make_proc(stdout=output)):
                info = probe_media(f)
        assert info.duration_seconds is None
        assert info.has_audio is True

    def test_multiple_audio_streams_uses_first(self, tmp_path):
        f = tmp_path / "multi.mkv"
        f.write_bytes(b"fake")
        with patch("shutil.which", return_value="/usr/bin/ffprobe"):
            with patch("subprocess.run", return_value=_make_proc(stdout=MULTIPLE_AUDIO_OUTPUT)):
                info = probe_media(f)
        assert info.audio_codec == "aac"  # first stream codec

    def test_returns_resolved_path(self, tmp_path):
        f = tmp_path / "audio.mp3"
        f.write_bytes(b"fake")
        with patch("shutil.which", return_value="/usr/bin/ffprobe"):
            with patch("subprocess.run", return_value=_make_proc(stdout=AUDIO_ONLY_OUTPUT)):
                info = probe_media(f)
        assert info.path.is_absolute()
