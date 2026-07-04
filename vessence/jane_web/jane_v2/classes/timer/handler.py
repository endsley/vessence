"""Timer Stage 2 handler.

Handles four actions entirely on the Android client via CLIENT_TOOL markers:
  - set    → [[CLIENT_TOOL:timer.set:{"duration_ms": <ms>, "label": "..."}]]
  - cancel → [[CLIENT_TOOL:timer.cancel:{}]]
  - list   → [[CLIENT_TOOL:timer.list:{}]]
  - delete → [[CLIENT_TOOL:timer.delete:{"id"|"index"|"label": ...}]]

The server keeps NO state about scheduled alarms — the phone owns every
timer via AlarmManager so they ring even when offline.

Multi-turn conversation support: when the user says something like "I
want to create a timer" without specifying a duration, this handler
emits a STAGE2_FOLLOWUP pending_action and asks a follow-up question.
The pending_action_resolver routes the user's next reply back to this
handler (bypassing Stage 1) with the collected state in `pending`, so
the exchange feels like one logical turn from the user's perspective.

State machine (SET flow):
  enter(no duration)      → ask duration           [pending: awaiting=duration]
  enter(duration, label)  → fire                   [no pending]
  enter(duration, !label) → ask label              [pending: awaiting=label]
  resume(awaiting=duration, prompt) → parse → ask label OR re-ask
  resume(awaiting=label, prompt)    → parse → fire
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

from .parsing import (
    extract_delete_target as _extract_delete_target,
    extract_label as _extract_label,
    label_from_reply as _label_from_reply,
    looks_like_new_timer as _looks_like_new_timer,
    parse_delete_phrase as _parse_delete_phrase,
    parse_duration_ms as _parse_duration_ms,
    parse_followup_duration_ms as _parse_followup_duration_ms,
)
from .intent_rules import (
    CANCEL_WORDS as _CANCEL_WORDS,
    COUNT_PHRASES as _COUNT_PHRASES,
    CREATE_TIMER_WORDS as _CREATE_TIMER_WORDS,
    CREATE_VERBS as _CREATE_VERBS,
    LIST_WORDS as _LIST_WORDS,
    SET_TRIGGERS as _SET_TRIGGERS,
    STRICT_LIST_PHRASES as _STRICT_LIST_PHRASES,
    TIMER_NOUNS as _TIMER_NOUNS,
    has_timer_set_trigger as _has_timer_set_trigger,
    is_cancel_query as _is_cancel_query,
    is_count_query as _is_count_query,
    is_list_query as _is_list_query,
    wants_timer_creation as _wants_timer_creation,
)
from .responses import (
    build_ask_duration_response as _ask_duration,
    build_ask_label_response as _ask_label,
    build_cancel_response as _build_cancel_response,
    build_count_response as _build_count_response,
    build_delete_response as _build_delete_response,
    build_duration_retry_response as _build_duration_retry_response,
    build_list_response as _build_list_response,
    build_set_response as _build_set_response,
)

logger = logging.getLogger(__name__)

# ── Follow-up helpers ─────────────────────────────────────────────────────

# Pivot detection moved out of this handler on 2026-04-17. The brittle
# _PIVOT_PREFIXES list (which leaked every new pivot phrase) has been
# replaced by the LLM-backed check in
# stage2_dispatcher._continuation_check, keyed off the literal question
# we stored in pending["question"].


# `_looks_like_pivot` removed — pivot detection is dispatcher-level now.
# `_looks_like_new_timer` is still used below to detect "user wants a NEW
# timer while we're still assembling the current one" — this is a same-
# class restart signal that the dispatcher's LLM gate won't catch (same
# class, same handler), so keep it.


@dataclass(frozen=True)
class _TimerActionParams:
    action: str | None = None
    duration_text: str | None = None
    label: str | None = None
    label_provided: bool = False
    delete_target: str | None = None


def _fire_set(duration_ms: int, label: str, *, from_followup: bool = False) -> dict:
    logger.info("timer handler: fire duration_ms=%d label=%r", duration_ms, label)
    return _build_set_response(duration_ms, label, from_followup=from_followup)


def _handle_resume(prompt: str, pending: dict) -> dict | None:
    """Called when the pending_action_resolver routes a follow-up reply
    back to us.

    `pending` is the `data` dict we stashed last turn (the pipeline
    passes `pending_data` through, not the whole pending_action record).
    It contains the accumulated state plus an `awaiting` key marking
    what the user's reply is answering.
    """
    # End-of-conversation phrase mid-flow: cancel the in-progress setup.
    from agent_skills import end_phrase
    from agent_skills.private_handler_utils import end_conversation
    if end_phrase.is_end(prompt):
        logger.info("timer handler: end-phrase mid-setup → cancel")
        return end_conversation("Ok.", structured={"intent": "timer"})

    # Cross-class pivot detection is dispatcher-level now (LLM gate against
    # the literal question we stored in pending["question"]). The one thing
    # we still check locally is a same-class "new timer" restart signal —
    # the LLM can't catch this because the class doesn't change.
    if _looks_like_new_timer(prompt):
        logger.info("timer handler: new-timer restart detected mid-flow → abandon")
        return {"abandon_pending": True}

    # Treat `pending` directly as the data dict — that's how the
    # dispatcher hands it to us.
    data = dict(pending or {})
    awaiting = data.pop("awaiting", None)

    if awaiting == "duration":
        dur = _parse_followup_duration_ms(prompt)
        if dur <= 0:
            # Re-ask once.
            return _build_duration_retry_response(data)
        data["duration_ms"] = dur
        # If we already have a label from earlier, fire; otherwise ask.
        if data.get("label"):
            return _fire_set(dur, data["label"], from_followup=True)
        return _ask_label(data)

    if awaiting == "label":
        label = _label_from_reply(prompt)
        dur = int(data.get("duration_ms") or 0)
        if dur <= 0:
            return _ask_duration({"label": label})
        return _fire_set(dur, label, from_followup=True)

    logger.warning("timer handler: unknown awaiting %r — abandoning", awaiting)
    return {"abandon_pending": True}


def _timer_action_params(params: dict | None) -> _TimerActionParams:
    if not params:
        return _TimerActionParams()
    label = params.get("label")
    return _TimerActionParams(
        action=(params.get("action") or "").strip().lower() or None,
        duration_text=(params.get("duration_text") or None),
        label=label,
        label_provided=label is not None,
        delete_target=(params.get("delete_target") or None),
    )


def _handle_params_action(
    prompt: str,
    p_lower: str,
    parsed: _TimerActionParams,
) -> tuple[bool, dict | None]:
    if parsed.action is None:
        return False, None

    if parsed.action == "count":
        logger.info("timer handler: count query (params)")
        return True, _build_count_response()

    if parsed.action == "list":
        logger.info("timer handler: list (params)")
        return True, _build_list_response()

    if parsed.action == "cancel":
        logger.info("timer handler: cancel (params)")
        return True, _build_cancel_response()

    if parsed.action == "delete":
        target = _parse_delete_phrase(parsed.delete_target or "") or _extract_delete_target(p_lower)
        if target is None:
            logger.info("timer handler: delete with no resolvable target — escalating")
            return True, None
        logger.info("timer handler: delete %s (params)", target)
        return True, _build_delete_response(target)

    if parsed.action == "set":
        duration_ms = 0
        if parsed.duration_text:
            duration_ms = _parse_duration_ms(parsed.duration_text)
        if duration_ms <= 0:
            duration_ms = _parse_duration_ms(prompt)
        if duration_ms <= 0:
            logger.info("timer handler: set with no duration — ask")
            return True, _ask_duration({})
        # Label: use parsed label if provided (even if ""), else extract.
        label = parsed.label if parsed.label_provided else _extract_label(prompt)
        if label is None or (label == "" and not parsed.label_provided):
            return True, _ask_label({"duration_ms": duration_ms})
        # `label == ""` from params means user opted out → fire without label.
        return True, _fire_set(duration_ms, label or "")

    return False, None


def _handle_legacy_prompt(prompt: str, p_lower: str) -> dict | None:
    # COUNT / QUERY — "how many timers do I have"
    # timer.list already returns a count-friendly summary on Android.
    if _is_count_query(p_lower):
        logger.info("timer handler: count query")
        return _build_count_response()

    # DELETE specific timer (by id / index / label)
    target = _extract_delete_target(p_lower)
    if target is not None:
        logger.info("timer handler: delete %s", target)
        return _build_delete_response(target)

    # CANCEL (all timers)
    if _is_cancel_query(p_lower):
        logger.info("timer handler: cancel")
        return _build_cancel_response()

    # LIST — must mention timer/countdown OR use a timer-specific list phrase
    if _is_list_query(p_lower):
        logger.info("timer handler: list")
        return _build_list_response()

    # SET
    duration_ms = _parse_duration_ms(prompt)
    logger.info("timer handler: SET parse → duration_ms=%d from prompt=%r",
                duration_ms, prompt[:120])

    # "Wants a timer, no duration yet" — conversational creation.
    # ("hey Jane I want to create a timer" / "start a timer for me" /
    #  "can you set a timer for")
    if duration_ms <= 0:
        # Stage 1 already classified this as `timer:High`, so an empty
        # duration is almost always a cut-off sentence like "set a timer
        # for ...". Ask rather than escalating to Opus.
        if _wants_timer_creation(p_lower) or p_lower.startswith("i ") or "i want" in p_lower:
            logger.info("timer handler: timer intent with no duration → ask")
            return _ask_duration({})
        logger.info("timer handler: couldn't parse duration — escalating")
        return None  # let Stage 3 (Opus) figure it out

    # Guard: conversational phrases containing a duration are NOT timer commands
    # ("let me rest for 10 minutes", "I need 5 minutes to think").
    # Require at least one timer-ish trigger word OR a very short utterance.
    if not _has_timer_set_trigger(prompt, p_lower):
        logger.info("timer handler: duration found but no timer trigger — escalating")
        return None

    label = _extract_label(prompt)
    # Duration known but no label → ask (user can always say "no label").
    if not label:
        logger.info("timer handler: duration=%d but no label → ask", duration_ms)
        return _ask_label({"duration_ms": duration_ms})
    return _fire_set(duration_ms, label)


def handle(prompt: str, pending: dict | None = None, params: dict | None = None) -> dict | None:
    # ── Resume path: we're mid-conversation with this user ────────────
    if pending:
        return _handle_resume(prompt, pending)

    p_lower = prompt.lower()
    params_handled, params_response = _handle_params_action(
        prompt,
        p_lower,
        _timer_action_params(params),
    )
    if params_handled:
        return params_response

    return _handle_legacy_prompt(prompt, p_lower)
