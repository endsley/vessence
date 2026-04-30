"""clinic_schedules_info Stage 2 handler.

Architecture: handler is a CONTEXT PROVIDER, not a reply writer. Stage 1
(v3 classifier) extracts the loader + slot params in its single qwen call;
this handler runs ONE small SQL query keyed by `params["loader"]`, hands a
tiny fact slice to the Stage 2 LLM, and lets it phrase the reply.

There is NO Python-side intent detection, NO regex routing of which slice
to load. Stage 1 already decided. The handler is mechanical.

Loaders (selected by params["loader"]):
  - today_overview  → today's active count, cancellations, next patient
  - day             → a specific weekday's active patients (params["day"])
  - cancellations   → cancellations for a specific day or today
  - next_patient    → next not-yet-seen patient today
  - patient_detail  → a single patient's clinical detail (by name or index)
  - weekly          → per-day counts for the whole week

If `params` is missing or `loader` is unknown, fall back to today_overview.

Privacy: privacy="local_only" — patient PII never leaves this process.
qwen runs locally via Ollama; structured context never crosses a process
boundary.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

from jane_web.jane_v2.models import (
    LOCAL_LLM as MODEL,
    LOCAL_LLM_NUM_CTX,
    LOCAL_LLM_TIMEOUT,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_URL,
)

logger = logging.getLogger(__name__)

DB_PATH = Path(os.environ.get("VESSENCE_DATA_HOME", "/home/chieh/ambient/vessence-data")) / "schedule.db"

_WEEK_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_LATE_BUFFER_MINUTES = 15

_VALID_LOADERS = {
    "today_overview", "day", "cancellations",
    "next_patient", "patient_detail", "weekly",
}


def _expires_at(minutes: int = 2) -> str:
    return (_dt.datetime.utcnow() + _dt.timedelta(minutes=minutes)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _parse_time(t: str) -> datetime:
    t = (t or "").strip().lower().replace("a", " AM").replace("p", " PM")
    try:
        return datetime.strptime(t, "%I:%M %p")
    except ValueError:
        return datetime.min


def _fmt_time(t: str) -> str:
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


def _normalize_day(day: str | None) -> str | None:
    """Map 'today'/'tomorrow'/weekday names to a canonical weekday name."""
    if not day:
        return None
    d = day.strip().lower()
    if d == "today":
        return datetime.now().strftime("%A")
    if d == "tomorrow":
        return (datetime.now() + timedelta(days=1)).strftime("%A")
    for wd in _WEEK_DAYS:
        if d == wd.lower():
            return wd
    return None


def _now_meta() -> dict:
    now = datetime.now()
    return {
        "today": now.strftime("%A"),
        "current_time": now.strftime("%I:%M %p").lstrip("0"),
    }


# ─── Per-loader fact builders ───────────────────────────────────────────

def _fetch_day_rows(week_start: str, day: str) -> list[dict]:
    """All rows for a given weekday in the current week, sorted by time."""
    conn = _db_conn()
    if not conn:
        return []
    try:
        rows = conn.execute(
            "SELECT patient_name, start_time, status, "
            "health_concerns, recommendations, visit_summary "
            "FROM appointments WHERE week_start=? AND day_of_week=?",
            (week_start, day),
        ).fetchall()
    finally:
        conn.close()
    parsed = [
        {
            "name": r[0],
            "time": _fmt_time(r[1]),
            "db_time": r[1],
            "status": r[2],
            "health_concerns": r[3] or None,
            "recommendations": r[4] or None,
            "visit_summary": r[5] or None,
        }
        for r in rows
    ]
    parsed.sort(key=lambda e: _parse_time(e["db_time"]))
    return parsed


def _split_active_cancelled(rows: list[dict]) -> tuple[list[dict], list[dict]]:
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


def _facts_today_overview(week_start: str) -> dict:
    meta = _now_meta()
    rows = _fetch_day_rows(week_start, meta["today"])
    active, cancelled = _split_active_cancelled(rows)
    return {
        **meta,
        "loader": "today_overview",
        "active_count": len(active),
        "active_patients": [{"index": p["index"], "name": p["name"], "time": p["time"]} for p in active],
        "cancelled": cancelled,
        "next_patient": _compute_next_patient(active),
    }


def _facts_day(week_start: str, day: str | None) -> dict:
    meta = _now_meta()
    target = _normalize_day(day) or meta["today"]
    rows = _fetch_day_rows(week_start, target)
    active, cancelled = _split_active_cancelled(rows)
    return {
        **meta,
        "loader": "day",
        "day": target,
        "active_count": len(active),
        "active_patients": [{"index": p["index"], "name": p["name"], "time": p["time"]} for p in active],
        "cancelled": cancelled,
    }


def _facts_cancellations(week_start: str, day: str | None) -> dict:
    meta = _now_meta()
    target = _normalize_day(day) or meta["today"]
    rows = _fetch_day_rows(week_start, target)
    _, cancelled = _split_active_cancelled(rows)
    return {
        **meta,
        "loader": "cancellations",
        "day": target,
        "cancelled": cancelled,
        "cancelled_count": len(cancelled),
    }


def _compute_next_patient(active: list[dict]) -> dict | None:
    now = datetime.now()
    cutoff = now - timedelta(minutes=_LATE_BUFFER_MINUTES)
    today_date = now.date()
    upcoming = []
    for p in active:
        parsed = _parse_time(p["time"])
        if parsed == datetime.min:
            continue
        appt_dt = datetime.combine(today_date, parsed.time())
        if appt_dt >= cutoff:
            upcoming.append((appt_dt, p))
    upcoming.sort(key=lambda r: r[0])
    if not upcoming:
        return None
    dt, p = upcoming[0]
    return {
        "name": p["name"],
        "time": p["time"],
        "minutes_from_now": int((dt - now).total_seconds() // 60),
    }


def _facts_next_patient(week_start: str) -> dict:
    meta = _now_meta()
    rows = _fetch_day_rows(week_start, meta["today"])
    active, _ = _split_active_cancelled(rows)
    return {
        **meta,
        "loader": "next_patient",
        "next_patient": _compute_next_patient(active),
        "remaining_today": [
            {"index": p["index"], "name": p["name"], "time": p["time"]}
            for p in active
        ],
    }


def _find_patient_in_week(
    week_start: str, name: str, day: str | None = None
) -> dict | None:
    """Search the requested day first, else every day this week, for a name match."""
    needle = name.strip().lower()
    if not needle:
        return None
    target_day = _normalize_day(day)
    search_days = [target_day] if target_day else list(_WEEK_DAYS)
    for d in search_days:
        for entry in _fetch_day_rows(week_start, d):
            if needle in (entry["name"] or "").lower():
                return {**entry, "day": d}
    return None


def _facts_patient_detail(
    week_start: str,
    name: str | None,
    index: int | None,
    day: str | None = None,
) -> dict:
    meta = _now_meta()
    out = {**meta, "loader": "patient_detail"}
    target_day = _normalize_day(day) or meta["today"]

    if name:
        match = _find_patient_in_week(week_start, name, day=target_day)
        if match:
            out["patient"] = {
                "name": match["name"],
                "day": match["day"],
                "time": match["time"],
                "status": match["status"],
                "health_concerns": match["health_concerns"],
                "recommendations": match["recommendations"],
                "visit_summary": match["visit_summary"],
            }
        else:
            out["patient"] = None
            out["lookup_name"] = name
        return out

    if index is not None:
        rows = _fetch_day_rows(week_start, target_day)
        active, _ = _split_active_cancelled(rows)
        if 1 <= index <= len(active):
            p = active[index - 1]
            out["patient"] = {
                "name": p["name"],
                "day": target_day,
                "time": p["time"],
                "index": p["index"],
                "health_concerns": p["health_concerns"],
                "recommendations": p["recommendations"],
                "visit_summary": p["visit_summary"],
            }
        else:
            out["patient"] = None
            out["lookup_index"] = index
            out["active_day_count"] = len(active)
            out["day"] = target_day
        return out

    # Neither name nor index — return the requested day's roster so the LLM can ask.
    rows = _fetch_day_rows(week_start, target_day)
    active, _ = _split_active_cancelled(rows)
    out["patient"] = None
    out["day"] = target_day
    out["active_today"] = [
        {"index": p["index"], "name": p["name"], "time": p["time"]} for p in active
    ]
    return out


def _normalize_params(params: dict | None) -> dict:
    """Repair common classifier extraction mistakes before loading facts.

    Ordinal or named patient references are more specific than generic
    schedule loaders, so they must resolve to patient_detail even if qwen
    emitted next_patient/day/today_overview.
    """
    normalized = dict(params or {})
    loader = normalized.get("loader")
    if loader not in _VALID_LOADERS:
        loader = "today_overview"
    if normalized.get("patient_name") or normalized.get("patient_index") is not None:
        loader = "patient_detail"
    normalized["loader"] = loader
    return normalized


def _facts_weekly(week_start: str) -> dict:
    meta = _now_meta()
    counts = []
    for d in _WEEK_DAYS:
        rows = _fetch_day_rows(week_start, d)
        active, cancelled = _split_active_cancelled(rows)
        counts.append({
            "day": d,
            "active": len(active),
            "cancelled": len(cancelled),
        })
    return {
        **meta,
        "loader": "weekly",
        "week_start": week_start,
        "per_day_counts": counts,
    }


def _build_facts(params: dict) -> dict:
    """Dispatch on params['loader'] to one focused fact builder."""
    params = _normalize_params(params)
    loader = params.get("loader")

    week_start = _current_week_start()
    if not week_start:
        return {**_now_meta(), "loader": loader, "error": "schedule_db_unavailable"}

    if loader == "today_overview":
        return _facts_today_overview(week_start)
    if loader == "day":
        return _facts_day(week_start, params.get("day"))
    if loader == "cancellations":
        return _facts_cancellations(week_start, params.get("day"))
    if loader == "next_patient":
        return _facts_next_patient(week_start)
    if loader == "patient_detail":
        return _facts_patient_detail(
            week_start,
            params.get("patient_name"),
            params.get("patient_index"),
            params.get("day"),
        )
    if loader == "weekly":
        return _facts_weekly(week_start)
    return _facts_today_overview(week_start)


# ─── Pending-action markers (routing only — no question text needed) ────

def _pending(awaiting: str, **data) -> dict:
    payload = {"awaiting": awaiting}
    payload.update(data)
    return {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "clinic schedules info",
        "status": "awaiting_user",
        "awaiting": awaiting,
        "data": payload,
        "question": f"(awaiting:{awaiting})",
        "expires_at": _expires_at(),
    }


# ─── Stage 2 LLM call ────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are Jane, a personal AI assistant. You're answering \
questions about Chieh's wife Kathia's acupuncture clinic schedule.

ABSOLUTE RULES:
1. THE FACTS ARE AUTHORITATIVE. Never invent patients, times, days, \
cancellations, or events. If something is not in `facts`, do not mention \
it. The week shown is the only week you know about.
2. Address Chieh directly. Speak naturally and conversationally.
3. Output spoken text only. No <spoken> tags. No [[...]] markers. No \
markdown code blocks.

THE FACTS:
- `facts.loader` tells you which slice of the schedule was loaded. The \
shape of `facts` reflects that loader — answer from the fields present.
- `facts.today` is the current weekday. `facts.current_time` is the wall clock.
- `active_patients` entries carry `index`, `name`, `time`. `patient` (singular) \
includes clinical detail (`health_concerns`, `recommendations`, `visit_summary`).
- `cancelled` entries carry `name` and `time` only.
- `next_patient` is the next not-yet-seen patient today, or null.

ANSWERING:
- For lists of patients: order by time, include the time next to each name. \
Use numbers (1., 2., 3.) when there are 3+ patients.
- For counts: state the number; offer to list names if helpful.
- For cancellations: name the cancelled patients with times. If `cancelled` \
is empty, say so plainly. Do NOT pivot to active patients.
- For weekly overview: summarize per_day_counts; highlight the busiest day. \
Offer to drill into one.
- For patient detail: quote the relevant clinical field VERBATIM \
(visit_summary by default; health_concerns or recommendations if those words \
were used).
- For next patient: use `facts.next_patient`. If null, say there are no more \
patients today.
- If `pending_state` is present, the user is replying to a question Jane \
asked previously — use it to interpret short replies.
- If `facts.patient` is null and `lookup_name` or `lookup_index` is set, \
say honestly that you couldn't find that patient.
- If `facts.error` is "schedule_db_unavailable", say the schedule data isn't \
available right now.

LENGTH:
- 1-2 sentences for counts, single-fact answers, and acknowledgments.
- A list is fine when explicitly asked for names — keep each line short.
- Patient detail can be longer because the clinical value is quoted."""


