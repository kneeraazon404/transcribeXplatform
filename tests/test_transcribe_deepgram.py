"""Tests for transcribe_deepgram.py — Deepgram REST API backend."""
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from transcribe_deepgram import (
    DeepgramKeyMissingError,
    _ensure_api_key,
    transcribe_with_deepgram,
)


# ---------------------------------------------------------------------------
# _ensure_api_key
# ---------------------------------------------------------------------------

class TestEnsureApiKey:
    def test_raises_when_missing(self, monkeypatch):
        monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
        with pytest.raises(DeepgramKeyMissingError, match="DEEPGRAM_API_KEY"):
            _ensure_api_key()

    def test_returns_key_when_present(self, monkeypatch):
        monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test-key")
        assert _ensure_api_key() == "dg-test-key"


# ---------------------------------------------------------------------------
# transcribe_with_deepgram
# ---------------------------------------------------------------------------

def _dg_response(utterances=None, channel_text=None, status_code=200):
    """Build a fake httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = ""

    results: dict = {}
    if utterances is not None:
        results["utterances"] = utterances
    if channel_text is not None:
        results["channels"] = [
            {"alternatives": [{"transcript": channel_text}]}
        ]

    resp.json.return_value = {"results": results}
    return resp


class TestTranscribeWithDeeepgram:
    def test_file_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test")
        with pytest.raises(FileNotFoundError):
            transcribe_with_deepgram(tmp_path / "missing.wav")

    def test_api_error_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF fake")
        err_resp = MagicMock()
        err_resp.status_code = 401
        err_resp.text = "Unauthorized"
        with patch("httpx.post", return_value=err_resp):
            with pytest.raises(RuntimeError, match="401"):
                transcribe_with_deepgram(audio)

    def test_basic_transcription_with_utterances(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF fake")

        utterances = [
            {"speaker": 0, "start": 0.0, "end": 5.0, "transcript": "Hello there"},
            {"speaker": 1, "start": 5.2, "end": 9.0, "transcript": "Hi back"},
        ]
        with patch("httpx.post", return_value=_dg_response(utterances=utterances)):
            turns = transcribe_with_deepgram(audio)

        assert len(turns) == 2
        assert turns[0].text == "Hello there"
        assert turns[1].text == "Hi back"

    def test_speaker_labels_preserved(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF fake")

        utterances = [
            {"speaker": 0, "start": 0.0, "end": 5.0, "transcript": "Speaker zero"},
            {"speaker": 1, "start": 5.5, "end": 9.0, "transcript": "Speaker one"},
        ]
        with patch("httpx.post", return_value=_dg_response(utterances=utterances)):
            turns = transcribe_with_deepgram(audio)

        assert turns[0].speaker_label == "0"
        assert turns[1].speaker_label == "1"

    def test_timestamps_preserved(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF fake")

        utterances = [{"speaker": 0, "start": 12.5, "end": 18.0, "transcript": "Test"}]
        with patch("httpx.post", return_value=_dg_response(utterances=utterances)):
            turns = transcribe_with_deepgram(audio)

        assert turns[0].start_seconds == pytest.approx(12.5)
        assert turns[0].end_seconds == pytest.approx(18.0)

    def test_fallback_to_channel_transcript_when_no_utterances(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF fake")

        with patch("httpx.post", return_value=_dg_response(channel_text="Fallback text")):
            turns = transcribe_with_deepgram(audio)

        assert len(turns) == 1
        assert turns[0].text == "Fallback text"
        assert turns[0].speaker_label == "A"

    def test_empty_transcript_text_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF fake")

        utterances = [
            {"speaker": 0, "start": 0.0, "end": 2.0, "transcript": "  "},
            {"speaker": 0, "start": 2.0, "end": 5.0, "transcript": "Real text"},
        ]
        with patch("httpx.post", return_value=_dg_response(utterances=utterances)):
            turns = transcribe_with_deepgram(audio)

        assert len(turns) == 1
        assert turns[0].text == "Real text"

    def test_model_passed_as_query_param(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF fake")

        with patch("httpx.post", return_value=_dg_response(utterances=[])) as mock_post:
            transcribe_with_deepgram(audio, model="nova-2")

        call_kwargs = mock_post.call_args
        params = call_kwargs[1].get("params") or call_kwargs[0][1]
        assert params["model"] == "nova-2"

    def test_auth_header_sent(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEEPGRAM_API_KEY", "my-secret-key")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF fake")

        with patch("httpx.post", return_value=_dg_response(utterances=[])) as mock_post:
            transcribe_with_deepgram(audio)

        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Token my-secret-key"

    def test_no_results_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFF fake")

        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"results": {}}
        with patch("httpx.post", return_value=resp):
            turns = transcribe_with_deepgram(audio)

        assert turns == []
