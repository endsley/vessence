"""Pure schedule helpers for clinic schedule fact builders."""
from __future__ import annotations

from datetime import datetime, timedelta


WEEK_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
LATE_BUFFER_MINUTES = 15
VALID_LOADERS = {
    "today_overview", "day", "cancellations",
    "next_patient", "patient_detail", "weekly",
}


def parse_time(value: str) -> datetime:
    value = (value or "").strip().lower()
    if value.endswith("am"):
        value = value[:-2].strip() + " AM"
    elif value.endswith("pm"):
        value = value[:-2].strip() + " PM"
    elif value.endswith("a"):
        value = value[:-1].strip() + " AM"
    elif value.endswith("p"):
        value = value[:-1].strip() + " PM"
    try:
        return datetime.strptime(value, "%I:%M %p")
    except ValueError:
        return datetime.min


def fmt_time(value: str) -> str:
    text = (value or "").strip().lower()
    if text.endswith("a"):
        return text[:-1] + "am"
    if text.endswith("p"):
        return text[:-1] + "pm"
    return text


def normalize_day(day: str | None, now: datetime | None = None) -> str | None:
    """Map today/tomorrow/weekday names to a canonical weekday name."""
    if not day:
        return None
    now = now or datetime.now()
    value = day.strip().lower()
    if value == "today":
        return now.strftime("%A")
    if value == "tomorrow":
        return (now + timedelta(days=1)).strftime("%A")
    for weekday in WEEK_DAYS:
        if value == weekday.lower():
            return weekday
    return None


def now_meta(now: datetime | None = None) -> dict:
    now = now or datetime.now()
    return {
        "today": now.strftime("%A"),
        "current_time": now.strftime("%I:%M %p").lstrip("0"),
    }


def split_active_cancelled(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    active, cancelled = [], []
    for entry in rows:
        if entry["status"] == "cancelled-out":
            cancelled.append({"name": entry["name"], "time": entry["time"]})
        else:
            active.append({
                "index": len(active) + 1,
                "name": entry["name"],
                "time": entry["time"],
                "health_concerns": entry["health_concerns"],
                "recommendations": entry["recommendations"],
                "visit_summary": entry["visit_summary"],
            })
    return active, cancelled


def active_patient_briefs(active: list[dict]) -> list[dict]:
    return [
        {"index": patient["index"], "name": patient["name"], "time": patient["time"]}
        for patient in active
    ]


def compute_next_patient(
    active: list[dict],
    now: datetime | None = None,
    late_buffer_minutes: int = LATE_BUFFER_MINUTES,
) -> dict | None:
    now = now or datetime.now()
    cutoff = now - timedelta(minutes=late_buffer_minutes)
    today_date = now.date()
    upcoming = []
    for patient in active:
        parsed = parse_time(patient["time"])
        if parsed == datetime.min:
            continue
        appointment_dt = datetime.combine(today_date, parsed.time())
        if appointment_dt >= cutoff:
            upcoming.append((appointment_dt, patient))
    upcoming.sort(key=lambda row: row[0])
    if not upcoming:
        return None
    appointment_dt, patient = upcoming[0]
    return {
        "name": patient["name"],
        "time": patient["time"],
        "minutes_from_now": int((appointment_dt - now).total_seconds() // 60),
    }


def normalize_params(params: dict | None) -> dict:
    """Repair common classifier extraction mistakes before loading facts."""
    normalized = dict(params or {})
    loader = normalized.get("loader")
    if loader not in VALID_LOADERS:
        loader = "today_overview"
    if normalized.get("patient_name") or normalized.get("patient_index") is not None:
        loader = "patient_detail"
    normalized["loader"] = loader
    return normalized
