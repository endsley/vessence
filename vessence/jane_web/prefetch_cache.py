"""Short-lived memory prefetch cache for Jane web sessions."""

from __future__ import annotations

import time
from collections.abc import Callable


class PrefetchMemoryCache:
    def __init__(
        self,
        *,
        ttl_seconds: float = 60,
        max_entries: int = 100,
        time_fn: Callable[[], float] = time.time,
    ):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.time_fn = time_fn
        self.entries: dict[str, dict] = {}

    def _fresh_entry(self, session_id: str) -> dict | None:
        cached = self.entries.get(session_id)
        if cached and (self.time_fn() - cached["timestamp"]) < self.ttl_seconds:
            return cached
        return None

    def is_fresh(self, session_id: str) -> bool:
        return self._fresh_entry(session_id) is not None

    def get(self, session_id: str) -> str:
        """Return a cached prefetch memory result if it is still within TTL, else ''."""
        cached = self._fresh_entry(session_id)
        if cached:
            return cached.get("result", "")
        return ""

    def store(self, session_id: str, result: str) -> None:
        self.entries[session_id] = {"result": result, "timestamp": self.time_fn()}
        # Prune expired entries to prevent unbounded growth.
        if len(self.entries) > self.max_entries:
            now = self.time_fn()
            expired = [key for key, value in self.entries.items() if now - value["timestamp"] > self.ttl_seconds]
            for key in expired:
                self.entries.pop(key, None)
