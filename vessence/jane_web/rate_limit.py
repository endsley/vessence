"""Rate-limit helpers for Jane web middleware."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from time import monotonic


def active_window_hits(hits: list[float], cutoff: float) -> list[float]:
    return [timestamp for timestamp in hits if timestamp > cutoff]


def stale_rate_limit_keys(hits_by_key: dict[str, list[float]], now: float) -> list[str]:
    return [key for key, hits in hits_by_key.items() if not hits or hits[-1] < now - 120]


class RateLimiter:
    """Simple in-memory sliding-window rate limiter."""

    def __init__(self, *, time_fn: Callable[[], float] = monotonic):
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup: float = time_fn()
        self._time_fn = time_fn

    def check(self, key: str, max_requests: int, window_seconds: float) -> bool:
        now = self._time_fn()
        if now - self._last_cleanup > 60:
            self._cleanup(now)
        cutoff = now - window_seconds
        timestamps = active_window_hits(self._hits[key], cutoff)
        if len(timestamps) >= max_requests:
            self._hits[key] = timestamps
            return False
        timestamps.append(now)
        self._hits[key] = timestamps
        return True

    def _cleanup(self, now: float) -> None:
        for key in stale_rate_limit_keys(self._hits, now):
            del self._hits[key]
        self._last_cleanup = now


RATE_LIMIT_CHAT_PATHS = frozenset({"/api/jane/chat/stream", "/api/jane/chat"})
RATE_LIMIT_AUTH_PATHS = frozenset(
    {
        "/auth/google",
        "/auth/google/callback",
        "/api/auth/google-token",
        "/api/auth/verify-otp",
        "/api/auth/verify-share",
        "/api/auth/check",
        "/api/auth/is-new-device",
        "/api/cli-login",
        "/api/cli-login/code",
    }
)
RATE_LIMIT_UPLOAD_PATHS = frozenset({"/api/files/upload", "/api/tax/upload"})
RATE_LIMIT_EXEMPT_PATHS = frozenset(
    {
        "/api/device-diagnostics",
        "/api/crash-report",
        "/api/self-healing/report",
    }
)


def rate_limit_category(path: str) -> tuple[str, int, float]:
    """Return (category_suffix, max_requests, window_seconds) for a path."""

    if path in RATE_LIMIT_EXEMPT_PATHS:
        return ("", 0, 0)
    if path in RATE_LIMIT_CHAT_PATHS:
        return ("chat", 30, 60)
    if path in RATE_LIMIT_AUTH_PATHS:
        return ("auth", 10, 60)
    if path in RATE_LIMIT_UPLOAD_PATHS:
        return ("upload", 20, 60)
    if path.startswith("/api/"):
        return ("api", 60, 60)
    return ("", 0, 0)
