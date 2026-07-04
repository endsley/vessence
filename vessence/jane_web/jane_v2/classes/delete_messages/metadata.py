"""Delete messages class — dismiss/delete SMS and notifications.

Always escalates to Stage 3 by design. Resolving WHICH messages the
user means ("the spam ones", "those texts from Kathia", "the ones
about my package") needs the same nuanced inbox triage that
read_messages requires — important-vs-spam classification, sender
matching against contacts, contextual references to recent reads.
qwen2.5:7b can't do that reliably, so Opus owns it.

Output: Opus emits `[[CLIENT_TOOL:messages.dismiss:{...}]]` which the
Android handler executes (deletes SMS rows from the phone DB AND
dismisses matching notifications from the shade).
"""

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


def _escalation_context() -> str:
    """Inject recent synced messages so Opus can match the user's
    referent ("those spam texts", "the one from Kathia") against
    actual inbox contents and pull the right addresses."""
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

    lines = [
        "[delete messages escalation context]",
        "",
        "Tool: [[CLIENT_TOOL:messages.dismiss:{\"addresses\":[\"<num1>\",\"<num2>\"]}]]",
        "  - addresses: list of phone number strings to delete. Matches the SMS "
        "'address' column LIKE '%<normalized>%' so format variations are fine.",
        "  - Optional: \"senders\" (list of name patterns) — used only for "
        "notification dismissal when the phone number isn't known. Prefer "
        "addresses; fall back to senders only when the inbox row has no number.",
        "  - Two-phase on the phone: (1) delete SMS rows from Telephony.Sms "
        "(needs default-SMS-app status, may fail with sms_access=false — that's "
        "ok, notifications still get dismissed); (2) cancel matching notifications "
        "from the shade.",
        "",
        "Workflow:",
        "  1. Match the user's reference ('the spam', 'that promo text', 'Kathia's "
        "messages') against the synced inbox below.",
        "  2. Collect the phone numbers/addresses for the matching rows.",
        "  3. Confirm BEFORE deleting if the user was vague or the match isn't "
        "obvious: read back \"I'll delete the 3 messages from <senders> — sounds "
        "good?\" and wait for yes. Skip confirmation only when the user was "
        "explicit (\"delete the messages from 555-1234\", \"yes delete those\").",
        "  4. Emit the CLIENT_TOOL marker. Reply \"Deleted.\" or \"Dismissed N "
        "messages from <sender>.\" Don't quote the deleted bodies.",
        "",
        "DO NOT delete contact messages without explicit confirmation. Promo / "
        "automated / shortcode (5-6 digit address) senders are fine to delete on "
        "a clear order like \"delete the spam\".",
        "",
    ]

    if not rows:
        lines.append("No synced messages in the database yet.")
        return "\n".join(lines)

    lines.append("Recent synced messages (most recent first):")
    for i, r in enumerate(rows, 1):
        r = dict(r)
        body = (r["body"] or "").strip()[:160]
        lines.append(_format_synced_message_line(i, r, body))
    return "\n".join(lines)


PARAMS_SCHEMA = {
    "scope": (
        "enum|null — one of: spam | sender | specific | all_recent. "
        "spam = 'delete the spam', 'get rid of the promos'. "
        "sender = 'delete Kathia's messages', 'remove texts from mom'. "
        "specific = user named a single message ('that text about my package'). "
        "all_recent = 'clear my inbox', 'delete everything'. "
        "Null when scope is unclear — Opus will ask."
    ),
    "filter_sender": (
        "string|null — sender name when the user named one. Opus resolves "
        "this against contacts and the inbox to get phone numbers."
    ),
}


METADATA = {
    "name": "delete messages",
    "priority": 10,
    "description": (
        "[delete messages]\n"
        "User wants Jane to delete or dismiss SMS / text messages from the "
        "phone inbox or notification shade. Positive signals: 'delete those "
        "texts', 'dismiss the spam', 'remove that promo message', 'get rid "
        "of those notifications', 'clear out the messages from <sender>'.\n"
        "NOT this class:\n"
        "  - 'delete my contact for X' → 'others' (contact deletion, "
        "different tool)\n"
        "  - 'remove from my todo list' → 'todo list'\n"
        "  - 'stop sending me notifications' → 'others' (settings / "
        "preference change, not deleting existing messages)\n"
        "  - 'unsubscribe from this list' → 'others' (Jane can't "
        "unsubscribe FROM the sender's side)\n"
        "  - 'delete that email' → 'others' (email lives elsewhere)\n"
        "  - 'cancel that text I was about to send' → 'send message' "
        "(aborting an open draft, not deleting received SMS)"
    ),
    "params_schema": PARAMS_SCHEMA,
    "few_shot": [
        ("delete those spam texts", "delete messages:High"),
        ("dismiss the promo message", "delete messages:High"),
        ("get rid of the texts from that 5-digit number", "delete messages:High"),
        ("remove the messages from Kathia about the package", "delete messages:High"),
        ("clear out my inbox", "delete messages:High"),
        ("delete the last text from mom", "delete messages:High"),
        # Contrast cases — NOT delete_messages
        ("cancel the text I was drafting", "send message:High"),
        ("delete my contact for John", "others:Low"),
        ("remove eggs from my todo list", "todo list:High"),
        ("stop sending me promo notifications", "others:Low"),
    ],
    "ack": "Looking at your messages…",
    "escalate_ack": "Let me see which ones you mean…",
    "escalation_context": _escalation_context,
}
