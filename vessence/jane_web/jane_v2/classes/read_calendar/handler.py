"""Read calendar Stage 2 handler.

Fetches Google Calendar events via agent_skills.calendar_tools, pre-formats
them into a clean human-readable list (deterministic count + day-of-week +
natural times), and asks Qwen to rephrase conversationally.

Pre-processing in Python avoids sending raw JSON with ISO timestamps,
long HTML descriptions, and opaque IDs to the local LLM. Qwen only
needs to convert a numbered list into a spoken sentence — no date math,
no counting, no HTML parsing.

Returns:
    {"text": "<answer>"}   → success, pipeline returns to user
    None                    → escalate to Stage 3
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta

import httpx

from jane_web.jane_v2.models import (
    LOCAL_LLM as MODEL,
    LOCAL_LLM_NUM_CTX,
    LOCAL_LLM_TIMEOUT,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_URL,
)

logger = logging.getLogger(__name__)

_RANGE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\btoday\b", re.I), "today"),
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
    """Format a datetime into spoken-friendly time like '7pm' or '2:30pm'."""
    if dt.minute == 0:
        return dt.strftime("%-I%p").lower()
    return dt.strftime("%-I:%M%p").lower()


def _simplify_events(events: list[dict], today: date) -> str:
    """Convert raw Google Calendar events into a pre-formatted summary.

    Returns a numbered list with deterministic count, day-of-week, and
    natural time formatting. Strips description, id, and html_link so
    Qwen only sees what matters.
    """
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

_DETAIL_OFFER = " Want details on any of them?"

_DETAIL_TEMPLATE = """\
You are Jane, a personal assistant. Give a short spoken summary of \
this single calendar event.

Today is {today_weekday}, {today_date}.

CRITICAL — this response will be read aloud. Keep it to 1-2 sentences. \
Mention the title, day, time, and any useful detail from the description \
(like a meeting link or location). Skip HTML formatting, IDs, and URLs.

Event:
- Title: {summary}
- When: {when}
- Description: {description}

Your spoken answer:"""


def _resolve_range(prompt: str) -> str:
    p = (prompt or "").lower()
    for pat, hint in _RANGE_PATTERNS:
        if pat.search(p):
            return hint
    return "today"


def _expires_at(minutes: int = 2) -> str:
    import datetime as _dt
    return (_dt.datetime.utcnow() + _dt.timedelta(minutes=minutes)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _pending(awaiting: str, data: dict, question: str = "") -> dict:
    return {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "read calendar",
        "status": "awaiting_user",
        "awaiting": awaiting,
        "data": {**data, "awaiting": awaiting},
        "question": question,
        "expires_at": _expires_at(2),
    }


_DECLINE_PHRASES = {
    "no", "nope", "nah", "no thanks", "no thank you", "i'm good",
    "im good", "that's okay", "thats okay", "all good", "never mind",
    "nevermind", "not right now", "maybe later",
}


def _is_decline(text: str) -> bool:
    return text.strip().lower().rstrip(".!") in _DECLINE_PHRASES


def _match_event_by_reply(reply: str, events: list[dict]) -> dict | None:
    """Match a user reply like '2', 'the sump pump one', 'ML reading group'
    to one of the stored events."""
    reply_lower = reply.strip().lower()
    if reply_lower.isdigit():
        idx = int(reply_lower) - 1
        if 0 <= idx < len(events):
            return events[idx]
        return None
    for ev in events:
        title = (ev.get("summary") or "").lower()
        if title and title in reply_lower:
            return ev
        words = [w for w in title.split() if len(w) > 3]
        if words and any(w in reply_lower for w in words):
            return ev
    return None


def _format_event_when(ev: dict) -> str:
    """Format an event's start/end into a human-readable string."""
    start_raw = str(ev.get("start", ""))
    end_raw = str(ev.get("end", ""))
    if "T" in start_raw:
        dt = datetime.fromisoformat(start_raw)
        when = f"{dt.strftime('%A %B %-d')}, {_format_time(dt)}"
        if "T" in end_raw:
            end_dt = datetime.fromisoformat(end_raw)
            when += f"–{_format_time(end_dt)}"
        return when
    try:
        d = date.fromisoformat(start_raw)
        return f"{d.strftime('%A %B %-d')} (all day)"
    except ValueError:
        return start_raw


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


async def _handle_detail_request(prompt: str, pending: dict) -> dict | None:
    """Resume path: user asked for details on a specific event."""
    if _is_decline(prompt):
        return {"text": "Okay, sounds good."}

    pending_data = pending.get("data") if isinstance(pending.get("data"), dict) else pending
    events = pending_data.get("events") or []
    if not events:
        return None

    ev = _match_event_by_reply(prompt, events)
    if ev is None:
        return {"abandon_pending": True, "force_stage3": True}

    today = date.today()
    desc_raw = ev.get("description") or "None"
    if len(desc_raw) > 400:
        desc_raw = desc_raw[:400] + "…"
    desc_clean = re.sub(r"<[^>]+>", " ", desc_raw).strip()

    detail_prompt = (
        _DETAIL_TEMPLATE
        .replace("{today_weekday}", today.strftime("%A"))
        .replace("{today_date}", today.strftime("%B %d, %Y"))
        .replace("{summary}", ev.get("summary") or "Untitled")
        .replace("{when}", _format_event_when(ev))
        .replace("{description}", desc_clean or "None")
    )

    text = await _ask_qwen(detail_prompt, num_predict=100)
    if not text:
        return None

    logger.info("calendar handler: detail for %r → %d chars", ev.get("summary", ""), len(text))
    return {"text": text}


async def handle(prompt: str, pending: dict | None = None) -> dict | None:
    if pending:
        return await _handle_detail_request(prompt, pending)

    p_lower = (prompt or "").lower()
    if any(phrase in p_lower for phrase in _FORCE_ESCALATE_PHRASES):
        logger.info("calendar handler: edit/create phrase → escalate early")
        return None

    range_hint = _resolve_range(prompt)

    try:
        from agent_skills.calendar_tools import list_events_in_range
        events = list_events_in_range(range_hint, max_results=25)
    except Exception as e:
        logger.warning("calendar handler: fetch failed: %s", e)
        return None

    today = date.today()
    events_summary = _simplify_events(events or [], today)
    today_weekday = today.strftime("%A")
    today_date = today.strftime("%B %d, %Y")

    full_prompt = (
        _ANSWER_TEMPLATE
        .replace("{events_summary}", events_summary)
        .replace("{prompt}", prompt)
        .replace("{today_weekday}", today_weekday)
        .replace("{today_date}", today_date)
    )

    text = await _ask_qwen(full_prompt, num_predict=120)
    if not text:
        logger.info("calendar handler: empty response, escalating")
        return None
    if _ESCALATE_RE.search(text):
        logger.info("calendar handler: ESCALATE marker, escalating")
        return None

    event_count = len(events) if events else 0
    logger.info("calendar handler: answered in %d chars (range=%s, events=%d, summary_len=%d)",
                len(text), range_hint, event_count, len(events_summary))

    if event_count >= 2:
        offer = _DETAIL_OFFER
        slim_events = [
            {"summary": ev.get("summary", ""), "start": ev.get("start", ""),
             "end": ev.get("end", ""), "description": ev.get("description", "")}
            for ev in events
        ]
        return {
            "text": text + offer,
            "structured": {
                "intent": "read calendar",
                "entities": {"event_count": event_count, "range": range_hint},
                "pending_action": _pending(
                    "event_detail",
                    {"events": slim_events},
                    question="Want details on any of them?",
                ),
            },
        }

    return {"text": text}
