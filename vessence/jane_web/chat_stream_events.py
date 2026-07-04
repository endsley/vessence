"""NDJSON event-shape helpers for Jane chat streams."""

from __future__ import annotations

import json
from typing import Any


OFFLOADED_TASK_MESSAGE = (
    "I'll work on that in the background. You'll see progress updates here as I go."
)


def stream_event_chunk(event_type: str, data: Any, **extra: Any) -> str:
    payload = {"type": event_type, "data": data}
    payload.update(extra)
    return json.dumps(payload) + "\n"


def done_stream_chunk(data: Any) -> str:
    return stream_event_chunk("done", data)


def status_stream_chunk(data: Any) -> str:
    return stream_event_chunk("status", data)


def error_stream_chunk(data: Any) -> str:
    return stream_event_chunk("error", data)


def instant_command_stream_chunks(result: str) -> list[str]:
    return [
        stream_event_chunk("delta", result),
        done_stream_chunk(result),
    ]


def offloaded_task_stream_chunks(
    task_id: str,
    message: str = OFFLOADED_TASK_MESSAGE,
) -> list[str]:
    return [
        stream_event_chunk("offloaded", message, task_id=task_id),
        done_stream_chunk(message),
    ]
