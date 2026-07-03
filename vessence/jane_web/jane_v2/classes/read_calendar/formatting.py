"""Pure range and event formatting helpers for the read-calendar handler."""
from __future__ import annotations

import re
from datetime import date, datetime


# Stage 2 only accepts prompts that explicitly name a day or week range.
RANGE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\btoday\b", re.I), "today"),
    (re.compile(r"\btonight\b", re.I), "today"),
    (re.compile(r"\btomorrow\b", re.I), "tomorrow"),
    (re.compile(r"\bthis week\b", re.I), "this week"),
    (re.compile(r"\bnext week\b", re.I), "next week"),
    (re.compile(r"\bmonday\b", re.I), "monday"),
    (re.compile(r"\btuesday\b", re.I), "tuesday"),
    (re.compile(r"\bwednesday\b", re.I), "wednesday"),
    (re.compile(r"\bthursday\b", re.I), "thursday"),
    (re.compile(r"\bfriday\b", re.I), "friday"),
    (re.compile(r"\bsaturday\b", re.I), "saturday"),
    (re.compile(r"\bsunday\b", re.I), "sunday"),
]


def format_time(value: datetime) -> str:
    if value.minute == 0:
        return value.strftime("%-I%p").lower()
    return value.strftime("%-I:%M%p").lower()


def simplify_events(events: list[dict], today: date) -> str:
    if not events:
        return "No events."
    lines = [f"Total: {len(events)} event{'s' if len(events) != 1 else ''}\n"]
    for index, event in enumerate(events, 1):
        summary = event.get("summary") or "Untitled"
        start_raw = str(event.get("start", ""))
        end_raw = str(event.get("end", ""))
        if "T" in start_raw:
            start = datetime.fromisoformat(start_raw)
            day_label = start.strftime("%A %B %-d")
            time_str = format_time(start)
            if "T" in end_raw:
                end = datetime.fromisoformat(end_raw)
                lines.append(f"{index}. {summary} — {day_label}, {time_str}–{format_time(end)}")
            else:
                lines.append(f"{index}. {summary} — {day_label}, {time_str}")
        else:
            try:
                day = date.fromisoformat(start_raw)
                day_label = day.strftime("%A %B %-d")
            except ValueError:
                day_label = start_raw
            lines.append(f"{index}. {summary} — {day_label} (all day)")
    return "\n".join(lines)


def resolve_range(prompt: str) -> str | None:
    """Return the matched day/week hint, or None if the prompt is vague."""
    prompt_lower = (prompt or "").lower()
    for pattern, hint in RANGE_PATTERNS:
        if pattern.search(prompt_lower):
            return hint
    return None


def match_event(prompt: str, events: list[dict]) -> dict | None:
    """Find the event the user is referring to by number or keyword."""
    prompt_lower = prompt.strip().lower()
    nums = re.findall(r"\b(\d+)\b", prompt_lower)
    if nums:
        index = int(nums[0]) - 1
        if 0 <= index < len(events):
            return events[index]

    best = None
    best_score = 0
    for event in events:
        name = (event.get("summary") or "").lower()
        if not name:
            continue
        score = sum(1 for word in name.split() if word in prompt_lower)
        if score > best_score:
            best_score = score
            best = event
    return best if best_score > 0 else None


def format_event_detail(event: dict) -> str:
    """Format a single event into a readable detail block for qwen."""
    lines = [f"Name: {event.get('summary') or 'Untitled'}"]
    start_raw = str(event.get("start", ""))
    end_raw = str(event.get("end", ""))
    if "T" in start_raw:
        start = datetime.fromisoformat(start_raw)
        lines.append(f"Day: {start.strftime('%A %B %-d')}")
        lines.append(f"Time: {format_time(start)}")
        if "T" in end_raw:
            end = datetime.fromisoformat(end_raw)
            lines.append(f"End: {format_time(end)}")
    else:
        lines.append(f"Day: {start_raw} (all day)")

    description = (event.get("description") or "").strip()
    if description:
        lines.append(f"Description: {description[:300]}")
    else:
        lines.append("Description: none")
    return "\n".join(lines)
