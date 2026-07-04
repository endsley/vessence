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

import datetime as _dt
import logging

from jane_web.jane_v2.pending_action_phrases import (
    STAGE3_CANCEL_STRONG as _STAGE3_CANCEL_STRONG,
    is_cancel as _is_cancel,
    is_confirm as _is_confirm,
    is_edit_intent as _is_edit_intent,
    is_high_precision_interrupt as _is_high_precision_interrupt,
    is_topic_pivot as _is_topic_pivot,
    normalize_reply as _normalize,
)
from jane_web.jane_v2.pending_action_resolution import (
    resolve_pending_action_response as _resolve_pending_action_response,
)

logger = logging.getLogger(__name__)


def _utc_now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _parse_expires_at(raw: str) -> _dt.datetime:
    """Parse pending_action expires_at values as UTC-aware datetimes.

    Existing handlers write timestamps like ``YYYY-MM-DDTHH:MM:SSZ``. Older
    callers may omit the trailing ``Z``; keep those valid by treating naive
    values as UTC.
    """
    text = (raw or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    expires_at = _dt.datetime.fromisoformat(text)
    if expires_at.tzinfo is None:
        return expires_at.replace(tzinfo=_dt.timezone.utc)
    return expires_at.astimezone(_dt.timezone.utc)


def _is_expired(pending: dict) -> bool:
    """True when pending.expires_at is set AND has passed.

    Handlers stash an ISO UTC timestamp ("YYYY-MM-DDTHH:MM:SSZ") so a
    stale mid-conversation slot can't intercept an unrelated next turn
    minutes or hours later. A missing / malformed field defaults to
    *not expired* (pre-existing behavior).
    """
    raw = (pending or {}).get("expires_at")
    if not raw:
        return False
    try:
        return _utc_now() >= _parse_expires_at(raw)
    except Exception:
        return False


def _is_blank_pending_reply(user_text: str) -> bool:
    return len((user_text or "").strip()) < 2


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
    # Guard against empty / whitespace-only / filler-only STT transcripts
    # while a pending_action is active. A blank follow-up would otherwise
    # be treated as "the user's answer" and trigger an abandon_pending in
    # handlers like todo_list's _match_category (no match → abandon). See
    # transcript review 2026-04-18 Issue 10: debounced STT relaunch
    # produced a blank follow-up that silently killed a good pending slot.
    if _is_blank_pending_reply(user_text):
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

    if _is_expired(pending):
        logger.info("resolver: pending %s expired at %s → ignoring",
                    pending.get("type"), pending.get("expires_at"))
        return None

    turn_id = state.get("pending_turn_id")

    return _resolve_pending_action_response(pending, user_text, turn_id, logger=logger)
