"""Tests for transcribe_aai.py — AssemblyAI integration and speaker name extraction."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from transcribe_aai import (
    AssemblyAIError,
    _ensure_api_key,
    _extract_speaker_names,
    transcribe_with_normalization,
)

# ---------------------------------------------------------------------------
# _ensure_api_key
# ---------------------------------------------------------------------------


class TestEnsureApiKey:
    def test_raises_when_key_missing(self, monkeypatch):
        monkeypatch.delenv("ASSEMBLYAI_API_KEY", raising=False)
        with pytest.raises(AssemblyAIError, match="ASSEMBLYAI_API_KEY"):
            _ensure_api_key()

    def test_returns_key_when_present(self, monkeypatch):
        monkeypatch.setenv("ASSEMBLYAI_API_KEY", "test-key-123")
        assert _ensure_api_key() == "test-key-123"


# ---------------------------------------------------------------------------
# _extract_speaker_names
# ---------------------------------------------------------------------------


class TestExtractSpeakerNames:
    def _make_transcript(self, speech_understanding=None, json_response=None):
        transcript = MagicMock()
        transcript.speech_understanding = speech_understanding
        transcript.json_response = json_response
        return transcript

    def _su_payload(self, speakers):
        return {"result": {"speaker_identification": {"speakers": speakers}}}

    def test_no_speech_understanding_returns_empty(self):
        transcript = self._make_transcript(
            speech_understanding=None, json_response=None
        )
        assert _extract_speaker_names(transcript) == {}

    def test_extracts_names_from_attribute(self):
        payload = self._su_payload(
            [
                {"speaker_label": "A", "name": "Mike"},
                {"speaker_label": "B", "name": "Jennifer"},
            ]
        )
        transcript = self._make_transcript(speech_understanding=payload)
        result = _extract_speaker_names(transcript)
        assert result == {"A": "Mike", "B": "Jennifer"}

    def test_extracts_names_from_json_response(self):
        payload = self._su_payload(
            [
                {"speaker_label": "A", "name": "Alice"},
            ]
        )
        transcript = self._make_transcript(
            speech_understanding=None,
            json_response={"speech_understanding": payload},
        )
        result = _extract_speaker_names(transcript)
        assert result == {"A": "Alice"}

    def test_attribute_takes_priority_over_json_response(self):
        attr_payload = self._su_payload([{"speaker_label": "A", "name": "FromAttr"}])
        jr_payload = self._su_payload([{"speaker_label": "A", "name": "FromJR"}])
        transcript = self._make_transcript(
            speech_understanding=attr_payload,
            json_response={"speech_understanding": jr_payload},
        )
        result = _extract_speaker_names(transcript)
        assert result["A"] == "FromAttr"

    def test_skips_entries_missing_name(self):
        payload = self._su_payload(
            [
                {"speaker_label": "A", "name": "Mike"},
                {"speaker_label": "B"},  # missing name
            ]
        )
        transcript = self._make_transcript(speech_understanding=payload)
        result = _extract_speaker_names(transcript)
        assert "B" not in result
        assert result["A"] == "Mike"

    def test_skips_entries_with_empty_name(self):
        payload = self._su_payload(
            [
                {"speaker_label": "A", "name": ""},
            ]
        )
        transcript = self._make_transcript(speech_understanding=payload)
        result = _extract_speaker_names(transcript)
        assert result == {}

    def test_skips_entries_missing_label(self):
        payload = self._su_payload(
            [
                {"name": "OrphanName"},
            ]
        )
        transcript = self._make_transcript(speech_understanding=payload)
        result = _extract_speaker_names(transcript)
        assert result == {}

    def test_malformed_payload_returns_empty(self):
        transcript = self._make_transcript(speech_understanding="not-a-dict")
        result = _extract_speaker_names(transcript)
        assert result == {}

    def test_getattr_exception_returns_empty(self):
        transcript = MagicMock(spec=[])  # no attributes
        result = _extract_speaker_names(transcript)
        assert result == {}

    def test_empty_speakers_list(self):
        payload = self._su_payload([])
        transcript = self._make_transcript(speech_understanding=payload)
        assert _extract_speaker_names(transcript) == {}


# ---------------------------------------------------------------------------
# transcribe_with_normalization (integration, fully mocked)
# ---------------------------------------------------------------------------


class TestTranscribeWithNormalization:
    def _make_utterance(self, speaker, start_ms, end_ms, text):
        utt = MagicMock()
        utt.speaker = speaker
        utt.start = start_ms
        utt.end = end_ms
        utt.text = text
        return utt

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
            transcribe_with_normalization(
                tmp_path / "missing.mp3",
                tmp_path / "out.md",
            )

    def test_non_media_extension_raises_clear_error(self, tmp_path):
        txt_file = tmp_path / "doc.txt"
        txt_file.write_text("not audio")
        media_info = self._make_media_info(txt_file, has_audio=False)
        with patch("transcribe_aai.probe_media", return_value=media_info):
            with pytest.raises(ValueError, match="Invalid file type"):
                transcribe_with_normalization(txt_file, tmp_path / "out.md")

    def test_no_audio_stream_raises(self, tmp_path):
        video = tmp_path / "silent.mp4"
        video.write_bytes(b"fake")
        media_info = self._make_media_info(video, has_audio=False)
        with patch("transcribe_aai.probe_media", return_value=media_info):
            with pytest.raises(ValueError, match="No audio stream"):
                transcribe_with_normalization(video, tmp_path / "out.md")

    def test_successful_pipeline_creates_markdown(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASSEMBLYAI_API_KEY", "test-key")
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        wav = tmp_path / "audio_normalized.wav"
        wav.write_bytes(b"RIFF fake")

        media_info = self._make_media_info(audio)
        audio_result = self._make_audio_result(wav)
        utterances = [
            self._make_utterance("A", 0, 5000, "Hello world"),
            self._make_utterance("B", 5000, 10000, "Hi there"),
        ]
        transcript = MagicMock()
        transcript.status.name = "completed"
        transcript.utterances = utterances
        transcript.words = ["Hello", "world", "Hi", "there"]
        transcript.speech_understanding = None
        transcript.json_response = None

        import assemblyai as aai

        transcript.status = aai.TranscriptStatus.completed

        out_md = tmp_path / "out.md"

        with patch("transcribe_aai.probe_media", return_value=media_info):
            with patch("transcribe_aai.normalize_to_wav", return_value=audio_result):
                with patch(
                    "transcribe_aai.transcribe_audio_file", return_value=transcript
                ):
                    md_path, _ = transcribe_with_normalization(audio, out_md)

        assert md_path == out_md.resolve()
        content = out_md.read_text(encoding="utf-8")
        assert "Hello world" in content
        assert "Hi there" in content

    def test_title_appears_in_output(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASSEMBLYAI_API_KEY", "test-key")
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        wav = tmp_path / "audio_normalized.wav"
        wav.write_bytes(b"RIFF fake")

        media_info = self._make_media_info(audio)
        audio_result = self._make_audio_result(wav)
        utterances = [self._make_utterance("A", 0, 1000, "Hello")]
        transcript = MagicMock()
        transcript.utterances = utterances
        transcript.words = []
        transcript.speech_understanding = None
        transcript.json_response = None

        import assemblyai as aai

        transcript.status = aai.TranscriptStatus.completed

        out_md = tmp_path / "out.md"

        with patch("transcribe_aai.probe_media", return_value=media_info):
            with patch("transcribe_aai.normalize_to_wav", return_value=audio_result):
                with patch(
                    "transcribe_aai.transcribe_audio_file", return_value=transcript
                ):
                    transcribe_with_normalization(
                        audio, out_md, title="My Custom Title"
                    )

        assert "# My Custom Title" in out_md.read_text(encoding="utf-8")

    def test_speaker_names_used_when_available(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASSEMBLYAI_API_KEY", "test-key")
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        wav = tmp_path / "audio_normalized.wav"
        wav.write_bytes(b"RIFF fake")

        media_info = self._make_media_info(audio)
        audio_result = self._make_audio_result(wav)
        utterances = [self._make_utterance("A", 0, 5000, "Hey there")]
        su_payload = {
            "result": {
                "speaker_identification": {
                    "speakers": [{"speaker_label": "A", "name": "Mike"}]
                }
            }
        }
        transcript = MagicMock()
        transcript.utterances = utterances
        transcript.words = []
        transcript.speech_understanding = su_payload
        transcript.json_response = None

        import assemblyai as aai

        transcript.status = aai.TranscriptStatus.completed

        out_md = tmp_path / "out.md"

        with patch("transcribe_aai.probe_media", return_value=media_info):
            with patch("transcribe_aai.normalize_to_wav", return_value=audio_result):
                with patch(
                    "transcribe_aai.transcribe_audio_file", return_value=transcript
                ):
                    transcribe_with_normalization(audio, out_md)

        assert "Mike: Hey there" in out_md.read_text(encoding="utf-8")

    def test_temp_dir_cleaned_up_after_success(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASSEMBLYAI_API_KEY", "test-key")
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"fake")
        wav = tmp_path / "audio_normalized.wav"
        wav.write_bytes(b"RIFF fake")

        media_info = self._make_media_info(audio)
        audio_result = self._make_audio_result(wav)
        utterances = [self._make_utterance("A", 0, 1000, "Hi")]
        transcript = MagicMock()
        transcript.utterances = utterances
        transcript.words = []
        transcript.speech_understanding = None
        transcript.json_response = None

        import assemblyai as aai

        transcript.status = aai.TranscriptStatus.completed

        created_dirs = []

        original_mkdtemp = __import__("tempfile").mkdtemp

        def capturing_mkdtemp():
            d = original_mkdtemp()
            created_dirs.append(d)
            return d

        out_md = tmp_path / "out.md"

        with patch("transcribe_aai.probe_media", return_value=media_info):
            with patch("transcribe_aai.normalize_to_wav", return_value=audio_result):
                with patch(
                    "transcribe_aai.transcribe_audio_file", return_value=transcript
                ):
                    with patch("tempfile.mkdtemp", side_effect=capturing_mkdtemp):
                        transcribe_with_normalization(audio, out_md, keep_wav=False)

        # All created temp dirs should be cleaned up
        for d in created_dirs:
            assert not Path(d).exists()


# ---------------------------------------------------------------------------
# transcribe_audio_file
# ---------------------------------------------------------------------------


class TestTranscribeAudioFile:
    def test_uses_speech_models_config_field(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASSEMBLYAI_API_KEY", "test-key")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"fake")

        transcript = MagicMock()
        transcript.status = MagicMock()
        transcript.status = __import__("assemblyai").TranscriptStatus.completed
        transcript.utterances = [MagicMock()]
        transcript.words = []
        transcript.speech_understanding = None
        transcript.json_response = None

        with patch("transcribe_aai.aai.TranscriptionConfig") as config_cls:
            fake_config = MagicMock()
            config_cls.return_value = fake_config

            with patch("transcribe_aai.aai.Transcriber") as transcriber_cls:
                transcriber = transcriber_cls.return_value
                transcriber.transcribe.return_value = transcript

                result = __import__("transcribe_aai").transcribe_audio_file(audio)

        assert result is transcript
        assert config_cls.call_count == 1
        assert config_cls.call_args.kwargs["speech_models"] == ["universal-2"]
        assert "speech_model" not in config_cls.call_args.kwargs
        transcriber.transcribe.assert_called_once_with(str(audio), fake_config)
