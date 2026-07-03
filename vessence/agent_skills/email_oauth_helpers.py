"""Pure helpers for Gmail OAuth token storage and refresh policy."""

from __future__ import annotations

import os
import re
from typing import Any


TOKEN_FILE_PREFIX = "gmail_token_"
REFRESH_LEEWAY_SECONDS = 300


def normalized_user_id(user_id: str | None) -> str:
    return (user_id or "").strip().lower()


def token_slug(user_id: str) -> str:
    normalized = normalized_user_id(user_id)
    slug = normalized.replace("@", "_at_").replace(".", "_")
    return re.sub(r"[^a-z0-9_-]+", "_", slug).strip("_")


def account_token_file(
    creds_dir: str,
    user_id: str,
    *,
    token_file_prefix: str = TOKEN_FILE_PREFIX,
) -> str:
    slug = token_slug(user_id)
    if not slug:
        raise ValueError("Gmail user_id is required for account-specific token storage")
    return os.path.join(creds_dir, f"{token_file_prefix}{slug}.json")


def build_token_payload(
    user_id: str,
    token_data: dict[str, Any],
    *,
    stored_at: float,
) -> dict[str, Any]:
    normalized_user = normalized_user_id(user_id)
    if not normalized_user:
        raise ValueError("Gmail user_id is required")
    return {
        "user_id": normalized_user,
        "access_token": token_data.get("access_token", ""),
        "refresh_token": token_data.get("refresh_token", ""),
        "token_type": token_data.get("token_type", "Bearer"),
        "expires_at": token_data.get("expires_at", 0),
        "scope": token_data.get("scope", ""),
        "stored_at": stored_at,
    }


def should_write_legacy_token(legacy_user: str, normalized_user: str) -> bool:
    return not legacy_user or legacy_user == normalized_user


def should_refresh_token(
    expires_at: float,
    *,
    now: float,
    leeway_seconds: int = REFRESH_LEEWAY_SECONDS,
) -> bool:
    return not now < (expires_at - leeway_seconds)


def apply_refresh_response(
    token_data: dict[str, Any],
    new_tokens: dict[str, Any],
    *,
    now: float,
) -> dict[str, Any]:
    token_data["access_token"] = new_tokens["access_token"]
    token_data["expires_at"] = now + new_tokens.get("expires_in", 3600)
    if "refresh_token" in new_tokens:
        token_data["refresh_token"] = new_tokens["refresh_token"]
    return token_data
