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
import re

logger = logging.getLogger(__name__)

# High-precision interrupt intents. When a user mid-pending types one of these
# unmistakable standalone requests (e.g. "what time is it", "what's the
# weather", "cancel that"), the resolver releases the pending slot so Stage 1
# can classify the new intent normally instead of misrouting the utterance as
# the answer to a stale AWAITING question.
#
# Reason: see transcript review 2026-04-18 Issues 1 and 5 — "what time is it"
# was consumed by an [[AWAITING:re_sign_in_confirm]] pending, and "what's the
# weather like today" was consumed by [[AWAITING:confirm_restart]].
#
# Only applied to open-ended follow-up types (STAGE3_FOLLOWUP, STAGE2_FOLLOWUP)
# — confirm/cancel flows (SMS drafts) keep their strict semantics because
# there a plain "yes" / "cancel" is the most likely intent.
_HIGH_PRECISION_INTERRUPT_RE = re.compile(
    r"(?:"
    r"^\s*what(?:'s|\s+is)?\s+(?:the\s+)?time\b"
    r"|^\s*what\s+time\s+is\s+it\b"
    r"|^\s*(?:tell|give)\s+me\s+the\s+time\b"
    r"|^\s*what(?:'s|\s+is)?\s+(?:the\s+)?weather\b"
    r"|^\s*(?:how(?:'s|\s+is)\s+)?(?:the\s+)?weather\b"
    r"|^\s*(?:set|start)\s+(?:a|the)?\s*timer\b"
    r"|^\s*(?:cancel|stop)\s+(?:the|my)\s+timer\b"
    r"|^\s*(?:text|message|sms|send\s+(?:a\s+)?text\s+to)\b"
    r"|^\s*tell\s+(?:\w+\s+){0,3}(?:that|hi|hello|to\s+)"
    r")",
    re.IGNORECASE,
)


def _is_high_precision_interrupt(text: str) -> bool:
    """True if the user's reply is an unmistakable standalone intent that
    should release a stale pending slot (GET_TIME / WEATHER / TIMER / SMS)."""
    if not text or not text.strip():
        return False
    return bool(_HIGH_PRECISION_INTERRUPT_RE.search(text.strip()))


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
        ts = raw.rstrip("Z")
        exp = _dt.datetime.fromisoformat(ts)
        return _dt.datetime.utcnow() >= exp
    except Exception:
        return False

# Exact-match confirm phrases. Must be the whole reply (possibly with
# trailing punctuation / filler) — we do NOT match mid-sentence, because
# "yes please cancel" would be ambiguous.
_CONFIRM = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "okey",
    "send it", "send it please", "do it", "go ahead", "go",
    "send", "send that", "send that please", "please send it",
    "that's right", "confirmed", "confirm", "sounds good", "perfect",
    "ship it", "looks good", "that works", "good to go", "fire away",
}

# Edit-intent prefixes. If the user's reply starts with one of these,
# treat it as a revise-the-draft request rather than a confirm/cancel.
# We route to Stage 3 so Opus can compose the new body, but pass along
# the pending draft_id + existing body so the round-trip is explicit.
_EDIT_PREFIXES = (
    "add ", "append ", "also say ", "also add ", "also ",
    "make it ", "change it to ", "change the ", "replace ",
    "say ", "reword ", "rewrite ", "rephrase ", "instead say ",
    "remove ", "drop ", "take out ", "shorten it", "lengthen it",
    "make it shorter", "make it longer", "make it more ",
    "tell them ", "tell her ", "tell him ", "tell it ",
    "actually ",
)

# Strong-cancel vocabulary for STAGE3_FOLLOWUP — narrower than the
# universal set so plain "no" / "nope" can survive as a legitimate
# answer to an Opus yes/no question.
_STAGE3_CANCEL_STRONG = {
    "cancel", "cancel that", "cancel it", "never mind", "nevermind",
    "forget it", "drop it", "abort", "scratch that", "stop",
}


