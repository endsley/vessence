"""Prompt helpers for the read-calendar Stage 2 handler."""
from __future__ import annotations

import re
from datetime import date


ANSWER_TEMPLATE = """\
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

DETAIL_TEMPLATE = """\
You are Jane, a personal assistant. The user asked for details about \
a specific calendar event. Read the event info below and give a short, \
natural spoken summary.

Include: event name, day, time, duration, and description (if any). \
If there's no description, just say there are no extra details.

Keep it to 1-2 sentences, conversational, speakable.

Event info:
{event_info}

Your spoken answer:"""

ESCALATE_RE = re.compile(r"\bESCALATE\b", re.IGNORECASE)
FORCE_ESCALATE_PHRASES = (
    "schedule a", "create a", "add a", "set up a",
    "cancel my", "delete my", "remove my",
    "move my", "reschedule", "change my",
)


def build_calendar_answer_prompt(
    events_summary: str,
    user_prompt: str,
    today: date,
) -> str:
    return (
        ANSWER_TEMPLATE
        .replace("{events_summary}", events_summary)
        .replace("{prompt}", user_prompt)
        .replace("{today_weekday}", today.strftime("%A"))
        .replace("{today_date}", today.strftime("%B %d, %Y"))
    )


def build_event_detail_prompt(event_info: str) -> str:
    return DETAIL_TEMPLATE.replace("{event_info}", event_info)


def calendar_llm_payload(
    prompt_text: str,
    *,
    model: str,
    num_predict: int,
    num_ctx: int,
    keep_alive: str | int,
) -> dict:
    return {
        "model": model,
        "prompt": prompt_text,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2, "num_predict": num_predict, "num_ctx": num_ctx},
        "keep_alive": keep_alive,
    }


def response_requests_escalation(text: str) -> bool:
    return bool(ESCALATE_RE.search(text or ""))


def should_force_calendar_escalate(prompt: str) -> bool:
    prompt_lower = (prompt or "").lower()
    return any(phrase in prompt_lower for phrase in FORCE_ESCALATE_PHRASES)
