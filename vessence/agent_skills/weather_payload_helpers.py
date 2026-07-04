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


def current_weather_payload(weather: dict[str, Any], wmo_codes: dict[int, str]) -> dict[str, Any]:
    current = weather["current"]
    return {
        "temperature": f"{current['temperature_2m']}{DEGREES_F}",
        "feels_like": f"{current['apparent_temperature']}{DEGREES_F}",
        "humidity": f"{current['relative_humidity_2m']}%",
        "wind": f"{current['wind_speed_10m']} mph",
        "condition": wmo_codes.get(current["weather_code"], "Unknown"),
    }


def air_quality_payload(aqi: dict[str, Any]) -> dict[str, Any]:
    current = aqi["current"]
    return {
        "us_aqi": current["us_aqi"],
        "pm2_5": f"{current['pm2_5']} {MICROGRAMS_PER_M3}",
        "pm10": f"{current['pm10']} {MICROGRAMS_PER_M3}",
        "ozone": f"{current['ozone']} {MICROGRAMS_PER_M3}",
    }


def forecast_day_payload(
    daily: dict[str, Any],
    index: int,
    *,
    wmo_codes: dict[int, str],
) -> dict[str, Any]:
    day = daily["time"][index]
    weekday = date.fromisoformat(day).strftime("%A")
    return {
        "date": day,
        "weekday": weekday,
        "high": f"{daily['temperature_2m_max'][index]}{DEGREES_F}",
        "low": f"{daily['temperature_2m_min'][index]}{DEGREES_F}",
        "condition": wmo_codes.get(daily["weathercode"][index], "Unknown"),
        "precipitation": f"{daily['precipitation_sum'][index]} in",
        "humidity": (
            f"{daily['relative_humidity_2m_min'][index]}-"
            f"{daily['relative_humidity_2m_max'][index]}%"
        ),
        "wind": f"{daily['wind_speed_10m_max'][index]} mph",
        "uv_index": daily["uv_index_max"][index],
    }


def forecast_payload(weather: dict[str, Any], wmo_codes: dict[int, str]) -> list[dict[str, Any]]:
    daily = weather["daily"]
    return [
        forecast_day_payload(daily, index, wmo_codes=wmo_codes)
        for index, _day in enumerate(daily["time"])
    ]


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
        "current": current_weather_payload(weather, wmo_codes),
        "air_quality": air_quality_payload(aqi),
        "forecast": forecast_payload(weather, wmo_codes),
    }

    if pollen:
        result["pollen"] = pollen

    return result
