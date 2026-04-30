"""Delete email class — trash/dismiss email via Gmail API.

Always escalates to Stage 3 by design — same rationale as `delete_messages`
for SMS. Resolving WHICH messages the user means ("the spam ones",
"that promo from Macy's", "the one from Bob about taxes") needs the same
inbox triage as read_email: contact-aware sender matching, important-vs-spam
classification, contextual references to recent reads. qwen2.5:7b can't do
that reliably so Opus owns it.

Output: Opus emits `[[CLIENT_TOOL:email.delete:{"message_id":"..."}]]`
which jane_proxy intercepts and executes server-side via
`agent_skills.email_tools.delete_email` (Gmail API trash, not permanent).
For batch deletion (multiple message_ids), Opus emits one marker per
message — the proxy executes each in turn.
"""

import datetime
import logging

_logger = logging.getLogger(__name__)


def _format_email_block(label: str, emails: list[dict]) -> str:
    """Render emails for Opus, INCLUDING message_id (delete needs it)."""
    if not emails:
        return f"{label}\nNone.\n[END]"
    lines = [label]
    for i, e in enumerate(emails, 1):
        msg_id = (e.get("message_id") or e.get("id") or "").strip()
        sender = (e.get("sender") or "Unknown")[:80]
        subject = (e.get("subject") or "(no subject)")[:120]
        snippet = (e.get("snippet") or "").strip()[:200]
        when = (e.get("date") or "").strip()[:40]
        unread_tag = " (unread)" if e.get("is_unread") else ""
        lines.append(f"{i}. id={msg_id} [{when}] {sender}{unread_tag}")
        lines.append(f"   Subject: {subject}")
        if snippet:
            lines.append(f"   Snippet: {snippet}")
    lines.append("[END]")
    return "\n".join(lines)


def _escalation_context() -> str:
    """Inject inbox + spam so Opus can match the user's reference
    ("delete that spam from Macy's", "trash the promos") against actual
    Gmail rows and pull the right message_ids."""
    try:
        from agent_skills.email_tools import read_inbox
    except Exception as e:
        return f"[EMAIL ERROR]\nEmail tools failed to import: {e}\n[END]"

    parts = [
        "[delete email escalation context]",
        "",
        'Tool: [[CLIENT_TOOL:email.delete:{"message_id":"<id>"}]]',
        "  - message_id: the Gmail message id from the inbox/spam blocks below "
        "(the `id=...` field on each line). One marker per email.",
        "  - Server moves it to Trash (not permanent delete).",
        "",
        "Workflow:",
        "  1. Match the user's reference ('the spam', 'that Macy's email', "
        "'the promo from Best Buy') against the inbox + spam buckets below.",
        "  2. Collect the message_ids for each match.",
        "  3. Confirm BEFORE deleting unless the user was explicit:",
        '     read back "I\'ll trash the 3 promo emails from Macy\'s, Best Buy, '
        'and Sephora — sounds good?" and wait for yes. Skip confirmation only '
        "for explicit asks like \"delete the spam\" / \"yes trash those\".",
        "  4. Emit one CLIENT_TOOL marker per message_id. Reply "
        '"Trashed N emails." Do not quote the deleted bodies.',
        "",
        "DO NOT delete personal/contact emails without explicit confirmation. "
        "Promo / marketing / spam-folder messages are fine to delete on a "
        "clear order like \"delete the spam\" or \"trash all the promos\".",
        "",
    ]

    creds_failed = False
    blocks = []

    try:
        unread = read_inbox(limit=10, query="is:unread")
        blocks.append(_format_email_block("[EMAIL INBOX — unread]", unread))
    except RuntimeError as e:
        creds_failed = True
        blocks.append(
            "[EMAIL ERROR]\n"
            f"Gmail not set up: {e}\n"
            "Tell the user they need to sign in with Google on the Vessence "
            "web UI to enable email access.\n[END]"
        )
    except Exception as e:
        _logger.warning("delete_email escalation: inbox fetch failed: %s", e)
        blocks.append(f"[EMAIL INBOX — unread]\nFetch failed: {e}\n[END]")

    if not creds_failed:
        try:
            spam = read_inbox(limit=15, query="in:spam")
            blocks.append(_format_email_block("[EMAIL SPAM — recent]", spam))
        except Exception as e:
            _logger.warning("delete_email escalation: spam fetch failed: %s", e)
            blocks.append(f"[EMAIL SPAM — recent]\nFetch failed: {e}\n[END]")

        try:
            promo = read_inbox(limit=15, query="category:promotions")
            blocks.append(_format_email_block("[EMAIL PROMOTIONS — recent]", promo))
        except Exception as e:
            _logger.warning("delete_email escalation: promo fetch failed: %s", e)
            blocks.append(f"[EMAIL PROMOTIONS — recent]\nFetch failed: {e}\n[END]")

        blocks.append(
            f"(Fetched at {datetime.datetime.utcnow().isoformat()}Z. "
            "Use the message_id (id=...) from the matching row when emitting "
            "the email.delete marker.)"
        )

    return "\n".join(parts) + "\n\n" + "\n\n".join(blocks)


