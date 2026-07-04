"""Read messages class — check/read text messages."""

import logging
import sys
from pathlib import Path

from jane_web.jane_v2.classes.sms_metadata_helpers import (
    format_synced_message_line as _format_synced_message_line,
)

_VAULT_WEB_DIR = Path(__file__).resolve().parents[4] / "vault_web"
if str(_VAULT_WEB_DIR) not in sys.path:
    sys.path.insert(0, str(_VAULT_WEB_DIR))

_logger = logging.getLogger(__name__)


def _readback_body(row: dict, max_chars: int = 800) -> str:
    try:
        from jane_web.message_readback import body_for_readback_prompt

        return body_for_readback_prompt(row, max_chars=max_chars)
    except Exception as e:
        _logger.info("read_messages readback enrichment failed: %s", e)
        body = (row.get("body") or "").strip()
        return body[:max_chars]


def _read_messages_instruction_text() -> str:
    return (
        "Interpret and summarize these messages for the user. "
        "SENT = user's outgoing messages, RECEIVED = incoming. "
        "Classify each as important (personal/contact) or spam/promo. "
        "Quote contact messages verbatim; summarize spam briefly."
        " Use body text from resolved links when available. If a message says "
        "the linked TalkingPoints content could not be opened automatically, "
        "say that instead of reading the wrapper notification as the message."
    )


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
    for i, r in enumerate(rows, 1):
        r = dict(r)
        body = _readback_body(r)
        lines.append(_format_synced_message_line(i, r, body))

    lines.append("")
    lines.append(_read_messages_instruction_text())
    return "\n".join(lines)


PARAMS_SCHEMA = {
    "filter_sender": (
        "string|null — sender name the user asked about ('what did Kathia text me'). "
        "Null when the user wants the whole inbox."
    ),
    "unread_only": (
        "bool — true when the user said unread/new/recent ('any new texts', "
        "'unread messages'). false when they want all recent messages."
    ),
    "limit": (
        "int|null — explicit cap if the user said one ('last 5 messages'). "
        "Null means use the handler default."
    ),
}


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
    "params_schema": PARAMS_SCHEMA,
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
