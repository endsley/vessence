"""Weather class — classifier metadata.

The description is built dynamically so it can include today's date
and the current forecast window pulled from weather.json.
"""

from __future__ import annotations

import json
from pathlib import Path

WEATHER_PATH = Path("/home/chieh/ambient/vessence-data/cache/weather.json")


def _description() -> str:
    try:
        data = json.loads(WEATHER_PATH.read_text())
        forecast = data["forecast"]
        first, last = forecast[0], forecast[-1]
        weekday_first = first.get("weekday", "")
        weekday_last = last.get("weekday", "")
        today_line = f"- Today's date: {first['date']} ({weekday_first})"
        window_line = (
            f"- Forecast window: {first['date']} ({weekday_first}) "
            f"through {last['date']} ({weekday_last}) — {len(forecast)} days"
        )
    except Exception:
        today_line = "- Today's date: (unknown — weather cache unavailable)"
        window_line = "- Forecast window: 7 days"
    return (
        "[weather]\n"
        "Local weather cache contents:\n"
        "- Location: Medford, MA (ONLY location stored)\n"
        f"{today_line}\n"
        f"{window_line}\n"
        "- Current conditions: temperature, feels-like, humidity, "
        "wind speed, sky condition\n"
        "- Current air quality: US AQI, PM2.5, PM10, ozone\n"
        "- Pollen (if TOMORROW_IO_API_KEY is set): tree, grass, weed levels\n"
        "- Daily forecast per day: high, low, condition, precipitation, "
        "humidity range, wind, UV index\n"
        "- NOT stored: dew point, barometric pressure, wind direction, "
        "sunrise/sunset, past weather, other cities, beyond the forecast window\n"
        "- DOES NOT handle: current time, current date, clocks, calendars, "
        "or questions about how the weather feature/code/cron/report works. "
        "Those go to 'others'."
    )


METADATA = {
    "name": "weather",
    "priority": 10,
    "description": _description,
    "few_shot": [
        ("What's the temperature in Medford right now?", "weather:High"),
        ("Will it rain tomorrow?", "weather:High"),
        ("light frizzles a little bit of rain", "others:Low"),
        ("What was the temperature last Tuesday?", "weather:Medium"),
    ],
    "ack": "Checking the weather…",
    "escalate_ack": "Let me dig a little deeper on that weather question…",
}
