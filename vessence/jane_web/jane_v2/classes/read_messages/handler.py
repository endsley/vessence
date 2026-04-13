"""Read Messages Stage 2 handler.

Queries the server-side synced_messages database. Contact messages are
read verbatim (deterministic); non-contact / spam messages are collapsed
into a one-line tail summary. No phone round-trip needed.
"""

from __future__ import annotations

import datetime
import logging
import sys
from pathlib import Path

_VAULT_WEB_DIR = Path(__file__).resolve().parents[4] / "vault_web"
if str(_VAULT_WEB_DIR) not in sys.path:
    sys.path.insert(0, str(_VAULT_WEB_DIR))

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 10

# Keywords that suggest the user is talking about the pipeline itself, not asking
# to hear their texts. If none of these plus no read-intent words match, escalate.
_ARCH_WORDS = ("architecture", "infrastructure", "pipeline", "handler", "classifier", "stage")


def _fetch_messages(limit: int = DEFAULT_LIMIT, contact_only: bool = False) -> list[dict]:
    """Fetch recent messages from the synced_messages database."""
    try:
        from database import get_db
    except Exception as e:
        logger.warning("read_messages handler: database import failed: %s", e)
        return []

    try:
        with get_db() as conn:
            where = "WHERE is_contact = 1" if contact_only else ""
            rows = conn.execute(
                f"SELECT sender, body, timestamp_ms, is_contact, msg_type "
                f"FROM synced_messages {where} "
                f"ORDER BY timestamp_ms DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("read_messages handler: query failed: %s", e)
        return []


def _is_personal(msg: dict) -> bool:
    """Personal = from a known contact and not flagged spam."""
    return bool(msg.get("is_contact")) and msg.get("msg_type") != "spam"


def _fmt_time(ts_ms: int) -> str:
    return datetime.datetime.fromtimestamp(ts_ms / 1000).strftime("%I:%M %p").lstrip("0")


async def handle(prompt: str, context: str = "") -> dict | None:
    """Read recent texts: contacts verbatim, others collapsed into a tail summary."""
    p_lower = prompt.lower()
    if any(w in p_lower for w in _ARCH_WORDS):
        return {"wrong_class": True}

    messages = _fetch_messages(limit=DEFAULT_LIMIT)

    if not messages:
        return {"text": "You don't have any synced messages yet."}

    personal = [m for m in messages if _is_personal(m)]
    other = [m for m in messages if not _is_personal(m)]

    parts: list[str] = []

    if personal:
        if len(personal) == 1:
            parts.append("You have 1 message from a contact.")
        else:
            parts.append(f"You have {len(personal)} messages from contacts.")
        for m in personal:
            sender = m["sender"] or "Unknown"
            body = (m["body"] or "").strip()
            parts.append(f"From {sender} at {_fmt_time(m['timestamp_ms'])}: {body}")
    else:
        parts.append("No new messages from contacts.")

    if other:
        senders = []
        seen = set()
        for m in other:
            s = (m["sender"] or "Unknown").split(":")[0].strip()
            if s not in seen:
                seen.add(s)
                senders.append(s)
        sender_list = ", ".join(senders[:3])
        more = "" if len(senders) <= 3 else f" and {len(senders) - 3} others"
        noun = "texts" if len(other) > 1 else "text"
        parts.append(f"Plus {len(other)} other {noun} from {sender_list}{more} — mostly promo or automated.")

    text = "\n\n".join(parts)
    logger.info("read_messages handler: read %d personal, collapsed %d other", len(personal), len(other))
    return {"text": text}
