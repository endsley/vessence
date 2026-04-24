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
import re
from datetime import date, timedelta
from pathlib import Path

import httpx

from jane_web.jane_v2.models import LOCAL_LLM as MODEL, LOCAL_LLM_NUM_CTX, LOCAL_LLM_TIMEOUT, OLLAMA_URL

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

_VALID_TOPICS = {"current", "forecast", "precipitation", "wind",
                 "air_quality", "pollen", "overview"}

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday",
             "saturday", "sunday"]


def _normalize_day(day: str | None, forecast: list[dict]) -> dict | None:
    """Return the forecast entry matching `day`, or None if not found.

    Accepts: today, tomorrow, weekday name, or 'this_week'/'weekend' (None).
    'weekend' / 'this_week' return None — caller treats as multi-day.
    """
    if not day or not forecast:
        return None
    d = day.strip().lower()
    if d in ("this_week", "weekend", "week"):
        return None  # multi-day — caller handles
    today = date.today()
    if d == "today":
        target = today
    elif d == "tomorrow":
        target = today + timedelta(days=1)
    elif d in _WEEKDAYS:
        target_idx = _WEEKDAYS.index(d)
        days_ahead = (target_idx - today.weekday()) % 7
        target = today + timedelta(days=days_ahead)
    else:
        # Try ISO date
        m = re.match(r"\d{4}-\d{2}-\d{2}", d)
        if m:
            try:
                target = date.fromisoformat(m.group(0))
            except ValueError:
                return None
        else:
            return None
    target_iso = target.isoformat()
    for entry in forecast:
        if entry.get("date") == target_iso:
            return entry
    return None


def _slice_for(topic: str, day: str | None, data: dict) -> dict | None:
    """Build the smallest dict that answers the topic/day combo. Returns
    None when the slice can't be assembled (escalate)."""
    forecast = data.get("forecast") or []
    current = data.get("current") or {}
    air = data.get("air_quality") or {}
    pollen = data.get("pollen")

    day_entry = _normalize_day(day, forecast)
    multi_day = day and day.lower() in ("this_week", "weekend", "week")

    if topic == "pollen":
        if not pollen:
            return None  # cache doesn't have pollen → escalate
        return {"topic": "pollen", "pollen": pollen}

    if topic == "air_quality":
        return {"topic": "air_quality", "air_quality": air}

    if topic == "wind":
        if day_entry:
            return {"topic": "wind", "day": day_entry.get("weekday"),
                    "wind": day_entry.get("wind")}
        return {"topic": "wind", "current_wind": current.get("wind")}

    if topic == "precipitation":
        if multi_day:
            days = forecast[:7]
        elif day_entry:
            days = [day_entry]
        else:
            days = forecast[:3]  # default: today + next 2
        slim = [{"weekday": d.get("weekday"), "date": d.get("date"),
                 "precipitation": d.get("precipitation"),
                 "condition": d.get("condition")} for d in days]
        return {"topic": "precipitation", "days": slim}

    if topic == "forecast":
        if multi_day:
            days = forecast[:7]
            slim = [{"weekday": d.get("weekday"), "high": d.get("high"),
                     "low": d.get("low"), "condition": d.get("condition")}
                    for d in days]
            return {"topic": "weekly_forecast", "days": slim}
        if day_entry:
            return {"topic": "day_forecast", "day": day_entry}
        # default: today
        return {"topic": "day_forecast", "day": forecast[0] if forecast else {}}

    if topic == "current":
        return {"topic": "current", "current": current,
                "today": forecast[0] if forecast else {}}

    # overview = "how's the weather": current + today's forecast
    return {"topic": "overview", "current": current,
            "today": forecast[0] if forecast else {},
            "air_quality_aqi": air.get("us_aqi") or air.get("aqi")}


_ANSWER_TEMPLATE = """You are Jane answering a voice weather question.

Use ONLY the data slice below to answer. Speak in ONE sentence (two at \
absolute most). Be casual, like a friend — no preamble, no formal phrasing.

Style rules:
- Round numbers ("51" not "51.1"). Say "degrees" not "°F".
- Drop the location and date unless directly asked.
- Skip lists; say it as prose.

Examples of the desired tone:
- "It's 51 and feels like 41, pretty clear out."
- "Light drizzle tomorrow."
- "High of 58 today, overcast."
- "Air quality's good — AQI is 35."
- "Around 80 on Wednesday, mostly cloudy."

Data slice:
{slice}

User question: {prompt}

Your 1-sentence spoken answer:"""


async def _phrase(slice_obj: dict, prompt: str) -> str | None:
    body = {
        "model": MODEL,
        "prompt": _ANSWER_TEMPLATE.format(
            slice=json.dumps(slice_obj, indent=2), prompt=prompt
        ),
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2, "num_predict": 60, "num_ctx": LOCAL_LLM_NUM_CTX},
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
        logger.warning("weather handler: ollama call failed: %s", e)
        return None
    return text or None


async def handle(prompt: str, params: dict | None = None) -> dict | None:
    p_lower = (prompt or "").lower()
    if any(phrase in p_lower for phrase in _FORCE_ESCALATE_PHRASES):
        logger.info("weather handler: research/online phrase → escalate")
        return None

    params = params or {}
    location = (params.get("location") or "").strip().lower()
    if location and location not in ("medford", "medford ma", "medford, ma"):
        logger.info("weather handler: non-Medford location %r → escalate", location)
        return None

    try:
        data = json.loads(WEATHER_PATH.read_text())
    except Exception as e:
        logger.warning("weather handler: cache unreadable: %s", e)
        return None

    topic = (params.get("topic") or "overview").strip().lower()
    if topic not in _VALID_TOPICS:
        logger.info("weather handler: unknown topic %r → overview", topic)
        topic = "overview"
    day = params.get("day")

    slice_obj = _slice_for(topic, day, data)
    if slice_obj is None:
        logger.info("weather handler: no slice for topic=%s day=%s → escalate",
                    topic, day)
        return None

    text = await _phrase(slice_obj, prompt)
    if not text:
        return None
    logger.info("weather handler: answered (topic=%s day=%s, %d chars)",
                topic, day, len(text))
    return {"text": text}
