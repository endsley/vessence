"""Pure helpers for work_log_tools.py."""
from __future__ import annotations

import os
from collections.abc import Mapping


def resolve_activity_log_path(env: Mapping[str, str], *, home: str) -> str:
    ambient_base = env.get("AMBIENT_BASE", os.path.join(home, "ambient"))
    essences_dir = env.get(
        "TOOLS_DIR",
        env.get("ESSENCES_DIR", os.path.join(ambient_base, "skills")),
    )
    return os.path.join(essences_dir, "work_log", "user_data", "activity_log.json")


def activity_entry(
    *,
    description: str,
    category: str,
    timestamp: str,
    timestamp_epoch: float,
) -> dict:
    return {
        "timestamp": timestamp,
        "timestamp_epoch": timestamp_epoch,
        "description": description,
        "category": category,
    }


def coerce_entry_list(data) -> list:
    return data if isinstance(data, list) else []


def append_bounded(entries: list, entry: dict, *, max_entries: int = 200) -> list:
    return [*entries, entry][-max_entries:]


def recent_entries(entries: list, count: int = 20) -> list[dict]:
    return list(reversed(entries[-count:]))
