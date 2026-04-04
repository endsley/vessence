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
        """)
