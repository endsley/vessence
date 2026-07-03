"""Read calendar Stage 2 handler — repeating-read pattern.

Fetches Google Calendar events via agent_skills.calendar_tools, pre-formats
them into a clean human-readable list (deterministic count + day-of-week +
natural times), and asks Qwen to rephrase conversationally.

Pre-processing in Python avoids sending raw JSON with ISO timestamps,
long HTML descriptions, and opaque IDs to the local LLM. Qwen only
needs to convert a numbered list into a spoken sentence — no date math,
no counting, no HTML parsing.

Routing rule (Stage 2 vs Stage 3):
  Stage 2 only handles prompts that explicitly name a day or week
  ("today", "tomorrow", "this week", "next Friday"). Vague queries
  ("what's coming up", "anything important", "what's on my agenda")
  escalate to Stage 3 — Opus has the context to apply richer filtering
  (time-of-day, importance, attendees) than this handler does.

Multi-turn (repeating-read):
  After listing events, Jane asks "Would you like to know the details
  of any particular event?" If the user names one, Qwen formats the
  detail view (description, time, link). After details, Jane asks
  "Would you like to know about another day?" The loop continues for
  every reply that names a day; it ends when the user says no, says
  an end-phrase ("nevermind"/"stop"), or pivots to a different topic.

Returns:
    {"text": "<answer>", "structured": {...}}        → Stage 2 success
    {"abandon_pending": True, "force_stage3": True}  → pivot mid-flow
    {"text": "Ok.", "conversation_end": True, ...}   → end-of-flow
    None                                              → escalate to Stage 3
"""

from __future__ import annotations

import logging
from datetime import date

from jane_web.jane_v2.ollama_client import post_local_llm_response as _post_local_llm_response

from .formatting import (
    RANGE_PATTERNS as _RANGE_PATTERNS,
    format_event_detail as _format_event_detail,
    format_time as _format_time,
    match_event as _match_event,
    resolve_range as _resolve_range,
    simplify_events as _simplify_events,
)
from .responses import (
    ANOTHER_DAY_QUESTION as _ANOTHER_DAY_QUESTION,
    DAY_CHOICE_QUESTION as _DAY_CHOICE_QUESTION,
    DETAIL_FOLLOWUP as _DETAIL_FOLLOWUP,
    build_another_day_response as _ask_another_day,
    build_calendar_pending as _pending,
    build_day_choice_response as _build_day_choice_response,
    build_event_choice_response as _build_event_choice_response,
    build_event_detail_response as _build_event_detail_response,
    build_range_followup_response as _wrap_with_followup,
)
from .prompts import (
    ANSWER_TEMPLATE as _ANSWER_TEMPLATE,
    DETAIL_TEMPLATE as _DETAIL_TEMPLATE,
    ESCALATE_RE as _ESCALATE_RE,
    FORCE_ESCALATE_PHRASES as _FORCE_ESCALATE_PHRASES,
    build_calendar_answer_prompt as _build_calendar_answer_prompt,
    build_event_detail_prompt as _build_event_detail_prompt,
    calendar_llm_payload as _calendar_llm_payload,
    response_requests_escalation as _response_requests_escalation,
    should_force_calendar_escalate as _should_force_calendar_escalate,
)

logger = logging.getLogger(__name__)

async def _ask_qwen(prompt_text: str, num_predict: int = 120) -> str | None:
    try:
        return await _post_local_llm_response(
            prompt_text,
            _calendar_llm_payload,
            payload_kwargs={"num_predict": num_predict},
        ) or None
    except Exception as e:
        logger.warning("calendar handler: ollama call failed: %s", e)
        return None


async def _show_event_detail(ev: dict, last_range: str) -> dict | None:
    """Show details for a single event, then ask about another day."""
    info = _format_event_detail(ev)
    prompt_text = _build_event_detail_prompt(info)
    text = await _ask_qwen(prompt_text, num_predict=100)
    if not text:
        text = info
    logger.info("calendar handler: showed detail for %r", ev.get("summary", "?"))
    return _build_event_detail_response(text, ev, last_range)


