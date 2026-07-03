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

import logging
import os
import sqlite3
from pathlib import Path

from jane_web.jane_v2.ollama_client import post_local_llm_response as _post_local_llm_response

from .schedule_helpers import (
    WEEK_DAYS as _WEEK_DAYS,
    active_patient_briefs as _active_patient_briefs,
    compute_next_patient as _compute_next_patient,
    fmt_time as _fmt_time,
    normalize_day as _normalize_day,
    normalize_params as _normalize_params,
    now_meta as _now_meta,
    parse_time as _parse_time,
    split_active_cancelled as _split_active_cancelled,
)
from .prompting import (
    SYSTEM_PROMPT as _SYSTEM_PROMPT,
    conversation_context_block as _conversation_context_block,
    phrase_prompt as _phrase_prompt,
    phrase_request_payload as _phrase_request_payload,
)
from .responses import (
    build_clinic_pending as _pending,
    build_clinic_response as _build_clinic_response,
)

logger = logging.getLogger(__name__)

DB_PATH = Path(os.environ.get("VESSENCE_DATA_HOME", "/home/chieh/ambient/vessence-data")) / "schedule.db"


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


def _facts_today_overview(week_start: str) -> dict:
    meta = _now_meta()
    rows = _fetch_day_rows(week_start, meta["today"])
    active, cancelled = _split_active_cancelled(rows)
    return {
        **meta,
        "loader": "today_overview",
        "active_count": len(active),
        "active_patients": _active_patient_briefs(active),
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
        "active_patients": _active_patient_briefs(active),
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


def _facts_next_patient(week_start: str) -> dict:
    meta = _now_meta()
    rows = _fetch_day_rows(week_start, meta["today"])
    active, _ = _split_active_cancelled(rows)
    return {
        **meta,
        "loader": "next_patient",
        "next_patient": _compute_next_patient(active),
        "remaining_today": _active_patient_briefs(active),
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
    out["active_today"] = _active_patient_briefs(active)
    return out


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


# ─── Stage 2 LLM call ────────────────────────────────────────────────────

async def _phrase_reply(structured_context: dict, conversation_context: str = "") -> str:
    """Call qwen with the focused facts and return the phrased reply."""
    def payload_builder(_prompt_text: str, *, model: str, num_ctx: int, keep_alive: str | int) -> dict:
        return _phrase_request_payload(
            structured_context,
            conversation_context,
            model=model,
            num_ctx=num_ctx,
            keep_alive=keep_alive,
        )

    try:
        text = await _post_local_llm_response("", payload_builder)
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

    # _build_clinic_response returns the documented {"text": ..., "structured": ...} shape.
    return _build_clinic_response(reply)
