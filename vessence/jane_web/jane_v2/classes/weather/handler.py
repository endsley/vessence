"""Weather Stage 2 handler — params-driven slice + Stage 2 LLM phrasing.

Stage 1 (v3 classifier) extracts {topic, day, location} via PARAMS_SCHEMA.
This handler is a context provider: pick a small fact slice from the
cache based on `topic`/`day` and hand it to qwen2.5:7b to phrase a
1-sentence spoken reply. No more dumping the whole cache into the LLM
context.

Returns:
    {"text": "<answer>"}   → success, pipeline returns to user
    None                   → escalate to Stage 3 (cache miss, non-Medford
                             location, research/online questions)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from jane_web.jane_v2.ollama_client import post_local_llm_response as _post_local_llm_response

from .slices import (
    DAY_PHRASE_MAP as _DAY_PHRASE_MAP,
    NEUTRAL_DAY_REFS as _NEUTRAL_DAY_REFS,
    VALID_TOPICS as _VALID_TOPICS,
    WEEKDAYS as _WEEKDAYS,
    day_from_followup as _day_from_followup,
    day_reference as _day_reference,
    ensure_day_reference as _ensure_day_reference,
    normalize_day as _normalize_day,
    slice_for as _slice_for,
    without_debug_fields as _without_debug_fields,
)
from .phrasing import (
    ANSWER_TEMPLATE as _ANSWER_TEMPLATE,
    weather_answer_prompt as _weather_answer_prompt,
    weather_phrase_payload as _weather_phrase_payload,
)
from .responses import (
    build_weather_followup_response as _wrap_with_followup,
)

logger = logging.getLogger(__name__)
WEATHER_PATH = Path("/home/chieh/ambient/vessence-data/cache/weather.json")

# Phrases that need research/online lookup the cache can't satisfy — escalate
# immediately rather than spend ~10s in the LLM only to decline.
_FORCE_ESCALATE_PHRASES = (
    "online search", "do a search", "look it up", "look up",
    "search online", "search the web", "google ", "search google",
    "what's causing", "what is causing", "why is", "why is the",
    "explain why", "explain the cause", "cause of",
    "news about", "latest on",
)
_MEDFORD_LOCATIONS = ("medford", "medford ma", "medford, ma")


def _abandon_to_stage3() -> dict:
    return {"abandon_pending": True, "force_stage3": True}


def _pending_payload(pending: dict) -> dict | None:
    if not isinstance(pending, dict):
        return None
    if "data" not in pending:
        return pending
    data = pending.get("data")
    return data if isinstance(data, dict) else None


def _pending_weather_fields(pending: dict) -> tuple[str, str] | None:
    data = _pending_payload(pending)
    if data is None:
        return None
    topic = data.get("topic") or "overview"
    location = data.get("location") or ""
    if not isinstance(topic, str) or not isinstance(location, str):
        return None
    location = location.strip().lower()
    if location and location not in _MEDFORD_LOCATIONS:
        return None
    return topic.strip().lower(), location


async def _phrase(slice_obj: dict, prompt: str) -> str | None:
    day_ref = _day_reference(slice_obj)

    def payload_builder(prompt_text: str, *, model: str, num_ctx: int, keep_alive: str | int) -> dict:
        return _weather_phrase_payload(
            slice_obj,
            prompt_text,
            model=model,
            num_ctx=num_ctx,
            keep_alive=keep_alive,
        )

    try:
        text = await _post_local_llm_response(prompt, payload_builder)
    except Exception as e:
        logger.warning("weather handler: ollama call failed: %s", e)
        return None
    if not text:
        return None
    return _ensure_day_reference(text, day_ref)


async def _answer_for(prompt: str, topic: str, day, location: str | None) -> dict | None:
    """Resolve a topic/day pair → spoken text wrapped with follow-up.
    Returns None on cache miss / phrasing failure."""
    try:
        data = json.loads(WEATHER_PATH.read_text())
    except Exception as e:
        logger.warning("weather handler: cache unreadable: %s", e)
        return None
    if not isinstance(data, dict):
        logger.warning("weather handler: cache malformed: expected object, got %s",
                       type(data).__name__)
        return None
    slice_obj = _slice_for(topic, day, data)
    if slice_obj is None:
        return None
    text = await _phrase(slice_obj, prompt)
    if not text:
        return None
    logger.info("weather handler: answered (topic=%s day=%s, %d chars)",
                topic, day, len(text))
    return _wrap_with_followup(text, topic, location)


async def _handle_pending_weather(prompt: str, pending: dict) -> dict | None:
    from agent_skills import end_phrase
    from agent_skills.private_handler_utils import end_conversation

    if end_phrase.is_end(prompt):
        logger.info("weather handler: end-phrase on resume — closing")
        return end_conversation("Ok.", structured={"intent": "weather"})

    fields = _pending_weather_fields(pending)
    if fields is None:
        logger.info("weather handler: malformed or non-Medford pending state → abandon")
        return _abandon_to_stage3()
    topic, location = fields

    day_spec = _day_from_followup(prompt)
    if not day_spec:
        logger.info("weather handler: no day in follow-up reply → escalate")
        return _abandon_to_stage3()
    result = await _answer_for(prompt, topic, day_spec, location)
    if result is None:
        return _abandon_to_stage3()
    return result


async def handle(prompt: str, context: str = "", pending: dict | None = None,
                 params: dict | None = None) -> dict | None:
    p_lower = (prompt or "").lower()
    if any(phrase in p_lower for phrase in _FORCE_ESCALATE_PHRASES):
        logger.info("weather handler: research/online phrase → escalate")
        return None

    # ── Resume branch (repeating-read continuation) ──────────────────────
    if pending:
        return await _handle_pending_weather(prompt, pending)

    if params is None:
        params = {}
    elif not isinstance(params, dict):
        logger.info("weather handler: malformed params → escalate")
        return None

    location = params.get("location") or ""
    topic = params.get("topic") or "overview"
    if not isinstance(location, str) or not isinstance(topic, str):
        logger.info("weather handler: malformed params fields → escalate")
        return None
    location = location.strip().lower()
    if location and location not in _MEDFORD_LOCATIONS:
        logger.info("weather handler: non-Medford location %r → escalate", location)
        return None

    topic = topic.strip().lower()
    if topic not in _VALID_TOPICS:
        logger.info("weather handler: unknown topic %r → overview", topic)
        topic = "overview"
    day = params.get("day")

    result = await _answer_for(prompt, topic, day, location)
    if result is None:
        logger.info("weather handler: no slice for topic=%s day=%s → escalate",
                    topic, day)
        return None
    return result
