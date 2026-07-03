"""Source-file loaders for transcript quality review."""
from __future__ import annotations

import json
from pathlib import Path

from agent_skills.transcript_review_format import (
    android_event_line,
    pipeline_event_line,
    prompt_dump_turn,
)


def load_prompt_dump(path: Path, date_str: str) -> list[dict]:
    if not path.exists():
        return []
    turns = []
    with path.open() as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            turn = prompt_dump_turn(record, date_str)
            if turn:
                turns.append(turn)
    return turns


def load_pipeline_events(path: Path, date_str: str) -> list[str]:
    if not path.exists():
        return []
    lines = []
    with path.open() as handle:
        for line in handle:
            event_line = pipeline_event_line(line, date_str)
            if event_line:
                lines.append(event_line)
    return lines


def load_android_events(path: Path, date_str: str) -> list[str]:
    if not path.exists():
        return []
    lines = []
    with path.open() as handle:
        for raw in handle:
            try:
                record = json.loads(raw)
            except json.JSONDecodeError:
                continue
            event_line = android_event_line(record, date_str)
            if event_line:
                lines.append(event_line)
    return lines
