"""Response builders for the weather Stage 2 handler."""

from __future__ import annotations

from agent_skills.private_handler_utils import pending_continuation as _pending_continuation


INTENT = "weather"
WEATHER_FOLLOWUP_QUESTION = "Want the weather for another day?"


def build_weather_followup_response(spoken: str, topic: str, location: str | None) -> dict:
    text = f"{spoken} {WEATHER_FOLLOWUP_QUESTION}"
    return {
        "text": text,
        "structured": {
            "intent": INTENT,
            "pending_action": _pending_continuation(
                handler_class=INTENT,
                awaiting="another_day_or_stop",
                question=WEATHER_FOLLOWUP_QUESTION,
                data={"topic": topic, "location": location or ""},
            ),
        },
    }
