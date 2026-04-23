"""Tests for transcribe_openai.py — OpenAI Whisper API backend."""
import builtins
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from transcribe_openai import (
    OpenAIKeyMissingError,
    OpenAINotInstalledError,
    _ensure_api_key,
    _ensure_openai,
    transcribe_with_openai,
)
from format_md import SpeakerTurn


# ---------------------------------------------------------------------------
# _ensure_openai
# ---------------------------------------------------------------------------

class TestEnsureOpenAI:
    def test_raises_when_not_installed(self):
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "openai":
                raise ImportError("No module named 'openai'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(OpenAINotInstalledError, match="pip install openai"):
                _ensure_openai()

    def test_passes_when_installed(self):
        fake_module = MagicMock()
        with patch.dict("sys.modules", {"openai": fake_module}):
            _ensure_openai()  # should not raise


# ---------------------------------------------------------------------------
# _ensure_api_key
# ---------------------------------------------------------------------------

class TestEnsureApiKey:
    def test_raises_when_missing(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(OpenAIKeyMissingError, match="OPENAI_API_KEY"):
            _ensure_api_key()

    def test_returns_key_when_present(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        assert _ensure_api_key() == "sk-test-key"


# ---------------------------------------------------------------------------
# transcribe_with_openai
# ---------------------------------------------------------------------------

def _make_segment(start, end, text):
    seg = MagicMock()
    seg.start = start
    seg.end = end
    seg.text = text
    return seg


def _make_openai_response(segments, full_text=""):
    resp = MagicMock()
    resp.segments = segments
    resp.text = full_text
    return resp


class TestTranscribeWithOpenAI:
    def test_file_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        fake_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": fake_openai}):
            with pytest.raises(FileNotFoundError):
                transcribe_with_openai(tmp_path / "missing.wav")

    def test_file_too_large_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        large_file = tmp_path / "big.wav"
        large_file.write_bytes(b"x" * (26 * 1024 * 1024))  # 26 MB
        fake_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": fake_openai}):
            with pytest.raises(ValueError, match="25 MB limit"):
                transcribe_with_openai(large_file)

    def test_basic_transcription(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF" + b"\x00" * 100)

        segments = [
            _make_segment(0.0, 5.0, "Hello world"),
            _make_segment(5.0, 10.0, "How are you"),
        ]
        response = _make_openai_response(segments)

        fake_client = MagicMock()
        fake_client.audio.transcriptions.create.return_value = response
        fake_openai = MagicMock()
        fake_openai.OpenAI.return_value = fake_client

        with patch.dict("sys.modules", {"openai": fake_openai}):
            turns = transcribe_with_openai(audio)

        assert len(turns) == 2
        assert turns[0].text == "Hello world"
        assert turns[1].text == "How are you"

    def test_timestamps_preserved(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF" + b"\x00" * 100)

        segments = [_make_segment(13.5, 20.0, "Test")]
        response = _make_openai_response(segments)
        fake_client = MagicMock()
        fake_client.audio.transcriptions.create.return_value = response
        fake_openai = MagicMock()
        fake_openai.OpenAI.return_value = fake_client

        with patch.dict("sys.modules", {"openai": fake_openai}):
            turns = transcribe_with_openai(audio)

        assert turns[0].start_seconds == pytest.approx(13.5)
        assert turns[0].end_seconds == pytest.approx(20.0)

    def test_all_turns_have_generic_label(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF" + b"\x00" * 100)

        segments = [_make_segment(0, 5, "One"), _make_segment(5, 10, "Two")]
        response = _make_openai_response(segments)
        fake_client = MagicMock()
        fake_client.audio.transcriptions.create.return_value = response
        fake_openai = MagicMock()
        fake_openai.OpenAI.return_value = fake_client

        with patch.dict("sys.modules", {"openai": fake_openai}):
            turns = transcribe_with_openai(audio)

        # All attributed to single generic label (no diarization)
        assert all(t.speaker_label == "A" for t in turns)

    def test_fallback_to_full_text_when_no_segments(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF" + b"\x00" * 100)

        response = _make_openai_response(segments=[], full_text="Full transcript text")
        fake_client = MagicMock()
        fake_client.audio.transcriptions.create.return_value = response
        fake_openai = MagicMock()
        fake_openai.OpenAI.return_value = fake_client

        with patch.dict("sys.modules", {"openai": fake_openai}):
            turns = transcribe_with_openai(audio)

        assert len(turns) == 1
        assert turns[0].text == "Full transcript text"

    def test_empty_segments_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF" + b"\x00" * 100)

        segments = [
            _make_segment(0, 5, "   "),
            _make_segment(5, 10, "Real content"),
        ]
        response = _make_openai_response(segments)
        fake_client = MagicMock()
        fake_client.audio.transcriptions.create.return_value = response
        fake_openai = MagicMock()
        fake_openai.OpenAI.return_value = fake_client

        with patch.dict("sys.modules", {"openai": fake_openai}):
            turns = transcribe_with_openai(audio)

        assert len(turns) == 1
        assert turns[0].text == "Real content"

    def test_model_passed_to_api(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF" + b"\x00" * 100)

        response = _make_openai_response([_make_segment(0, 5, "Hello")])
        fake_client = MagicMock()
        fake_client.audio.transcriptions.create.return_value = response
        fake_openai = MagicMock()
        fake_openai.OpenAI.return_value = fake_client

        with patch.dict("sys.modules", {"openai": fake_openai}):
            transcribe_with_openai(audio, model="gpt-4o-transcribe")

        call_kwargs = fake_client.audio.transcriptions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4o-transcribe"
