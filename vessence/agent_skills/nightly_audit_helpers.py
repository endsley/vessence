"""Pure helpers for nightly_audit.py."""

from __future__ import annotations

import datetime as dt
from pathlib import Path


def truncate_text(text: str, max_chars: int) -> str:
    if len(text) > max_chars:
        return text[:max_chars] + f"\n... [truncated at {max_chars} chars]"
    return text


def first_script_lines(text: str, max_lines: int) -> str:
    return "\n".join(text.splitlines()[:max_lines])


def latest_audit_summary_payload(
    now: dt.datetime,
    report: str,
    report_path: Path,
    health_summary: str,
) -> dict:
    return {
        "generated_at": now.isoformat(),
        "report_path": str(report_path),
        "health_summary": health_summary,
        "report": report.strip(),
    }


def is_sleep_window_hour(hour: int) -> bool:
    return 1 <= hour < 7
