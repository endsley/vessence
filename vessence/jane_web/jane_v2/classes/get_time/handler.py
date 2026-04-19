"""Stage 2 handler for GET_TIME — LLM-generated response with injected time info.

Version B architecture (2026-04-18):
  Instead of a canned "Let me check your phone's clock" + `device.speak_time`
  client-tool round-trip, the handler now:
    1. Fetches the current local date/time on the SERVER.
    2. Feeds the time data + recent conversation + user prompt to the
       local LLM (the same warm runner v3's classifier uses).
    3. Returns the LLM's response directly. Android's TTS speaks it
       as-is — no client tool.

  Benefit: the answer is tailored to the user's actual wording
  ("is it late?" → "Past 9 already, yeah"; "what time is my meeting?"
  → context-aware reply from FIFO). Cost: ~500-900 ms extra per turn
  for the LLM call.

  TODO(timezone): currently uses the server's local clock. When the
  phone ships `client_time_iso` in the request body, we'll prefer that
  so Android users in a different TZ get accurate answers.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)


def _format_time_info() -> str:
    """Return a human-readable block of date/time info suitable for LLM
    consumption: day of week, month + day, time with AM/PM, timezone."""
    now = datetime.now().astimezone()
    return (
        f"Current local time: {now.strftime('%-I:%M %p')} on "
        f"{now.strftime('%A, %B %-d, %Y')} "
        f"(timezone: {now.tzname()})."
    )


def _build_prompt(user_prompt: str, fifo_block: str, time_info: str) -> str:
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


async def _call_local_llm(prompt_text: str) -> str:
    """Reuse the v3 classifier's warm Ollama runner for Stage 2 generation.
    num_ctx is pinned via LOCAL_LLM_NUM_CTX so we never evict/reload
    (see preference_registry.json::unified_local_llm_num_ctx)."""
    import httpx
    from jane_web.jane_v2.models import (
        LOCAL_LLM,
        LOCAL_LLM_NUM_CTX,
        LOCAL_LLM_TIMEOUT,
        OLLAMA_KEEP_ALIVE,
        OLLAMA_URL,
    )
    body = {
        "model": LOCAL_LLM,
        "prompt": prompt_text,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.3,  # small amount of variety for natural replies
            "num_predict": 80,
            "num_ctx": LOCAL_LLM_NUM_CTX,
        },
        "keep_alive": OLLAMA_KEEP_ALIVE,
    }
    async with httpx.AsyncClient(timeout=LOCAL_LLM_TIMEOUT) as client:
        r = await client.post(OLLAMA_URL, json=body)
        r.raise_for_status()
        try:
            from jane_web.jane_v2.models import record_ollama_activity
            record_ollama_activity()
        except Exception:
            pass
        return (r.json().get("response") or "").strip()


async def handle(prompt: str, context: str = "") -> dict:
    """Generate a time/date answer via the local LLM with the current
    time injected into the prompt.

    `context` is the recent FIFO rendered as prose by v3's pipeline.
    """
    time_info = _format_time_info()
    llm_prompt = _build_prompt(prompt, context or "", time_info)

    t0 = time.perf_counter()
    try:
        raw = await _call_local_llm(llm_prompt)
    except Exception as e:
        logger.warning("get_time: LLM call failed (%s) — falling back to time info", e)
        raw = f"THOUGHT: LLM unavailable, falling back.\nREPLY: {time_info}"
    latency_ms = int((time.perf_counter() - t0) * 1000)

    # Parse THOUGHT / REPLY blocks. Fall back to the whole response if
    # the model didn't follow the format.
    thought = ""
    reply = raw.strip()
    for line in raw.splitlines():
        s = line.strip()
        if s.upper().startswith("THOUGHT:"):
            thought = s.split(":", 1)[1].strip()
        elif s.upper().startswith("REPLY:"):
            reply = s.split(":", 1)[1].strip()
    reply = reply.strip().strip('"').strip("'").strip()
    if not reply:
        reply = time_info

    logger.info(
        "get_time: LLM %dms — thought=%r reply=%r",
        latency_ms, thought[:80], reply[:80],
    )
    return {"text": reply, "thought": thought}
