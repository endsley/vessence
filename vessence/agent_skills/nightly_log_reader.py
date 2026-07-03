"""Log reading helpers for nightly self-improvement reports."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any


_LOG_TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:,\d+)?")


def read_text(path: Path, *, tail_chars: int | None = None) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""
    except Exception:
        return ""
    if tail_chars and len(text) > tail_chars:
        return text[-tail_chars:]
    return text


def timestamp_window_for_run(
    text: str,
    started_iso: str,
    elapsed_s: int,
    *,
    tail_chars: int,
) -> str | None:
    if not started_iso:
        return None
    try:
        started_at = dt.datetime.fromisoformat(started_iso)
        ended_at = started_at + dt.timedelta(seconds=elapsed_s + 5)
        start_offset: int | None = None
        end_offset: int | None = None
        offset = 0
        for line in text.splitlines(keepends=True):
            match = _LOG_TIMESTAMP_RE.match(line)
            if match:
                ts = dt.datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
                if start_offset is None and started_at <= ts <= ended_at:
                    start_offset = offset
                elif start_offset is not None and ts > ended_at:
                    end_offset = offset
                    break
            offset += len(line)
        if start_offset is not None:
            window = text[start_offset:end_offset]
            if len(window) > tail_chars:
                return window[-tail_chars:]
            return window
    except Exception:
        return None
    return None


def marker_window_for_run(text: str, started_iso: str) -> str | None:
    if not started_iso:
        return None
    marker = f"===== Run {started_iso}"
    idx = text.rfind(marker)
    if idx == -1:
        marker = f"===== Run {started_iso[:19]}"
        idx = text.rfind(marker)
    if idx == -1:
        return None
    window = text[idx:]
    next_idx = window.find("\n\n===== Run ", len(marker))
    if next_idx != -1:
        window = window[:next_idx]
    return window


def read_job_log(result: dict[str, Any], *, tail_chars: int = 12000) -> str:
    raw_log_path = str(result.get("log") or "").strip()
    if not raw_log_path:
        return ""
    text = read_text(Path(raw_log_path))
    started_iso = str(result.get("started_iso") or "")
    elapsed_s = int(result.get("elapsed_s") or 0)

    timestamp_window = timestamp_window_for_run(
        text,
        started_iso,
        elapsed_s,
        tail_chars=tail_chars,
    )
    if timestamp_window is not None:
        return timestamp_window

    marker_window = marker_window_for_run(text, started_iso)
    if marker_window is not None:
        text = marker_window

    if len(text) > tail_chars:
        return text[-tail_chars:]
    return text
