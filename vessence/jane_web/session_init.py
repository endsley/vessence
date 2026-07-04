"""Streaming helpers for Jane persistent-session initialization."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any


def _session_init_prompt(system_prompt: str) -> str:
    return (
        f"{system_prompt}\n\n"
        "This is a session initialization. Read your configuration and prepare for conversation. "
        "Respond with a single short, warm greeting (1 sentence max). Do not ask questions."
    )


async def session_init_stream_chunks(
    *,
    manager: Any,
    build_context_async: Callable[..., Awaitable[Any]],
    get_execution_profile_fn: Callable[[str], Any],
    brain_name: str,
    user_id: str,
    session_id: str,
    init_status: str,
    status_chunk_fn: Callable[[str], str],
    done_chunk_fn: Callable[[str], str],
    logger: Any,
) -> AsyncIterator[str]:
    status_queue: asyncio.Queue[str] = asyncio.Queue()

    def emit_status(msg: str) -> None:
        status_queue.put_nowait(msg)

    try:
        emit_status("Loading personality and context...")
        ctx = await build_context_async(
            "Session initialization",
            [],
            session_id=session_id,
            platform="web",
            on_status=emit_status,
            user_id=user_id,
        )

        while not status_queue.empty():
            status = status_queue.get_nowait()
            yield status_chunk_fn(status)

        yield status_chunk_fn(init_status)

        profile = get_execution_profile_fn(brain_name)
        greeting = await manager.run_turn(
            user_id,
            session_id,
            _session_init_prompt(ctx.system_prompt),
            on_delta=lambda delta: None,
            on_status=lambda status: None,
            timeout_seconds=profile.timeout_seconds,
            model=None,
            yolo=profile.mode == "yolo",
        )
        yield done_chunk_fn(greeting.strip())
    except Exception:
        logger.exception("Init session failed")
        yield done_chunk_fn("Hey! Ready when you are.")
