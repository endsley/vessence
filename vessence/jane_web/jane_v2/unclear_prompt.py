"""Description-based detector for STT-noisy / malformed prompts.

Unlike the other class handlers (which vote via chroma exemplars), this
module runs a small qwen call that reasons about *why* a prompt might be
unclear — background speech bleeding in, speaker misspeaking, STT cutting
off the start/end — and returns True if the prompt should be re-requested
from the user instead of processed.

Flow: Stage 1 runs first. If its top-1 chroma match is essentially
verbatim (`min_dist ≤ SKIP_DIST`), we know the prompt is a known clean
command and skip this detector entirely. Otherwise we ask qwen whether
the prompt exhibits any of the noise signs and short-circuit with a
"say that again?" response when it does.
"""

from __future__ import annotations

import logging
from typing import Final

import httpx

logger = logging.getLogger(__name__)

# When chroma's nearest exemplar is this close, the prompt is essentially
# a verbatim known command — don't pay for a coherence LLM call.
SKIP_DIST: Final[float] = 0.02

# Fixed reply when we decide to re-request. Kept short so TTS is instant.
REPEAT_REPLY: Final[str] = "Sorry, could you say that again?"

_PROMPT_TEMPLATE = """A user just spoke a command to Jane. Speech-to-text sometimes adds noise: background conversation bleeds in, the speaker misspeaks mid-sentence, or the recording cuts off the start or end.

Decide whether the transcribed prompt is CLEAR enough to act on, or UNCLEAR and should be repeated.

Signs a prompt is UNCLEAR:
- A stray leading or trailing word that does not grammatically fit the rest (looks like bleed-through from someone else talking nearby)
- Contradictory or self-correcting fragments stitched together ("play uh no wait the other thing")
- An incomplete sentence that does not stand on its own ("what's the weather in", "turn on the", "can you please")
- Word salad or two unrelated clauses fused without a conjunction

Signs a prompt is CLEAR — default to CLEAR unless you see a specific reason above:
- A natural single sentence, even if short ("what time", "hi", "yes", "read my messages")
- A common command or question that stands on its own, even if terse
- Minor filler like "um" or "uh" does NOT by itself make it unclear

User prompt: {prompt}

Answer ONE word — CLEAR or UNCLEAR:"""


async def is_unclear(prompt: str, *, timeout_s: float | None = None) -> bool:
    """Return True when the prompt looks like STT noise and should be re-requested.

    Returns False on any error (fail-open — we don't want to loop the user on
    "say again" because qwen timed out).
    """
    if not prompt or not prompt.strip():
        return False

    try:
        from jane_web.jane_v2.models import (
            LOCAL_LLM as model,
            LOCAL_LLM_NUM_CTX,
            LOCAL_LLM_TIMEOUT,
            OLLAMA_KEEP_ALIVE,
            OLLAMA_URL,
            record_ollama_activity,
        )
    except Exception as e:
        logger.warning("unclear_prompt: models import failed: %s", e)
        return False

    body = {
        "model": model,
        "prompt": _PROMPT_TEMPLATE.format(prompt=prompt.strip()),
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 5,
            "num_ctx": LOCAL_LLM_NUM_CTX,
        },
        "keep_alive": OLLAMA_KEEP_ALIVE,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_s or LOCAL_LLM_TIMEOUT) as client:
            r = await client.post(OLLAMA_URL, json=body)
            r.raise_for_status()
            raw = (r.json().get("response") or "").strip().upper()
            try:
                record_ollama_activity()
            except Exception:
                pass
    except Exception as e:
        logger.warning("unclear_prompt: qwen call failed (%s) — failing open (treating as clear)", e)
        return False

    unclear = raw.startswith("UNCLEAR")
    logger.info(
        "unclear_prompt: %s for %r (raw=%r)",
        "UNCLEAR" if unclear else "CLEAR", prompt[:80], raw[:20],
    )
    return unclear
