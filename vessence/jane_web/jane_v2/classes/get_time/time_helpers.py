"""Fast-path and prompt helpers for the get-time handler."""
from __future__ import annotations

import re
from datetime import datetime


FAST_TIME_RE = re.compile(
    r"^\s*"
    r"(?:hey\s+jane[,\s]+)?"
    r"(?:please\s+|can\s+you\s+|could\s+you\s+|would\s+you\s+)?"
    r"(?:just\s+)?"
    r"(?:tell\s+me\s+|give\s+me\s+|say\s+)?"
    r"(?:"
    r"what\s+time(?:\s+is\s+it|\s+now)?"
    r"|what(?:'?s|\s+is)\s+(?:the\s+)?(?:current\s+)?(?:time|clock)(?:\s+is\s+it|\s+now)?"
    r"|(?:the\s+)?(?:current\s+)?(?:time|clock)"
    r")"
    r"(?:\s+please)?"
    r"[\s?.!]*$",
    re.IGNORECASE,
)
FAST_DATE_RE = re.compile(
    r"^\s*(?:"
    r"(?:hey\s+jane,?\s+)?"
    r"(?:please\s+|can\s+you\s+|could\s+you\s+)?"
    r"(?:"
    r"what\s+day(?:\s+of\s+the\s+week)?(?:\s+is\s+it|\s+today)?"
    r"|(?:what(?:'?s|\s+is)\s+(?:the\s+)?(?:current\s+|today'?s\s+)?)?"
    r"(?:date|day(?:\s+of\s+the\s+week)?|today)"
    r"(?:\s+is\s+it|\s+today)?"
    r")"
    r"[\s?.!]*$"
    r")",
    re.IGNORECASE,
)


def fast_time_reply(prompt: str, now: datetime | None = None) -> str | None:
    """Return a local direct answer for plain time/date queries."""
    prompt = (prompt or "").strip()
    if not prompt:
        return None
    now = now or datetime.now().astimezone()
    if FAST_TIME_RE.match(prompt):
        return f"It's {now.strftime('%-I:%M %p')}."
    if FAST_DATE_RE.match(prompt):
        return f"It's {now.strftime('%A, %B %-d')}."
    return None


def format_time_info(now: datetime | None = None) -> str:
    """Return a date/time info block suitable for LLM consumption."""
    now = now or datetime.now().astimezone()
    return (
        f"Current local time: {now.strftime('%-I:%M %p')} on "
        f"{now.strftime('%A, %B %-d, %Y')} "
        f"(timezone: {now.tzname()})."
    )


def build_prompt(user_prompt: str, fifo_block: str, time_info: str) -> str:
    fifo_section = (
        f"Recent conversation (oldest first):\n{fifo_block}\n"
        if fifo_block else
        "Recent conversation: (empty)\n"
    )
    return f"""You are Jane, a voice assistant. The intent classifier decided the user is asking about time, date, or day. The current time has been fetched for you — use it below together with the recent conversation to craft a short natural reply tailored to what the user actually asked.

{time_info}

{fifo_section}
User: "{user_prompt.strip()}"

Think briefly, then answer. Format your response as exactly TWO fields:

THOUGHT: <one short line: what did the user actually want — the time, the day, a date, or something contextual like "is it late"? Any FIFO context I should weave in?>
REPLY: <the one-sentence spoken answer. Natural conversational English for TTS. No markdown, no lists, no emoji. Do not say "according to my clock" or "based on the info" — just answer.>"""


def time_llm_payload(
    prompt_text: str,
    *,
    model: str,
    num_ctx: int,
    keep_alive: str | int,
) -> dict:
    return {
        "model": model,
        "prompt": prompt_text,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 80,
            "num_ctx": num_ctx,
        },
        "keep_alive": keep_alive,
    }


def parse_llm_response(raw: str, fallback: str) -> tuple[str, str]:
    """Return `(thought, reply)` from the handler's THOUGHT/REPLY format."""
    thought = ""
    reply = raw.strip()
    for line in raw.splitlines():
        text = line.strip()
        if text.upper().startswith("THOUGHT:"):
            thought = text.split(":", 1)[1].strip()
        elif text.upper().startswith("REPLY:"):
            reply = text.split(":", 1)[1].strip()
    reply = reply.strip().strip('"').strip("'").strip()
    if not reply:
        reply = fallback
    return thought, reply
