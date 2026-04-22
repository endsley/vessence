"""clinic_schedules_info Stage 2 handler.

Queries the SQLite schedule DB and returns a spoken answer for:
  - How many patients on a given day
  - Who are the patients on a given day
  - Busiest day / weekly summary

After answering about a specific day, attaches a STAGE2_FOLLOWUP
pending_action so short follow-ups like "what about Tuesday" are routed
back here by the dispatcher (instead of going through chroma, which
would require embedding bare weekday names as clinic exemplars and
pollute other classes).

Falls through to Stage 3 if the question can't be matched.
"""

from __future__ import annotations

import datetime as _dt
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

_FOLLOW_UP_QUESTION = "Would you like to know about another day?"
_FOLLOW_UP = f" {_FOLLOW_UP_QUESTION}"

_PATIENT_FOLLOW_UP_QUESTION = "Any other patients you would like to know about?"

_LIST_FOLLOW_UP_QUESTION = (
    "Is there a specific patient you want more details of? "
    "If so tell me the patient ID."
)

_COUNT_FOLLOW_UP_QUESTION = "Would you like to know the names of these patients?"

_CONFIRM_RE = re.compile(
    r"\b(yes|yeah|yep|yup|sure|ok|okay|please|list|tell me|go ahead|"
    r"names?|show me|do it|sounds good|of course)\b",
    re.IGNORECASE,
)

_DECLINE_RE = re.compile(
    r"^\s*(no|no thanks|nope|none|that'?s all|i'?m good|all good|nothing else|done|stop)\s*\.?\s*$",
    re.IGNORECASE,
)


