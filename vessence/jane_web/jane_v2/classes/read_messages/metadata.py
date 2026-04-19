"""Read messages class — check/read text messages."""

import datetime
import logging
import sys
from pathlib import Path

_VAULT_WEB_DIR = Path(__file__).resolve().parents[4] / "vault_web"
if str(_VAULT_WEB_DIR) not in sys.path:
    sys.path.insert(0, str(_VAULT_WEB_DIR))

_logger = logging.getLogger(__name__)


def _escalation_context() -> str:
    """Inject recent synced messages so Stage 3 (Opus) can analyze them
    without re-querying the database."""
    try:
        from database import get_db
    except Exception as e:
        return f"Message database unavailable: {e}"

    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT sender, body, timestamp_ms, is_contact, msg_type "
                "FROM synced_messages "
                "ORDER BY timestamp_ms DESC LIMIT 20",
                (),
            ).fetchall()
    except Exception as e:
        return f"Message query failed: {e}"

    if not rows:
        return "No synced messages in the database yet."

    lines = ["Recent synced messages (most recent first):"]
    for i, r in enumerate(rows):
        r = dict(r)
        ts = datetime.datetime.fromtimestamp(
            r["timestamp_ms"] / 1000
        ).strftime("%m/%d %I:%M %p").lstrip("0")
        sender_raw = r["sender"] or "Unknown"
        body = (r["body"] or "").strip()[:200]
        kind = "contact" if r.get("is_contact") else (r.get("msg_type") or "unknown")
        if sender_raw.startswith("Me → "):
            other = sender_raw[len("Me → "):].strip()
            lines.append(
                f"{i+1}. [{ts}] (SENT by user to {other}) ({kind}): {body}"
            )
        else:
            lines.append(
                f"{i+1}. [{ts}] (RECEIVED from {sender_raw}) ({kind}): {body}"
            )

    lines.append("")
    lines.append(
        "Interpret and summarize these messages for the user. "
        "SENT = user's outgoing messages, RECEIVED = incoming. "
        "Classify each as important (personal/contact) or spam/promo. "
        "Quote contact messages verbatim; summarize spam briefly."
    )
    return "\n".join(lines)


METADATA = {
    "name": "read messages",
    "priority": 10,
    "description": (
        "[read messages]\n"
        "User wants Jane to read incoming SMS / text messages from the "
        "phone inbox. Positive signals: 'read my messages', 'any new "
        "texts?', 'what did X text me?', 'unread messages'.\n"
        "NOT this class: meta questions about a past CONVERSATION turn "
        "with Jane ('the last message you sent me', 'why did your last "
        "reply take so long?') — those are self-reference debugging, "
        "not inbox readback."
    ),
    "few_shot": [
        ("read my messages", "read messages:High"),
        ("any new texts", "read messages:High"),
        ("what did Kathia text me", "read messages:High"),
        ("any unread messages", "read messages:High"),
        ("check my inbox", "read messages:High"),
        ("do I have any new messages", "read messages:High"),
        # Contrast cases — NOT read_messages (meta/debug about Jane's
        # own previous replies, not SMS inbox).
        ("your last message took a while, why?", "others:Low"),
        ("the last message when I asked you took a while", "others:Low"),
        ("why was your last reply so slow", "others:Low"),
        ("why did the last message take so long", "others:Low"),
        ("explain the delay on the last message", "others:Low"),
    ],
    "ack": "Checking your messages…",
    "escalate_ack": "Let me check your messages…",
    "escalation_context": _escalation_context,
}
