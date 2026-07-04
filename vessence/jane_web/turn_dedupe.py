"""Persistent turn-level idempotency / dedupe for Android streaming chat.

Android's `ChatRepository.streamChat()` attaches an `X-Request-ID` UUID to
every user turn. On a retry (same turn_id within TTL) the server must not
re-dispatch the turn to the LLM — duplicate dispatch would double-send
SMS, double-book calendar events, etc.

Storage: a `turn_dedupe` table in the canonical conversation ledger at
`$VAULT_HOME/conversation_history_ledger.db` (same SQLite file used for
`_log_to_ledger`). In-memory caches are NOT safe — the primary trigger
for retries is a server restart, which would wipe them.

State machine per turn_id:
  PENDING   — first request in flight. A retry during this window
              attaches to the same in-memory stream broadcaster.
  COMPLETED — first request finished. A retry replays the cached
              NDJSON body as a synthetic stream.
  FAILED    — first request errored. A retry is allowed to re-dispatch.

Nightly janitor prunes rows older than 24h (see janitor_system.py).
"""
from __future__ import annotations

import datetime
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

VAULT_HOME = os.environ.get(
    "VAULT_HOME",
    os.path.join(os.environ.get("AMBIENT_BASE", os.path.expanduser("~/ambient")), "vault"),
)
LEDGER_DB = Path(VAULT_HOME) / "conversation_history_ledger.db"

# Dedupe window in seconds. 300s covers a slow LLM turn + the client's
# 30s "Jane is restarting" wait + a couple of retries.
DEDUPE_TTL_SECONDS = 300

# How long to hold a join-in-flight request waiting for a PENDING row to
# flip to COMPLETED before giving up and replaying.
JOIN_WAIT_SECONDS = 120

_db_lock = threading.Lock()


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def _age_seconds_since(created_at: str, *, now: datetime.datetime | None = None) -> float:
    dt = datetime.datetime.fromisoformat(created_at.replace(" ", "T"))
    return ((now or _utcnow()) - dt).total_seconds()


def _existing_row_blocks_begin(
    status: str,
    created_at: str,
    *,
    now: datetime.datetime | None = None,
    ttl_seconds: int = DEDUPE_TTL_SECONDS,
) -> bool:
    try:
        age = _age_seconds_since(created_at, now=now)
    except Exception:
        age = 0.0
    return age <= ttl_seconds and status in ("pending", "completed")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(LEDGER_DB))
    c.row_factory = sqlite3.Row
    return c


def init_schema() -> None:
    """Create the turn_dedupe table + index if missing. Idempotent.

    Called from jane-web startup so the table is always there by the time
    the first request arrives.
    """
    with _db_lock, _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS turn_dedupe (
                turn_id       TEXT PRIMARY KEY,
                session_id    TEXT,
                status        TEXT CHECK(status IN ('pending','completed','failed')),
                response_json TEXT,
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at  DATETIME
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_turn_dedupe_created ON turn_dedupe(created_at)")
        c.commit()


@dataclass
class DedupeRow:
    turn_id: str
    session_id: str
    status: str
    response_json: Optional[str]
    created_at: str
    completed_at: Optional[str]

    @property
    def age_seconds(self) -> float:
        """Best-effort — SQLite returns the timestamp as a string."""
        try:
            return _age_seconds_since(self.created_at)
        except Exception:
            return 0.0


def _get_row(turn_id: str) -> Optional[DedupeRow]:
    with _db_lock, _conn() as c:
        row = c.execute(
            "SELECT turn_id, session_id, status, response_json, created_at, completed_at "
            "FROM turn_dedupe WHERE turn_id = ?",
            (turn_id,),
        ).fetchone()
        if row is None:
            return None
        return DedupeRow(
            turn_id=row["turn_id"],
            session_id=row["session_id"],
            status=row["status"],
            response_json=row["response_json"],
            created_at=str(row["created_at"]),
            completed_at=str(row["completed_at"]) if row["completed_at"] else None,
        )


def lookup(turn_id: str) -> Optional[DedupeRow]:
    """Return a row if it exists AND is within the dedupe window.

    Rows older than DEDUPE_TTL_SECONDS are treated as absent (and will be
    overwritten on the next `try_begin`). Returning None from here means
    the caller should dispatch to the brain normally.
    """
    row = _get_row(turn_id)
    if row is None:
        return None
    if row.age_seconds > DEDUPE_TTL_SECONDS:
        return None
    return row


def try_begin(turn_id: str, session_id: str) -> bool:
    """Mark a turn as PENDING. Returns True on success (caller owns
    dispatch). Returns False if the row already exists and is still within
    the window — caller should `lookup()` to see what to do.

    On successful begin, a FAILED row inside the window is OVERWRITTEN
    (retry of a previously-failed turn is permitted).
    """
    with _db_lock, _conn() as c:
        existing = c.execute(
            "SELECT status, created_at FROM turn_dedupe WHERE turn_id = ?",
            (turn_id,),
        ).fetchone()
        if existing:
            status = existing["status"]
            if _existing_row_blocks_begin(status, str(existing["created_at"])):
                return False
            # status=failed OR aged out → overwrite.
            c.execute("DELETE FROM turn_dedupe WHERE turn_id = ?", (turn_id,))
        c.execute(
            "INSERT INTO turn_dedupe (turn_id, session_id, status) VALUES (?, ?, 'pending')",
            (turn_id, session_id),
        )
        c.commit()
        return True


def mark_completed(turn_id: str, response_json: str) -> None:
    """Flip PENDING → COMPLETED with the cached NDJSON body attached."""
    with _db_lock, _conn() as c:
        c.execute(
            "UPDATE turn_dedupe SET status='completed', response_json=?, "
            "completed_at=CURRENT_TIMESTAMP WHERE turn_id = ?",
            (response_json, turn_id),
        )
        c.commit()


def mark_failed(turn_id: str) -> None:
    """Flip PENDING → FAILED so a retry is allowed to re-dispatch.

    Called when the brain errored without producing a usable response.
    FAILED rows are overwriten on the next `try_begin` within the window.
    """
    with _db_lock, _conn() as c:
        c.execute(
            "UPDATE turn_dedupe SET status='failed', completed_at=CURRENT_TIMESTAMP "
            "WHERE turn_id = ?",
            (turn_id,),
        )
        c.commit()


def wait_for_completion(turn_id: str, timeout_s: float = JOIN_WAIT_SECONDS) -> Optional[str]:
    """Poll the row until it transitions out of PENDING, or timeout.

    Returns the `response_json` on COMPLETED, None on FAILED or timeout.
    Used when a retry lands while the original turn is still in flight.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        row = _get_row(turn_id)
        if row is None or row.status == "failed":
            return None
        if row.status == "completed":
            return row.response_json
        time.sleep(0.5)
    return None


def prune_old(older_than_seconds: int = 24 * 60 * 60) -> int:
    """Delete rows older than N seconds. Returns the number of rows deleted.

    Called from the nightly janitor.
    """
    with _db_lock, _conn() as c:
        cutoff = f"-{older_than_seconds} seconds"
        cur = c.execute(
            "DELETE FROM turn_dedupe WHERE created_at < datetime('now', ?)",
            (cutoff,),
        )
        c.commit()
        return cur.rowcount
