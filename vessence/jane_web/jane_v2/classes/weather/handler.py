"""Weather Stage 2 handler.

Takes a user prompt, injects the cached weather.json into a dedicated
answer template, asks gemma4:e2b to produce a 1-2 sentence spoken
answer, and returns either:

    {"text": "<answer>"}   → success, pipeline returns to user
    None                    → escalate to Stage 3 (v1 brain)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

MODEL = "gemma4:e2b"
OLLAMA_URL = "http://localhost:11434/api/generate"
WEATHER_PATH = Path("/home/chieh/ambient/vessence-data/cache/weather.json")


_ANSWER_TEMPLATE = """You are Jane, a personal assistant. Answer the \
user's weather question using the cached data below.

The cache contains: current conditions for Medford, MA (temperature, \
feels-like, humidity, wind, sky condition, air quality) AND a 7-day \
forecast where each day has a date, weekday, high, low, condition, \
precipitation amount, humidity range, wind, and UV index. If a \
"pollen" block is present it contains tree, grass, and weed pollen \
levels (None/Very Low/Low/Medium/High/Very High). Use all data freely.

CRITICAL — this response will be read aloud by a voice assistant. \
Your answer must be:
- SHORT: ONE sentence. Two at the absolute most. No lists.
- CONVERSATIONAL: like a friend answering — not formal. Skip the \
preamble, just answer.
- SPEAKABLE: round numbers ("51" not "51.1"), say "degrees" not \
"°F", drop the location name and date unless directly asked.

Good examples (style to copy):
- "It's 51 and feels like 41, pretty clear out."
- "Yeah, light drizzle tomorrow."
- "High of about 58 today, overcast."
- "Air quality's good — AQI is 35."
- "Around 80 on Wednesday, mostly cloudy."
- "Tree pollen is high right now, grass and weeds are low."
- "Pollen's pretty bad — tree is high, you might want to take something."

Bad examples (too wordy / too formal — do NOT write like this):
- "The current temperature in Medford, MA is 51.1°F..."
- "The high temperature today will be 58.6°F with overcast conditions."

Only respond with the single word ESCALATE when the question asks \
about: (a) a city other than Medford, (b) past weather / yesterday, \
(c) a date more than 6 days in the future, or (d) a field the cache \
does NOT store (dew point, barometric pressure, wind direction, \
sunrise/sunset) — pollen IS stored when the block is present.

Weather data (JSON):
{weather_json}

User question: {prompt}

Your 1-sentence spoken answer (or the single word ESCALATE):"""


_ESCALATE_RE = re.compile(r"\bESCALATE\b", re.IGNORECASE)


async def handle(prompt: str) -> dict | None:
    try:
        weather_json = WEATHER_PATH.read_text()
    except Exception as e:
        logger.warning("weather handler: could not read cache: %s", e)
        return None

    body = {
        "model": MODEL,
        "prompt": _ANSWER_TEMPLATE.replace("{weather_json}", weather_json).replace(
            "{prompt}", prompt
        ),
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2, "num_predict": 120},
        "keep_alive": "1h",
    }
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(OLLAMA_URL, json=body)
            r.raise_for_status()
            text = (r.json().get("response") or "").strip()
    except Exception as e:
        logger.warning("weather handler: ollama call failed: %s", e)
        return None

    if not text:
        logger.info("weather handler: empty response, escalating")
        return None
    if _ESCALATE_RE.search(text):
        logger.info("weather handler: ESCALATE marker, escalating")
        return None

    logger.info("weather handler: answered in %d chars", len(text))
    return {"text": text}
