from __future__ import annotations

import datetime as dt
import secrets
import sqlite3

import pytest


@pytest.fixture()
def vault_db(tmp_path, monkeypatch):
    db_path = tmp_path / "vault_web" / "vault_web.db"

    from vault_web import database

    monkeypatch.setattr(database, "DB_PATH", str(db_path), raising=False)
    database._wal_configured_paths.clear()
    database.init_db()
    return database, db_path


def _future_iso(hours: int = 1) -> str:
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    return (now + dt.timedelta(hours=hours)).isoformat()


def _sqlite_timestamp(seconds_ago: int = 0) -> str:
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    return (now - dt.timedelta(seconds=seconds_ago)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def test_get_db_context_manager_closes_connection_and_sets_busy_timeout(vault_db):
    database, _ = vault_db

    with database.get_db() as conn:
        assert (
            conn.execute("PRAGMA busy_timeout").fetchone()[0]
            == database.SQLITE_BUSY_TIMEOUT_MS
        )
        conn.execute("CREATE TABLE IF NOT EXISTS close_check (id INTEGER)")

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")


def test_validate_session_throttles_last_used_touch(vault_db):
    _, db_path = vault_db

    from vault_web import auth

    session_id = secrets.token_hex(32)
    fp = "session-touch-fp"
    old_last_used = _sqlite_timestamp(seconds_ago=120)

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO sessions
            (id, device_fingerprint, trusted, expires_at, last_used)
        VALUES (?, ?, 1, ?, ?)
        """,
        (session_id, fp, _future_iso(), old_last_used),
    )
    conn.commit()
    conn.close()

    assert auth.validate_session(session_id, fp) is True
    conn = sqlite3.connect(db_path)
    first_touch = conn.execute(
        "SELECT last_used FROM sessions WHERE id=?", (session_id,)
    ).fetchone()[0]
    conn.close()
    assert first_touch != old_last_used

    assert auth.validate_session(session_id, fp) is True
    conn = sqlite3.connect(db_path)
    second_touch = conn.execute(
        "SELECT last_used FROM sessions WHERE id=?", (session_id,)
    ).fetchone()[0]
    conn.close()
    assert second_touch == first_touch


def test_session_last_used_touch_ignores_locked_database(vault_db):
    _, _ = vault_db

    from vault_web import auth

    class LockedConnection:
        def execute(self, *_args, **_kwargs):
            raise sqlite3.OperationalError("database is locked")

    auth._touch_session_last_used(LockedConnection(), "session-id")
