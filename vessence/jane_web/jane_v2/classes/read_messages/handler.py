"""Read Messages — always escalates to Stage 3 by design.

Reading messages requires nuanced analysis (important-vs-spam triage,
sender relevance, natural-language summarization, contact-aware quoting)
that the local qwen2.5:7b can't reliably do. Opus owns this entirely.
The handler is a thin guard that only blocks meta / architecture phrases
that get misclassified as read_messages, then returns None to escalate.
Recent messages are prefetched into the Opus prompt by `_escalation_context()`
in `metadata.py`.
"""

from __future__ import annotations

import logging

from jane_web.jane_v2.classes.message_guard_helpers import (
    ARCHITECTURE_GUARD_WORDS as _ARCH_WORDS,
    contains_architecture_phrase,
)

logger = logging.getLogger(__name__)

_META_PHRASES = (
    "your last message", "your last reply", "your previous message",
    "your previous reply", "the last message you", "the last reply you",
    "last message took", "last reply took", "last message when i asked",
    "took a while", "took so long", "so slow", "explain why",
    "why did you", "why was your",
)


def contains_meta_self_reference(prompt: str) -> bool:
    p_lower = (prompt or "").lower()
    return any(phrase in p_lower for phrase in _META_PHRASES)


def should_reject_read_messages_prompt(prompt: str) -> bool:
    return contains_architecture_phrase(prompt) or contains_meta_self_reference(prompt)


async def handle(prompt: str, context: str = "", params: dict | None = None) -> dict | None:
    if contains_architecture_phrase(prompt):
        return {"wrong_class": True}
    if contains_meta_self_reference(prompt):
        logger.info("read_messages handler: meta/self-reference phrase → wrong_class")
        return {"wrong_class": True}

    logger.info("read_messages handler: escalating to Stage 3 by design")
    return None
