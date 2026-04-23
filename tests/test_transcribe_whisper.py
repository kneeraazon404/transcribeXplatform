"""Tests for transcribe_whisper.py — faster-whisper local backend."""
import builtins
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from transcribe_whisper import (
    WhisperNotInstalledError,
    _ensure_faster_whisper,
    transcribe_with_whisper,
    transcribe_whisper_pipeline,
)
from format_md import SpeakerTurn


# ---------------------------------------------------------------------------
# _ensure_faster_whisper
# ---------------------------------------------------------------------------

class TestEnsureFasterWhisper:
    def test_raises_when_not_installed(self):
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "faster_whisper":
                raise ImportError("No module named 'faster_whisper'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(WhisperNotInstalledError, match="faster-whisper not installed"):
                _ensure_faster_whisper()

    def test_passes_when_installed(self):
        fake_module = MagicMock()
        with patch.dict("sys.modules", {"faster_whisper": fake_module}):
            _ensure_faster_whisper()  # should not raise


# ---------------------------------------------------------------------------
# transcribe_with_whisper
# ---------------------------------------------------------------------------

def _make_segment(start, end, text):
    seg = MagicMock()
    seg.start = start
    seg.end = end
    seg.text = text
    return seg


def _make_whisper_model(segments, language="en", language_probability=0.99):
    info = MagicMock()
    info.language = language
    info.language_probability = language_probability

    model = MagicMock()
    model.transcribe.return_value = (iter(segments), info)
    return model


class TestTranscribeWithWhisper:
    def test_file_not_found(self, tmp_path):
        fake_module = MagicMock()
        with patch.dict("sys.modules", {"faster_whisper": fake_module}):
            with pytest.raises(FileNotFoundError):
                transcribe_with_whisper(tmp_path / "missing.wav")

    def test_basic_transcription(self, tmp_path):
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF fake")

        segments = [
            _make_segment(0.0, 5.0, "Hello world"),
            _make_segment(5.0, 10.0, "How are you"),
        ]
        model = _make_whisper_model(segments)
        fake_fw = MagicMock()
        fake_fw.WhisperModel.return_value = model

        with patch.dict("sys.modules", {"faster_whisper": fake_fw}):
            turns = transcribe_with_whisper(audio)

        assert len(turns) == 2
        assert turns[0].text == "Hello world"
        assert turns[1].text == "How are you"

    def test_timestamps_preserved(self, tmp_path):
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF fake")

        segments = [_make_segment(13.5, 20.0, "Testing")]
        model = _make_whisper_model(segments)
        fake_fw = MagicMock()
        fake_fw.WhisperModel.return_value = model

        with patch.dict("sys.modules", {"faster_whisper": fake_fw}):
            turns = transcribe_with_whisper(audio)

        assert turns[0].start_seconds == pytest.approx(13.5)
        assert turns[0].end_seconds == pytest.approx(20.0)

    def test_all_segments_attributed_to_speaker_1(self, tmp_path):
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF fake")

        segments = [
            _make_segment(0, 5, "First"),
            _make_segment(5, 10, "Second"),
        ]
        model = _make_whisper_model(segments)
        fake_fw = MagicMock()
        fake_fw.WhisperModel.return_value = model

        with patch.dict("sys.modules", {"faster_whisper": fake_fw}):
            turns = transcribe_with_whisper(audio)

        # All turns should have generic label → renders as "Speaker 1"
        assert all(len(t.speaker_label) <= 1 or t.speaker_label.isdigit() for t in turns)

    def test_empty_segments_skipped(self, tmp_path):
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF fake")

        segments = [
            _make_segment(0, 5, "  "),  # whitespace only
            _make_segment(5, 10, ""),   # empty
            _make_segment(10, 15, "Real content"),
        ]
        model = _make_whisper_model(segments)
        fake_fw = MagicMock()
        fake_fw.WhisperModel.return_value = model

        with patch.dict("sys.modules", {"faster_whisper": fake_fw}):
            turns = transcribe_with_whisper(audio)

        assert len(turns) == 1
        assert turns[0].text == "Real content"

    def test_language_code_passed_to_model(self, tmp_path):
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF fake")

        model = _make_whisper_model([])
        fake_fw = MagicMock()
        fake_fw.WhisperModel.return_value = model

        with patch.dict("sys.modules", {"faster_whisper": fake_fw}):
            transcribe_with_whisper(audio, language_code="es")

        call_kwargs = model.transcribe.call_args
        assert call_kwargs[1].get("language") == "es" or "es" in call_kwargs[0]

    def test_model_size_passed_to_constructor(self, tmp_path):
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF fake")

        model = _make_whisper_model([])
        fake_fw = MagicMock()
        fake_fw.WhisperModel.return_value = model

        with patch.dict("sys.modules", {"faster_whisper": fake_fw}):
            transcribe_with_whisper(audio, model_size="small")

        fake_fw.WhisperModel.assert_called_once()
        call_args = fake_fw.WhisperModel.call_args
        assert call_args[0][0] == "small" or call_args[1].get("model_size_or_path") == "small"


# ---------------------------------------------------------------------------
# transcribe_whisper_pipeline
# ---------------------------------------------------------------------------

class TestTranscribeWhisperPipeline:
    def _make_media_info(self, path, has_audio=True):
        from media_probe import MediaInfo
        return MediaInfo(
            path=Path(path),
            duration_seconds=30.0,
            has_audio=has_audio,
            has_video=False,
            audio_codec="mp3",
            video_codec=None,
        )

    def _make_audio_result(self, wav_path):
        from ffmpeg_audio import AudioExtractResult
        return AudioExtractResult(
            input_path=wav_path,
            media_info=MagicMock(),
            output_wav_path=wav_path,
            stderr_tail="",
        )

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            transcribe_whisper_pipeline(
                tmp_path / "missing.mp3",
                tmp_path / "out.md",
            )

    def test_non_media_extension_raises(self, tmp_path):
        txt = tmp_path / "doc.txt"
        txt.write_text("not audio")
        media_info = self._make_media_info(txt, has_audio=False)
        with patch("transcribe_whisper.probe_media", return_value=media_info):
            with pytest.raises(ValueError, match="Invalid file type"):
                transcribe_whisper_pipeline(txt, tmp_path / "out.md")

    def test_no_audio_stream_raises(self, tmp_path):
        video = tmp_path / "silent.mp4"
        video.write_bytes(b"fake")
        media_info = self._make_media_info(video, has_audio=False)
        with patch("transcribe_whisper.probe_media", return_value=media_info):
            with pytest.raises(ValueError, match="No audio stream"):
                transcribe_whisper_pipeline(video, tmp_path / "out.md")

    def test_successful_pipeline_creates_markdown(self, tmp_path):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        wav = tmp_path / "audio_normalized.wav"
        wav.write_bytes(b"RIFF fake")

        media_info = self._make_media_info(audio)
        audio_result = self._make_audio_result(wav)
        turns = [
            SpeakerTurn("A", 0.0, 5.0, "Hello from Whisper"),
        ]
        out_md = tmp_path / "out.md"

        with patch("transcribe_whisper.probe_media", return_value=media_info):
            with patch("transcribe_whisper.normalize_to_wav", return_value=audio_result):
                with patch("transcribe_whisper.transcribe_with_whisper", return_value=turns):
                    md_path, _ = transcribe_whisper_pipeline(audio, out_md)

        assert md_path == out_md.resolve()
        assert "Hello from Whisper" in out_md.read_text(encoding="utf-8")

    def test_title_in_output(self, tmp_path):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        wav = tmp_path / "audio_normalized.wav"
        wav.write_bytes(b"RIFF fake")

        media_info = self._make_media_info(audio)
        audio_result = self._make_audio_result(wav)
        turns = [SpeakerTurn("A", 0.0, 5.0, "Test")]
        out_md = tmp_path / "out.md"

        with patch("transcribe_whisper.probe_media", return_value=media_info):
            with patch("transcribe_whisper.normalize_to_wav", return_value=audio_result):
                with patch("transcribe_whisper.transcribe_with_whisper", return_value=turns):
                    transcribe_whisper_pipeline(audio, out_md, title="Whisper Test")

        assert "# Whisper Test" in out_md.read_text(encoding="utf-8")

    def test_temp_dir_cleaned_up(self, tmp_path):
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        wav = tmp_path / "audio_normalized.wav"
        wav.write_bytes(b"RIFF fake")

        media_info = self._make_media_info(audio)
        audio_result = self._make_audio_result(wav)
        turns = [SpeakerTurn("A", 0.0, 5.0, "Test")]
        created_dirs = []

        original_mkdtemp = __import__("tempfile").mkdtemp
        def capturing_mkdtemp():
            d = original_mkdtemp()
            created_dirs.append(d)
            return d

        out_md = tmp_path / "out.md"

        with patch("transcribe_whisper.probe_media", return_value=media_info):
            with patch("transcribe_whisper.normalize_to_wav", return_value=audio_result):
                with patch("transcribe_whisper.transcribe_with_whisper", return_value=turns):
                    with patch("tempfile.mkdtemp", side_effect=capturing_mkdtemp):
                        transcribe_whisper_pipeline(audio, out_md, keep_wav=False)

        for d in created_dirs:
            assert not Path(d).exists()
