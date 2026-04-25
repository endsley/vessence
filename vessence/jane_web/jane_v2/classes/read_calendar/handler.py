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
  After answering one day, Jane asks "Would you like to know about
  another day?" and stores a STAGE2_FOLLOWUP pending. The loop continues
  for every reply that names a day; it ends when the user says no, says
  an end-phrase ("nevermind"/"stop"), or pivots to a different topic.

Returns:
    {"text": "<answer>", "structured": {...}}        → Stage 2 success
    {"abandon_pending": True, "force_stage3": True}  → pivot mid-flow
    {"text": "Ok.", "conversation_end": True, ...}   → end-of-flow
    None                                              → escalate to Stage 3
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

import httpx

from jane_web.jane_v2.models import (
    LOCAL_LLM as MODEL,
    LOCAL_LLM_NUM_CTX,
    LOCAL_LLM_TIMEOUT,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_URL,
)

logger = logging.getLogger(__name__)

# Stage-2 ONLY accepts prompts that explicitly name a specific day or
# week range. Anything vaguer ("what's coming up", "anything important",
# "what's next on my calendar") is intentionally NOT in this list — those
# escalate to Stage 3 so Opus can interpret intent and apply richer
# filtering (time-of-day, importance, attendees, etc.).
_RANGE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\btoday\b", re.I), "today"),
    (re.compile(r"\btonight\b", re.I), "today"),
    (re.compile(r"\btomorrow\b", re.I), "tomorrow"),
    (re.compile(r"\bthis week\b", re.I), "this week"),
    (re.compile(r"\bnext week\b", re.I), "next week"),
    (re.compile(r"\bmonday\b", re.I), "monday"),
    (re.compile(r"\btuesday\b", re.I), "tuesday"),
    (re.compile(r"\bwednesday\b", re.I), "wednesday"),
    (re.compile(r"\bthursday\b", re.I), "thursday"),
    (re.compile(r"\bfriday\b", re.I), "friday"),
    (re.compile(r"\bsaturday\b", re.I), "saturday"),
    (re.compile(r"\bsunday\b", re.I), "sunday"),
]


def _format_time(dt: datetime) -> str:
    if dt.minute == 0:
        return dt.strftime("%-I%p").lower()
    return dt.strftime("%-I:%M%p").lower()


def _simplify_events(events: list[dict], today: date) -> str:
    if not events:
        return "No events."
    lines = [f"Total: {len(events)} event{'s' if len(events) != 1 else ''}\n"]
    for i, ev in enumerate(events, 1):
        summary = ev.get("summary") or "Untitled"
        start_raw = str(ev.get("start", ""))
        end_raw = str(ev.get("end", ""))
        if "T" in start_raw:
            dt = datetime.fromisoformat(start_raw)
            day_label = dt.strftime("%A %B %-d")
            time_str = _format_time(dt)
            if "T" in end_raw:
                end_dt = datetime.fromisoformat(end_raw)
                lines.append(f"{i}. {summary} — {day_label}, {time_str}–{_format_time(end_dt)}")
            else:
                lines.append(f"{i}. {summary} — {day_label}, {time_str}")
        else:
            try:
                d = date.fromisoformat(start_raw)
                day_label = d.strftime("%A %B %-d")
            except ValueError:
                day_label = start_raw
            lines.append(f"{i}. {summary} — {day_label} (all day)")
    return "\n".join(lines)


_ANSWER_TEMPLATE = """\
You are Jane, a personal assistant. Rephrase the calendar summary \
below into a short spoken response.

Today is {today_weekday}, {today_date}.

CRITICAL — this response will be read aloud by a voice assistant. \
Your answer must be:
- SHORT: 1-3 sentences max. No lists, no bullet points.
- CONVERSATIONAL: like a friend answering — not formal.
- SPEAKABLE: say times naturally ("9am", "2:30pm"), skip timezone \
labels, round durations.
- ACCURATE: use the EXACT count and dates from the summary below. \
Do not guess or recount — the count is already computed for you.

Good examples:
- "You're clear today, nothing on the calendar."
- "You've got a dentist appointment at 2pm and dinner with Lee at 7."
- "Pretty packed tomorrow — 3 meetings starting at 9am."
- "Just one thing Thursday, a call with Sarah at 11."
- "You've got four things next week — trash Tuesday at 7pm, sump pump \
service Wednesday, ML Reading Group Thursday 11 to 12:30, and paying \
your mom Friday at 2."

Bad examples (too wordy):
- "Based on your Google Calendar data, you have the following events..."
- "Here is a summary of your upcoming calendar events for today..."

If there are no events, just say the day is clear. Keep it natural.

Only respond with the single word ESCALATE if the question asks \
about creating, editing, or deleting events — those need Stage 3.

Calendar summary:
{events_summary}

User question: {prompt}

Your spoken answer (or the single word ESCALATE):"""

_ESCALATE_RE = re.compile(r"\bESCALATE\b", re.IGNORECASE)

