"""Queue-progress announcement helpers for the web task offloader."""

from __future__ import annotations

import json
import fcntl
import os
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


def append_task_progress_announcement_once(
    path: Path,
    task_id: str,
    message: str,
    created_at: str,
    *,
    final: bool = False,
) -> bool:
    """Append a queue-progress entry once by its stable task ID.

    Critical self-healing notifications use one immutable task ID.  The lock
    and on-disk scan make a retry safe even if the process crashed after the
    append but before it could mark the related incident notification sent.
    Returns ``True`` only when this invocation wrote the line.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+") as lock_handle:
        try:
            lock_path.chmod(0o600)
        except OSError:
            pass
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            if path.is_file():
                with path.open("r", encoding="utf-8", errors="replace") as reader:
                    for raw in reader:
                        try:
                            payload = json.loads(raw)
                        except (TypeError, json.JSONDecodeError):
                            continue
                        if (
                            isinstance(payload, dict)
                            and payload.get("type") == QUEUE_PROGRESS_TYPE
                            and str(payload.get("id") or "") == task_id
                        ):
                            return False
            with path.open("a", encoding="utf-8") as handle:
                try:
                    path.chmod(0o600)
                except OSError:
                    pass
                handle.write(task_progress_json_line(task_id, message, created_at, final=final) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            return True
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