def _expires_at(minutes: int = 2) -> str:
    return (_dt.datetime.utcnow() + _dt.timedelta(minutes=minutes)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


# In-process session-keyed cache for pending patient-selection data. This
# is the only place the numbered list lives across turns for privacy classes
# — the FIFO record strips `patient_list` on write (it's PII), so replaying
# a pending selection relies on this cache. Keys are session_ids; values are
# {patient_list, expires_ts}. Never touches disk, never crosses processes.
_PENDING_SELECTION_CACHE: dict[str, dict] = {}
_PENDING_SELECTION_TTL_SECONDS = 180  # matches _expires_at default × 1.5


def _selection_cache_put(session_id: str | None, patient_list: list) -> None:
    if not session_id or not patient_list:
        return
    import time as _t
    # Opportunistic GC of stale entries.
    now = _t.time()
    stale = [k for k, v in _PENDING_SELECTION_CACHE.items() if v.get("expires_ts", 0) < now]
    for k in stale:
        _PENDING_SELECTION_CACHE.pop(k, None)
    _PENDING_SELECTION_CACHE[session_id] = {
        "patient_list": patient_list,
        "expires_ts": now + _PENDING_SELECTION_TTL_SECONDS,
    }


def _selection_cache_get(session_id: str | None) -> list | None:
    if not session_id:
        return None
    import time as _t
    entry = _PENDING_SELECTION_CACHE.get(session_id)
    if not entry:
        return None
    if entry.get("expires_ts", 0) < _t.time():
        _PENDING_SELECTION_CACHE.pop(session_id, None)
        return None
    return entry.get("patient_list") or None


def _pending_day_followup() -> dict:
    """STAGE2_FOLLOWUP marker after answering about a specific day."""
    return {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "clinic schedules info",
        "status": "awaiting_user",
        "awaiting": "another_day",
        "data": {"awaiting": "another_day"},
        "question": _FOLLOW_UP_QUESTION,
        "expires_at": _expires_at(),
    }


def _pending_count_followup(day_of_week: str) -> dict:
    """STAGE2_FOLLOWUP after a count answer — offer to list the names."""
    return {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "clinic schedules info",
        "status": "awaiting_user",
        "awaiting": "names_for_day_confirm",
        "data": {
            "awaiting": "names_for_day_confirm",
            "day_of_week": day_of_week,
        },
        "question": _COUNT_FOLLOW_UP_QUESTION,
        "expires_at": _expires_at(),
    }


def _pending_patient_selection(patient_list: list) -> dict:
    """STAGE2_FOLLOWUP marker after printing a numbered patient list.

    Carries the list so the reply ("1", "patient 2", or "Caile Hanlon")
    can be resolved back to a patient name.
    """
    return {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "clinic schedules info",
        "status": "awaiting_user",
        "awaiting": "patient_selection_from_list",
        "data": {
            "awaiting": "patient_selection_from_list",
            "patient_list": patient_list,
        },
        "question": _LIST_FOLLOW_UP_QUESTION,
        "expires_at": _expires_at(),
    }


def _pending_patient_followup(detail_type: str, patient_name: str) -> dict:
    """STAGE2_FOLLOWUP marker after answering about a specific patient.

    Remembers the last detail_type so a bare-name reply ("Jeremy") gets
    the same field (health concerns / recommendations / visit summary)
    without the user having to restate it.
    """
    return {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "clinic schedules info",
        "status": "awaiting_user",
        "awaiting": "another_patient",
        "data": {
            "awaiting": "another_patient",
            "last_detail_type": detail_type,
            "last_patient": patient_name,
        },
        "question": _PATIENT_FOLLOW_UP_QUESTION,
        "expires_at": _expires_at(),
    }


def _attach_day_followup(result: dict | None) -> dict | None:
    """If the text includes the day follow-up question, attach pending_action."""
    if not result or not isinstance(result, dict):
        return result
    if _FOLLOW_UP_QUESTION not in (result.get("text") or ""):
        return result
    structured = dict(result.get("structured") or {})
    structured.setdefault("intent", "clinic schedules info")
    structured["pending_action"] = _pending_day_followup()
    result["structured"] = structured
    return result


def _extract_name_from_reply(prompt: str) -> str | None:
    """Best-effort name extraction from a short follow-up reply.

    Returns None for declines ("no thanks"). Otherwise strips common
    lead-ins and filler, returning whatever substring looks name-like.
    SQL does LOWER(patient_name) LIKE '%x%' so case doesn't matter.
    """
    p = (prompt or "").strip().rstrip(".!?,")
    if not p or _DECLINE_RE.match(p):
        return None
    p = re.sub(
        r"^(how about|what about|tell me about|show me|and|also|and then|then)\s+",
        "", p, flags=re.I,
    )
    p = re.sub(r"\b(the|a|an|please|for|of|about)\b", " ", p, flags=re.I)
    p = re.sub(r"\s+", " ", p).strip().rstrip("?.!,")
    return p or None

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


def _fmt_time(t: str) -> str:
    """Render DB times ('8:00a', '2:30p') in the user's preferred '8:00am' form."""
    s = (t or "").strip().lower()
    if s.endswith("a"):
        return s[:-1] + "am"
    if s.endswith("p"):
        return s[:-1] + "pm"
    return s


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


async def handle(prompt: str, pending: dict | None = None) -> dict | None:
    p = (prompt or "").lower()

    # Resume branches. `pending` here is the inner state dict the pipeline
    # unwrapped from pending_action["data"] — it holds `awaiting`, plus
    # whatever fields the relevant _pending_*_followup() builder stored.
    if pending:
        awaiting = pending.get("awaiting")
        if awaiting == "names_for_day_confirm":
            return _resume_count_followup(prompt, pending)
        if awaiting == "patient_selection_from_list":
            return _resume_patient_selection(prompt, pending)
        if awaiting == "another_patient":
            return _resume_another_patient(prompt, pending)
        # "another_day" or untagged fall through to the standard logic below.

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
        if pending:
            # Follow-up turn but no day mentioned — user isn't continuing the
            # day-by-day flow (e.g. "no thanks", "that's all"). Let the
            # pipeline re-route instead of dumping the weekly summary.
            return {"abandon_pending": True}
        # First-turn weekly summary (no day specified)
        return _weekly_summary()

    raw_day = day_match.group(1).lower()
    if raw_day == "today":
        day_of_week = date.today().strftime("%A")
    elif raw_day == "tomorrow":
        day_of_week = (date.today() + timedelta(days=1)).strftime("%A")
    else:
        day_of_week = _DAYS[raw_day]

    if _COUNT_RE.search(p):
        result = _count_for_day(day_of_week)
    elif _WHO_RE.search(p):
        result = _names_for_day(day_of_week)
    else:
        result = _count_for_day(day_of_week)
    return _attach_day_followup(result)


# Whole-reply numeric: "1", "1.", "2nd", "#3"
_ID_PURE_RE = re.compile(r"^\s*#?\s*(\d+)(?:st|nd|rd|th)?\s*\.?\s*$", re.IGNORECASE)
# Explicit prefix anywhere: "patient 1", "number 2", "#3", "no. 4", "# 2"
_ID_PREFIXED_RE = re.compile(
    r"\b(?:patient|number|no\.?|#)\s*#?\s*(\d+)(?:st|nd|rd|th)?\b",
    re.IGNORECASE,
)

# Spelled-out ordinals/cardinals: "patient two", "number three",
# "patient the fourth". STT often transcribes small numbers as words,
# so the literal regex above misses them and the surrounding extraction
# falls through to treating the entire phrase as a patient name (bug
# observed on 2026-04-21: "okay can you tell me more about patient
# number two" → "I don't have detail records for okay can you tell
# me more patient number two this week.").
_WORD_NUMBERS: dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "eleventh": 11, "twelfth": 12,
}
_ID_WORD_PREFIXED_RE = re.compile(
    r"\b(?:patient|number|no\.?|#)\s+(?:the\s+)?"
    r"(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"eleventh|twelfth)\b",
    re.IGNORECASE,
)
# Whole-reply word number: "two", "first", "the second", "the second."
# Standalone replies are common when the user just echoes a number — keep
# this strict (full-match anchor) so it doesn't steal from name-based replies
# like "Jeremy" or "tell me about the second patient" (the prefixed regex
# above handles those).
_ID_PURE_WORD_RE = re.compile(
    r"^\s*(?:the\s+)?"
    r"(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"eleventh|twelfth)"
    r"\s*\.?\s*$",
    re.IGNORECASE,
)


