"""pending_action_resolver.py — deterministic pre-Stage-1 router.

When FIFO carries an unresolved pending_action (e.g. "awaiting confirmation
to send SMS to Kathia"), a short user reply like "yes" or "cancel that"
should NOT be embedded-classified from scratch — that risks routing to
GREETING, OTHERS, or something equally wrong. Instead we intercept those
replies here and return a deterministic routing decision.

Two resolution modes:

1. **SEND_MESSAGE_CONFIRMATION** — yes/cancel resolution. Returns
   action="confirm" or action="cancel" and the pipeline short-circuits
   to send/drop the queued SMS.

2. **STAGE2_FOLLOWUP** — generic multi-turn handler loop. Stage 2
   handlers that need to ask the user questions (e.g. the timer handler
   asking for duration or label) stash their open state as a pending
   action of this type. Returns action="followup" with the target
   handler_class and its collected data; the pipeline re-dispatches the
   handler with that context instead of running Stage 1 again. The
   handler is then responsible for either (a) finishing and emitting
   the action, (b) asking the next question (new pending_action), or
   (c) abandoning so Stage 1 resumes.

Universal cancel phrases (no / cancel / never mind) ALWAYS abort any
pending, regardless of type. This is the global escape hatch.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Exact-match confirm phrases. Must be the whole reply (possibly with
# trailing punctuation / filler) — we do NOT match mid-sentence, because
# "yes please cancel" would be ambiguous.
_CONFIRM = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "okey",
    "send it", "send it please", "do it", "go ahead", "go",
    "send", "send that", "send that please", "please send it",
    "that's right", "confirmed", "confirm", "sounds good", "perfect",
}

_CANCEL = {
    "no", "nope", "nah", "cancel", "cancel that", "cancel it",
    "never mind", "nevermind", "stop", "don't", "dont",
    "don't send", "dont send", "don't send it", "dont send it",
    "abort", "forget it", "drop it", "scratch that",
}

_PUNCT_RE = re.compile(r"[.!?,\s]+$")


def _normalize(text: str) -> str:
    return _PUNCT_RE.sub("", (text or "").strip().lower())


def _is_confirm(text: str) -> bool:
    return _normalize(text) in _CONFIRM


def _is_cancel(text: str) -> bool:
    return _normalize(text) in _CANCEL


def resolve(session_id: str | None, user_text: str) -> dict | None:
    """Check whether the user's reply deterministically resolves a pending action.

    Returns:
      {"action": "confirm" | "cancel", "pending": <pending_action_dict>,
       "pending_turn_id": <str|None>}
        — caller should execute the resolution instead of calling Stage 1.
      None — no pending action, or reply doesn't match. Caller falls through
             to normal Stage 1 classification.
    """
    if not session_id or not user_text:
        return None
    try:
        from vault_web.recent_turns import get_active_state
    except Exception as e:
        logger.warning("resolver: could not import FIFO helpers: %s", e)
        return None

    try:
        state = get_active_state(session_id)
    except Exception as e:
        logger.warning("resolver: get_active_state failed: %s", e)
        return None

    pending = state.get("pending_action")
    if not pending:
        return None

    ptype = pending.get("type", "")
    turn_id = state.get("pending_turn_id")

    # Universal cancel — applies regardless of pending type. Gives the
    # user an always-available escape hatch from any multi-turn flow.
    if _is_cancel(user_text):
        logger.info("resolver: global cancel matched for pending %s", ptype)
        return {"action": "cancel", "pending": pending, "pending_turn_id": turn_id}

    # Legacy SMS confirm/cancel — simple yes/no resolution.
    if ptype == "SEND_MESSAGE_CONFIRMATION":
        if _is_confirm(user_text):
            logger.info("resolver: confirm matched for pending %s", ptype)
            return {"action": "confirm", "pending": pending, "pending_turn_id": turn_id}
        return None

    # Generic Stage 2 follow-up loop. The handler declared in
    # pending.handler_class wants to receive the user's reply with the
    # collected context so far (pending.data) so it can either finish or
    # ask the next question.
    if ptype == "STAGE2_FOLLOWUP":
        handler_class = pending.get("handler_class", "")
        if not handler_class:
            logger.warning("resolver: STAGE2_FOLLOWUP missing handler_class")
            return None
        logger.info("resolver: followup → %s (awaiting=%s)",
                    handler_class, pending.get("awaiting") or pending.get("data", {}).get("awaiting"))
        return {
            "action": "followup",
            "handler_class": handler_class,
            "pending": pending,
            "pending_data": pending.get("data", {}),
            "pending_turn_id": turn_id,
        }

    return None
