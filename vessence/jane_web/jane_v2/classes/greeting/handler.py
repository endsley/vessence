"""Greeting Stage 2 handler.

Handles basic greetings ("hey", "how's it going", "good morning") with a
fast, contextual reply using qwen2.5:7b. No Opus needed.

Returns {"text": "..."} for simple greetings, or None to escalate when
the greeting contains a follow-up question or task.
"""

from __future__ import annotations

import logging

from jane_web.jane_v2.ollama_client import post_local_llm_response as _post_local_llm_response

from .canned import (
    CANNED_PATTERNS as _CANNED_PATTERNS,
    CANNED_REPLIES as _CANNED_REPLIES,
    PROMPT_TEMPLATE as _PROMPT_TEMPLATE,
    build_greeting_prompt as _build_greeting_prompt,
    canned_reply as _canned_reply,
    clean_greeting_text as _clean_greeting_text,
    greeting_llm_payload as _greeting_llm_payload,
    is_wrong_class as _is_wrong_class,
)

logger = logging.getLogger(__name__)


def greeting_response(text: str) -> dict:
    return {"text": text}


async def handle(prompt: str, context: str = "") -> dict | None:
    """Generate a quick greeting reply.

    Returns {"text": "..."} or None to escalate to Stage 3.
    """
    if not isinstance(prompt, str):
        return None

    canned = _canned_reply(prompt)
    if canned:
        logger.info("greeting handler: canned → %r", canned[:60])
        return greeting_response(canned)

    full_prompt = _build_greeting_prompt(prompt, context)

    try:
        text = await _post_local_llm_response(full_prompt, _greeting_llm_payload)
    except Exception as e:
        logger.warning("greeting handler: LLM call failed: %s", e)
        return None

    if not text:
        return None

    # Classification confirmation: if LLM says WRONG_CLASS, defer to Stage 3
    if _is_wrong_class(text):
        logger.info("greeting handler: LLM says WRONG_CLASS — escalating to Stage 3")
        return None

    text = _clean_greeting_text(text)

    logger.info("greeting handler: %r → %r", prompt[:40], text[:80])
    return greeting_response(text)
