"""auth.py — TOTP, sessions, trusted devices, lockout."""
import os
import sys
import secrets
import hashlib
import datetime
from pathlib import Path
import pyotp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from jane.config import ENV_FILE_PATH

load_dotenv(ENV_FILE_PATH)

from .database import get_db

MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 30
SESSION_TRUSTED_DAYS = 7

TOTP_SECRET = os.getenv("VAULT_TOTP_SECRET", "")


def get_allowed_emails() -> list[str]:
    """Return all allowed Google emails as a list (supports comma-separated ALLOWED_GOOGLE_EMAILS)."""
    return [e.strip().lower() for e in os.getenv("ALLOWED_GOOGLE_EMAILS", "").split(",") if e.strip()]


def is_allowed_email(email: str) -> bool:
    """Check if an email is in the allowed list."""
    allowed = get_allowed_emails()
    if not allowed:
        return True  # no allowlist = open access
    return email.strip().lower() in allowed


def user_id_from_email(email: str) -> str:
    """Derive a stable user_id from an email address."""
    return email.strip().lower().replace("@", "_at_").replace(".", "_")


def default_user_id() -> str:
    allowed = get_allowed_emails()
    if allowed:
        return user_id_from_email(allowed[0])
    user_name = os.getenv("USER_NAME", "").strip().lower()
    if user_name:
        return "_".join(user_name.split())
    return "user"


def get_totp() -> pyotp.TOTP:
    return pyotp.TOTP(TOTP_SECRET)


# Keep for share OTP (guest access) — no Discord dependency needed here
def send_otp_discord(otp: str, context: str = "login") -> bool:
    """No-op: Discord OTP removed. Share codes are still validated via verify_share."""
    return True


def create_otp() -> str:
    """No-op: TOTP doesn't need server-side code generation."""
    return ""


def verify_otp(code: str, ip: str) -> tuple[bool, str]:
    """Verify a TOTP code from an authenticator app. Returns (success, error_message)."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM failed_attempts WHERE ip=?", (ip,)).fetchone()
        if row and row["locked_until"]:
            locked_until = datetime.datetime.fromisoformat(row["locked_until"])
            if datetime.datetime.utcnow() < locked_until:
                remaining = int((locked_until - datetime.datetime.utcnow()).total_seconds() / 60) + 1
                return False, f"Too many attempts. Try again in {remaining} minute(s)."

    totp = get_totp()
    if totp.verify(code, valid_window=1):
        with get_db() as conn:
            conn.execute("DELETE FROM failed_attempts WHERE ip=?", (ip,))
        return True, ""

    with get_db() as conn:
        _record_failed_attempt(conn, ip)
    return False, "Invalid code."


def get_totp_uri(account_name: str = "", issuer: str = "Amber Vault") -> str:
    if not account_name:
        account_name = os.environ.get("USER_NAME", "Vault")
    return get_totp().provisioning_uri(name=account_name, issuer_name=issuer)


def _record_failed_attempt(conn, ip: str):
    row = conn.execute("SELECT * FROM failed_attempts WHERE ip=?", (ip,)).fetchone()
    if row:
        new_count = row["count"] + 1
        locked_until = None
        if new_count >= MAX_ATTEMPTS:
            locked_until = (
                datetime.datetime.utcnow() + datetime.timedelta(minutes=LOCKOUT_MINUTES)
            ).isoformat()
        conn.execute(
            "UPDATE failed_attempts SET count=?, locked_until=? WHERE ip=?",
            (new_count, locked_until, ip)
        )
    else:
        conn.execute("INSERT INTO failed_attempts (ip, count) VALUES (?, 1)", (ip,))


def unlock_ip(ip: str = None):
    """Unlock all IPs or a specific one (called by Amber)."""
    with get_db() as conn:
        if ip:
            conn.execute("DELETE FROM failed_attempts WHERE ip=?", (ip,))
        else:
            conn.execute("DELETE FROM failed_attempts")


def create_session(device_fingerprint: str, trusted: bool, user_id: str | None = None, email: str | None = None) -> str:
    if not user_id:
        user_id = user_id_from_email(email) if email else default_user_id()
    session_id = secrets.token_hex(32)
    if trusted:
        expires = datetime.datetime.utcnow() + datetime.timedelta(days=SESSION_TRUSTED_DAYS)
    else:
        expires = datetime.datetime.utcnow() + datetime.timedelta(hours=12)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO sessions (id, user_id, device_fingerprint, trusted, expires_at) VALUES (?,?,?,?,?)",
            (session_id, user_id, device_fingerprint, int(trusted), expires.isoformat())
        )
    return session_id


def get_session_user(session_id: str) -> str | None:
    """Return the user_id (email) for a session, or None if invalid."""
    if not session_id:
        return None
    with get_db() as conn:
        row = conn.execute("SELECT user_id, expires_at FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            return None
        if datetime.datetime.utcnow() > datetime.datetime.fromisoformat(row["expires_at"]):
            conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
            return None
        return row["user_id"]


def validate_session(session_id: str, device_fingerprint: str) -> bool:
    if not session_id:
        return False
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        if not row:
            return False
        expires = datetime.datetime.fromisoformat(row["expires_at"])
        if datetime.datetime.utcnow() > expires:
            conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
            return False
        # Verify device fingerprint matches the one used at session creation
        if row["device_fingerprint"] and device_fingerprint != row["device_fingerprint"]:
            return False
        conn.execute(
            "UPDATE sessions SET last_used=CURRENT_TIMESTAMP WHERE id=?", (session_id,)
        )
        return True


def is_device_trusted(fingerprint: str) -> bool:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM trusted_devices WHERE fingerprint=?", (fingerprint,)
        ).fetchone()
        return row is not None


def register_trusted_device(fingerprint: str, label: str):
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM trusted_devices WHERE fingerprint=?", (fingerprint,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE trusted_devices SET label=?, last_used=CURRENT_TIMESTAMP WHERE fingerprint=?",
                (label, fingerprint),
            )
            return existing["id"]
    device_id = secrets.token_hex(8)
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO trusted_devices (id, fingerprint, label) VALUES (?,?,?)",
            (device_id, fingerprint, label)
        )
    return device_id


def get_trusted_device_by_id(device_id: str):
    if not device_id:
        return None
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM trusted_devices WHERE id=?", (device_id,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE trusted_devices SET last_used=CURRENT_TIMESTAMP WHERE id=?",
                (device_id,),
            )
        return row


def get_trusted_device_by_fingerprint(fingerprint: str):
    if not fingerprint:
        return None
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM trusted_devices WHERE fingerprint=?", (fingerprint,)
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE trusted_devices SET last_used=CURRENT_TIMESTAMP WHERE fingerprint=?",
                (fingerprint,),
            )
        return row


def get_trusted_devices():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM trusted_devices ORDER BY last_used DESC").fetchall()
        return [dict(r) for r in rows]


def revoke_device(device_id: str):
    with get_db() as conn:
        conn.execute("DELETE FROM trusted_devices WHERE id=?", (device_id,))
        conn.execute(
            "DELETE FROM sessions WHERE device_fingerprint IN "
            "(SELECT fingerprint FROM trusted_devices WHERE id=?)",
            (device_id,)
        )


def device_fingerprint_from_request(request) -> str:
    ua = request.headers.get("user-agent", "")
    # Use real client IP behind reverse proxies (Cloudflare, nginx)
    ip = (request.headers.get("CF-Connecting-IP")
          or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
          or request.client.host)
    raw = f"{ip}:{ua}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