async def _phrase_reply(structured_context: dict, conversation_context: str = "") -> str:
    """Call qwen with the focused facts and return the phrased reply."""
    ctx_block = ""
    if conversation_context and conversation_context.strip():
        ctx_block = f"Recent conversation:\n{conversation_context.strip()}\n\n"

    user_said = structured_context.get("user_said", "")
    facts = structured_context.get("facts", {})
    pending_state = structured_context.get("pending_state")

    parts = [
        _SYSTEM_PROMPT,
        "",
        ctx_block + f"The user just said: \"{user_said}\"",
        "",
        f"Facts (JSON):\n{json.dumps(facts, indent=2, default=str)}",
    ]
    if pending_state:
        parts.append(
            f"\nPending state from prior turn:\n{json.dumps(pending_state, indent=2, default=str)}"
        )
    parts.append("\nReply (spoken text only):")

    full_prompt = "\n".join(parts)

    body = {
        "model": MODEL,
        "prompt": full_prompt,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 600,
            "num_ctx": LOCAL_LLM_NUM_CTX,
        },
        "keep_alive": OLLAMA_KEEP_ALIVE,
    }
    try:
        async with httpx.AsyncClient(timeout=LOCAL_LLM_TIMEOUT) as client:
            r = await client.post(OLLAMA_URL, json=body)
            r.raise_for_status()
            try:
                from jane_web.jane_v2.models import record_ollama_activity
                record_ollama_activity()
            except Exception:
                pass
            text = (r.json().get("response") or "").strip()
            return text or "I couldn't put together a reply just now."
    except Exception as e:
        logger.warning("clinic: stage 2 LLM call failed: %s", e)
        return "I'm having trouble reaching the schedule right now."


# ─── Main entrypoint ────────────────────────────────────────────────────

async def handle(
    prompt: str,
    pending: dict | None = None,
    context: str = "",
    params: dict | None = None,
) -> dict | None:
    """Run one loader keyed by params['loader'], hand facts to Stage 2 LLM.

    `params` arrives from the v3 classifier's single qwen call (loader +
    optional day / patient_name / patient_index). Missing or unknown
    loader falls back to today_overview.
    """
    facts = _build_facts(params or {})
    logger.info(
        "clinic: loader=%s day=%s name=%s idx=%s",
        facts.get("loader"),
        (params or {}).get("day"),
        (params or {}).get("patient_name"),
        (params or {}).get("patient_index"),
    )

    structured = {
        "intent": "clinic_schedules_info",
        "user_said": prompt,
        "pending_state": pending or None,
        "facts": facts,
    }

    reply = await _phrase_reply(structured, context)

    out: dict = {
        "text": reply,
        "structured": {
            "intent": "clinic schedules info",
            "pending_action": _pending("clinic_followup"),
        },
    }
    return out
