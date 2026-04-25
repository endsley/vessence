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

_DETAIL_FOLLOWUP = "Would you like to know the details of any particular event?"
_ANOTHER_DAY_QUESTION = "Would you like to know about another day?"
_DAY_CHOICE_QUESTION = "Which day?"

_DETAIL_TEMPLATE = """\
You are Jane, a personal assistant. The user asked for details about \
a specific calendar event. Read the event info below and give a short, \
natural spoken summary.

Include: event name, day, time, duration, and description (if any). \
If there's no description, just say there are no extra details.

Keep it to 1-2 sentences, conversational, speakable.

Event info:
{event_info}

Your spoken answer:"""


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


def _wrap_with_followup(spoken: str, range_hint: str, events: list[dict] | None = None) -> dict:
    """After listing events, ask about details; if no events, ask about another day."""
    has_events = bool(events)
    if has_events:
        question = _DETAIL_FOLLOWUP
        awaiting = "event_detail_or_stop"
        serialized = [
            {k: ev.get(k, "") for k in ("id", "summary", "description", "start", "end", "html_link")}
            for ev in events
        ]
        data = {"last_range": range_hint, "events": serialized}
    else:
        question = _ANOTHER_DAY_QUESTION
        awaiting = "another_day_or_stop"
        data = {"last_range": range_hint}

    return {
        "text": f"{spoken} {question}",
        "structured": {
            "intent": "read calendar",
            "entities": {"range": range_hint},
            "pending_action": _pending(awaiting, question, data),
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


def _match_event(prompt: str, events: list[dict]) -> dict | None:
    """Find the event the user is referring to by number or keyword."""
    p = prompt.strip().lower()
    nums = re.findall(r"\b(\d+)\b", p)
    if nums:
        idx = int(nums[0]) - 1
        if 0 <= idx < len(events):
            return events[idx]
    best = None
    best_score = 0
    for ev in events:
        name = (ev.get("summary") or "").lower()
        if not name:
            continue
        words = name.split()
        score = sum(1 for w in words if w in p)
        if score > best_score:
            best_score = score
            best = ev
    return best if best_score > 0 else None


def _format_event_detail(ev: dict) -> str:
    """Format a single event into a readable detail block for Qwen."""
    lines = [f"Name: {ev.get('summary') or 'Untitled'}"]
    start_raw = str(ev.get("start", ""))
    end_raw = str(ev.get("end", ""))
    if "T" in start_raw:
        dt = datetime.fromisoformat(start_raw)
        lines.append(f"Day: {dt.strftime('%A %B %-d')}")
        lines.append(f"Time: {_format_time(dt)}")
        if "T" in end_raw:
            end_dt = datetime.fromisoformat(end_raw)
            lines.append(f"End: {_format_time(end_dt)}")
    else:
        lines.append(f"Day: {start_raw} (all day)")
    desc = (ev.get("description") or "").strip()
    if desc:
        lines.append(f"Description: {desc[:300]}")
    else:
        lines.append("Description: none")
    return "\n".join(lines)


async def _show_event_detail(ev: dict, last_range: str) -> dict | None:
    """Show details for a single event, then ask about another day."""
    info = _format_event_detail(ev)
    prompt_text = _DETAIL_TEMPLATE.replace("{event_info}", info)
    text = await _ask_qwen(prompt_text, num_predict=100)
    if not text:
        text = info
    logger.info("calendar handler: showed detail for %r", ev.get("summary", "?"))
    return {
        "text": f"{text} {_ANOTHER_DAY_QUESTION}",
        "structured": {
            "intent": "read calendar",
            "entities": {"event_id": ev.get("id")},
            "pending_action": _pending(
                "another_day_or_stop",
                _ANOTHER_DAY_QUESTION,
                {"last_range": last_range},
            ),
        },
    }


def _ask_another_day(last_range: str) -> dict:
    """Transition to the 'another day?' follow-up."""
    return {
        "text": _ANOTHER_DAY_QUESTION,
        "structured": {
            "intent": "read calendar",
            "pending_action": _pending(
                "another_day_or_stop",
                _ANOTHER_DAY_QUESTION,
                {"last_range": last_range},
            ),
        },
    }


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
            return {
                "text": "Which one?",
                "structured": {
                    "intent": "read calendar",
                    "pending_action": _pending(
                        "awaiting_event_choice", "Which one?",
                        {"last_range": last_range, "events": events},
                    ),
                },
            }
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