_CANCEL = {
    "no", "nope", "nah", "cancel", "cancel that", "cancel it",
    "never mind", "nevermind", "stop", "don't", "dont",
    "don't send", "dont send", "don't send it", "dont send it",
    "abort", "forget it", "drop it", "scratch that",
}

# Topic-pivot phrases. When a user is mid-follow-up and explicitly says they
# want to shift the conversation (e.g. "different issue", "change the subject",
# "not about that"), clear the pending slot instead of forcing the reply
# through the pending handler or Stage 3 follow-up loop. The next Stage 1
# classification then routes the real intent afresh.
# Matches anywhere in the user's reply (not just full-match), because pivots
# are often embedded in a sentence ("no no I actually think we should focus
# on the different issue").
_PIVOT_PHRASES = (
    "different issue", "different topic", "different subject",
    "different question", "another issue", "another topic",
    "another subject", "another question",
    "change the subject", "change the topic", "change subject",
    "switch the subject", "switch the topic", "switch subject",
    "new subject", "new topic",
    "focus on (?:a |the )?different",
    "focus on (?:a |the )?another",
    "not about that", "not about this",
    "not what i asked", "not what i meant", "not what i was asking",
    "that(?:'| a)?s not what i",
    "forget that,? (?:let(?:'| a)?s|lets|what about|how about)",
    "never mind that,? (?:let(?:'| a)?s|lets|what about|how about)",
    "(?:can we|let(?:'| a)?s|lets) (?:talk about|discuss) (?:something|a different)",
    "move on to",
    "change of subject", "change of topic",
)
_PIVOT_RE = re.compile(
    r"\b(?:" + "|".join(_PIVOT_PHRASES) + r")\b",
    re.IGNORECASE,
)


def _is_topic_pivot(text: str) -> bool:
    """True if the user's reply indicates an explicit change of subject."""
    if not text:
        return False
    return bool(_PIVOT_RE.search(text))


_PUNCT_RE = re.compile(r"[.!?,\s]+$")


def _normalize(text: str) -> str:
    return _PUNCT_RE.sub("", (text or "").strip().lower())


def _is_confirm(text: str) -> bool:
    return _normalize(text) in _CONFIRM


def _is_cancel(text: str) -> bool:
    return _normalize(text) in _CANCEL


