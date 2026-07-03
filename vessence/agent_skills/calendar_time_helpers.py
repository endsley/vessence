"""Pure time/range helpers for calendar_tools.py."""

from __future__ import annotations

from datetime import datetime, time as dtime, timedelta, timezone
from typing import Any


WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def day_range(day, tz) -> tuple[datetime, datetime]:
    start = datetime.combine(day, dtime.min, tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), dtime.min, tzinfo=tz)
    return start, end


def resolve_range_for_now(range_hint: str | None, now: datetime) -> tuple[datetime, datetime]:
    tz = now.tzinfo
    today = now.date()
    hint = (range_hint or "today").strip().lower().replace(" ", "_")

    if hint == "today":
        return day_range(today, tz)
    if hint == "tomorrow":
        return day_range(today + timedelta(days=1), tz)
    if hint == "weekend":
        days_to_sat = (5 - today.weekday()) % 7
        saturday = today + timedelta(days=days_to_sat)
        monday = saturday + timedelta(days=2)
        return (
            datetime.combine(saturday, dtime.min, tzinfo=tz),
            datetime.combine(monday, dtime.min, tzinfo=tz),
        )
    if hint == "this_week":
        monday = today - timedelta(days=today.weekday())
        next_monday = monday + timedelta(days=7)
        return (
            datetime.combine(monday, dtime.min, tzinfo=tz),
            datetime.combine(next_monday, dtime.min, tzinfo=tz),
        )
    if hint == "next_week":
        monday = today + timedelta(days=(7 - today.weekday()))
        next_monday = monday + timedelta(days=7)
        return (
            datetime.combine(monday, dtime.min, tzinfo=tz),
            datetime.combine(next_monday, dtime.min, tzinfo=tz),
        )
    if hint == "next":
        return now, now + timedelta(days=7)
    if hint in ("next_30_days", "next_30"):
        return now, now + timedelta(days=30)
    if hint in ("next_60_days", "next_60"):
        return now, now + timedelta(days=60)
    if hint in ("next_90_days", "next_90"):
        return now, now + timedelta(days=90)
    if hint in WEEKDAYS:
        days_ahead = (WEEKDAYS[hint] - today.weekday()) % 7
        return day_range(today + timedelta(days=days_ahead), tz)
    try:
        day = datetime.strptime(hint, "%Y-%m-%d").date()
        return day_range(day, tz)
    except ValueError:
        return day_range(today, tz)


def dt_to_iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def to_local_naive_iso(value: str) -> str:
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    return parsed.replace(tzinfo=None).isoformat(timespec="seconds")


def reminder_overrides_body(reminders_minutes: list[int]) -> dict[str, Any]:
    if len(reminders_minutes) > 5:
        raise ValueError("Google Calendar allows at most 5 reminder overrides.")
    for minutes in reminders_minutes:
        if not isinstance(minutes, int) or minutes < 0 or minutes > 40320:
            raise ValueError(
                f"Reminder minutes must be int in [0, 40320]; got {minutes!r}."
            )
    return {
        "useDefault": False,
        "overrides": [
            {"method": "popup", "minutes": minutes} for minutes in reminders_minutes
        ],
    }
