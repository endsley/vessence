"""Pure session-key and pruning helpers for Jane proxy state."""
from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def session_composite_key(user_id: str, session_id: str) -> str:
    return f"{user_id}:{session_id}"


def split_session_composite_key(composite_key: str) -> tuple[str, str]:
    user_id, separator, session_id = composite_key.partition(":")
    if not separator:
        return (user_id, "")
    return (user_id, session_id)


def global_idle_blocks_prune(now_ts: float, global_last_active_ts: float, ttl_seconds: float) -> bool:
    return bool(global_last_active_ts and now_ts - global_last_active_ts <= ttl_seconds)


def read_global_idle_ts(path: str | Path, *, now_ts: float) -> float:
    """Read a global activity timestamp, clamping future values to now."""
    try:
        with Path(path).open() as f:
            ts = float(json.load(f).get("last_active_ts", 0))
        return min(ts, now_ts)
    except Exception:
        return 0.0


def stale_session_keys(
    sessions: Mapping[str, Any],
    *,
    now_ts: float,
    ttl_seconds: float,
) -> list[str]:
    return [
        composite_key
        for composite_key, state in list(sessions.items())
        if now_ts - state.last_accessed_at > ttl_seconds
    ]


def oldest_session_key(sessions: Mapping[str, Any]) -> str:
    return min(sessions, key=lambda key: sessions[key].last_accessed_at)
