"""Helpers for Jane chat stream turn idempotency."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TurnDedupeStart:
    active_turn_id: str
    replay_response_json: str | None = None
    replay_reason: str | None = None
    pending_join_waited: bool = False


def _default_store() -> Any:
    try:
        from jane_web import turn_dedupe
    except ImportError:
        import turn_dedupe  # type: ignore
    return turn_dedupe


def _completed_replay(
    row: Any,
    reason: str,
    *,
    pending_join_waited: bool = False,
) -> TurnDedupeStart | None:
    if row and row.status == "completed" and row.response_json:
        return TurnDedupeStart(
            active_turn_id="",
            replay_response_json=row.response_json,
            replay_reason=reason,
            pending_join_waited=pending_join_waited,
        )
    return None


async def begin_turn_dedupe(turn_id: str, session_id: str, store: Any | None = None) -> TurnDedupeStart:
    """Decide whether a streaming turn should dispatch, replay, or skip dedupe."""
    clean_turn_id = (turn_id or "").strip()
    if not clean_turn_id:
        return TurnDedupeStart(active_turn_id="")

    dedupe = store or _default_store()
    existing = dedupe.lookup(clean_turn_id)
    if existing is not None:
        replay = _completed_replay(existing, "completed")
        if replay is not None:
            return replay
        if existing.status == "pending":
            cached = await asyncio.to_thread(dedupe.wait_for_completion, clean_turn_id)
            if cached:
                return TurnDedupeStart(
                    active_turn_id="",
                    replay_response_json=cached,
                    replay_reason="joined",
                    pending_join_waited=True,
                )
            pending_join_waited = True
        else:
            pending_join_waited = False
    else:
        pending_join_waited = False

    begun = dedupe.try_begin(clean_turn_id, session_id)
    if begun:
        return TurnDedupeStart(
            active_turn_id=clean_turn_id,
            pending_join_waited=pending_join_waited,
        )

    row = dedupe.lookup(clean_turn_id)
    replay = _completed_replay(row, "race_completed", pending_join_waited=pending_join_waited)
    if replay is not None:
        return replay
    return TurnDedupeStart(active_turn_id="", pending_join_waited=pending_join_waited)


async def iter_replay_ndjson(response_json: str) -> AsyncIterator[str]:
    """Replay cached NDJSON, preserving only nonblank lines with trailing newlines."""
    for line in (response_json or "").splitlines():
        if line.strip():
            yield line + "\n"


def finalize_turn_dedupe(
    turn_id: str,
    chunks: list[str],
    *,
    had_error: bool,
    store: Any | None = None,
) -> None:
    """Persist the final idempotency state for a turn if dedupe is active."""
    clean_turn_id = (turn_id or "").strip()
    if not clean_turn_id:
        return
    dedupe = store or _default_store()
    if had_error:
        dedupe.mark_failed(clean_turn_id)
    else:
        dedupe.mark_completed(clean_turn_id, "".join(chunks))
