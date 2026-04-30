"""Read calendar class — check/read Google Calendar events.

Stage 2 handles prompts that explicitly name a day or week ("today",
"tomorrow", "this week", "next Friday"). When Stage 2 escalates — vague
phrasing, calendar API failure, or the LLM emits ESCALATE — Opus needs
the events injected, otherwise it can only improvise ("Let me check your
calendar...") and end the turn empty.

Until 2026-04-26 there was no `escalation_context` here, so the phone-1
"what's on my calendar today" turn at id=6177 escalated and Jane only
emitted the placeholder ack with no actual answer. This module now
mirrors `read_email` / `delete_messages`: the metadata owns its data
injection so Stage 3 always has a calendar block to work from.
"""

import datetime
import logging

_logger = logging.getLogger(__name__)


def _format_event_line(i: int, ev: dict) -> str:
    summary = (ev.get("summary") or "Untitled")[:120]
    start_raw = str(ev.get("start", "")).strip()
    end_raw = str(ev.get("end", "")).strip()
    if "T" in start_raw:
        try:
            dt = datetime.datetime.fromisoformat(start_raw)
            day = dt.strftime("%a %b %-d")
            start_t = dt.strftime("%-I:%M%p").lower()
        except ValueError:
            day, start_t = start_raw, ""
        end_t = ""
        if "T" in end_raw:
            try:
                end_dt = datetime.datetime.fromisoformat(end_raw)
                end_t = end_dt.strftime("%-I:%M%p").lower()
            except ValueError:
                pass
        time_range = f"{start_t}–{end_t}" if end_t else start_t
        return f"{i}. {summary} — {day}, {time_range}"
    if start_raw:
        return f"{i}. {summary} — {start_raw} (all day)"
    return f"{i}. {summary}"


def _format_calendar_block(label: str, events: list[dict]) -> str:
    if not events:
        return f"{label}\nNothing scheduled.\n[END]"
    lines = [label]
    for i, ev in enumerate(events, 1):
        lines.append(_format_event_line(i, ev))
        desc = (ev.get("description") or "").strip()
        if desc:
            lines.append(f"   Notes: {desc[:200]}")
    lines.append("[END]")
    return "\n".join(lines)


def _escalation_context() -> str:
    """Inject today + tomorrow + the next 90 days so Opus can answer both
    focused queries ("what's on my calendar today") and forward-looking
    semantic queries ("when's my next doctor's appointment", "anything
    important coming up", "what's my schedule like in June") in a single
    turn — without making a second API call.

    Three buckets:
      - today: focused, kept as a separate bucket so Opus can pick it
        out fast when the user just wants today.
      - tomorrow: same rationale.
      - next 90 days: the wide window. ~90 days × ~1 event/day = ~90
        events × ~150 chars = ~14k chars ≈ 3.5k tokens. Comfortable
        within Opus's context budget and covers the "next doctor's
        appointment" / "anything important coming up" use cases that
        previously fell off the end of the 7-day window. Bumped from
        25 to 200 max_results so a packed 3-month calendar doesn't
        truncate.

    Failures fall back inline; one bucket erroring shouldn't blank the rest.
    """
    try:
        from agent_skills.calendar_tools import list_events_in_range
    except Exception as e:
        return f"[CALENDAR ERROR]\nCalendar tools failed to import: {e}\n[END]"

    parts = []
    creds_failed = False

    for label, range_hint, max_results in (
        ("[CALENDAR — today]", "today", 25),
        ("[CALENDAR — tomorrow]", "tomorrow", 25),
        ("[CALENDAR — next 90 days]", "next_90_days", 200),
    ):
        if creds_failed:
            break
        try:
            events = list_events_in_range(range_hint, max_results=max_results)
            parts.append(_format_calendar_block(label, events))
        except RuntimeError as e:
            creds_failed = True
            parts.append(
                "[CALENDAR ERROR]\n"
                f"Google Calendar not set up: {e}\n"
                "Tell the user they need to sign in with Google on the "
                "Vessence web UI to enable calendar access.\n[END]"
            )
        except Exception as e:
            _logger.warning(
                "read_calendar escalation: fetch failed for %s: %s",
                range_hint, e,
            )
            parts.append(f"{label}\nFetch failed: {e}\n[END]")

    if not creds_failed:
        parts.append(
            f"(Fetched at {datetime.datetime.utcnow().isoformat()}Z. "
            "Answer the user from the most relevant bucket. The 90-day "
            "bucket is for forward-looking semantic queries (next "
            "appointment with X, anything coming up, what's in May). "
            "Quote event names and times. Skip events that already "
            "ended unless the user asked about them.)"
        )

    return "\n\n".join(parts)


PARAMS_SCHEMA = {
    "day": (
        "string|null — today | tomorrow | Monday..Sunday | this_week | next_week, "
        "or a specific date phrase the user said. Null = treat as today."
    ),
    "range": (
        "enum REQUIRED — one of: single_day | week | month. "
        "single_day for 'what's on my calendar [today/tomorrow/Monday]'. "
        "week for 'this week / next week / weekly agenda'. "
        "month for explicitly month-scoped queries (rare)."
    ),
}


METADATA = {
    "name": "read calendar",
    "priority": 10,
    "description": (
        "[read calendar]\n"
        "User wants Jane to check / read / summarize their Google Calendar. "
        "The server fetches events via the Google Calendar API (server-side, "
        "NOT via the phone). The brain sees a [CALENDAR DATA] block with "
        "events for the requested range and summarizes them.\n\n"
        "Example phrasings the user might say:\n"
        "  - \"what's on my calendar today\"\n"
        "  - \"what's on my calendar tomorrow\"\n"
        "  - \"check my calendar\"\n"
        "  - \"what's my agenda today\"\n"
        "  - \"anything on my calendar this week\"\n"
        "  - \"what do I have on my calendar today\"\n\n"
        "Adversarial phrasings that LOOK LIKE 'read calendar' but ARE NOT:\n"
        "  - \"schedule a meeting with Bob tomorrow\" → 'others' (create event)\n"
        "  - \"cancel my 3pm\" → 'others' (edit event)\n"
        "  - \"move my meeting to tomorrow\" → 'others' (edit event)\n"
        "  - \"tell Kathia I have a meeting today\" → 'send message'\n"
        "  - \"what did we talk about in yesterday's meeting\" → 'others' (memory)\n"
        "  - \"what time is it\" → 'get time'"
    ),
    "params_schema": PARAMS_SCHEMA,
    "escalation_context": _escalation_context,
    "few_shot": [],
    "ack": "Checking your calendar…",
    "escalate_ack": "Let me check your calendar…",
}
