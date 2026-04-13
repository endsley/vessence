"""recent_turns.py — per-session FIFO of compact turn summaries.

Unlike the ChromaDB thematic memory (which indexes turns for semantic
similarity search), this is a plain ordered list per session that
answers one question cheaply: "give me the last N turns."

Used by v2's ack generator and classifier so they can show context to
gemma4 without going through a vector search — just a ~1ms SQLite read.

Design:
  - One row per turn, inserted after the turn completes.
  - Each session is capped at DEFAULT_MAX_TURNS entries (default 10).
    Older entries are deleted on insert — true FIFO eviction.
  - `summary` is whatever the caller chooses. Keeping it to a
    truncated "user: … / jane: …" string (no LLM) makes this path
    free and fast; swapping in a real LLM-produced summary later is
    a matter of changing the caller, not this module.

API:
    add(session_id, summary, max_keep=10) -> None
    get_recent(session_id, n=10)          -> list[str]  # oldest -> newest
    clear(session_id)                     -> None
    count(session_id)                     -> int
"""

from __future__ import annotations

import logging
from .database import get_db

logger = logging.getLogger(__name__)

DEFAULT_MAX_TURNS = 10


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
