"""email_oauth.py — Gmail OAuth token management.

Stores Gmail OAuth refresh tokens in the credentials directory.
Tokens are obtained during Google Sign-In when gmail scopes are requested.

Token storage path: $VESSENCE_DATA_HOME/credentials/gmail_token.json
"""
import json
import logging
import os
import time

_logger = logging.getLogger(__name__)

_VESSENCE_DATA_HOME = os.environ.get(
    "VESSENCE_DATA_HOME",
    os.path.join(os.path.expanduser("~"), "ambient", "vessence-data"),
)
_CREDS_DIR = os.path.join(_VESSENCE_DATA_HOME, "credentials")
_TOKEN_FILE = os.path.join(_CREDS_DIR, "gmail_token.json")


def _ensure_creds_dir() -> None:
    os.makedirs(_CREDS_DIR, exist_ok=True)


def store_gmail_token(user_id: str, token_data: dict) -> str:
    """Save OAuth token data to the credentials directory.

    Args:
        user_id: The Google account email address.
        token_data: Dict containing access_token, refresh_token, expires_at, etc.

    Returns:
        Path to the saved token file.
    """
    _ensure_creds_dir()
    payload = {
        "user_id": user_id,
        "access_token": token_data.get("access_token", ""),
        "refresh_token": token_data.get("refresh_token", ""),
        "token_type": token_data.get("token_type", "Bearer"),
        "expires_at": token_data.get("expires_at", 0),
        "scope": token_data.get("scope", ""),
        "stored_at": time.time(),
    }
    with open(_TOKEN_FILE, "w") as f:
        json.dump(payload, f, indent=2)
    os.chmod(_TOKEN_FILE, 0o600)
    _logger.info("Gmail token stored for user %s at %s", user_id, _TOKEN_FILE)
    return _TOKEN_FILE


def load_gmail_token(user_id: str | None = None) -> dict | None:
    """Load saved Gmail token from disk.

    Args:
        user_id: Optional — if provided, verifies the token belongs to this user.

    Returns:
        Token dict or None if not found / user mismatch.
    """
    if not os.path.exists(_TOKEN_FILE):
        _logger.warning("No Gmail token file found at %s", _TOKEN_FILE)
        return None
    with open(_TOKEN_FILE) as f:
        data = json.load(f)
    if user_id and data.get("user_id", "").lower() != user_id.lower():
        _logger.warning("Token user mismatch: wanted %s, got %s", user_id, data.get("user_id"))
        return None
    return data


def refresh_token_if_needed(user_id: str | None = None) -> dict | None:
    """Refresh the access token if it has expired.

    Uses the stored refresh_token to obtain a new access_token from Google.

    Returns:
        Updated token dict, or None on failure.
    """
    token_data = load_gmail_token(user_id)
    if token_data is None:
        return None

    expires_at = token_data.get("expires_at", 0)
    # Refresh if token expires within the next 5 minutes
    if time.time() < (expires_at - 300):
        return token_data

    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        _logger.error("No refresh token available — cannot refresh Gmail access token")
        return None

    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        _logger.error("GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET not set — cannot refresh")
        return None

    try:
        import httpx

        resp = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        new_tokens = resp.json()
    except Exception as exc:
        _logger.error("Failed to refresh Gmail token: %s", exc)
        return None

    token_data["access_token"] = new_tokens["access_token"]
    token_data["expires_at"] = time.time() + new_tokens.get("expires_in", 3600)
    if "refresh_token" in new_tokens:
        token_data["refresh_token"] = new_tokens["refresh_token"]

    stored_user = token_data.get("user_id", user_id or "")
    store_gmail_token(stored_user, token_data)
    _logger.info("Gmail token refreshed successfully")
    return token_data
