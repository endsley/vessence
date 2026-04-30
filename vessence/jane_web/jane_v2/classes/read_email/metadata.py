"""Read email class — check/read email inbox.

Stage 2 has no handler — read_email always escalates to Stage 3 (Opus)
because triage / spam-vs-personal classification / contact-aware quoting
is judgment work qwen2.5:7b can't do reliably. Opus gets the data via
`_escalation_context()` below, which fetches BOTH unread inbox and recent
spam in one shot so questions like "what's my most recent junk mail" can
be answered in a single turn — no CLIENT_TOOL round-trip.

Until 2026-04-26 v3 had no email-fetch path at all (the legacy v1 Gemma
router did the fetch but v3 inherited none of it), so Opus would receive
the class_protocol — which describes an `[EMAIL INBOX DATA]` block — but
no actual data, and reply "I don't see any email data loaded." This module
closes that gap by owning the fetch alongside the class metadata, mirroring
how `delete_messages` and `read_messages` handle their own data injection.
"""

import datetime
import logging

_logger = logging.getLogger(__name__)


def _format_email_block(label: str, emails: list[dict]) -> str:
    if not emails:
        return f"{label}\nNone.\n[END]"
    lines = [label]
    for i, e in enumerate(emails, 1):
        sender = (e.get("sender") or "Unknown")[:80]
        subject = (e.get("subject") or "(no subject)")[:120]
        snippet = (e.get("snippet") or "").strip()[:200]
        when = (e.get("date") or "").strip()[:40]
        unread_tag = " (unread)" if e.get("is_unread") else ""
        lines.append(f"{i}. [{when}] {sender}{unread_tag}")
        lines.append(f"   Subject: {subject}")
        if snippet:
            lines.append(f"   Snippet: {snippet}")
    lines.append("[END]")
    return "\n".join(lines)


def _escalation_context() -> str:
    """Inject inbox + spam so Opus can answer "check my email", "any new
    emails", or "what's my most recent junk mail" in one turn.

    Two Gmail buckets are fetched sequentially (callable runs inside a
    sync context — see jane_v2/stage3_escalate.py:206):
      - is:unread (limit 10) — what the user usually means by "email"
      - in:spam   (limit 10) — what they mean by "junk" / "spam"
    """
    try:
        from agent_skills.email_tools import read_inbox
    except Exception as e:
        return f"[EMAIL ERROR]\nEmail tools failed to import: {e}\n[END]"

    parts = []
    creds_failed = False

    try:
        unread = read_inbox(limit=10, query="is:unread")
        parts.append(_format_email_block("[EMAIL INBOX — unread]", unread))
    except RuntimeError as e:
        creds_failed = True
        parts.append(
            "[EMAIL ERROR]\n"
            f"Gmail not set up: {e}\n"
            "Tell the user they need to sign in with Google on the Vessence "
            "web UI to enable email access.\n[END]"
        )
    except Exception as e:
        _logger.warning("read_email escalation: inbox fetch failed: %s", e)
        parts.append(f"[EMAIL INBOX — unread]\nFetch failed: {e}\n[END]")

    if not creds_failed:
        try:
            spam = read_inbox(limit=10, query="in:spam")
            parts.append(_format_email_block("[EMAIL SPAM — recent]", spam))
        except Exception as e:
            _logger.warning("read_email escalation: spam fetch failed: %s", e)
            parts.append(f"[EMAIL SPAM — recent]\nFetch failed: {e}\n[END]")

        parts.append(
            f"(Fetched at {datetime.datetime.utcnow().isoformat()}Z. "
            "Triage: personal/important emails first; skip obvious "
            "promo/marketing UNLESS the user asked about junk / spam / "
            "promotions — then summarize from the SPAM bucket. Quote sender "
            "and subject. Honor any specific sender or count the user named.)"
        )

    return "\n\n".join(parts)


PARAMS_SCHEMA = {
    "filter_sender": (
        "string|null — sender name the user asked about ('did Alice email me'). "
        "Null when the user wants the inbox overview."
    ),
    "unread_only": (
        "bool — true for 'new/unread/any new emails'. false for 'recent emails'."
    ),
    "importance": (
        "enum — one of: any | important. "
        "important when the user said 'important', 'urgent', 'real ones'. "
        "any otherwise."
    ),
    "limit": (
        "int|null — explicit cap ('top 5 emails'). Null = handler default."
    ),
}


METADATA = {
    "name": "read email",
    "priority": 10,
    "description": (
        "[read email]\n"
        "User wants Jane to check / read / summarize their email inbox or "
        "spam folder. Server fetches both buckets (inbox + spam) via the "
        "Gmail API (server-side, NOT the phone) and injects them as data "
        "blocks for Opus to triage. Routes that go here include 'check my "
        "email', 'any new emails', 'what's my most recent junk mail', "
        "'anything important in my inbox'.\n\n"
        "Example phrasings the user might say:\n"
        "  - \"check my email\"\n"
        "  - \"any new emails\"\n"
        "  - \"read my email\"\n"
        "  - \"what's in my inbox\"\n"
        "  - \"did Alice email me\"\n"
        "  - \"how many unread emails do I have\"\n"
        "  - \"any important email today\"\n"
        "  - \"what's my most recent junk mail\"\n"
        "  - \"any spam today\"\n\n"
        "Adversarial phrasings that LOOK LIKE 'read email' but ARE NOT:\n"
        "  - \"send an email to Bob\" → 'others' (Opus composes + sends)\n"
        "  - \"delete all spam emails\" → 'others' (bulk action not supported)\n"
        "  - \"archive the email from Alice\" → 'others'\n"
        "  - \"read my text messages\" → 'read messages' (SMS, not email)\n"
        "  - \"what did Bob say in his last email last week\" → 'others' (needs memory / search)"
    ),
    "params_schema": PARAMS_SCHEMA,
    "escalation_context": _escalation_context,
    "few_shot": [],
    "ack": "Checking your email…",
    "escalate_ack": "Let me check your email…",
}
