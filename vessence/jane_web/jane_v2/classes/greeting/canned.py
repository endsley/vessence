"""Canned greeting and cleanup helpers for the greeting handler."""
from __future__ import annotations

from collections.abc import Callable, Sequence
import random
import re


CANNED_REPLIES = {
    "check_in": [
        "Going well, thanks for asking; what's up?",
        "All good here; what's on your mind?",
        "Doing fine; what's up?",
    ],
    "hello": [
        "Hey, what's up?",
        "Hi, what's up?",
        "Hey there, what do you need?",
    ],
    "morning": [
        "Morning, what's up?",
        "Good morning, what's on the agenda?",
    ],
    "afternoon": [
        "Afternoon, what's up?",
        "Good afternoon, what's up?",
    ],
    "evening": [
        "Evening, what do you need?",
        "Good evening, what's up?",
    ],
    "thanks": [
        "Anytime.",
        "You're welcome.",
        "Sure thing.",
    ],
}

CANNED_PATTERNS = [
    (
        re.compile(
            r"^(how'?s? (it going|things|you|everything)|"
            r"how are you|how you (doing|holding up)|"
            r"what'?s up|what'?s new|sup|you good|you there)\??$"
        ),
        "check_in",
    ),
    (re.compile(r"^(hi+|hey+|hello+|yo|howdy|heya|hiya)\b[.!? ]*$"), "hello"),
    (re.compile(r"^good morning\b[.!? ]*$"), "morning"),
    (re.compile(r"^good afternoon\b[.!? ]*$"), "afternoon"),
    (re.compile(r"^good evening\b[.!? ]*$"), "evening"),
    (
        re.compile(r"^(thanks|thank you|thx|ty|appreciate (it|you))\b[.!? ]*$"),
        "thanks",
    ),
]

PROMPT_TEMPLATE = """\
The classifier thinks the user is greeting you (saying hi, checking in, etc.).
First, confirm: is this actually a greeting or casual check-in?
If NOT (e.g., they're asking a question, giving a command, or continuing a prior topic), \
output ONLY: WRONG_CLASS

If YES, you are Jane, a personal AI assistant. Respond naturally in 1 short sentence — \
warm, casual, like a friend. No markdown. No lists. No filler questions like "how can I help you?"

{context_block}User: {prompt}
Jane:"""


def canned_reply(
    prompt: str,
    chooser: Callable[[Sequence[str]], str] = random.choice,
) -> str | None:
    """Return a canned greeting reply, or None if qwen should handle it."""
    normalized = (prompt or "").strip().lower().rstrip(".!?,")
    for pattern, bucket in CANNED_PATTERNS:
        if pattern.match(normalized):
            return chooser(CANNED_REPLIES[bucket])
    return None


def context_block(context: str) -> str:
    if context and context.strip():
        return f"Recent conversation:\n{context.strip()}\n\n"
    return ""


def build_greeting_prompt(prompt: str, context: str = "") -> str:
    return PROMPT_TEMPLATE.format(
        prompt=(prompt or "").strip(),
        context_block=context_block(context),
    )


def greeting_llm_payload(
    prompt_text: str,
    *,
    model: str,
    num_ctx: int,
    keep_alive: str | int = -1,
) -> dict:
    return {
        "model": model,
        "prompt": prompt_text,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.7, "num_predict": 60, "num_ctx": num_ctx},
        "keep_alive": keep_alive,
    }


def is_wrong_class(text: str) -> bool:
    return "WRONG_CLASS" in (text or "").upper()


def clean_greeting_text(text: str) -> str:
    text = (text or "").strip()
    if text.lower().startswith("jane:"):
        return text[5:].strip()
    return text
