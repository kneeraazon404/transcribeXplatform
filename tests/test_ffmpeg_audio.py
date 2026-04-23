"""Tests for ffmpeg_audio.py — audio normalization via ffmpeg."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ffmpeg_audio import (
    normalize_to_wav,
    FFmpegNotInstalledError,
    FFmpegProcessError,
)
from media_probe import MediaInfo


def _make_proc(returncode=0, stderr=""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.stderr = stderr
    proc.stdout = ""
    return proc


def _fake_media_info(path, has_audio=True):
    return MediaInfo(
        path=Path(path),
        duration_seconds=60.0,
        has_audio=has_audio,
        has_video=False,
        audio_codec="mp3",
        video_codec=None,
    )


class TestNormalizeToWav:
    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            normalize_to_wav(tmp_path / "nonexistent.mp3", tmp_path)

    def test_ffmpeg_not_installed(self, tmp_path):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        with patch("shutil.which", return_value=None):
            with pytest.raises(FFmpegNotInstalledError):
                normalize_to_wav(audio, tmp_path)

    def test_no_audio_stream_raises(self, tmp_path):
        audio = tmp_path / "silent.mp4"
        audio.write_bytes(b"fake")
        no_audio_info = _fake_media_info(audio, has_audio=False)
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("ffmpeg_audio.probe_media", return_value=no_audio_info):
                with pytest.raises(ValueError, match="No audio stream"):
                    normalize_to_wav(audio, tmp_path)

    def test_ffmpeg_process_error(self, tmp_path):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        media_info = _fake_media_info(audio)
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("ffmpeg_audio.probe_media", return_value=media_info):
                with patch("subprocess.run", return_value=_make_proc(returncode=1, stderr="conversion failed")):
                    with pytest.raises(FFmpegProcessError):
                        normalize_to_wav(audio, tmp_path)

    def test_successful_conversion(self, tmp_path):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        media_info = _fake_media_info(audio)

        def fake_run(cmd, **kwargs):
            # Simulate ffmpeg creating the output file
            out_wav = tmp_path / "audio_normalized.wav"
            out_wav.write_bytes(b"RIFF fake wav")
            return _make_proc(returncode=0)

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("ffmpeg_audio.probe_media", return_value=media_info):
                with patch("subprocess.run", side_effect=fake_run):
                    result = normalize_to_wav(audio, tmp_path)

        assert result.input_path == audio.resolve()
        assert result.output_wav_path.name == "audio_normalized.wav"
        assert result.output_wav_path.parent == tmp_path

    def test_output_directory_created(self, tmp_path):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        out_dir = tmp_path / "nested" / "output"
        media_info = _fake_media_info(audio)

        def fake_run(cmd, **kwargs):
            out_wav = out_dir / "audio_normalized.wav"
            out_wav.parent.mkdir(parents=True, exist_ok=True)
            out_wav.write_bytes(b"RIFF fake wav")
            return _make_proc(returncode=0)

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("ffmpeg_audio.probe_media", return_value=media_info):
                with patch("subprocess.run", side_effect=fake_run):
                    result = normalize_to_wav(audio, out_dir)

        assert out_dir.exists()

    def test_result_contains_media_info(self, tmp_path):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        media_info = _fake_media_info(audio)

        def fake_run(cmd, **kwargs):
            out_wav = tmp_path / "audio_normalized.wav"
            out_wav.write_bytes(b"RIFF fake wav")
            return _make_proc()

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("ffmpeg_audio.probe_media", return_value=media_info):
                with patch("subprocess.run", side_effect=fake_run):
                    result = normalize_to_wav(audio, tmp_path)

        assert result.media_info == media_info

    def test_default_sample_rate_16khz(self, tmp_path):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        media_info = _fake_media_info(audio)
        captured_cmd = []

        def fake_run(cmd, **kwargs):
            captured_cmd.extend(cmd)
            out_wav = tmp_path / "audio_normalized.wav"
            out_wav.write_bytes(b"RIFF fake wav")
            return _make_proc()

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("ffmpeg_audio.probe_media", return_value=media_info):
                with patch("subprocess.run", side_effect=fake_run):
                    normalize_to_wav(audio, tmp_path)

        assert "16000" in captured_cmd

    def test_mono_flag_in_command(self, tmp_path):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        media_info = _fake_media_info(audio)
        captured_cmd = []

        def fake_run(cmd, **kwargs):
            captured_cmd.extend(cmd)
            out_wav = tmp_path / "audio_normalized.wav"
            out_wav.write_bytes(b"RIFF fake wav")
            return _make_proc()

        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("ffmpeg_audio.probe_media", return_value=media_info):
                with patch("subprocess.run", side_effect=fake_run):
                    normalize_to_wav(audio, tmp_path)

        assert "1" in captured_cmd  # -ac 1 for mono
        assert "pcm_s16le" in captured_cmd
