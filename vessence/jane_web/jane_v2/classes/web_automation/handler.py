"""Web automation Stage 2 handler.

Phase 1 design: the handler always **declines at Stage 2** so the
pipeline escalates to Stage 3 (Opus). Opus sees the
``escalation_context`` from metadata, plus the user prompt, and emits
``[[CLIENT_TOOL:web.<action>:<json>]]`` markers. The
``jane_proxy``/pipeline interceptor translates those into calls on
``agent_skills.web_automation.skill.dispatch_action`` against a
long-lived session for the duration of the task.

Returning None here is a feature, not a TODO — browser automation is
fundamentally iterative: snapshot, reason, act, snapshot, ... which is
the Stage 3 loop's home turf. Trying to do a one-shot Stage 2 answer
would require guessing the page structure before loading it.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def handle(prompt: str, context: str = "") -> dict | None:
    """Always decline so Stage 3 takes over with the brain loop."""
    _ = prompt, context
    logger.info("web_automation handler: declining → escalate to Stage 3")
    return None
