"""Shared helpers for queue-progress announcement JSONL entries."""

from __future__ import annotations

import json
import os
from typing import Any


def queue_announcements_path(data_home: str) -> str:
    return os.path.join(data_home, "data", "jane_announcements.jsonl")


def queue_progress_id(prefix: str, timestamp_ms: int) -> str:
    return f"{prefix}_{timestamp_ms}"


def queue_progress_payload(
    progress_id: str,
    message: str,
    final: bool,
    timestamp_iso: str,
) -> dict[str, Any]:
    return {
        "timestamp": timestamp_iso,
        "type": "queue_progress",
        "id": progress_id,
        "message": message,
        "final": final,
    }


def queue_progress_json_line(
    progress_id: str,
    message: str,
    final: bool,
    timestamp_iso: str,
) -> str:
    return json.dumps(queue_progress_payload(progress_id, message, final, timestamp_iso))


def append_queue_progress_announcement(
    path: str,
    progress_id: str,
    message: str,
    final: bool,
    timestamp_iso: str,
) -> None:
    with open(path, "a") as file:
        file.write(queue_progress_json_line(progress_id, message, final, timestamp_iso) + "\n")
