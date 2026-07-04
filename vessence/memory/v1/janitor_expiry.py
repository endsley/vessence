"""Expiration decision helpers for memory janitor cleanup."""

from __future__ import annotations

import datetime
from typing import Any


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def is_expired_value(expires_at: Any, *, now_ts: float | None = None) -> bool:
    """Return True if expires_at (Unix int/float or ISO string) has passed."""
    if not expires_at:
        return False
    if now_ts is None:
        now_ts = _utcnow().timestamp()
    if isinstance(expires_at, (int, float)):
        return expires_at < now_ts
    try:
        return datetime.datetime.fromisoformat(str(expires_at)).timestamp() < now_ts
    except Exception:
        return False


def expired_ids_from_metadata(
    ids: list[str],
    metadatas: list[dict[str, Any] | None],
    *,
    now_ts: float | None = None,
) -> list[str]:
    return [
        memory_id
        for memory_id, metadata in zip(ids, metadatas)
        if is_expired_value((metadata or {}).get("expires_at"), now_ts=now_ts)
    ]


def old_ids_from_metadata(
    ids: list[str],
    metadatas: list[dict[str, Any] | None],
    *,
    cutoff: datetime.datetime,
) -> list[str]:
    old_ids: list[str] = []
    for memory_id, metadata in zip(ids, metadatas):
        timestamp = (metadata or {}).get("timestamp")
        if timestamp:
            try:
                if datetime.datetime.fromisoformat(str(timestamp)) < cutoff:
                    old_ids.append(memory_id)
            except Exception:
                pass
    return old_ids
