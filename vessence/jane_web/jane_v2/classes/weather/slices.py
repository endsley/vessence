"""Pure day parsing and weather-slice helpers for the weather handler."""
from __future__ import annotations

import re
from datetime import date, timedelta


VALID_TOPICS = {"current", "forecast", "precipitation", "wind",
                "air_quality", "pollen", "overview"}

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday",
            "saturday", "sunday"]

DAY_PHRASE_MAP = [
    ("day after tomorrow", None),
    ("tomorrow", "tomorrow"),
    ("today", "today"),
    ("tonight", "today"),
    ("this week", "this_week"),
    ("the week", "this_week"),
    ("weekend", "weekend"),
    ("monday", "monday"), ("tuesday", "tuesday"), ("wednesday", "wednesday"),
    ("thursday", "thursday"), ("friday", "friday"), ("saturday", "saturday"),
    ("sunday", "sunday"),
]

NEUTRAL_DAY_REFS = ("today", "the next several days")
MULTI_DAY_SPECS = frozenset({"this_week", "weekend", "week"})


def day_from_followup(prompt: str, today: date | None = None) -> str | None:
    """Map a follow-up reply to a day spec, or None if no day is detected."""
    prompt_lower = (prompt or "").lower()
    if not prompt_lower.strip():
        return None
    today = today or date.today()
    for phrase, mapped in DAY_PHRASE_MAP:
        if phrase in prompt_lower:
            if phrase == "day after tomorrow":
                return (today + timedelta(days=2)).isoformat()
            return mapped
    return None


def normalize_day(
    day: str | None,
    forecast: list[dict],
    today: date | None = None,
) -> dict | None:
    """Return the forecast entry matching `day`, or None if not found."""
    if not day or not forecast:
        return None
    day_lower = day.strip().lower()
    if day_lower in ("this_week", "weekend", "week"):
        return None
    today = today or date.today()
    if day_lower == "today":
        target = today
    elif day_lower == "tomorrow":
        target = today + timedelta(days=1)
    elif day_lower in WEEKDAYS:
        target_idx = WEEKDAYS.index(day_lower)
        days_ahead = (target_idx - today.weekday()) % 7
        target = today + timedelta(days=days_ahead)
    else:
        match = re.match(r"\d{4}-\d{2}-\d{2}", day_lower)
        if not match:
            return None
        try:
            target = date.fromisoformat(match.group(0))
        except ValueError:
            return None

    target_iso = target.isoformat()
    for entry in forecast:
        if entry.get("date") == target_iso:
            return entry
    return None


def without_debug_fields(entry: dict) -> dict:
    return {key: value for key, value in entry.items() if not key.startswith("debug_")}


def is_multi_day_spec(day: str | None) -> bool:
    return bool(day and day.lower() in MULTI_DAY_SPECS)


def precipitation_day_payload(entry: dict) -> dict:
    return {
        "weekday": entry.get("weekday"),
        "date": entry.get("date"),
        "precipitation": entry.get("precipitation"),
        "condition": entry.get("condition"),
    }


def weekly_forecast_day_payload(entry: dict) -> dict:
    return {
        "weekday": entry.get("weekday"),
        "high": entry.get("high"),
        "low": entry.get("low"),
        "condition": entry.get("condition"),
    }


def precipitation_entries(day_entry: dict | None, forecast: list[dict], *, multi_day: bool) -> list[dict]:
    if multi_day:
        return forecast[:7]
    if day_entry:
        return [day_entry]
    return forecast[:3]


def pollen_slice(pollen: object) -> dict | None:
    if not pollen:
        return None
    return {"topic": "pollen", "pollen": pollen}


def air_quality_slice(air_quality: dict) -> dict:
    return {"topic": "air_quality", "air_quality": air_quality}


def wind_slice(day_entry: dict | None, current: dict) -> dict:
    if day_entry:
        return {
            "topic": "wind",
            "day": day_entry.get("weekday"),
            "wind": day_entry.get("wind"),
        }
    return {"topic": "wind", "current_wind": current.get("wind")}


