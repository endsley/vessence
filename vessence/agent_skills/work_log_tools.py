"""
work_log_tools.py — Activity logging tools for the Work Log essence.

Provides:
    - log_activity(description, category) — writes a timestamped entry
    - get_recent_activities(count) — reads recent entries
"""

import json
import os
import time
from pathlib import Path

from agent_skills.work_log_helpers import (
    activity_entry as _activity_entry,
    append_bounded as _append_bounded,
    coerce_entry_list as _coerce_entry_list,
    recent_entries as _recent_entries,
    resolve_activity_log_path as _resolve_activity_log_path,
)


def _get_activity_log_path() -> str:
    log_path = _resolve_activity_log_path(os.environ, home=str(Path.home()))
    log_dir = os.path.dirname(log_path)
    os.makedirs(log_dir, exist_ok=True)
    return log_path


def log_activity(description: str, category: str = "general") -> dict:
    """Write a timestamped activity entry to the Work Log."""
    log_path = _get_activity_log_path()

    entry = _activity_entry(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        timestamp_epoch=time.time(),
        description=description,
        category=category,
    )

    # Read existing entries
    entries = []
    if os.path.isfile(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            entries = _coerce_entry_list(data)
        except (json.JSONDecodeError, OSError):
            entries = []

    # Keep only the most recent 200 entries to avoid unbounded growth
    entries = _append_bounded(entries, entry, max_entries=200)

    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    return entry


def get_recent_activities(count: int = 20) -> list[dict]:
    """Read the most recent activity entries from the Work Log."""
    log_path = _get_activity_log_path()

    if not os.path.isfile(log_path):
        return []

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Return most recent entries, newest first
        return _recent_entries(_coerce_entry_list(data), count)
    except (json.JSONDecodeError, OSError):
        return []
