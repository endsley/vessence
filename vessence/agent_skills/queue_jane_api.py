"""Shared Jane API helpers for prompt/job queue runners."""

from __future__ import annotations

from dataclasses import dataclass
import json
from collections.abc import Iterable
from typing import Any, Callable


@dataclass(frozen=True)
class QueueStreamResult:
    text: str
    success: bool
    error: str | None = None
    source: str = "stream"


def queue_chat_payload(message: str, session_id: str) -> dict[str, str]:
    return {
        "message": message,
        "session_id": session_id,
        "platform": "queue",
    }


def queue_chat_stream_url(jane_url: str) -> str:
    return f"{jane_url}/api/jane/chat/stream"


def queue_chat_sync_url(jane_url: str) -> str:
    return f"{jane_url}/api/jane/chat"


def parse_queue_stream_lines(lines: Iterable[str]) -> QueueStreamResult:
    response_text = ""
    for line in lines:
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("type") == "delta":
            response_text += event.get("data", "")
        elif event.get("type") == "done":
            if not response_text:
                response_text = event.get("data", "")
            break
        elif event.get("type") == "error":
            err = event.get("data", "Unknown error")
            return QueueStreamResult(text=f"Error: {err}", success=False, error=str(err))

    return QueueStreamResult(
        text=response_text,
        success=bool(response_text.strip()),
    )


def queue_sync_response_result(payload: dict[str, Any]) -> QueueStreamResult:
    response = payload.get("text", "")
    return QueueStreamResult(text=response, success=bool(response), source="sync")


def queue_http_error_result(status_code: int) -> QueueStreamResult:
    error = f"HTTP {status_code}"
    return QueueStreamResult(text=f"Error: {error}", success=False, error=error, source="sync")


def run_queue_chat_request(
    jane_url: str,
    message: str,
    session_id: str,
    *,
    post: Callable[..., Any],
    stream_timeout: tuple[int, None] = (10, None),
    sync_timeout: tuple[int, int] = (10, 600),
) -> QueueStreamResult:
    payload = queue_chat_payload(message, session_id)
    response = post(
        queue_chat_stream_url(jane_url),
        json=payload,
        stream=True,
        timeout=stream_timeout,
    )
    if response.status_code == 401:
        response = post(
            queue_chat_sync_url(jane_url),
            json=payload,
            timeout=sync_timeout,
        )
        if response.ok:
            return queue_sync_response_result(response.json())
        return queue_http_error_result(response.status_code)

    return parse_queue_stream_lines(response.iter_lines(decode_unicode=True))