def _is_edit_intent(text: str) -> bool:
    """True if the user's reply looks like a draft revision instruction
    (e.g. 'add a please', 'make it shorter', 'say I love you')."""
    t = _normalize(text)
    if not t or t in _CONFIRM or t in _CANCEL:
        return False
    for p in _EDIT_PREFIXES:
        if t.startswith(p.rstrip().lower()):
            return True
    return False


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
    _stripped = (user_text or "").strip()
    if len(_stripped) < 2:
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

    ptype = pending.get("type", "")
    turn_id = state.get("pending_turn_id")

    # High-precision interrupt intents override open-ended follow-ups so a
    # clearly-standalone request (e.g. "what time is it", "what's the
    # weather") can't be hijacked by a stale AWAITING slot. Uses the same
    # "pivot" action so the pipeline writes a cancelled marker and lets
    # Stage 1 classify the new intent. SMS confirm/cancel flows keep their
    # strict semantics because confirm/cancel vocabulary doesn't match this
    # pattern.
    if (ptype in ("STAGE3_FOLLOWUP", "STAGE2_FOLLOWUP")
            and _is_high_precision_interrupt(user_text)):
        logger.info(
            "resolver: high-precision interrupt detected for %s — clearing "
            "pending, falling through to Stage 1 (text=%r)",
            ptype, (user_text or "")[:80],
        )
        return {
            "action": "pivot",
            "pending": pending,
            "pending_turn_id": turn_id,
        }

    # Topic-pivot detection — for open-ended follow-up types, treat an
    # explicit "different issue" / "change the subject" / "not what I asked
    # for" as a signal to clear the pending slot and let Stage 1
    # reclassify the new intent from scratch. Confirm/cancel flows (SMS
    # drafts, send-confirmation) keep their strict yes/no semantics — the
    # user there will typically say "cancel" / "no" instead of a pivot.
    # The pipeline treats action="pivot" as: write a cancelled marker
    # for this pending's type, then run Stage 1 on the prompt as usual.
    if ptype in ("STAGE3_FOLLOWUP", "STAGE2_FOLLOWUP") and _is_topic_pivot(user_text):
        logger.info(
            "resolver: topic-pivot detected for %s — clearing pending, "
            "falling through to Stage 1 (text=%r)",
            ptype, (user_text or "")[:80],
        )
        return {
            "action": "pivot",
            "pending": pending,
            "pending_turn_id": turn_id,
        }

    # Universal cancel — applies to most pending types. For
    # STAGE3_FOLLOWUP and SEND_MESSAGE_DRAFT_OPEN specifically we narrow
    # the cancel vocabulary, because plain "no" is often a legitimate
    # response ("should I send?" → "no, change the wording" should not
    # silently abort the draft).
    if _is_cancel(user_text):
        if ptype in ("STAGE3_FOLLOWUP", "SEND_MESSAGE_DRAFT_OPEN"):
            if _normalize(user_text) not in _STAGE3_CANCEL_STRONG:
                # Let weak cancels like "no" / "nope" fall through so
                # Opus / the draft edit path can handle the real intent.
                logger.info(
                    "resolver: soft-cancel %r ignored for %s "
                    "— letting it fall through",
                    _normalize(user_text), ptype,
                )
            else:
                logger.info("resolver: strong cancel matched for %s", ptype)
                return {"action": "cancel", "pending": pending,
                        "pending_turn_id": turn_id}
        else:
            logger.info("resolver: global cancel matched for pending %s", ptype)
            return {"action": "cancel", "pending": pending,
                    "pending_turn_id": turn_id}

    # Legacy SMS confirm/cancel — simple yes/no resolution.
    if ptype == "SEND_MESSAGE_CONFIRMATION":
        if _is_confirm(user_text):
            logger.info("resolver: confirm matched for pending %s", ptype)
            return {"action": "confirm", "pending": pending, "pending_turn_id": turn_id}
        return None

    # SMS draft-open (Stage 3 emitted sms_draft / sms_draft_update last turn).
    # Short-circuit confirms to sms_send, strong cancels to sms_cancel, and
    # edit intents to sms_draft_update (the pipeline composes the new body).
    if ptype == "SEND_MESSAGE_DRAFT_OPEN":
        if _is_confirm(user_text):
            logger.info("resolver: draft_send matched for pending %s", ptype)
            return {"action": "sms_draft_send", "pending": pending,
                    "pending_turn_id": turn_id}
        # Cancel was already handled by the universal _is_cancel branch above —
        # if we got here with a non-confirm, non-cancel reply, check for edit.
        if _is_edit_intent(user_text):
            logger.info("resolver: draft_edit matched for pending %s", ptype)
            return {"action": "sms_draft_edit", "pending": pending,
                    "pending_turn_id": turn_id}
        # Anything else → fall through to Stage 1 (user pivoted away from
        # draft). The draft stays open; its 5-min TTL handles GC.
        return None

    # Stage 3 follow-up. Opus ended its last reply with [[AWAITING:<topic>]]
    # meaning it asked the user a question and needs the reply back. Route
    # the next prompt straight to Stage 3, skipping Stage 1 classification
    # and Stage 2 handlers entirely.
    if ptype == "STAGE3_FOLLOWUP":
        logger.info("resolver: stage3_followup (awaiting=%s)",
                    pending.get("awaiting"))
        return {
            "action": "stage3_followup",
            "pending": pending,
            "pending_data": pending.get("data", {}),
            "pending_turn_id": turn_id,
        }

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
