"""Normal Jane chat stream runner."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

try:
    from .chat_stream_dedupe import finalize_turn_dedupe
    from .chat_stream_events import error_stream_chunk
    from .chat_stream_limits import mark_stream_closed, mark_stream_open
except ImportError:
    from chat_stream_dedupe import finalize_turn_dedupe
    from chat_stream_events import error_stream_chunk
    from chat_stream_limits import mark_stream_closed, mark_stream_open


CONNECTION_LOST_MESSAGE = "\u26a0\ufe0f Connection lost. Please try again."
JANE_UNREACHABLE_PREFIX = "\u26a0\ufe0f Could not reach Jane:"


def stream_identity(
    *,
    auth_session_id: str,
    requested_conversation_session_id: str,
    get_session_user_fn: Callable[[str], str | None],
    default_user_id_fn: Callable[[], str],
    scoped_session_id_fn: Callable[[str, str], str],
) -> tuple[str, str]:
    user_id = get_session_user_fn(auth_session_id) or default_user_id_fn()
    return user_id, scoped_session_id_fn(user_id, requested_conversation_session_id)


async def normal_chat_stream_chunks(
    *,
    active_streams: dict[str, int],
    stream_ip: str,
    auth_session_id: str,
    body_session_id: str | None,
    requested_conversation_session_id: str,
    message: str,
    file_context: str | None,
    platform: str | None,
    tts_enabled: bool,
    turn_id: str,
    response_wait_seconds: float,
    stream_message_fn: Callable[..., AsyncIterator[str]],
    get_session_user_fn: Callable[[str], str | None],
    default_user_id_fn: Callable[[], str],
    scoped_session_id_fn: Callable[[str, str], str],
    session_log_id_fn: Callable[[str | None], str],
    logger: Any,
    finalize_turn_dedupe_fn: Callable[..., None] = finalize_turn_dedupe,
    error_chunk_fn: Callable[[str], str] = error_stream_chunk,
) -> AsyncIterator[str]:
    open_count = mark_stream_open(active_streams, stream_ip)
    logger.debug("Stream opened for %s (now %d active)", stream_ip, open_count)
    user_id, conversation_session_id = stream_identity(
        auth_session_id=auth_session_id,
        requested_conversation_session_id=requested_conversation_session_id,
        get_session_user_fn=get_session_user_fn,
        default_user_id_fn=default_user_id_fn,
        scoped_session_id_fn=scoped_session_id_fn,
    )
    logger.info(
        "Starting jane stream generator session=%s user=%s",
        session_log_id_fn(conversation_session_id),
        user_id,
    )
    captured: list[str] = []
    had_error = False
    try:
        async with asyncio.timeout(response_wait_seconds):
            async for chunk in stream_message_fn(
                user_id,
                conversation_session_id,
                message,
                file_context,
                platform=platform,
                tts_enabled=tts_enabled,
            ):
                if turn_id:
                    captured.append(chunk)
                yield chunk
    except (ConnectionError, OSError) as exc:
        had_error = True
        logger.warning(
            "jane_chat_stream connection error session=%s user=%s: %s",
            session_log_id_fn(auth_session_id),
            user_id,
            exc,
        )
        yield error_chunk_fn(CONNECTION_LOST_MESSAGE)
    except Exception as exc:
        had_error = True
        logger.exception(
            "jane_chat_stream failed active_session=%s body_session=%s user=%s: %s",
            session_log_id_fn(auth_session_id),
            session_log_id_fn(body_session_id),
            user_id,
            exc,
        )
        yield error_chunk_fn(f"{JANE_UNREACHABLE_PREFIX} {exc}")
        return
    finally:
        close_count = mark_stream_closed(active_streams, stream_ip)
        logger.debug("Stream closed for %s (now %d active)", stream_ip, close_count)
        logger.info("Jane stream generator closed session=%s", session_log_id_fn(auth_session_id))
        if turn_id:
            try:
                finalize_turn_dedupe_fn(turn_id, captured, had_error=had_error)
            except Exception as exc:
                logger.warning("turn_dedupe finalize failed: %s", exc)