PARAMS_SCHEMA = {
    "scope": (
        "enum|null — one of: spam | promotions | sender | specific | all_recent. "
        "spam = 'delete the spam', 'trash junk mail'. "
        "promotions = 'delete the promos', 'clean up promotions'. "
        "sender = 'delete that email from Macy's'. "
        "specific = user named one email. "
        "all_recent = 'clean my inbox' (rare; ask first). "
        "Null when scope is unclear — Opus will ask."
    ),
    "filter_sender": (
        "string|null — sender name when the user named one. Opus matches "
        "this against the inbox + spam blocks to pick message_ids."
    ),
}


METADATA = {
    "name": "delete email",
    "priority": 10,
    "description": (
        "[delete email]\n"
        "User wants Jane to delete / trash / dismiss email(s) from their "
        "Gmail inbox or spam/promotions folder. Server moves matched "
        "messages to Trash via the Gmail API (server-side, NOT the phone). "
        "Routes that go here include 'delete that spam email', 'trash the "
        "promos', 'delete all the marketing junk', 'get rid of that email "
        "from Macy's', 'clean up my spam folder'.\n\n"
        "Example phrasings the user might say:\n"
        "  - \"delete that spam email\"\n"
        "  - \"trash all the promos\"\n"
        "  - \"clean up my spam folder\"\n"
        "  - \"get rid of that email from Best Buy\"\n"
        "  - \"delete the marketing junk\"\n"
        "  - \"trash everything in spam\"\n"
        "  - \"delete that promo from Macy's\"\n\n"
        "Adversarial phrasings that LOOK LIKE 'delete email' but ARE NOT:\n"
        "  - \"delete those spam texts\" → 'delete messages' (SMS, not email)\n"
        "  - \"unsubscribe from this list\" → 'others' (not delete)\n"
        "  - \"archive that email\" → 'others' (archive ≠ delete)\n"
        "  - \"mark as read\" → 'others' (no delete intent)\n"
        "  - \"send an email\" → 'send email'\n"
        "  - \"check my email\" → 'read email'"
    ),
    "params_schema": PARAMS_SCHEMA,
    "escalation_context": _escalation_context,
    "few_shot": [
        ("delete that spam email", "delete email:High"),
        ("trash all the promos", "delete email:High"),
        ("clean up my spam folder", "delete email:High"),
        ("get rid of that email from Best Buy", "delete email:High"),
        ("delete all the marketing junk", "delete email:High"),
        # Contrast cases — NOT delete_email
        ("delete those spam texts", "delete messages:High"),
        ("send Bob an email", "send email:High"),
        ("check my email", "read email:High"),
    ],
    "ack": "Looking at your email…",
    "escalate_ack": "Let me see which ones you mean…",
}
