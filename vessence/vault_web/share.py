"""share.py — Share link generation and validation."""
import secrets
import datetime
from .database import get_db

# Default share link expiry: 7 days
SHARE_EXPIRY_DAYS = 7


def create_share(path: str, created_for: str, expiry_days: int = SHARE_EXPIRY_DAYS) -> str:
    """Generate a cryptographically secure share code for a path."""
    code = secrets.token_urlsafe(16)
    share_id = secrets.token_hex(8)
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=expiry_days)).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO share_links (id, code, path, created_for, expires_at) VALUES (?,?,?,?,?)",
            (share_id, code, path, created_for, expires_at)
        )
    return code


def validate_share(code: str) -> dict | None:
    """Returns share info if valid and not expired, None otherwise."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM share_links WHERE code=?", (code,)
        ).fetchone()
        if not row:
            return None
        # Check expiry if the column exists
        expires_at = row["expires_at"] if "expires_at" in row.keys() else None
        if expires_at:
            expiry = datetime.datetime.fromisoformat(expires_at)
            if datetime.datetime.utcnow() > expiry:
                conn.execute("DELETE FROM share_links WHERE code=?", (code,))
                return None
        conn.execute(
            "UPDATE share_links SET access_count=access_count+1 WHERE code=?", (code,)
        )
        return dict(row)


def list_shares() -> list:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM share_links ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def revoke_share(share_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM share_links WHERE id=?", (share_id,))
