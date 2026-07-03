"""sms_helpers.py — server-side SMS recipient resolution and draft storage.

Used by the Gemma classifier fast-path and the Opus fallback flow. Looks up
recipients in two places, in order:

  1. contact_aliases  — learned relational shortcuts ("wife" → Kathia's #)
  2. contacts         — phone-book entries synced from Android

The alias table is preferred because it's written by Opus (or the API) after
it resolves an unknown relational name via memory. Once an alias exists, the
classifier fast-path can resolve "my wife" in a single SQL lookup and skip
Opus entirely on subsequent turns.
"""
from __future__ import annotations

import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

from agent_skills.sms_helper_rules import (
    STOP_PREFIXES as _STOP_PREFIXES,
    alias_match_from_row as _alias_match_from_row,
    contact_lookup_from_rows as _contact_lookup_from_rows,
    draft_is_expired as _draft_is_expired,
    draft_payload_from_row as _draft_payload_from_row,
    escape_sql_like as _escape_sql_like,
    expired_draft_cutoff_text as _expired_draft_cutoff_text,
    normalize_name as _normalize_name,
)

# vault_web is the single source of truth for contacts/aliases/drafts.
_VAULT_WEB_DIR = Path(__file__).resolve().parents[1] / "vault_web"
if str(_VAULT_WEB_DIR) not in sys.path:
    sys.path.insert(0, str(_VAULT_WEB_DIR))

logger = logging.getLogger(__name__)

# Drafts older than this are considered stale and ignored/cleaned up.
DRAFT_TTL_SECONDS = 300  # 5 minutes


def resolve_recipient(name: str) -> Optional[dict]:
    """Resolve a free-text recipient to a phone number.

    Returns {phone_number, display_name, source} on a single unambiguous
    match, or None if unresolved/ambiguous. Ambiguous multi-matches also
    return None — the caller should fall through to Opus for disambiguation.

    source is "alias" or "contacts" so the caller can log which path hit.
    """
    norm = _normalize_name(name)
    if not norm:
        return None
    try:
        from database import get_db
    except Exception as e:
        logger.warning("resolve_recipient: database import failed: %s", e)
        return None

    try:
        with get_db() as conn:
            # 1) alias lookup — exact match on normalized alias
            row = conn.execute(
                "SELECT phone_number, display_name FROM contact_aliases "
                "WHERE LOWER(alias) = ? LIMIT 1",
                (norm,),
            ).fetchone()
            alias_match = _alias_match_from_row(row, norm)
            if alias_match:
                return alias_match

            # 2) contacts lookup — LIKE on display_name. Require a phone
            # number (email-only contacts are useless for SMS).
            escaped_norm = _escape_sql_like(norm)
            like = f"%{escaped_norm}%"
            rows = conn.execute(
                "SELECT display_name, phone_number FROM contacts "
                "WHERE display_name LIKE ? ESCAPE '\\' AND phone_number IS NOT NULL "
                "AND phone_number != '' "
                "ORDER BY is_primary DESC, display_name LIMIT 5",
                (like,),
            ).fetchall()
            # Collapse duplicates on display_name (contacts can have multiple
            # phone rows — pick the primary).
            contact_lookup = _contact_lookup_from_rows(rows)
            if contact_lookup.match:
                return contact_lookup.match
            if contact_lookup.ambiguous_count:
                logger.info(
                    "resolve_recipient: '%s' matched %d contacts — ambiguous",
                    name, contact_lookup.ambiguous_count,
                )
                return None
    except Exception as e:
        logger.warning("resolve_recipient failed for '%s': %s", name, e)
        return None

    return None


def add_alias(alias: str, phone_number: str, display_name: Optional[str] = None) -> bool:
    """Write an alias to contact_aliases. INSERT OR REPLACE on the alias key.

    Called by the Opus fallback path after it resolves an unknown relational
    name via memory, or by the /api/contacts/alias endpoint.
    """
    norm = _normalize_name(alias)
    if not norm or not phone_number:
        return False
    try:
        from database import get_db
        with get_db() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO contact_aliases "
                "(alias, phone_number, display_name) VALUES (?, ?, ?)",
                (norm, phone_number.strip(), (display_name or "").strip() or None),
            )
        logger.info("add_alias: %s → %s (%s)", norm, phone_number, display_name or "")
        return True
    except Exception as e:
        logger.warning("add_alias failed for '%s': %s", alias, e)
        return False


# ── SMS draft storage (fallback path only) ───────────────────────────────────

def create_draft(session_id: str, phone_number: str, body: str,
                 display_name: Optional[str] = None) -> Optional[str]:
    """Create a pending SMS draft and return its draft_id.

    Used by the fallback confirm flow: Gemma's gate failed or the recipient
    was ambiguous, Opus drafted a message, and now we need to hold onto it
    until the user confirms or cancels.
    """
    if not session_id or not phone_number or not body:
        return None
    draft_id = uuid.uuid4().hex[:12]
    try:
        from database import get_db
        with get_db() as conn:
            conn.execute(
                "INSERT INTO sms_drafts "
                "(draft_id, session_id, phone_number, display_name, body) "
                "VALUES (?, ?, ?, ?, ?)",
                (draft_id, session_id, phone_number, display_name, body),
            )
        return draft_id
    except Exception as e:
        logger.warning("create_draft failed: %s", e)
        return None


def get_latest_draft(session_id: str) -> Optional[dict]:
    """Return the most recent non-expired draft for a session, or None."""
    if not session_id:
        return None
    try:
        from database import get_db
        with get_db() as conn:
            row = conn.execute(
                "SELECT draft_id, phone_number, display_name, body, "
                "strftime('%s', created_at) AS created_epoch "
                "FROM sms_drafts WHERE session_id = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            if not row:
                return None
            created_epoch = int(row["created_epoch"] or 0)
            if _draft_is_expired(
                created_epoch,
                now=time.time(),
                ttl_seconds=DRAFT_TTL_SECONDS,
            ):
                # Stale — garbage-collect and pretend it doesn't exist.
                conn.execute("DELETE FROM sms_drafts WHERE draft_id = ?", (row["draft_id"],))
                return None
            return _draft_payload_from_row(row)
    except Exception as e:
        logger.warning("get_latest_draft failed: %s", e)
        return None


def delete_draft(draft_id: str) -> bool:
    """Delete a draft after confirm or cancel."""
    if not draft_id:
        return False
    try:
        from database import get_db
        with get_db() as conn:
            conn.execute("DELETE FROM sms_drafts WHERE draft_id = ?", (draft_id,))
        return True
    except Exception as e:
        logger.warning("delete_draft failed: %s", e)
        return False


def cleanup_expired_drafts() -> int:
    """Delete drafts older than DRAFT_TTL_SECONDS. Returns count deleted."""
    try:
        from database import get_db
        with get_db() as conn:
            cutoff = _expired_draft_cutoff_text(time.time(), DRAFT_TTL_SECONDS)
            cur = conn.execute(
                "DELETE FROM sms_drafts WHERE strftime('%s', created_at) < ?",
                (cutoff,),
            )
            return cur.rowcount or 0
    except Exception as e:
        logger.warning("cleanup_expired_drafts failed: %s", e)
        return 0