_FORCE_ESCALATE_PHRASES = (
    "schedule a", "create a", "add a", "set up a",
    "cancel my", "delete my", "remove my",
    "move my", "reschedule", "change my",
)

_FOLLOWUP_QUESTION = "Would you like to know about another day?"
_DAY_CHOICE_QUESTION = "Which day?"


def _resolve_range(prompt: str) -> str | None:
    """Return the matched day/week hint, or None if the prompt is vague.

    None is the signal to escalate: Stage 2 only handles calendar reads
    where the user explicitly named a specific day or week. Returning
    "today" by default would silently swallow vaguer queries that Opus
    is better positioned to answer.
    """
    p = (prompt or "").lower()
    for pat, hint in _RANGE_PATTERNS:
        if pat.search(p):
            return hint
    return None


def _expires_at(minutes: int = 2) -> str:
    import datetime as _dt
    return (_dt.datetime.utcnow() + _dt.timedelta(minutes=minutes)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _pending(awaiting: str, question: str, data: dict | None = None) -> dict:
    return {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "read calendar",
        "status": "awaiting_user",
        "awaiting": awaiting,
        "data": {**(data or {}), "awaiting": awaiting},
        "question": question,
        "expires_at": _expires_at(2),
    }


def _wrap_with_followup(spoken: str, range_hint: str) -> dict:
    """Append 'Would you like to know about another day?' + STAGE2_FOLLOWUP."""
    return {
        "text": f"{spoken} {_FOLLOWUP_QUESTION}",
        "structured": {
            "intent": "read calendar",
            "entities": {"range": range_hint},
            "pending_action": _pending(
                "another_day_or_stop",
                _FOLLOWUP_QUESTION,
                {"last_range": range_hint},
            ),
        },
    }


async def _ask_qwen(prompt_text: str, num_predict: int = 120) -> str | None:
    body = {
        "model": MODEL,
        "prompt": prompt_text,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2, "num_predict": num_predict, "num_ctx": LOCAL_LLM_NUM_CTX},
        "keep_alive": OLLAMA_KEEP_ALIVE,
    }
    try:
        async with httpx.AsyncClient(timeout=LOCAL_LLM_TIMEOUT) as client:
            r = await client.post(OLLAMA_URL, json=body)
            r.raise_for_status()
            try:
                from jane_web.jane_v2.models import record_ollama_activity
                record_ollama_activity()
            except Exception:
                pass
            return (r.json().get("response") or "").strip() or None
    except Exception as e:
        logger.warning("calendar handler: ollama call failed: %s", e)
        return None


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

    full_prompt = (
        _ANSWER_TEMPLATE
        .replace("{events_summary}", events_summary)
        .replace("{prompt}", prompt)
        .replace("{today_weekday}", today.strftime("%A"))
        .replace("{today_date}", today.strftime("%B %d, %Y"))
    )

    text = await _ask_qwen(full_prompt, num_predict=120)
    if not text:
        logger.info("calendar handler: empty response, escalating")
        return None
    if _ESCALATE_RE.search(text):
        logger.info("calendar handler: ESCALATE marker, escalating")
        return None

    event_count = len(events) if events else 0
    logger.info("calendar handler: answered (range=%s, events=%d, %d chars)",
                range_hint, event_count, len(text))
    return _wrap_with_followup(text, range_hint)


async def _handle_resume(prompt: str, pending: dict) -> dict | None:
    from agent_skills import end_phrase, confirmation
    from agent_skills.private_handler_utils import end_conversation

    awaiting = (pending.get("data") or {}).get("awaiting") or pending.get("awaiting")

    # End-of-loop signals — same in both states.
    if end_phrase.is_end(prompt) or confirmation.is_no(prompt):
        logger.info("calendar handler: end signal on resume (%s) → close", awaiting)
        return end_conversation("Ok.", structured={"intent": "read calendar"})

    if awaiting == "another_day_or_stop":
        # Day-name FIRST: "yes, tomorrow" / "tomorrow please" / bare "friday"
        # all carry an explicit day, and we should fetch it directly instead
        # of falling into the "Which day?" branch.
        range_hint = _resolve_range(prompt)
        if range_hint is not None:
            return await _answer_for_range(prompt, range_hint)
        # No day token but a clear "yes" → ask which day.
        if confirmation.is_yes(prompt):
            return {
                "text": _DAY_CHOICE_QUESTION,
                "structured": {
                    "intent": "read calendar",
                    "pending_action": _pending(
                        "awaiting_day_choice", _DAY_CHOICE_QUESTION,
                    ),
                },
            }
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

    p_lower = (prompt or "").lower()
    if any(phrase in p_lower for phrase in _FORCE_ESCALATE_PHRASES):
        logger.info("calendar handler: edit/create phrase → escalate early")
        return None

    range_hint = _resolve_range(prompt)
    if range_hint is None:
        logger.info("calendar handler: no specific day/week in prompt → Stage 3")
        return None

    return await _answer_for_range(prompt, range_hint)
