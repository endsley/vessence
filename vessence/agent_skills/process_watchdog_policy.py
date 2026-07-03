"""Pure policy helpers for process_watchdog.py."""
from __future__ import annotations

import re
from typing import Iterable


_RUNNING_FOR_RE = re.compile(
    r"\b(?P<count>\d+|an?|about an?|less than a)\s+"
    r"(?P<unit>second|seconds|minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)\b",
    re.IGNORECASE,
)

_UNIT_MINUTES = {
    "second": 0,
    "seconds": 0,
    "minute": 1,
    "minutes": 1,
    "hour": 60,
    "hours": 60,
    "day": 24 * 60,
    "days": 24 * 60,
    "week": 7 * 24 * 60,
    "weeks": 7 * 24 * 60,
    "month": 30 * 24 * 60,
    "months": 30 * 24 * 60,
    "year": 365 * 24 * 60,
    "years": 365 * 24 * 60,
}


def parse_running_for_minutes(duration_str: str) -> int:
    """Parse Docker's RunningFor text into approximate minutes."""
    text = duration_str.strip().lower()
    if not text:
        return 0
    match = _RUNNING_FOR_RE.search(text)
    if not match:
        return 0

    count_text = match.group("count")
    unit = match.group("unit")
    if count_text.startswith("less than"):
        count = 0
    elif count_text in {"a", "an", "about a", "about an"}:
        count = 1
    else:
        try:
            count = int(count_text)
        except ValueError:
            return 0
    return count * _UNIT_MINUTES[unit]


def docker_container_is_too_old(running_for: str, max_age_minutes: int) -> bool:
    return parse_running_for_minutes(running_for) > max_age_minutes


def parse_docker_ps_tts_line(line: str) -> tuple[str, str, str] | None:
    """Return (container_id, running_for, name) from a docker ps formatted row."""
    parts = line.split()
    if not parts:
        return None
    container_id = parts[0]
    running_for = " ".join(parts[1:-1])
    name = parts[-1] if len(parts) > 2 else ""
    return container_id, running_for, name


def command_is_protected(command: str, protected_names: Iterable[str]) -> bool:
    cmd_lower = command.lower()
    return any(name.lower() in cmd_lower for name in protected_names)
