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


def _get_activity_log_path() -> str:
    home = str(Path.home())
    ambient_base = os.environ.get("AMBIENT_BASE", os.path.join(home, "ambient"))
    essences_dir = os.environ.get("TOOLS_DIR",
                                  os.environ.get("ESSENCES_DIR",
                                                  os.path.join(ambient_base, "tools")))
    log_dir = os.path.join(essences_dir, "work_log", "user_data")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "activity_log.json")


def log_activity(description: str, category: str = "general") -> dict:
    """Write a timestamped activity entry to the Work Log."""
    log_path = _get_activity_log_path()

    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timestamp_epoch": time.time(),
        "description": description,
        "category": category,
    }

    # Read existing entries
    entries = []
    if os.path.isfile(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                entries = data
        except (json.JSONDecodeError, OSError):
            entries = []

    entries.append(entry)

    # Keep only the most recent 500 entries to avoid unbounded growth
    entries = entries[-500:]

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
        if not isinstance(data, list):
            return []
        # Return most recent entries, newest first
        return list(reversed(data[-count:]))
    except (json.JSONDecodeError, OSError):
        return []
