"""email_oauth.py — Gmail OAuth token management.

Stores Gmail OAuth refresh tokens in the credentials directory.
Tokens are obtained during Google Sign-In when gmail scopes are requested.

Token storage path: $VESSENCE_DATA_HOME/credentials/gmail_token.json
"""
import json
import logging
import os
import time
from pathlib import Path

from agent_skills.email_oauth_helpers import (
    TOKEN_FILE_PREFIX,
    account_token_file,
    apply_refresh_response,
    build_token_payload,
    normalized_user_id as _normalized_user_id,
    should_refresh_token,
    should_write_legacy_token,
    token_slug as _token_slug,
)

_logger = logging.getLogger(__name__)

_VESSENCE_DATA_HOME = os.environ.get(
    "VESSENCE_DATA_HOME",
    os.path.join(os.path.expanduser("~"), "ambient", "vessence-data"),
)
_CREDS_DIR = os.path.join(_VESSENCE_DATA_HOME, "credentials")
_TOKEN_FILE = os.path.join(_CREDS_DIR, "gmail_token.json")
_TOKEN_FILE_PREFIX = TOKEN_FILE_PREFIX
_BOOTSTRAPPED_GOOGLE_OAUTH_ENV = False


def _account_token_file(user_id: str) -> str:
    return account_token_file(
        _CREDS_DIR,
        user_id,
        token_file_prefix=_TOKEN_FILE_PREFIX,
    )


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
    normalized_user = _normalized_user_id(user_id)
    payload = build_token_payload(user_id, token_data, stored_at=time.time())

    account_file = _account_token_file(normalized_user)
    with open(account_file, "w") as f:
        json.dump(payload, f, indent=2)
    os.chmod(account_file, 0o600)

    # Backward compatibility: keep the legacy single-account token file as the
    # default sender, but do not let a second login overwrite a different
    # default account. This preserves chieh.t.wu@gmail.com while adding
    # juliaprocess@gmail.com as an explicit sender.
    legacy_user = ""
    if os.path.exists(_TOKEN_FILE):
        try:
            with open(_TOKEN_FILE) as f:
                legacy_user = _normalized_user_id(json.load(f).get("user_id"))
        except Exception:
            legacy_user = ""
    if should_write_legacy_token(legacy_user, normalized_user):
        with open(_TOKEN_FILE, "w") as f:
            json.dump(payload, f, indent=2)
        os.chmod(_TOKEN_FILE, 0o600)

    _logger.info("Gmail token stored for user %s at %s", normalized_user, account_file)
    return account_file


def load_gmail_token(user_id: str | None = None) -> dict | None:
    """Load saved Gmail token from disk.

    Args:
        user_id: Optional — if provided, verifies the token belongs to this user.

    Returns:
        Token dict or None if not found / user mismatch.
    """
    normalized_user = _normalized_user_id(user_id)

    if normalized_user:
        account_file = _account_token_file(normalized_user)
        if os.path.exists(account_file):
            with open(account_file) as f:
                return json.load(f)
        if os.path.exists(_TOKEN_FILE):
            with open(_TOKEN_FILE) as f:
                data = json.load(f)
            if _normalized_user_id(data.get("user_id")) == normalized_user:
                return data
        for path in Path(_CREDS_DIR).glob(f"{_TOKEN_FILE_PREFIX}*.json"):
            try:
                with open(path) as f:
                    data = json.load(f)
            except Exception:
                continue
            if _normalized_user_id(data.get("user_id")) == normalized_user:
                _logger.info("Loaded Gmail token for %s from %s", normalized_user, path)
                return data
        _logger.warning("No Gmail token found for user %s", normalized_user)
        return None

    default_user = _normalized_user_id(os.environ.get("JANE_DEFAULT_GMAIL_SENDER"))
    if default_user:
        return load_gmail_token(default_user)

    if os.path.exists(_TOKEN_FILE):
        with open(_TOKEN_FILE) as f:
            return json.load(f)

    account_tokens = [
        path for path in Path(_CREDS_DIR).glob(f"{_TOKEN_FILE_PREFIX}*.json")
        if path.name != os.path.basename(_TOKEN_FILE)
    ]
    if len(account_tokens) == 1:
        with open(account_tokens[0]) as f:
            return json.load(f)

    _logger.warning("No default Gmail token file found at %s", _TOKEN_FILE)
    return None


def list_gmail_token_users() -> list[str]:
    """Return Gmail accounts with stored OAuth tokens."""
    users: set[str] = set()
    paths = []
    if os.path.exists(_TOKEN_FILE):
        paths.append(Path(_TOKEN_FILE))
    paths.extend(Path(_CREDS_DIR).glob(f"{_TOKEN_FILE_PREFIX}*.json"))

    for path in paths:
        try:
            with open(path) as f:
                user = _normalized_user_id(json.load(f).get("user_id"))
            if user:
                users.add(user)
        except Exception:
            continue

    return sorted(users)


def _bootstrap_google_oauth_env() -> None:
    """Load OAuth client settings for cron-safe Gmail token refresh."""
    global _BOOTSTRAPPED_GOOGLE_OAUTH_ENV
    if _BOOTSTRAPPED_GOOGLE_OAUTH_ENV:
        return
    _BOOTSTRAPPED_GOOGLE_OAUTH_ENV = True

    try:
        from dotenv import load_dotenv
        from jane.config import ENV_FILE_PATH

        load_dotenv(ENV_FILE_PATH)
    except Exception as exc:
        _logger.debug("Gmail OAuth dotenv bootstrap skipped: %s", exc)

    if os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"):
        return

    try:
        from agent_skills.secret_store import SecretStore

        store = SecretStore()
        if not store.is_unlocked():
            return
        for key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"):
            value = store.get(key)
            if value and not os.environ.get(key):
                os.environ[key] = value
    except Exception as exc:
        _logger.debug("Gmail OAuth SecretStore bootstrap skipped: %s", exc)


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
    if not should_refresh_token(expires_at, now=time.time()):
        return token_data

    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        _logger.error("No refresh token available — cannot refresh Gmail access token")
        return None

    _bootstrap_google_oauth_env()
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

    apply_refresh_response(token_data, new_tokens, now=time.time())

    stored_user = token_data.get("user_id", user_id or "")
    store_gmail_token(stored_user, token_data)
    _logger.info("Gmail token refreshed successfully")
    return token_data