def _extract_selection_id(prompt: str) -> int | None:
    """Pick an integer out of a reply ONLY when it's clearly a selection.

    Just a bare digit string, one with an explicit 'patient/number/#'
    prefix, or a spelled-out cardinal/ordinal following that prefix.
    Prevents 'room 3' or 'April 2nd' from silently selecting patient 3/2.
    """
    stripped = (prompt or "").strip()
    m = _ID_PURE_RE.match(stripped)
    if m:
        return int(m.group(1))
    m = _ID_PURE_WORD_RE.match(stripped)
    if m:
        return _WORD_NUMBERS.get(m.group(1).lower())
    m = _ID_PREFIXED_RE.search(stripped)
    if m:
        return int(m.group(1))
    m = _ID_WORD_PREFIXED_RE.search(stripped)
    if m:
        return _WORD_NUMBERS.get(m.group(1).lower())
    return None


def _resume_patient_selection(prompt: str, pending_data: dict) -> dict | None:
    """Reply to 'Is there a specific patient...?' — accept number or name."""
    patient_list = pending_data.get("patient_list") or []
    if not patient_list:
        # FIFO strips patient_list from pending_action.data for privacy
        # classes. Fall back to the in-process session cache before giving up.
        try:
            from jane_web.session_context import get_current_session_id
            patient_list = _selection_cache_get(get_current_session_id()) or []
        except Exception:
            patient_list = []
        if not patient_list:
            return {"abandon_pending": True}
    p = (prompt or "").strip()
    if not p or _DECLINE_RE.match(p):
        return {"abandon_pending": True}

    # If the reply mentions a weekday, the user is switching topic back to
    # schedules for another day — let the main handle() logic re-route
    # instead of treating "Tuesday" as a patient name.
    if _DAY_RE.search(p):
        return {"abandon_pending": True}

    # Numeric selection. Passes the full prompt through to _patient_detail
    # so "health concerns for patient 2" still routes to the right field.
    n = _extract_selection_id(p)
    if n is not None:
        if 1 <= n <= len(patient_list):
            entry = patient_list[n - 1]
            return _patient_detail(
                p.lower(), entry["name"],
                appointment_time=entry.get("db_time"),
            )
        return {
            "text": (
                f"I only see {len(patient_list)} patient{'s' if len(patient_list) != 1 else ''} "
                f"in the list. Which patient ID did you mean?"
            )
        }

    # Strip detail keywords before extracting a name, so "recommendations for
    # Sally" yields "Sally" not "Recommendations Sally".
    cleaned = _DETAIL_RE.sub(" ", prompt)
    name_candidate = _extract_name_from_reply(cleaned)
    if name_candidate:
        lc = name_candidate.lower()
        hits = [e for e in patient_list if lc in e["name"].lower()]
        if len(hits) == 1:
            entry = hits[0]
            return _patient_detail(
                p.lower(), entry["name"],
                appointment_time=entry.get("db_time"),
            )
        if len(hits) > 1:
            # Same patient, multiple appointments → treat as one pick by
            # letting the user specify a time or ID.
            unique_names = {e["name"] for e in hits}
            if len(unique_names) == 1:
                times = ", ".join(e["time"] for e in hits)
                return {
                    "text": (
                        f"{hits[0]['name']} has multiple appointments "
                        f"({times}). Which one — tell me the patient ID from the list."
                    )
                }
            names = ", ".join(e["name"] for e in hits[:4])
            return {"text": f"I found multiple patients matching '{name_candidate}': {names}. Which one did you mean?"}
        # Name wasn't in the visible list — defer to _patient_detail to search
        # the full week, using the user's detail keywords if any.
        return _patient_detail(p.lower(), name_candidate)

    return {"abandon_pending": True}


