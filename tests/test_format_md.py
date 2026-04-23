"""Tests for format_md.py — timestamp formatting, speaker turn conversion, markdown output."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from format_md import (
    SpeakerTurn,
    format_timestamp,
    is_detected_name,
    format_transcript_as_markdown,
    assemblyai_to_speaker_turns,
    save_transcript_markdown,
)


# ---------------------------------------------------------------------------
# format_timestamp
# ---------------------------------------------------------------------------

class TestFormatTimestamp:
    def test_zero(self):
        assert format_timestamp(0.0) == "[00:00:00]"

    def test_sub_second_truncated(self):
        assert format_timestamp(0.9) == "[00:00:00]"

    def test_59_seconds(self):
        assert format_timestamp(59.0) == "[00:00:59]"

    def test_exactly_one_minute(self):
        assert format_timestamp(60.0) == "[00:01:00]"

    def test_complex(self):
        assert format_timestamp(3661.0) == "[01:01:01]"

    def test_exactly_one_hour(self):
        assert format_timestamp(3600.0) == "[01:00:00]"

    def test_large_value(self):
        # 2h 30m 45s
        assert format_timestamp(9045.0) == "[02:30:45]"

    def test_over_24_hours(self):
        assert format_timestamp(86400.0) == "[24:00:00]"

    def test_fractional_seconds_truncated(self):
        assert format_timestamp(65.999) == "[00:01:05]"


# ---------------------------------------------------------------------------
# is_detected_name
# ---------------------------------------------------------------------------

class TestIsDetectedName:
    def test_single_letter_is_generic(self):
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            assert is_detected_name(letter) is False

    def test_empty_string_is_generic(self):
        assert is_detected_name("") is False

    def test_single_digit_is_generic(self):
        assert is_detected_name("0") is False
        assert is_detected_name("9") is False

    def test_multi_digit_number_is_generic(self):
        assert is_detected_name("10") is False
        assert is_detected_name("99") is False

    def test_unknown_case_insensitive_is_generic(self):
        assert is_detected_name("Unknown") is False
        assert is_detected_name("unknown") is False
        assert is_detected_name("UNKNOWN") is False

    def test_real_name_is_detected(self):
        assert is_detected_name("Mike") is True
        assert is_detected_name("Jennifer") is True
        assert is_detected_name("Em") is True

    def test_two_letter_name_is_detected(self):
        assert is_detected_name("Jo") is True

    def test_full_name_is_detected(self):
        assert is_detected_name("John Smith") is True


# ---------------------------------------------------------------------------
# format_transcript_as_markdown
# ---------------------------------------------------------------------------

class TestFormatTranscriptAsMarkdown:
    def _turn(self, label, start, text):
        return SpeakerTurn(speaker_label=label, start_seconds=start, end_seconds=start + 5, text=text)

    def test_empty_turns_no_title(self):
        assert format_transcript_as_markdown([]) == ""

    def test_empty_turns_with_title(self):
        result = format_transcript_as_markdown([], title="My Meeting")
        assert result == "# My Meeting\n"

    def test_title_appears_at_top(self):
        turns = [self._turn("A", 0, "Hello")]
        result = format_transcript_as_markdown(turns, title="Interview")
        lines = result.splitlines()
        assert lines[0] == "# Interview"
        assert lines[1] == ""
        assert lines[2].startswith("[00:00:00]")

    def test_no_title_no_header(self):
        turns = [self._turn("A", 0, "Hello")]
        result = format_transcript_as_markdown(turns)
        assert not result.startswith("#")

    def test_single_generic_speaker(self):
        turns = [self._turn("A", 0, "Hello world")]
        result = format_transcript_as_markdown(turns)
        assert "Speaker 1: Hello world" in result

    def test_two_generic_speakers_numbered_sequentially(self):
        turns = [
            self._turn("A", 0, "Hi there"),
            self._turn("B", 10, "Hello back"),
        ]
        result = format_transcript_as_markdown(turns)
        assert "Speaker 1: Hi there" in result
        assert "Speaker 2: Hello back" in result

    def test_detected_name_used_directly(self):
        turns = [self._turn("Mike", 0, "Good morning")]
        result = format_transcript_as_markdown(turns)
        assert "Mike: Good morning" in result
        assert "Speaker" not in result

    def test_mixed_detected_and_generic(self):
        turns = [
            self._turn("Mike", 0, "Hey there"),
            self._turn("A", 5, "Hi Mike"),
        ]
        result = format_transcript_as_markdown(turns)
        assert "Mike: Hey there" in result
        assert "Speaker 1: Hi Mike" in result

    def test_unknown_label_becomes_speaker_n(self):
        turns = [self._turn("Unknown", 0, "Testing")]
        result = format_transcript_as_markdown(turns)
        assert "Speaker 1: Testing" in result

    def test_timestamp_format_in_output(self):
        turns = [self._turn("A", 3661, "Late content")]
        result = format_transcript_as_markdown(turns)
        assert "[01:01:01]" in result

    def test_multiple_turns_same_speaker(self):
        turns = [
            self._turn("Mike", 0, "First"),
            self._turn("Mike", 10, "Second"),
        ]
        result = format_transcript_as_markdown(turns)
        assert result.count("Mike:") == 2

    def test_speaker_numbering_is_alphabetical(self):
        # Speakers are sorted alphabetically before numbering:
        # "A" → Speaker 1, "B" → Speaker 2 regardless of appearance order.
        turns = [
            self._turn("B", 0, "First B"),
            self._turn("A", 5, "First A"),
            self._turn("B", 10, "Second B"),
        ]
        result = format_transcript_as_markdown(turns)
        lines = [l for l in result.splitlines() if l.strip()]
        assert "Speaker 2: First B" in lines[0]
        assert "Speaker 1: First A" in lines[1]
        assert "Speaker 2: Second B" in lines[2]


# ---------------------------------------------------------------------------
# assemblyai_to_speaker_turns
# ---------------------------------------------------------------------------

def _mock_utterance(speaker, start_ms, end_ms, text):
    utt = MagicMock()
    utt.speaker = speaker
    utt.start = start_ms
    utt.end = end_ms
    utt.text = text
    return utt


class TestAssemblyaiToSpeakerTurns:
    def test_empty_utterances(self):
        assert assemblyai_to_speaker_turns([]) == []

    def test_basic_conversion(self):
        utts = [_mock_utterance("A", 0, 5000, "Hello")]
        turns = assemblyai_to_speaker_turns(utts)
        assert len(turns) == 1
        assert turns[0].speaker_label == "A"
        assert turns[0].start_seconds == 0.0
        assert turns[0].end_seconds == 5.0
        assert turns[0].text == "Hello"

    def test_milliseconds_to_seconds_conversion(self):
        utts = [_mock_utterance("A", 61500, 90000, "Late")]
        turns = assemblyai_to_speaker_turns(utts)
        assert turns[0].start_seconds == pytest.approx(61.5)
        assert turns[0].end_seconds == pytest.approx(90.0)

    def test_empty_text_skipped(self):
        utts = [
            _mock_utterance("A", 0, 1000, ""),
            _mock_utterance("B", 1000, 2000, "   "),
            _mock_utterance("A", 2000, 3000, "Hello"),
        ]
        turns = assemblyai_to_speaker_turns(utts)
        assert len(turns) == 1
        assert turns[0].text == "Hello"

    def test_none_text_skipped(self):
        utts = [_mock_utterance("A", 0, 1000, None)]
        turns = assemblyai_to_speaker_turns(utts)
        assert turns == []

    def test_text_stripped(self):
        utts = [_mock_utterance("A", 0, 1000, "  Hello world  ")]
        turns = assemblyai_to_speaker_turns(utts)
        assert turns[0].text == "Hello world"

    def test_speaker_names_mapping_applied(self):
        utts = [
            _mock_utterance("A", 0, 5000, "Hi"),
            _mock_utterance("B", 5000, 10000, "Hello"),
        ]
        names = {"A": "Mike", "B": "Jennifer"}
        turns = assemblyai_to_speaker_turns(utts, speaker_names=names)
        assert turns[0].speaker_label == "Mike"
        assert turns[1].speaker_label == "Jennifer"

    def test_speaker_names_partial_mapping(self):
        utts = [
            _mock_utterance("A", 0, 5000, "Hi"),
            _mock_utterance("B", 5000, 10000, "Hello"),
        ]
        names = {"A": "Mike"}  # B not mapped
        turns = assemblyai_to_speaker_turns(utts, speaker_names=names)
        assert turns[0].speaker_label == "Mike"
        assert turns[1].speaker_label == "B"  # falls back to raw label

    def test_speaker_names_empty_string_falls_back(self):
        utts = [_mock_utterance("A", 0, 5000, "Hi")]
        names = {"A": ""}  # empty string → fall back to raw label
        turns = assemblyai_to_speaker_turns(utts, speaker_names=names)
        assert turns[0].speaker_label == "A"

    def test_no_speaker_names_param(self):
        utts = [_mock_utterance("A", 0, 5000, "Hi")]
        turns = assemblyai_to_speaker_turns(utts)
        assert turns[0].speaker_label == "A"

    def test_numeric_speaker_label_stringified(self):
        utt = MagicMock()
        utt.speaker = 0  # integer, not string
        utt.start = 0
        utt.end = 1000
        utt.text = "Hello"
        turns = assemblyai_to_speaker_turns([utt])
        assert turns[0].speaker_label == "0"


# ---------------------------------------------------------------------------
# save_transcript_markdown
# ---------------------------------------------------------------------------

class TestSaveTranscriptMarkdown:
    def test_creates_file(self, tmp_path):
        turns = [SpeakerTurn("Mike", 0, 5, "Hello")]
        out = tmp_path / "out.md"
        result = save_transcript_markdown(turns, out)
        assert result == out
        assert out.exists()

    def test_file_contains_transcript(self, tmp_path):
        turns = [SpeakerTurn("Mike", 0, 5, "Hello world")]
        out = tmp_path / "out.md"
        save_transcript_markdown(turns, out, title="Test")
        content = out.read_text(encoding="utf-8")
        assert "# Test" in content
        assert "Mike: Hello world" in content

    def test_creates_parent_directories(self, tmp_path):
        turns = [SpeakerTurn("A", 0, 5, "Hi")]
        out = tmp_path / "nested" / "deep" / "out.md"
        save_transcript_markdown(turns, out)
        assert out.exists()

    def test_utf8_encoding(self, tmp_path):
        turns = [SpeakerTurn("María", 0, 5, "Hola, ¿cómo estás?")]
        out = tmp_path / "out.md"
        save_transcript_markdown(turns, out)
        content = out.read_text(encoding="utf-8")
        assert "María" in content
        assert "¿cómo estás?" in content

    def test_returns_resolved_path(self, tmp_path):
        turns = [SpeakerTurn("A", 0, 5, "Hi")]
        out = tmp_path / "out.md"
        result = save_transcript_markdown(turns, out)
        assert result.is_absolute()
