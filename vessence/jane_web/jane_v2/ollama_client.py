"""Shared Ollama response helper for Stage 2 handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx


async def post_ollama_response(
    url: str,
    payload: dict[str, Any],
    *,
    timeout: float,
    client_factory: Callable[..., Any] | None = None,
    activity_recorder: Callable[[], None] | None = None,
) -> str:
    factory = client_factory or httpx.AsyncClient
    async with factory(timeout=timeout) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        if activity_recorder is None:
            try:
                from jane_web.jane_v2.models import record_ollama_activity
                record_ollama_activity()
            except Exception:
                pass
        else:
            activity_recorder()
        return (response.json().get("response") or "").strip()


async def post_local_llm_response(
    prompt_text: str,
    payload_builder: Callable[..., dict[str, Any]],
    *,
    payload_kwargs: dict[str, Any] | None = None,
    response_poster: Callable[..., Awaitable[str]] = post_ollama_response,
) -> str:
    from jane_web.jane_v2.models import (
        LOCAL_LLM,
        LOCAL_LLM_NUM_CTX,
        LOCAL_LLM_TIMEOUT,
        OLLAMA_KEEP_ALIVE,
        OLLAMA_URL,
    )

    payload = payload_builder(
        prompt_text,
        model=LOCAL_LLM,
        num_ctx=LOCAL_LLM_NUM_CTX,
        keep_alive=OLLAMA_KEEP_ALIVE,
        **(payload_kwargs or {}),
    )
    return await response_poster(OLLAMA_URL, payload, timeout=LOCAL_LLM_TIMEOUT)
