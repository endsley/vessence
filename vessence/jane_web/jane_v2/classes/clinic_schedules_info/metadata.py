"""clinic_schedules_info class — classifier metadata."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path
import os

DB_PATH = Path(os.environ.get("VESSENCE_DATA_HOME", "/home/chieh/ambient/vessence-data")) / "schedule.db"


def _description() -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT week_start FROM appointments ORDER BY scraped_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            ws = date.fromisoformat(row[0])
            we = ws + timedelta(days=6)
            window = f"{ws.strftime('%b %d')} – {we.strftime('%b %d, %Y')}"
        else:
            window = "(no data yet)"
    except Exception:
        window = "(unavailable)"
    return (
        "[clinic_schedules_info]\n"
        "User wants to know about the acupuncturist's current-week schedule — "
        "how many patients she has on a given day, or who her patients are on a given day.\n\n"
        f"Data covers week: {window}\n"
        "Answers directly from SQLite — no browser needed.\n"
        "NOT for: booking appointments, historical data, other practitioners by name, "
        "clinic hours, availability, or work hours."
    )


def _escalation_context() -> str:
    return (
        "[clinic_schedules_info escalation context]\n"
        "The schedule DB is at $VESSENCE_DATA_HOME/schedule.db (SQLite).\n"
        "Table: appointments (columns: patient_name, day_of_week, date, start_time, "
        "end_time, status, health_concerns, recommendations, visit_summary, week_start).\n"
        "start_time format is '8:00a', '2:30p' — parse AM/PM for correct chronological sort.\n\n"
        "DISPLAY RULES:\n"
        "- Always list patients in chronological order, earliest appointment first.\n"
        "- Include the appointment time next to each patient name (e.g. 'Melissa at 8 AM, John at 9 AM').\n"
        "- Filter by current week: use the most recent week_start value.\n"
        "- Cancelled patients have status='cancelled-out'."
    )


METADATA = {
    "name": "clinic schedules info",
    "priority": 15,
    "description": _description,
    "escalation_context": _escalation_context,
    "few_shot": [
        ("how many patients does she have on Tuesday", "clinic_schedules_info:High"),
        ("who are the patients for her on Thursday", "clinic_schedules_info:High"),
        ("how many patients does Ariel have on Tuesday", "others:Low"),
        ("book a patient for Thursday", "others:Low"),
    ],
    "ack": "Checking the schedule…",
    "escalate_ack": "Let me look that up in the schedule…",
    # Privacy: patient data (names, health concerns, recommendations, visit
    # summaries) must never leave the local process. The pipeline:
    #   (1) refuses to escalate this class to Stage 3 (no_stage3=True),
    #   (2) redacts FIFO writes so a subsequent non-clinic turn that DOES
    #       escalate can't replay prior clinic content to Claude,
    #   (3) skips the Haiku thematic-memory writeback (cloud call).
    # The handler below is the terminal answer-giver. See Job #82.
    "no_stage3": True,
    "privacy": "local_only",
}