def _resume_count_followup(prompt: str, pending_data: dict) -> dict | None:
    """Reply to 'Would you like to know the names of these patients?'.

    Affirmative (yes/sure/names/etc.) → list names for the stored day, even
      if the reply also names a weekday (treated as emphasis, not a pivot).
    Decline → abandon.
    Weekday alone (no affirmation) → abandon so handle() re-routes.
    Anything else → abandon.
    """
    day = pending_data.get("day_of_week")
    p = (prompt or "").strip()
    if not p or _DECLINE_RE.match(p):
        return {"abandon_pending": True}
    if not day:
        return {"abandon_pending": True}
    if _CONFIRM_RE.search(p):
        return _names_for_day(day)
    if _DAY_RE.search(p):
        # User pivoting to a different day without confirming — let the
        # pipeline re-route the raw prompt through normal classification.
        return {"abandon_pending": True}
    return {"abandon_pending": True}


def _resume_another_patient(prompt: str, pending_data: dict) -> dict | None:
    """Handle a reply to 'Any other patients you would like to know about?'."""
    name_candidate = _extract_name_from_reply(prompt)
    if not name_candidate:
        return {"abandon_pending": True}
    last_type = pending_data.get("last_detail_type") or "Visit Summary"
    # Synthesize a prompt that steers _patient_detail to the same field
    # the user asked about last time.
    type_keyword = {
        "Health Concerns": "health concerns",
        "Recommendations": "recommendations",
        "Visit Summary": "visit summary",
    }.get(last_type, "visit summary")
    synthetic_p = f"{type_keyword} for {name_candidate}".lower()
    return _patient_detail(synthetic_p, name_candidate)


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
            base = (
                f"She has {active} active patient{'s' if active != 1 else ''} on {day_of_week}, "
                f"with {cancelled} cancellation{'s' if cancelled != 1 else ''} ({total} total booked)."
            )
        else:
            base = f"She has {total} patient{'s' if total != 1 else ''} on {day_of_week}."

        if active <= 0:
            # Nothing to list — keep the original day-switch follow-up.
            return {"text": f"{base}{_FOLLOW_UP}"}

        return {
            "text": f"{base} {_COUNT_FOLLOW_UP_QUESTION}",
            "structured": {
                "intent": "clinic schedules info",
                "pending_action": _pending_count_followup(day_of_week),
            },
        }
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
            return {"text": f"No patients scheduled on {day_of_week}."}
        sorted_rows = sorted(rows, key=lambda r: _parse_time(r[1]))
        active = [(r[0], r[1]) for r in sorted_rows if r[2] != "cancelled-out"]
        cancelled = [(r[0], r[1]) for r in sorted_rows if r[2] == "cancelled-out"]
        if not active:
            return {"text": f"No active patients scheduled on {day_of_week}."}

        numbered_lines: list[str] = []
        patient_list: list[dict] = []
        for i, (name, t) in enumerate(active, start=1):
            pretty = _fmt_time(t)
            numbered_lines.append(f"{i}. {pretty} {name}")
            # db_time is kept separately so _patient_detail can pin down the
            # exact appointment when a patient has multiple visits that week.
            patient_list.append({"index": i, "name": name, "time": pretty, "db_time": t})

        printed = "\n".join(numbered_lines)
        if cancelled:
            c_lines = [f"- {_fmt_time(t)} {n} (cancelled)" for n, t in cancelled]
            printed += "\n\n" + "\n".join(c_lines)

        spoken = (
            f"I have listed the patients in the chat for your view. "
            f"{_LIST_FOLLOW_UP_QUESTION}"
        )
        # Stash the list in the local-only session cache so a follow-up
        # ("patient 2", "Melissa") can still resolve even though the FIFO
        # record strips patient_list out of pending_action.data.
        try:
            from jane_web.session_context import get_current_session_id
            _selection_cache_put(get_current_session_id(), patient_list)
        except Exception as _cache_err:
            logger.warning("clinic: failed to cache pending selection: %s", _cache_err)
        return {
            "text": spoken,
            "print": printed,
            "structured": {
                "intent": "clinic schedules info",
                "pending_action": _pending_patient_selection(patient_list),
            },
        }
    finally:
        conn.close()


