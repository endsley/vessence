"""Stage 2 handler for TELL_JOKE — local-LLM-generated single joke.

The user asked Jane for a joke. We ask the local LLM (qwen2.5:7b) for ONE
short clean joke and return it as the spoken reply. No Opus, no client
tools. The recent FIFO is included so the model can avoid repeating a
joke it just told (e.g. "another joke" pivots to a new one).
"""

from __future__ import annotations

import logging
import time
from jane_web.jane_v2.ollama_client import post_local_llm_response as _post_local_llm_response

from .helpers import (
    PROMPT_TEMPLATE as _PROMPT_TEMPLATE,
    build_joke_prompt as _build_joke_prompt,
    joke_llm_payload as _joke_llm_payload,
    parse_joke_response as _parse_joke_response,
)

logger = logging.getLogger(__name__)


async def _call_local_llm(prompt_text: str) -> str:
    return await _post_local_llm_response(prompt_text, _joke_llm_payload)


def joke_success_response(reply: str, thought: str) -> dict:
    return {"text": reply, "thought": thought}


async def handle(prompt: str, context: str = "") -> dict | None:
    full_prompt = _build_joke_prompt(prompt, context)

    t0 = time.perf_counter()
    try:
        raw = await _call_local_llm(full_prompt)
    except Exception as e:
        logger.warning("tell_joke: LLM call failed (%s) — escalating", e)
        return None
    latency_ms = int((time.perf_counter() - t0) * 1000)

    thought, reply = _parse_joke_response(raw)
    if not reply:
        return None

    logger.info(
        "tell_joke: LLM %dms — thought=%r reply=%r",
        latency_ms, thought[:80], reply[:120],
    )
    return joke_success_response(reply, thought)
