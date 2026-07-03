"""Pure payload builders for cached weather data."""

from __future__ import annotations

from datetime import date
from typing import Any


POLLEN_LABELS = {
    0: "None",
    1: "Very Low",
    2: "Low",
    3: "Medium",
    4: "High",
    5: "Very High",
}

DEGREES_F = "\u00b0F"
MICROGRAMS_PER_M3 = "\u00b5g/m\u00b3"


def pollen_payload(values: dict[str, Any]) -> dict[str, Any]:
    tree_idx = values.get("treeIndex") or 0
    grass_idx = values.get("grassIndex") or 0
    weed_idx = values.get("weedIndex") or 0
    return {
        "tree": POLLEN_LABELS.get(int(tree_idx), "Unknown"),
        "grass": POLLEN_LABELS.get(int(grass_idx), "Unknown"),
        "weed": POLLEN_LABELS.get(int(weed_idx), "Unknown"),
        "tree_index": int(tree_idx),
        "grass_index": int(grass_idx),
        "weed_index": int(weed_idx),
    }


def weather_cache_payload(
    weather: dict[str, Any],
    aqi: dict[str, Any],
    pollen: dict[str, Any],
    *,
    location: str,
    fetched: str,
    wmo_codes: dict[int, str],
) -> dict[str, Any]:
    result = {
        "location": location,
        "fetched": fetched,
        "current": {
            "temperature": f"{weather['current']['temperature_2m']}{DEGREES_F}",
            "feels_like": f"{weather['current']['apparent_temperature']}{DEGREES_F}",
            "humidity": f"{weather['current']['relative_humidity_2m']}%",
            "wind": f"{weather['current']['wind_speed_10m']} mph",
            "condition": wmo_codes.get(weather["current"]["weather_code"], "Unknown"),
        },
        "air_quality": {
            "us_aqi": aqi["current"]["us_aqi"],
            "pm2_5": f"{aqi['current']['pm2_5']} {MICROGRAMS_PER_M3}",
            "pm10": f"{aqi['current']['pm10']} {MICROGRAMS_PER_M3}",
            "ozone": f"{aqi['current']['ozone']} {MICROGRAMS_PER_M3}",
        },
        "forecast": [],
    }

    if pollen:
        result["pollen"] = pollen

    for i, day in enumerate(weather["daily"]["time"]):
        weekday = date.fromisoformat(day).strftime("%A")
        result["forecast"].append(
            {
                "date": day,
                "weekday": weekday,
                "high": f"{weather['daily']['temperature_2m_max'][i]}{DEGREES_F}",
                "low": f"{weather['daily']['temperature_2m_min'][i]}{DEGREES_F}",
                "condition": wmo_codes.get(weather["daily"]["weathercode"][i], "Unknown"),
                "precipitation": f"{weather['daily']['precipitation_sum'][i]} in",
                "humidity": (
                    f"{weather['daily']['relative_humidity_2m_min'][i]}-"
                    f"{weather['daily']['relative_humidity_2m_max'][i]}%"
                ),
                "wind": f"{weather['daily']['wind_speed_10m_max'][i]} mph",
                "uv_index": weather["daily"]["uv_index_max"][i],
            }
        )

    return result
