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


# Default idle window after which the FIFO is treated as a stale
# conversation and wiped on the next turn. 30 s matches the user's
# expectation (2026-04-26): if the user pauses longer than this, the
# next thing they say is almost always a new topic, not a follow-up,
# so prior FIFO context becomes pollution rather than help.
IDLE_FLUSH_SECONDS = 30


def maybe_idle_flush(session_id: str, idle_seconds: int = IDLE_FLUSH_SECONDS) -> bool:
    """Wipe the FIFO if the most recent entry is older than `idle_seconds`.

    Called at the start of each new request so a long silence between
    turns is treated as an implicit conversation_end (the user wandered
    off, came back with a new topic). This is the auto-equivalent of the
    explicit FIFO clear at jane_v2/pipeline._persist_turn_to_fifo (which
    only fires on conversation_end=True from end_conversation handler).

    Skipped (returns False) when an active pending_action is awaiting the
    user's response — in confirmation flows ("send it?" → 35s pause →
    "yes") the user's pause is part of the flow, not a topic pivot, and
    flushing would drop the pending state mid-confirmation.

    Returns True if a flush actually happened.
    """
    if not session_id:
        return False
    try:
        # Compute age at the SQLite layer so we don't have to guess at
        # the on-disk timestamp format. `julianday('now')` is UTC; the
        # stored `created_at` defaults to CURRENT_TIMESTAMP which is
        # also UTC, so the subtraction yields the true wall-clock age
        # in days. Multiply by 86400 to get seconds. This avoids the
        # strptime fragility that broke when rows used `T`/`Z` ISO
        # form vs. SQLite's default `YYYY-MM-DD HH:MM:SS`.
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT
                    MAX(created_at) AS last_at,
                    COUNT(*) AS n,
                    (julianday('now') - julianday(MAX(created_at))) * 86400.0 AS age_s
                FROM recent_turns
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
            if not row or not row["n"] or not row["last_at"]:
                return False
            last_at_str = row["last_at"]
            age = row["age_s"]
            if age is None or age <= idle_seconds:
                return False

        # Late-bound pending-action check so a stale confirmation still
        # gets cleaned up (long-running pendings expire on their own via
        # _pending_is_active's expires_at check).
        try:
            state = get_active_state(session_id)
            pending = state.get("pending_action") if state else None
            if pending and _pending_is_active(pending):
                logger.info(
                    "recent_turns.maybe_idle_flush: session=%s age=%.1fs > %ds but pending_action active — skipped",
                    session_id[:12], age, idle_seconds,
                )
                return False
        except Exception:
            pass

        # Scope DELETE to rows existing at the time of the staleness
        # check (created_at <= last_at_str). Without this guard, a turn
        # written by a concurrent request between the MAX(created_at)
        # read above and this DELETE would be wiped along with the
        # stale rows. The structured persist path runs in
        # asyncio.to_thread (jane_v2/pipeline._persist_turns_async),
        # which is exactly the kind of overlap that triggers this.
        with get_db() as conn:
            conn.execute(
                "DELETE FROM recent_turns WHERE session_id = ? AND created_at <= ?",
                (session_id, last_at_str),
            )
        logger.info(
            "recent_turns.maybe_idle_flush: session=%s last_turn_age=%.1fs > %ds — wiped FIFO",
            session_id[:12], age, idle_seconds,
        )
        return True
    except Exception as e:
        logger.warning(
            "recent_turns.maybe_idle_flush failed (session=%s): %s",
            session_id[:12] if session_id else "?", e,
        )
        return False


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
    # Pending types that have been explicitly cancelled (topic pivot, etc).
    # Needed for type-only pendings like STAGE3_FOLLOWUP that have no
    # handler_class to suppress via resolved_handlers.
    cancelled_types: set = set()
    for rec in reversed(records):  # newest first
        pa = rec.get("pending_action")
        if pa and isinstance(pa, dict):
            hc = pa.get("handler_class", "")
            ptype = pa.get("type", "")
            status = pa.get("status", "")
            if status in ("resolved", "cancelled"):
                resolved_handlers.add(hc)
                if ptype:
                    cancelled_types.add(ptype)
            elif (_pending_is_active(pa)
                  and out["pending_action"] is None
                  and hc not in resolved_handlers
                  and ptype not in cancelled_types):
                out["pending_action"] = pa
                out["pending_turn_id"] = rec.get("turn_id")
        if not out["last_intent"] and rec.get("intent"):
            out["last_intent"] = rec.get("intent")
        if not out["last_entities"] and rec.get("entities"):
            out["last_entities"] = rec.get("entities")
    out["recent_summaries"] = [r.get("summary", "") for r in records if r.get("summary")]
    return out