def precipitation_slice(day_entry: dict | None, forecast: list[dict], *, multi_day: bool) -> dict:
    days = precipitation_entries(day_entry, forecast, multi_day=multi_day)
    slim = [precipitation_day_payload(entry) for entry in days]
    return {"topic": "precipitation", "days": slim}


def forecast_slice(day_entry: dict | None, forecast: list[dict], *, multi_day: bool) -> dict:
    if multi_day:
        days = forecast[:7]
        slim = [weekly_forecast_day_payload(entry) for entry in days]
        return {"topic": "weekly_forecast", "days": slim}
    if day_entry:
        return {"topic": "day_forecast", "day": without_debug_fields(day_entry)}
    return {
        "topic": "day_forecast",
        "day": without_debug_fields(forecast[0]) if forecast else {},
    }


def current_weather_slice(current: dict, forecast: list[dict]) -> dict:
    return {
        "topic": "current",
        "current": without_debug_fields(current),
        "today": without_debug_fields(forecast[0]) if forecast else {},
    }


def overview_weather_slice(current: dict, forecast: list[dict], air_quality: dict) -> dict:
    return {
        "topic": "overview",
        "current": without_debug_fields(current),
        "today": without_debug_fields(forecast[0]) if forecast else {},
        "air_quality_aqi": air_quality.get("us_aqi") or air_quality.get("aqi"),
    }


def slice_for(topic: str, day: str | None, data: dict) -> dict | None:
    """Build the smallest dict that answers the topic/day combo."""
    forecast = data.get("forecast") or []
    current = data.get("current") or {}
    air = data.get("air_quality") or {}
    pollen = data.get("pollen")

    day_entry = normalize_day(day, forecast)
    multi_day = is_multi_day_spec(day)

    if topic == "pollen":
        return pollen_slice(pollen)

    if topic == "air_quality":
        return air_quality_slice(air)

    if topic == "wind":
        return wind_slice(day_entry, current)

    if topic == "precipitation":
        return precipitation_slice(day_entry, forecast, multi_day=multi_day)

    if topic == "forecast":
        return forecast_slice(day_entry, forecast, multi_day=multi_day)

    if topic == "current":
        return current_weather_slice(current, forecast)

    return overview_weather_slice(current, forecast, air)


def day_reference(slice_obj: dict, today: date | None = None) -> str:
    """Human-readable day reference for the weather prompt template."""
    today = today or date.today()
    candidates = []
    if isinstance(slice_obj, dict):
        if isinstance(slice_obj.get("day"), dict):
            candidates.append(slice_obj["day"])
        if isinstance(slice_obj.get("today"), dict):
            candidates.append(slice_obj["today"])
        if isinstance(slice_obj.get("days"), list) and len(slice_obj["days"]) == 1:
            day_entry = slice_obj["days"][0]
            if isinstance(day_entry, dict):
                candidates.append(day_entry)

    for entry in candidates:
        iso = entry.get("date")
        weekday = entry.get("weekday")
        if not iso:
            continue
        try:
            entry_date = date.fromisoformat(iso)
        except ValueError:
            continue
        delta = (entry_date - today).days
        if delta == 0:
            return "today"
        if delta == 1:
            return "tomorrow"
        if 2 <= delta <= 6:
            return weekday or entry_date.strftime("%A")
        return weekday or iso

    if isinstance(slice_obj, dict) and isinstance(slice_obj.get("days"), list):
        return "the next several days"
    return "today"


def ensure_day_reference(text: str, day_ref: str) -> str:
    """Prepend a non-neutral day reference when qwen drops it."""
    if not text or not day_ref or day_ref in NEUTRAL_DAY_REFS:
        return text
    if re.search(rf"\b{re.escape(day_ref)}\b", text, flags=re.IGNORECASE):
        return text
    rest = text[0].lower() + text[1:] if text and text[0].isupper() else text
    return f"{day_ref.capitalize()}: {rest}"
