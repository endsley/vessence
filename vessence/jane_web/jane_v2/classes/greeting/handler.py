"""Greeting Stage 2 handler.

Handles basic greetings ("hey", "how's it going", "good morning") with a
fast, contextual reply using qwen2.5:7b. No Opus needed.

Returns {"text": "..."} for simple greetings, or None to escalate when
the greeting contains a follow-up question or task.
"""

from __future__ import annotations

import logging
import random
import re

import httpx

from jane_web.jane_v2.models import LOCAL_LLM as MODEL, LOCAL_LLM_NUM_CTX, LOCAL_LLM_TIMEOUT, OLLAMA_URL

logger = logging.getLogger(__name__)

# Deterministic canned replies for the most common greetings — saves a
# 7s Ollama round-trip on qwen2.5:7b cold load. Falls through to the
# LLM for anything less templated.
_CANNED_REPLIES = {
    "check_in": [
        "Going well, thanks for asking. What's up?",
        "All good here. What's on your mind?",
        "Doing fine. How can I help?",
    ],
    "hello": [
        "Hey! What's up?",
        "Hi! How can I help?",
        "Hey there. What do you need?",
    ],
    "morning": [
        "Morning! How can I help?",
        "Good morning! What's on the agenda?",
    ],
    "afternoon": [
        "Afternoon! What's up?",
        "Good afternoon! How can I help?",
    ],
    "evening": [
        "Evening! What do you need?",
        "Good evening! What's up?",
    ],
    "thanks": [
        "Anytime.",
        "You're welcome.",
        "Sure thing.",
    ],
}

_CANNED_PATTERNS = [
    # "how's it going", "how are you", "how you doing", "what's up"
    (re.compile(r"^(how'?s? (it going|things|you|everything)|"
                r"how are you|how you (doing|holding up)|"
                r"what'?s up|what'?s new|sup|you good|you there)\??$"),
     "check_in"),
    # bare hellos
    (re.compile(r"^(hi+|hey+|hello+|yo|howdy|heya|hiya)\b[.!? ]*$"), "hello"),
    # time-of-day
    (re.compile(r"^good morning\b"), "morning"),
    (re.compile(r"^good afternoon\b"), "afternoon"),
    (re.compile(r"^good evening\b"), "evening"),
    # thanks
    (re.compile(r"^(thanks|thank you|thx|ty|appreciate (it|you))\b[.!? ]*$"),
     "thanks"),
]


def _canned_reply(prompt: str) -> str | None:
    """Return a deterministic greeting reply, or None if we should use the LLM."""
    p = (prompt or "").strip().lower().rstrip(".!?,")
    for pattern, bucket in _CANNED_PATTERNS:
        if pattern.match(p):
            choices = _CANNED_REPLIES[bucket]
            return random.choice(choices)
    return None

_PROMPT_TEMPLATE = """\
The classifier thinks the user is greeting you (saying hi, checking in, etc.).
First, confirm: is this actually a greeting or casual check-in?
If NOT (e.g., they're asking a question, giving a command, or continuing a prior topic), \
output ONLY: WRONG_CLASS

If YES, you are Jane, a personal AI assistant. Respond naturally in 1 short sentence — \
warm, casual, like a friend. No markdown. No lists. No filler questions like "how can I help you?"

{context_block}User: {prompt}
Jane:"""


async def handle(prompt: str, context: str = "") -> dict | None:
    """Generate a quick greeting reply.

    Returns {"text": "..."} or None to escalate to Stage 3.
    """
    canned = _canned_reply(prompt)
    if canned:
        logger.info("greeting handler: canned → %r", canned[:60])
        return {"text": canned}

    context_block = ""
    if context and context.strip():
        context_block = f"Recent conversation:\n{context.strip()}\n\n"

    full_prompt = _PROMPT_TEMPLATE.format(
        prompt=prompt.strip(),
        context_block=context_block,
    )

    body = {
        "model": MODEL,
        "prompt": full_prompt,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.7, "num_predict": 60, "num_ctx": LOCAL_LLM_NUM_CTX},
        "keep_alive": -1,
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
            text = (r.json().get("response") or "").strip()
    except Exception as e:
        logger.warning("greeting handler: LLM call failed: %s", e)
        return None

    if not text:
        return None

    # Classification confirmation: if LLM says WRONG_CLASS, defer to Stage 3
    if "WRONG_CLASS" in text.upper():
        logger.info("greeting handler: LLM says WRONG_CLASS — escalating with self-correct")
        return {"wrong_class": True}

    # Clean up common LLM artifacts
    # Remove any self-attribution like "Jane:" at the start
    if text.lower().startswith("jane:"):
        text = text[5:].strip()

    logger.info("greeting handler: %r → %r", prompt[:40], text[:80])
    return {"text": text}
