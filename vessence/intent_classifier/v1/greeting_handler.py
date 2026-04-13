"""greeting_handler.py — Fast-path greeting responder.

Completely separate from Stage 1 / Stage 2. Called by the v2 proxy when
Stage 1 classifies the user's message as GREETING.

No LLM is used — greetings get instant responses from a curated set
matched to the time-of-day context of the message.

Public API:
    respond(message: str) -> str
        Return a natural, varied greeting response.

    is_pure_greeting(message: str) -> bool
        Quick pattern-match: True if the message is obviously just a greeting.
        Used for a pre-Stage1 fast path in the proxy (skips the Gemma call
        entirely for unambiguous greetings with no active FIFO context).
"""
from __future__ import annotations

import random
import re

# ── Pattern for pre-Stage1 fast path ─────────────────────────────────────────

_PURE_GREETING_RE = re.compile(
    r"^(hey|hi|hello|howdy|yo|sup|what'?s up|good\s+morning|good\s+afternoon|"
    r"good\s+evening|good\s+night|morning|evening|afternoon|hey\s+jane|hi\s+jane|"
    r"hello\s+jane|greetings|hiya|heya|hola|salut|ciao)\s*[!?.]*\s*$",
    re.IGNORECASE,
)


def is_pure_greeting(message: str) -> bool:
    """Return True if the message is unambiguously a standalone greeting.

    Used by the proxy to skip Stage 1 entirely when there is no active
    FIFO context — zero LLM calls for a simple "hey".
    """
    return bool(_PURE_GREETING_RE.match(message.strip()))


# ── Response pools ────────────────────────────────────────────────────────────

_GENERIC = [
    "Hey!",
    "Hi!",
    "Hey there!",
    "Hi there!",
    "Hey, good to hear from you.",
    "What's up?",
    "Hey — what do you need?",
]

_MORNING = [
    "Good morning!",
    "Morning!",
    "Morning — what's up?",
    "Good morning! Ready when you are.",
]

_AFTERNOON = [
    "Hey, good afternoon!",
    "Afternoon!",
    "Good afternoon — what's on your mind?",
]

_EVENING = [
    "Good evening!",
    "Evening!",
    "Evening — what do you need?",
]

_NIGHT = [
    "Still up?",
    "Late night. What do you need?",
    "Hey — burning the midnight oil?",
]

_WHATS_UP = [
    "Not much — what do you need?",
    "All good here. What's up with you?",
    "Ready whenever you are.",
]


# ── Public responder ──────────────────────────────────────────────────────────

def respond(message: str) -> str:
    """Return a short, natural greeting response appropriate to the message."""
    msg = message.strip().lower()

    if "morning" in msg:
        return random.choice(_MORNING)
    if "afternoon" in msg:
        return random.choice(_AFTERNOON)
    if "evening" in msg:
        return random.choice(_EVENING)
    if "night" in msg:
        return random.choice(_NIGHT)
    if "what" in msg and ("up" in msg or "sup" in msg):
        return random.choice(_WHATS_UP)
    if msg in ("yo", "sup"):
        return random.choice(_WHATS_UP)

    return random.choice(_GENERIC)
