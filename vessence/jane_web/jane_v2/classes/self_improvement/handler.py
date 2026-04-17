"""self_improvement Stage 2 handler — always declines, lets Stage 3 answer.

The pipeline injects the vocal-summary context when it sees
state["cls"] == "self improvement" on escalation. This handler exists
solely to satisfy the registry; returning None routes straight to
Stage 3 (Opus), which can speak the summaries naturally.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def handle(prompt: str, context: str = "", pending: dict | None = None):
    """Decline so the pipeline escalates to Stage 3."""
    logger.info("self_improvement handler: declining → escalate to Stage 3")
    return None