def _patient_detail(
    p: str,
    patient_name: str | None,
    appointment_time: str | None = None,
) -> dict | None:
    """Return health_concerns / recommendations / visit_summary for a named patient.

    These fields are too long to speak — response uses spoken + text blocks.
    When `appointment_time` is provided (DB format like '8:00a'), the query
    pins down that exact slot so a patient with multiple appointments this
    week resolves to a single row instead of an ambiguity prompt.
    """
    conn = _db_conn()
    if not conn:
        return None
    try:
        week_start = _current_week_start()
        if patient_name and appointment_time:
            norm = patient_name.lower()
            rows = conn.execute(
                "SELECT patient_name, health_concerns, recommendations, visit_summary "
                "FROM appointments WHERE week_start=? AND LOWER(patient_name) LIKE ? "
                "AND start_time=?",
                (week_start, f"%{norm}%", appointment_time),
            ).fetchall()
        elif patient_name:
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
            # Same patient across multiple appointments is one person — pick
            # the first row so details still land, instead of stalling.
            if len({r[0] for r in rows}) == 1:
                rows = rows[:1]
            else:
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

        spoken = (
            f"That's too long to speak — I've printed {name}'s {field_label} on screen. "
            f"{_PATIENT_FOLLOW_UP_QUESTION}"
        )
        return {
            "text": spoken,
            "print": f"**{name} — {field_label}**\n\n{value}",
            "structured": {
                "intent": "clinic schedules info",
                "pending_action": _pending_patient_followup(field_label, name),
            },
        }
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
