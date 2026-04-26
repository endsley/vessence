"""Delete Messages — always escalates to Stage 3 by design.

Selecting WHICH messages to delete needs the same inbox triage Opus
does for read_messages (sender matching, spam classification, fuzzy
referent resolution like "the one about my package"). qwen2.5:7b
can't do that, so the handler is a thin guard that only blocks
meta/architecture phrases that get misclassified as delete_messages,
then returns None to escalate.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_ARCH_WORDS = ("architecture", "infrastructure", "pipeline", "handler", "classifier", "stage")


async def handle(prompt: str, context: str = "", params: dict | None = None) -> dict | None:
    p_lower = prompt.lower()
    if any(w in p_lower for w in _ARCH_WORDS):
        return {"wrong_class": True}

    logger.info("delete_messages handler: escalating to Stage 3 by design")
    return None
