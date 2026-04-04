"""
Vessence Account Database — SQLite-backed user management.

Stores user accounts, relay tokens, published essences, purchases, and reviews.
"""

import os
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import bcrypt

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = os.getenv(
    "VESSENCE_ACCOUNTS_DB",
    os.path.expanduser("~/ambient/vessence-data/data/vessence_accounts.db"),
)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class User:
    id: str
    email: str
    display_name: str
    password_hash: str
    relay_token: str
    created_at: str
    last_login: Optional[str]
    is_seller: bool
    google_id: Optional[str]

    def to_public_dict(self) -> dict:
        """Return a dict safe for API responses (no password hash)."""
        return {
            "user_id": self.id,
            "email": self.email,
            "display_name": self.display_name,
            "relay_token": self.relay_token,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "is_seller": self.is_seller,
        }


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    relay_token TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    last_login TEXT,
    is_seller BOOLEAN DEFAULT FALSE,
    google_id TEXT
);

CREATE TABLE IF NOT EXISTS essences_published (
    id TEXT PRIMARY KEY,
    seller_id TEXT REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT,
    price REAL DEFAULT 0,
    download_count INTEGER DEFAULT 0,
    rating_avg REAL DEFAULT 0,
    rating_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    manifest_json TEXT
);

CREATE TABLE IF NOT EXISTS purchases (
    id TEXT PRIMARY KEY,
    buyer_id TEXT REFERENCES users(id),
    essence_id TEXT REFERENCES essences_published(id),
    price_paid REAL,
    purchased_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    essence_id TEXT REFERENCES essences_published(id),
    reviewer_id TEXT REFERENCES users(id),
    rating INTEGER CHECK(rating BETWEEN 1 AND 5),
    text TEXT,
    is_fair BOOLEAN,
    refund_eligible BOOLEAN DEFAULT FALSE,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_relay_token ON users(relay_token);
CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);
CREATE INDEX IF NOT EXISTS idx_essences_seller ON essences_published(seller_id);
CREATE INDEX IF NOT EXISTS idx_purchases_buyer ON purchases(buyer_id);
CREATE INDEX IF NOT EXISTS idx_reviews_essence ON reviews(essence_id);
"""

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode and foreign keys enabled."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_relay_token() -> str:
    """Generate a cryptographically secure relay token."""
    return secrets.token_hex(32)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# ---------------------------------------------------------------------------
# Row -> User
# ---------------------------------------------------------------------------

def _row_to_user(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        display_name=row["display_name"],
        password_hash=row["password_hash"],
        relay_token=row["relay_token"],
        created_at=row["created_at"],
        last_login=row["last_login"],
        is_seller=bool(row["is_seller"]),
        google_id=row["google_id"],
    )


# ---------------------------------------------------------------------------
# CRUD functions
# ---------------------------------------------------------------------------

def create_user(email: str, display_name: str, password: str) -> User:
    """Create a new user account. Raises ValueError if email already taken."""
    user_id = str(uuid.uuid4())
    pw_hash = hash_password(password)
    relay_token = _generate_relay_token()
    now = _now_iso()

    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO users (id, email, display_name, password_hash, relay_token, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, email.lower().strip(), display_name.strip(), pw_hash, relay_token, now),
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Email already registered: {email}") from e
    finally:
        conn.close()

    return User(
        id=user_id,
        email=email.lower().strip(),
        display_name=display_name.strip(),
        password_hash=pw_hash,
        relay_token=relay_token,
        created_at=now,
        last_login=None,
        is_seller=False,
        google_id=None,
    )


def create_user_from_google(email: str, display_name: str, google_id: str) -> User:
    """Create a new user from Google sign-in (no password needed)."""
    user_id = str(uuid.uuid4())
    # Generate a random password hash — user won't use password login
    pw_hash = hash_password(secrets.token_hex(32))
    relay_token = _generate_relay_token()
    now = _now_iso()

    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO users (id, email, display_name, password_hash, relay_token, created_at, google_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, email.lower().strip(), display_name.strip(), pw_hash, relay_token, now, google_id),
        )
        conn.commit()
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Email already registered: {email}") from e
    finally:
        conn.close()

    return User(
        id=user_id,
        email=email.lower().strip(),
        display_name=display_name.strip(),
        password_hash=pw_hash,
        relay_token=relay_token,
        created_at=now,
        last_login=None,
        is_seller=False,
        google_id=google_id,
    )


def get_user_by_email(email: str) -> Optional[User]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()
        return _row_to_user(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: str) -> Optional[User]:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _row_to_user(row) if row else None
    finally:
        conn.close()


def get_user_by_google_id(google_id: str) -> Optional[User]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE google_id = ?", (google_id,)
        ).fetchone()
        return _row_to_user(row) if row else None
    finally:
        conn.close()


def get_user_by_relay_token(token: str) -> Optional[User]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE relay_token = ?", (token,)
        ).fetchone()
        return _row_to_user(row) if row else None
    finally:
        conn.close()


def update_last_login(user_id: str):
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE users SET last_login = ? WHERE id = ?", (_now_iso(), user_id)
        )
        conn.commit()
    finally:
        conn.close()


def regenerate_relay_token(user_id: str) -> str:
    """Generate a new relay token for the user. Returns the new token."""
    new_token = _generate_relay_token()
    conn = _get_conn()
    try:
        result = conn.execute(
            "UPDATE users SET relay_token = ? WHERE id = ?", (new_token, user_id)
        )
        if result.rowcount == 0:
            raise ValueError(f"User not found: {user_id}")
        conn.commit()
    finally:
        conn.close()
    return new_token


# ---------------------------------------------------------------------------
# Initialize on import
# ---------------------------------------------------------------------------

init_db()
