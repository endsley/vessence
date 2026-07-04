"""Prompt and request builders for weather Stage 2 phrasing."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from .slices import day_reference


ANSWER_TEMPLATE = """You are Jane answering a voice weather question.

Use ONLY the data slice below to answer. Speak in ONE sentence (two at \
absolute most). Be casual, like a friend — no preamble, no formal phrasing.

Style rules:
- Round numbers ("51" not "51.1"). Say "degrees" not "°F".
- Drop the location and ISO date unless directly asked.
- Skip lists; say it as prose.
- The data slice is for {day_ref}. When {day_ref} is anything other than \
"today", the day reference MUST appear in your answer. Never say "today" \
unless {day_ref} is "today".

Examples of the desired tone (do NOT copy verbatim — adapt to the data):
- "It's 51 and feels like 41, pretty clear out."           (day_ref = today)
- "Around 47 with light drizzle tomorrow."                 (day_ref = tomorrow)
- "High around 73 on Wednesday, partly cloudy."           (day_ref = Wednesday)
- "Air quality's good — AQI is 35."                        (no day reference)
- "Looks like rain Saturday, high near 62."                (day_ref = Saturday)

Data slice (refer to this day as "{day_ref}"):
{slice}

User question: {prompt}

Your 1-sentence spoken answer:"""


def weather_answer_prompt(
    slice_obj: dict[str, Any],
    prompt: str,
    *,
    today: date | None = None,
) -> str:
    day_ref = day_reference(slice_obj, today=today)
    return ANSWER_TEMPLATE.format(
        slice=json.dumps(slice_obj, indent=2),
        prompt=prompt,
        day_ref=day_ref,
    )


def weather_phrase_payload(
    slice_obj: dict[str, Any],
    prompt: str,
    *,
    model: str,
    num_ctx: int,
    keep_alive: str | int = -1,
    today: date | None = None,
) -> dict[str, Any]:
    return {
        "model": model,
        "prompt": weather_answer_prompt(slice_obj, prompt, today=today),
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2, "num_predict": 60, "num_ctx": num_ctx},
        "keep_alive": keep_alive,
    }
