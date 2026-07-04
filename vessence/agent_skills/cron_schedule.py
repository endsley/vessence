"""Small cron schedule matcher used by essence scheduler."""
from __future__ import annotations

from datetime import datetime


def cron_weekday(now: datetime) -> int:
    return (now.weekday() + 1) % 7


def _cron_fields(now: datetime) -> list[int]:
    return [now.minute, now.hour, now.day, now.month, cron_weekday(now)]


def _field_matches(field_val: int, pattern: str) -> bool:
    if pattern == "*":
        return True
    if "/" in pattern:
        base, step = pattern.split("/")
        base_val = 0 if base == "*" else int(base)
        step_val = int(step)
        if step_val <= 0:
            return False
        return (field_val - base_val) % step_val == 0
    if "," in pattern:
        return field_val in [int(value) for value in pattern.split(",")]
    if "-" in pattern:
        low, high = pattern.split("-")
        return int(low) <= field_val <= int(high)
    return field_val == int(pattern)


def matches_schedule(schedule: str, now: datetime) -> bool:
    """Simple cron matcher for minute hour dom month dow."""
    parts = schedule.strip().split()
    if len(parts) != 5:
        return False
    try:
        return all(
            _field_matches(field_val, pattern)
            for field_val, pattern in zip(_cron_fields(now), parts)
        )
    except (ValueError, ZeroDivisionError):
        return False