async def _answer_for_range(prompt: str, range_hint: str) -> dict | None:
    """Fetch events for a range, render with Qwen, wrap with follow-up.

    Returns a Stage 2 result dict (with pending_action), or None to escalate.
    """
    try:
        from agent_skills.calendar_tools import list_events_in_range
        events = list_events_in_range(range_hint, max_results=25)
    except Exception as e:
        logger.warning("calendar handler: fetch failed: %s", e)
        return None

    today = date.today()
    events_summary = _simplify_events(events or [], today)

    full_prompt = _build_calendar_answer_prompt(events_summary, prompt, today)

    text = await _ask_qwen(full_prompt, num_predict=120)
    if not text:
        logger.info("calendar handler: empty response, escalating")
        return None
    if _response_requests_escalation(text):
        logger.info("calendar handler: ESCALATE marker, escalating")
        return None

    event_count = len(events) if events else 0
    logger.info("calendar handler: answered (range=%s, events=%d, %d chars)",
                range_hint, event_count, len(text))
    return _wrap_with_followup(text, range_hint, events=events)


async def _handle_resume(prompt: str, pending: dict) -> dict | None:
    from agent_skills import end_phrase, confirmation
    from agent_skills.private_handler_utils import end_conversation

    awaiting = (pending.get("data") or {}).get("awaiting") or pending.get("awaiting")

    # End-of-loop signals — same in both states.
    if end_phrase.is_end(prompt) or confirmation.is_no(prompt):
        logger.info("calendar handler: end signal on resume (%s) → close", awaiting)
        return end_conversation("Ok.", structured={"intent": "read calendar"})

    if awaiting == "event_detail_or_stop":
        events = (pending.get("data") or {}).get("events") or []
        last_range = (pending.get("data") or {}).get("last_range", "today")
        if confirmation.is_yes(prompt) and len(events) == 1:
            return await _show_event_detail(events[0], last_range)
        if confirmation.is_yes(prompt):
            return _build_event_choice_response(last_range, events)
        matched = _match_event(prompt, events)
        if matched:
            return await _show_event_detail(matched, last_range)
        range_hint = _resolve_range(prompt)
        if range_hint is not None:
            return await _answer_for_range(prompt, range_hint)
        logger.info("calendar handler: no event match in detail follow-up → ask another day")
        return _ask_another_day(last_range)

    if awaiting == "awaiting_event_choice":
        events = (pending.get("data") or {}).get("events") or []
        last_range = (pending.get("data") or {}).get("last_range", "today")
        matched = _match_event(prompt, events)
        if matched:
            return await _show_event_detail(matched, last_range)
        logger.info("calendar handler: no event match in 'which one?' reply → ask another day")
        return _ask_another_day(last_range)

    if awaiting == "another_day_or_stop":
        range_hint = _resolve_range(prompt)
        if range_hint is not None:
            return await _answer_for_range(prompt, range_hint)
        if confirmation.is_yes(prompt):
            return _build_day_choice_response()
        logger.info("calendar handler: no day in follow-up reply → escalate")
        return {"abandon_pending": True, "force_stage3": True}

    if awaiting == "awaiting_day_choice":
        range_hint = _resolve_range(prompt)
        if range_hint is None:
            logger.info("calendar handler: no day in 'which day?' reply → escalate")
            return {"abandon_pending": True, "force_stage3": True}
        return await _answer_for_range(prompt, range_hint)

    # Unknown awaiting tag — let Stage 3 sort it out.
    logger.info("calendar handler: unknown pending awaiting=%r → escalate", awaiting)
    return {"abandon_pending": True, "force_stage3": True}


async def handle(prompt: str, context: str = "", pending: dict | None = None,
                 params: dict | None = None) -> dict | None:
    if pending:
        return await _handle_resume(prompt, pending)

    if _should_force_calendar_escalate(prompt):
        logger.info("calendar handler: edit/create phrase → escalate early")
        return None

    range_hint = _resolve_range(prompt)
    if range_hint is None:
        logger.info("calendar handler: no specific day/week in prompt → Stage 3")
        return None

    return await _answer_for_range(prompt, range_hint)
