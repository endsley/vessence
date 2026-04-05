"""share.py — Share link generation and validation."""
import secrets
import random
import string
from .database import get_db


def create_share(path: str, created_for: str) -> str:
    """Generate a 6-digit share code for a path."""
    code = ''.join(random.choices(string.digits, k=6))
    share_id = secrets.token_hex(8)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO share_links (id, code, path, created_for) VALUES (?,?,?,?)",
            (share_id, code, path, created_for)
        )
    return code


def validate_share(code: str) -> dict | None:
    """Returns share info if valid, None otherwise."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM share_links WHERE code=?", (code,)
        ).fetchone()
        if not row:
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
