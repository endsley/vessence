"""Request logging policy helpers for Jane web middleware."""

from __future__ import annotations


POLLING_PATHS = frozenset({
    "/api/jane/announcements",
    "/health",
    "/api/files/changes",
    "/api/jane/live",
})


def is_polling_path(path: str) -> bool:
    return path in POLLING_PATHS


def should_touch_idle_state(path: str, method: str) -> bool:
    return not is_polling_path(path) and method in {"POST", "GET"} and "/api/" in path


def request_error_context(*, elapsed_ms: int, method: str, path: str) -> dict[str, int | str]:
    return {
        "elapsed_ms": elapsed_ms,
        "method": method,
        "path": path,
    }
