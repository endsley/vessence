"""Queue-progress announcement helpers for the web task offloader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


QUEUE_PROGRESS_TYPE = "queue_progress"


def task_progress_payload(
    task_id: str,
    message: str,
    created_at: str,
    *,
    final: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": task_id,
        "type": QUEUE_PROGRESS_TYPE,
        "message": message,
        "created_at": created_at,
    }
    if final:
        payload["final"] = True
    return payload


def task_progress_json_line(
    task_id: str,
    message: str,
    created_at: str,
    *,
    final: bool = False,
) -> str:
    return json.dumps(
        task_progress_payload(task_id, message, created_at, final=final),
        ensure_ascii=False,
    )


def append_task_progress_announcement(
    path: Path,
    task_id: str,
    message: str,
    created_at: str,
    *,
    final: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(task_progress_json_line(task_id, message, created_at, final=final) + "\n")
