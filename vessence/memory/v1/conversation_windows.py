"""Pure window-archival helpers for conversation memory."""

from __future__ import annotations

import datetime
from typing import Any

from memory.v1.conversation_text import compact_whitespace, looks_like_bad_thematic_output, strip_injected_metadata

LedgerTurn = tuple[int, Any, Any, datetime.datetime | None]
SessionTranscriptRow = tuple[Any, Any]


def parse_ledger_ts(raw: Any) -> datetime.datetime | None:
    if not raw:
        return None
    try:
        return datetime.datetime.fromisoformat(
            str(raw).replace("T", " ").split("+")[0].split(".")[0].strip()
        )
    except Exception:
        return None


def normalize_timestamp_for_sql(raw: str) -> str:
    return raw.replace("T", " ").split("+")[0].split(".")[0].strip()[:19]


def latest_metadata_timestamp(metadatas: list[dict[str, Any] | None]) -> str | None:
    stamps: list[str] = []
    for metadata in metadatas:
        if not metadata:
            continue
        for key in ("archived_at", "timestamp", "created_at", "updated_at"):
            if metadata.get(key):
                stamps.append(str(metadata[key]))
                break
    return max(stamps) if stamps else None


def transcript_line(role: Any, content: Any) -> str | None:
    cleaned = compact_whitespace(strip_injected_metadata(content or ""))
    if not cleaned or looks_like_bad_thematic_output(cleaned):
        return None
    return f"{(role or '').upper()}: {cleaned}"


def build_session_transcript(rows: list[SessionTranscriptRow]) -> str:
    lines = []
    for role, content in rows:
        line = transcript_line(role, content)
        if line is not None:
            lines.append(line)
    return "\n\n".join(lines)


def build_window_transcript(window: list[LedgerTurn]) -> str:
    lines = []
    for _tid, role, content, _ts in window:
        line = transcript_line(role, content)
        if line is not None:
            lines.append(line)
    return "\n\n".join(lines)


def group_ledger_turns(
    rows: list[tuple[int, Any, Any, Any]],
    *,
    idle_gap_minutes: int,
    max_turns: int,
) -> list[list[LedgerTurn]]:
    gap = datetime.timedelta(minutes=idle_gap_minutes)
    windows: list[list[LedgerTurn]] = []
    current: list[LedgerTurn] = []
    prev_ts = None
    for turn_id, role, content, raw_ts in rows:
        ts = parse_ledger_ts(raw_ts)
        gap_break = (
            prev_ts is not None and ts is not None and (ts - prev_ts) > gap
        )
        size_break = len(current) >= max_turns
        if current and (gap_break or size_break):
            windows.append(current)
            current = []
        current.append((turn_id, role, content, ts))
        if ts is not None:
            prev_ts = ts
    if current:
        windows.append(current)
    return windows
