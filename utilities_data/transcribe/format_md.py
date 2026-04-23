from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class SpeakerTurn:
    """Represents a continuous segment of speech from one speaker."""
    speaker_label: str
    start_seconds: float
    end_seconds: float
    text: str


def format_timestamp(seconds: float) -> str:
    """
    Convert seconds to [HH:MM:SS] format.
    Examples: 0.0 -> [00:00:00], 65.5 -> [00:01:05], 3661.0 -> [01:01:01]
    """
    td = timedelta(seconds=int(seconds))
    total_seconds = int(td.total_seconds())
    hh = total_seconds // 3600
    mm = (total_seconds % 3600) // 60
    ss = total_seconds % 60
    return f"[{hh:02d}:{mm:02d}:{ss:02d}]"


def is_detected_name(label: str) -> bool:
    """Return True if label looks like a real detected name, not a generic speaker label."""
    if len(label) <= 1:
        return False
    if label.isdigit():
        return False
    if label.lower() == "unknown":
        return False
    return True


def format_transcript_as_markdown(
    speaker_turns: list[SpeakerTurn],
    *,
    title: Optional[str] = None,
) -> str:
    """
    Format speaker turns as Markdown transcript.

    Output format:
    # Title (if provided)

    [00:00:00] Mike: Hello everyone, thanks for joining.
    [00:00:15] Speaker 1: Happy to be here.
    """
    lines = []

    if title:
        lines.append(f"# {title}")
        lines.append("")

    unique_speakers = sorted(set(turn.speaker_label for turn in speaker_turns))
    generic_speakers = [s for s in unique_speakers if not is_detected_name(s)]
    speaker_number_mapping = {label: i + 1 for i, label in enumerate(generic_speakers)}

    for turn in speaker_turns:
        timestamp = format_timestamp(turn.start_seconds)
        if is_detected_name(turn.speaker_label):
            speaker_name = turn.speaker_label
        else:
            speaker_number = speaker_number_mapping[turn.speaker_label]
            speaker_name = f"Speaker {speaker_number}"
        lines.append(f"{timestamp} {speaker_name}: {turn.text}")

    return "\n".join(lines)


def assemblyai_to_speaker_turns(
    utterances,
    speaker_names: Optional[dict[str, str]] = None,
) -> list[SpeakerTurn]:
    """
    Convert AssemblyAI utterances to SpeakerTurn objects.

    Args:
        utterances: List of AssemblyAI utterance objects
        speaker_names: Optional mapping of raw label (e.g. "A") to detected name (e.g. "Mike")

    Returns:
        List of SpeakerTurn objects
    """
    turns = []
    names = speaker_names or {}

    for utt in utterances:
        start_sec = utt.start / 1000.0  # ms -> s
        end_sec = utt.end / 1000.0  # ms -> s
        raw_label = str(utt.speaker)
        speaker = names.get(raw_label) or raw_label
        text = (utt.text or "").strip()

        if text:
            turns.append(
                SpeakerTurn(
                    speaker_label=speaker,
                    start_seconds=start_sec,
                    end_seconds=end_sec,
                    text=text,
                )
            )

    return turns


def save_transcript_markdown(
    speaker_turns: list[SpeakerTurn],
    output_path: str | Path,
    *,
    title: Optional[str] = None,
) -> Path:
    """
    Save formatted transcript to markdown file.

    Args:
        speaker_turns: List of SpeakerTurn objects
        output_path: Path to save markdown file
        title: Optional title for the transcript

    Returns:
        Path to saved markdown file
    """
    markdown = format_transcript_as_markdown(speaker_turns, title=title)

    out_path = Path(output_path).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    return out_path
