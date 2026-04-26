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

logger = logging.getLogger(__name__)

_ARCH_WORDS = ("architecture", "infrastructure", "pipeline", "handler", "classifier", "stage")

_META_PHRASES = (
    "your last message", "your last reply", "your previous message",
    "your previous reply", "the last message you", "the last reply you",
    "last message took", "last reply took", "last message when i asked",
    "took a while", "took so long", "so slow", "explain why",
    "why did you", "why was your",
)


async def handle(prompt: str, context: str = "", params: dict | None = None) -> dict | None:
    p_lower = prompt.lower()
    if any(w in p_lower for w in _ARCH_WORDS):
        return {"wrong_class": True}
    if any(p in p_lower for p in _META_PHRASES):
        logger.info("read_messages handler: meta/self-reference phrase → wrong_class")
        return {"wrong_class": True}

    logger.info("read_messages handler: escalating to Stage 3 by design")
    return None
