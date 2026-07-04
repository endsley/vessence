"""Response builders for the weather Stage 2 handler."""

from __future__ import annotations

from agent_skills.private_handler_utils import pending_continuation as _pending_continuation


INTENT = "weather"
WEATHER_FOLLOWUP_QUESTION = "Want the weather for another day?"


def weather_followup_text(spoken: str) -> str:
    return f"{spoken} {WEATHER_FOLLOWUP_QUESTION}"


def weather_followup_data(topic: str, location: str | None) -> dict:
    return {"topic": topic, "location": location or ""}


def build_weather_followup_response(spoken: str, topic: str, location: str | None) -> dict:
    return {
        "text": weather_followup_text(spoken),
        "structured": {
            "intent": INTENT,
            "pending_action": _pending_continuation(
                handler_class=INTENT,
                awaiting="another_day_or_stop",
                question=WEATHER_FOLLOWUP_QUESTION,
                data=weather_followup_data(topic, location),
            ),
        },
    }
