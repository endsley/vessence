"""recent_turns.py — per-session FIFO of compact turn summaries.

Unlike the ChromaDB thematic memory (which indexes turns for semantic
similarity search), this is a plain ordered list per session that
answers one question cheaply: "give me the last N turns."

Used by v2's ack generator and classifier so they can show context to
the local LLM without going through a vector search — just a ~1ms SQLite read.

Design:
  - One row per turn, inserted after the turn completes.
  - Each session is capped at DEFAULT_MAX_TURNS entries (default 20).
    Older entries are deleted on insert — true FIFO eviction.
  - `summary` is whatever the caller chooses. Keeping it to a
    truncated "user: … / jane: …" string (no LLM) makes this path
    free and fast; swapping in a real LLM-produced summary later is
    a matter of changing the caller, not this module.

API:
    add(session_id, summary, max_keep=20)               -> None
    get_recent(session_id, n=20)                        -> list[str]  # oldest -> newest
    clear(session_id)                                   -> None
    count(session_id)                                   -> int

Structured API (schema_version 1) — used by v2 3-stage pipeline:
    add_structured(session_id, record, max_keep=20)     -> None
    get_recent_structured(session_id, n=20)             -> list[dict]  # oldest -> newest
    get_active_state(session_id)                        -> dict
"""

from __future__ import annotations

import datetime as _dt
import json as _json
import logging
import uuid as _uuid
from .database import get_db

logger = logging.getLogger(__name__)

DEFAULT_MAX_TURNS = 20
STRUCTURED_SCHEMA_VERSION = 1


def add(session_id: str, summary: str, max_keep: int = DEFAULT_MAX_TURNS) -> None:
    """Insert a new turn summary, then trim the oldest rows so the
    session never has more than `max_keep` entries."""
    if not session_id or not summary:
        return
    summary = summary.strip()
    if not summary:
        return
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO recent_turns (session_id, summary) VALUES (?, ?)",
                (session_id, summary),
            )
            # Trim oldest so only the most recent `max_keep` rows survive.
            # Using a subquery that finds the ids to KEEP is more portable
            # than OFFSET/LIMIT for DELETE across SQLite versions.
            conn.execute(
                """
                DELETE FROM recent_turns
                WHERE session_id = ?
                  AND id NOT IN (
                    SELECT id FROM recent_turns
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                  )
                """,
                (session_id, session_id, max_keep),
            )
    except Exception as e:
        logger.warning("recent_turns.add failed (session=%s): %s", session_id[:12], e)


def get_recent(session_id: str, n: int = DEFAULT_MAX_TURNS) -> list[str]:
    """Return up to `n` most recent turn summaries for this session,
    ordered oldest-first so they read naturally as conversation history."""
    if not session_id:
        return []
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT summary
                FROM recent_turns
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, n),
            ).fetchall()
    except Exception as e:
        logger.warning(
            "recent_turns.get_recent failed (session=%s): %s", session_id[:12], e
        )
        return []
    # Reverse so the list reads oldest → newest.
    return [r["summary"] for r in reversed(rows)]


def clear(session_id: str) -> None:
    """Delete all recent-turn entries for a session (e.g. on session end)."""
    if not session_id:
        return
    try:
        with get_db() as conn:
            conn.execute("DELETE FROM recent_turns WHERE session_id = ?", (session_id,))
    except Exception as e:
        logger.warning("recent_turns.clear failed (session=%s): %s", session_id[:12], e)


def count(session_id: str) -> int:
    """Return how many recent-turn entries exist for a session."""
    if not session_id:
        return 0
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM recent_turns WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            return int(row["n"]) if row else 0
    except Exception as e:
        logger.warning("recent_turns.count failed (session=%s): %s", session_id[:12], e)
        return 0


def _format_turn_compact(user_msg: str, assistant_msg: str, max_chars: int = 600) -> str:
    """Collapse a user + assistant turn into a single compact line.

    Used by the default "no LLM" insertion path — the caller can also
    pass in a pre-summarized string if they prefer.
    """
    user = (user_msg or "").strip().replace("\n", " ")
    jane = (assistant_msg or "").strip().replace("\n", " ")
    combined = f"user: {user}\njane: {jane}"
    if len(combined) > max_chars:
        combined = combined[: max_chars - 3] + "..."
    return combined


# ─── Structured FIFO (schema_version 1) ────────────────────────────────────
#
# Records stored as a JSON blob in the `structured` column. The prose
# `summary` is also populated so legacy callers of get_recent() still work.
# Old rows with structured=NULL are returned as minimal dicts.
#
# Record shape:
#   required: schema_version, turn_id, session_id, created_at,
#             user_text, assistant_text, summary, stage, intent
#   optional: confidence, entities, pending_action, tool_results,
#             safety, metadata


