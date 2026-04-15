"""database.py — SQLite setup and helpers for vault_web."""
import sqlite3
import os
from pathlib import Path

DB_PATH = os.environ.get(
    "VAULT_WEB_DB_PATH",
    os.path.join(os.environ.get("VESSENCE_DATA_HOME", os.environ.get("AMBIENT_HOME", str(Path(__file__).resolve().parents[2]))), "vault_web", "vault_web.db"),
)


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT DEFAULT 'user',
                device_fingerprint TEXT,
                trusted BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                last_used DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS trusted_devices (
                id TEXT PRIMARY KEY,
                fingerprint TEXT UNIQUE,
                label TEXT,
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_used DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS otp_codes (
                code TEXT PRIMARY KEY,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                used INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS failed_attempts (
                ip TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0,
                locked_until DATETIME
            );

            CREATE TABLE IF NOT EXISTS share_links (
                id TEXT PRIMARY KEY,
                code TEXT UNIQUE,
                path TEXT,
                created_for TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS playlists (
                id TEXT PRIMARY KEY,
                name TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS playlist_tracks (
                id TEXT PRIMARY KEY,
                playlist_id TEXT REFERENCES playlists(id) ON DELETE CASCADE,
                path TEXT,
                position INTEGER,
                title TEXT
            );

            CREATE TABLE IF NOT EXISTS file_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                changed_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL,
                phone_number TEXT,
                email TEXT,
                is_primary BOOLEAN DEFAULT 0,
                contact_id TEXT,
                synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(display_name, phone_number, email)
            );

            CREATE TABLE IF NOT EXISTS synced_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT NOT NULL,
                body TEXT,
                timestamp_ms INTEGER NOT NULL,
                is_read BOOLEAN DEFAULT 1,
                is_contact BOOLEAN DEFAULT 0,
                msg_type TEXT DEFAULT 'personal',
                synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(sender, timestamp_ms, body)
            );

            -- Relational-name aliases learned over time (e.g. "wife" → Kathia's
            -- number). Survives the full-replace contacts sync because it's a
            -- separate table. Written by the classifier fast-path handler after
            -- Opus resolves an unknown name via memory, or by the add_alias API.
            CREATE TABLE IF NOT EXISTS contact_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alias TEXT NOT NULL,
                phone_number TEXT NOT NULL,
                display_name TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(alias)
            );

            CREATE INDEX IF NOT EXISTS idx_contact_aliases_alias
                ON contact_aliases(alias);

            -- Pending SMS drafts awaiting user confirmation. Only created on
            -- the fallback path when Gemma's coherence gate fails and the
            -- draft-confirm flow kicks in. Auto-expires after 5 minutes.
            CREATE TABLE IF NOT EXISTS sms_drafts (
                draft_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                phone_number TEXT NOT NULL,
                display_name TEXT,
                body TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_sms_drafts_session
                ON sms_drafts(session_id, created_at DESC);

            -- Per-session FIFO of recent turn summaries. Populated by
            -- the background persistence worker after every completed
            -- turn. Used by v2's ack generator / classifier for fast
            -- recency-based context (no similarity search needed).
            -- Capped per session — see vault_web/recent_turns.py.
            -- `structured` (JSON blob) + `schema_version` added for v2
            -- 3-stage pipeline's structured FIFO (job 069). Old rows have
            -- NULL structured + schema_version=0 and still read correctly.
            CREATE TABLE IF NOT EXISTS recent_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                structured TEXT,
                schema_version INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_recent_turns_session_id
                ON recent_turns(session_id, id DESC);
        """)

        # Additive migration for existing DBs that predate the structured columns.
        existing_cols = {row["name"] for row in conn.execute(
            "PRAGMA table_info(recent_turns)"
        ).fetchall()}
        if "structured" not in existing_cols:
            conn.execute("ALTER TABLE recent_turns ADD COLUMN structured TEXT")
        if "schema_version" not in existing_cols:
            conn.execute("ALTER TABLE recent_turns ADD COLUMN schema_version INTEGER DEFAULT 0")
