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
from jane_web.jane_v2.ollama_client import post_local_llm_response as _post_local_llm_response

from .time_helpers import (
    FAST_DATE_RE as _FAST_DATE_RE,
    FAST_TIME_RE as _FAST_TIME_RE,
    build_prompt as _build_prompt,
    fast_time_reply as _fast_time_reply,
    format_time_info as _format_time_info,
    parse_llm_response as _parse_llm_response,
    time_llm_payload as _time_llm_payload,
)

logger = logging.getLogger(__name__)


async def _call_local_llm(prompt_text: str) -> str:
    """Reuse the v3 classifier's warm Ollama runner for Stage 2 generation.
    num_ctx is pinned via LOCAL_LLM_NUM_CTX so we never evict/reload
    (see preference_registry.json::unified_local_llm_num_ctx)."""
    return await _post_local_llm_response(prompt_text, _time_llm_payload)


async def handle(prompt: str, context: str = "") -> dict:
    """Generate a time/date answer via the local LLM with the current
    time injected into the prompt.

    `context` is the recent FIFO rendered as prose by v3's pipeline.
    """
    # Fast path: simple "what time/date is it" queries skip the LLM
    # round-trip entirely. Cuts Stage 2 handler latency from ~3s to <10ms.
    fast = _fast_time_reply(prompt)
    if fast is not None:
        logger.info("get_time: fast path → %r", fast)
        return {
            "text": fast,
            "thought": "fast-path: simple time/date query",
            "conversation_end": True,
        }

    time_info = _format_time_info()
    llm_prompt = _build_prompt(prompt, context or "", time_info)

    t0 = time.perf_counter()
    try:
        raw = await _call_local_llm(llm_prompt)
    except Exception as e:
        logger.warning("get_time: LLM call failed (%s) — falling back to time info", e)
        raw = f"THOUGHT: LLM unavailable, falling back.\nREPLY: {time_info}"
    latency_ms = int((time.perf_counter() - t0) * 1000)

    thought, reply = _parse_llm_response(raw, fallback=time_info)

    logger.info(
        "get_time: LLM %dms — thought=%r reply=%r",
        latency_ms, thought[:80], reply[:80],
    )
    return {"text": reply, "thought": thought, "conversation_end": True}