def _now_iso() -> str:
    return _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_record(session_id: str, record: dict) -> dict:
    """Fill in defaults / coerce types so record is safe to persist."""
    r = dict(record) if record else {}
    r["schema_version"] = STRUCTURED_SCHEMA_VERSION
    r.setdefault("turn_id", _uuid.uuid4().hex[:16])
    r["session_id"] = session_id
    r.setdefault("created_at", _now_iso())
    r.setdefault("user_text", "")
    r.setdefault("assistant_text", "")
    r.setdefault("stage", "stage2")
    r.setdefault("intent", "")
    if "summary" not in r or not r.get("summary"):
        r["summary"] = _format_turn_compact(r.get("user_text", ""), r.get("assistant_text", ""))
    return r


def add_structured(session_id: str, record: dict, max_keep: int = DEFAULT_MAX_TURNS) -> None:
    """Insert a structured FIFO turn. Populates both `structured` (JSON)
    and `summary` so legacy prose callers keep working."""
    if not session_id or not record:
        return
    try:
        norm = _normalize_record(session_id, record)
        blob = _json.dumps(norm, ensure_ascii=True)
        with get_db() as conn:
            conn.execute(
                "INSERT INTO recent_turns (session_id, summary, structured, schema_version) "
                "VALUES (?, ?, ?, ?)",
                (session_id, norm["summary"], blob, STRUCTURED_SCHEMA_VERSION),
            )
            conn.execute(
                """
                DELETE FROM recent_turns
                WHERE session_id = ?
                  AND id NOT IN (
                    SELECT id FROM recent_turns
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                  )
                """,
                (session_id, session_id, max_keep),
            )
    except Exception as e:
        logger.warning("recent_turns.add_structured failed (session=%s): %s",
                       session_id[:12], e)


def _row_to_record(row) -> dict:
    """Hydrate a DB row into a structured record. Old prose-only rows
    get a minimal synthesized record with just `summary`."""
    blob = row["structured"] if "structured" in row.keys() else None
    if blob:
        try:
            return _json.loads(blob)
        except Exception:
            pass
    # Legacy row — synthesize.
    return {
        "schema_version": 0,
        "summary": row["summary"],
        "stage": "legacy",
        "intent": "",
        "user_text": "",
        "assistant_text": "",
    }


def get_recent_structured(session_id: str, n: int = DEFAULT_MAX_TURNS) -> list[dict]:
    """Return up to `n` most recent structured records, oldest-first."""
    if not session_id:
        return []
    try:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT summary, structured, schema_version
                FROM recent_turns
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, n),
            ).fetchall()
    except Exception as e:
        logger.warning("recent_turns.get_recent_structured failed (session=%s): %s",
                       session_id[:12], e)
        return []
    return [_row_to_record(r) for r in reversed(rows)]


def _pending_is_active(pending: dict) -> bool:
    """True if a pending_action is still open (awaiting user, not expired)."""
    if not pending or not isinstance(pending, dict):
        return False
    if pending.get("status") and pending["status"] not in ("awaiting_user", "open"):
        return False
    exp = pending.get("expires_at")
    if exp:
        try:
            exp_dt = _dt.datetime.strptime(exp, "%Y-%m-%dT%H:%M:%SZ")
            if _dt.datetime.utcnow() > exp_dt:
                return False
        except Exception:
            pass  # malformed expiration → treat as active
    return True


def get_active_state(session_id: str, lookback: int = DEFAULT_MAX_TURNS) -> dict:
    """Compute the current conversation state from recent FIFO records.

    Scans newest → oldest. Returns the newest unresolved pending_action
    (if any), the last known intent, and recent entities/summary.
    """
    out = {
        "pending_action": None,
        "pending_turn_id": None,
        "last_intent": "",
        "last_entities": {},
        "recent_summaries": [],
    }
    if not session_id:
        return out
    records = get_recent_structured(session_id, n=lookback)
    resolved_handlers: set = set()
    for rec in reversed(records):  # newest first
        pa = rec.get("pending_action")
        if pa and isinstance(pa, dict):
            hc = pa.get("handler_class", "")
            status = pa.get("status", "")
            if status in ("resolved", "cancelled"):
                resolved_handlers.add(hc)
            elif (_pending_is_active(pa)
                  and out["pending_action"] is None
                  and hc not in resolved_handlers):
                out["pending_action"] = pa
                out["pending_turn_id"] = rec.get("turn_id")
        if not out["last_intent"] and rec.get("intent"):
            out["last_intent"] = rec.get("intent")
        if not out["last_entities"] and rec.get("entities"):
            out["last_entities"] = rec.get("entities")
    out["recent_summaries"] = [r.get("summary", "") for r in records if r.get("summary")]
    return out
