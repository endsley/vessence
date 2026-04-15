"""Greeting Stage 2 handler.

Handles basic greetings ("hey", "how's it going", "good morning") with a
fast, contextual reply using qwen2.5:7b. No Opus needed.

Returns {"text": "..."} for simple greetings, or None to escalate when
the greeting contains a follow-up question or task.
"""

from __future__ import annotations

import logging

import httpx

from jane_web.jane_v2.models import LOCAL_LLM as MODEL, OLLAMA_URL

logger = logging.getLogger(__name__)

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
        "options": {"temperature": 0.7, "num_predict": 60},
        "keep_alive": -1,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(OLLAMA_URL, json=body)
            r.raise_for_status()
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
