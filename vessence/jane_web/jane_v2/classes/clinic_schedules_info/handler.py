"""clinic_schedules_info Stage 2 handler.

Queries the SQLite schedule DB and returns a spoken answer for:
  - How many patients on a given day
  - Who are the patients on a given day
  - Busiest day / weekly summary

Falls through to Stage 3 if the question can't be matched.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(os.environ.get("VESSENCE_DATA_HOME", "/home/chieh/ambient/vessence-data")) / "schedule.db"

_DAYS = {
    "monday": "Monday", "tuesday": "Tuesday", "wednesday": "Wednesday",
    "thursday": "Thursday", "friday": "Friday", "saturday": "Saturday",
    "sunday": "Sunday", "today": None, "tomorrow": None,  # resolved at runtime
}

_FOLLOW_UP = " Would you like to know about another day?"

_DAY_RE = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow)\b",
    re.IGNORECASE,
)
_COUNT_RE = re.compile(
    r"\bhow many\b|\bhow busy\b|\bhow packed\b|\bhow heavy\b|\bis she working\b|\bhow full\b",
    re.IGNORECASE,
)
_WHO_RE = re.compile(
    r"\bwho\b|\blist\b|\bnames?\b|\bpatients?\b|\bcoming in\b|\bseeing\b",
    re.IGNORECASE,
)
_DETAIL_RE = re.compile(
    r"\b(health concern|recommendation|visit summary|summary|concerns?)\b",
    re.IGNORECASE,
)
# Match "for John Doe", "John Doe's", or "of John Doe" — case-insensitive
_NAME_RE = re.compile(
    r"(?:\bfor\s+|\bof\s+)([A-Za-z][a-z]+(?:\s+[A-Za-z][a-z]+)+)"
    r"|([A-Za-z][a-z]+(?:\s+[A-Za-z][a-z]+)+)'s\b",
    re.IGNORECASE,
)


def _parse_time(t: str) -> datetime:
    """Parse '8:00a' / '2:30p' into a datetime for proper chronological sorting."""
    t = t.strip().lower().replace("a", " AM").replace("p", " PM")
    try:
        return datetime.strptime(t, "%I:%M %p")
    except ValueError:
        return datetime.min


def _db_conn():
    if not DB_PATH.exists():
        return None
    return sqlite3.connect(DB_PATH)


def _current_week_start() -> str | None:
    conn = _db_conn()
    if not conn:
        return None
    try:
        row = conn.execute(
            "SELECT week_start FROM appointments ORDER BY scraped_at DESC LIMIT 1"
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


async def handle(prompt: str) -> dict | None:
    p = (prompt or "").lower()

    # Patient-specific detail query (health concerns, recommendations, visit summary)
    if _DETAIL_RE.search(p):
        name_match = _NAME_RE.search(prompt)
        if name_match:
            patient_name = (name_match.group(1) or name_match.group(2)).strip()
        else:
            # No patient name found — fall through to Stage 3 for clarification
            return None
        return _patient_detail(p, patient_name)

    day_match = _DAY_RE.search(p)
    if not day_match:
        # No day mentioned — try weekly summary
        return _weekly_summary()

    raw_day = day_match.group(1).lower()
    if raw_day == "today":
        day_of_week = date.today().strftime("%A")
    elif raw_day == "tomorrow":
        day_of_week = (date.today() + timedelta(days=1)).strftime("%A")
    else:
        day_of_week = _DAYS[raw_day]

    if _COUNT_RE.search(p):
        return _count_for_day(day_of_week)
    elif _WHO_RE.search(p):
        return _names_for_day(day_of_week)
    else:
        return _count_for_day(day_of_week)


def _count_for_day(day_of_week: str) -> dict | None:
    conn = _db_conn()
    if not conn:
        logger.warning("schedule DB not found at %s", DB_PATH)
        return None
    try:
        week_start = _current_week_start()
        rows = conn.execute(
            "SELECT status FROM appointments WHERE day_of_week=? AND week_start=?",
            (day_of_week, week_start),
        ).fetchall()
        if not rows:
            return {"text": f"She has no patients scheduled on {day_of_week}.{_FOLLOW_UP}"}
        total = len(rows)
        cancelled = sum(1 for r in rows if r[0] == "cancelled-out")
        active = total - cancelled
        if cancelled:
            return {"text": (
                f"She has {active} active patient{'s' if active != 1 else ''} on {day_of_week}, "
                f"with {cancelled} cancellation{'s' if cancelled != 1 else ''} ({total} total booked).{_FOLLOW_UP}"
            )}
        return {"text": f"She has {total} patient{'s' if total != 1 else ''} on {day_of_week}.{_FOLLOW_UP}"}
    finally:
        conn.close()


def _names_for_day(day_of_week: str) -> dict | None:
    conn = _db_conn()
    if not conn:
        return None
    try:
        week_start = _current_week_start()
        rows = conn.execute(
            "SELECT patient_name, start_time, status FROM appointments "
            "WHERE day_of_week=? AND week_start=?",
            (day_of_week, week_start),
        ).fetchall()
        if not rows:
            return {"text": f"No patients scheduled on {day_of_week}.{_FOLLOW_UP}"}
        sorted_rows = sorted(rows, key=lambda r: _parse_time(r[1]))
        active = [(r[0], r[1]) for r in sorted_rows if r[2] != "cancelled-out"]
        cancelled = [(r[0], r[1]) for r in sorted_rows if r[2] == "cancelled-out"]
        if len(active) <= 6:
            name_str = ", ".join(f"{n} at {t}" for n, t in active)
        else:
            name_str = ", ".join(f"{n} at {t}" for n, t in active[:6]) + f", and {len(active) - 6} more"
        text = f"On {day_of_week} she has {len(active)} active patient{'s' if len(active) != 1 else ''}: {name_str}."
        if cancelled:
            c_list = [f"{n} at {t}" for n, t in cancelled[:3]]
            c_str = ", ".join(c_list)
            if len(cancelled) > 3:
                c_str += f" and {len(cancelled) - 3} more"
            text += f" Cancelled: {c_str}."
        text += _FOLLOW_UP
        return {"text": text}
    finally:
        conn.close()


def _patient_detail(p: str, patient_name: str | None) -> dict | None:
    """Return health_concerns / recommendations / visit_summary for a named patient.

    These fields are too long to speak — response uses spoken + text blocks.
    """
    conn = _db_conn()
    if not conn:
        return None
    try:
        week_start = _current_week_start()
        if patient_name:
            norm = patient_name.lower()
            rows = conn.execute(
                "SELECT patient_name, health_concerns, recommendations, visit_summary "
                "FROM appointments WHERE week_start=? AND LOWER(patient_name) LIKE ?",
                (week_start, f"%{norm}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT patient_name, health_concerns, recommendations, visit_summary "
                "FROM appointments WHERE week_start=? ORDER BY date, start_time",
                (week_start,),
            ).fetchall()

        if not rows:
            return {"text": f"I don't have detail records for {patient_name} this week."}

        if len(rows) > 1:
            names = ", ".join(r[0] for r in rows[:4])
            return {"text": f"I found multiple patients matching '{patient_name}': {names}. Which one did you mean?"}

        row = rows[0]
        name, health_concerns, recommendations, visit_summary = row

        if "health" in p or "concern" in p:
            field_label, value = "Health Concerns", health_concerns
        elif "recommend" in p:
            field_label, value = "Recommendations", recommendations
        else:
            field_label, value = "Visit Summary", visit_summary

        if not value:
            return {"text": f"No {field_label.lower()} data available for {name} yet."}

        spoken = f"That's too long to speak. Here's {name}'s {field_label}:"
        return {"text": spoken, "print": f"**{name} — {field_label}**\n\n{value}"}
    finally:
        conn.close()


def _weekly_summary() -> dict | None:
    conn = _db_conn()
    if not conn:
        return None
    try:
        week_start = _current_week_start()
        rows = conn.execute(
            "SELECT day_of_week, COUNT(*) as cnt FROM appointments "
            "WHERE week_start=? GROUP BY day_of_week ORDER BY cnt DESC",
            (week_start,),
        ).fetchall()
        if not rows:
            return {"text": "No schedule data available for this week."}
        parts = [f"{r[0]}: {r[1]}" for r in rows]
        busiest = rows[0]
        return {
            "text": (
                f"This week her busiest day is {busiest[0]} with {busiest[1]} patients. "
                f"Full breakdown — {', '.join(parts)}."
            )
        }
    finally:
        conn.close()
