"""Pure helpers for self-improvement vocal summary logs."""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Iterable
from typing import Any


SEVERITIES = {"critical", "medium", "low", "info"}
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def normalize_severity(severity: str | None) -> str:
    value = severity.lower() if severity else "info"
    return value if value in SEVERITIES else "info"


def compose_summary(
    summary: str | None = None,
    *,
    what_was_wrong: str | None = None,
    why_it_mattered: str | None = None,
    what_was_done: str | None = None,
) -> str:
    if summary is not None:
        return summary
    parts = []
    if what_was_wrong:
        parts.append(what_was_wrong.rstrip(".") + ".")
    if why_it_mattered:
        parts.append(why_it_mattered.rstrip(".") + ".")
    if what_was_done:
        parts.append(what_was_done.rstrip(".") + ".")
    return " ".join(parts).strip()


def build_vocal_summary_record(
    job: str,
    *,
    timestamp: str,
    summary: str | None = None,
    what_was_wrong: str | None = None,
    why_it_mattered: str | None = None,
    what_was_done: str | None = None,
    severity: str = "info",
) -> dict[str, Any] | None:
    summary_text = compose_summary(
        summary,
        what_was_wrong=what_was_wrong,
        why_it_mattered=why_it_mattered,
        what_was_done=what_was_done,
    )
    if not summary_text:
        return None

    record: dict[str, Any] = {
        "timestamp": timestamp,
        "job": job,
        "severity": normalize_severity(severity),
        "summary": summary_text,
    }
    if what_was_wrong:
        record["what_was_wrong"] = what_was_wrong
    if why_it_mattered:
        record["why_it_mattered"] = why_it_mattered
    if what_was_done:
        record["what_was_done"] = what_was_done
    return record


def parse_recent_summary_line(line: str, *, cutoff: dt.datetime) -> dict | None:
    line = line.strip()
    if not line:
        return None
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return None
    timestamp = record.get("timestamp", "")
    try:
        parsed = dt.datetime.strptime(timestamp, TIMESTAMP_FORMAT)
    except ValueError:
        return None
    if parsed < cutoff:
        return None
    return record


def recent_summaries_from_lines(
    lines: Iterable[str],
    *,
    cutoff: dt.datetime,
    limit: int | None = 30,
) -> list[dict]:
    entries = []
    for line in lines:
        record = parse_recent_summary_line(line, cutoff=cutoff)
        if record is not None:
            entries.append(record)
    entries.reverse()
    if limit:
        entries = entries[:limit]
    return entries
