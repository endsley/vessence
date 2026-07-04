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

import logging

from jane_web.jane_v2.classes.context_footers import fetched_at_footer
from jane_web.jane_v2.classes.email_metadata_helpers import (
    email_fetch_failed_block as _shared_email_fetch_failed_block,
    fetch_email_bucket as _shared_fetch_email_bucket,
    format_email_block as _shared_format_email_block,
    gmail_setup_error_block as _shared_gmail_setup_error_block,
)

_logger = logging.getLogger(__name__)


def _format_email_block(label: str, emails: list[dict]) -> str:
    return _shared_format_email_block(label, emails)


def _gmail_setup_error_block(error: Exception) -> str:
    return _shared_gmail_setup_error_block(error)


def _email_fetch_failed_block(label: str, error: Exception) -> str:
    return _shared_email_fetch_failed_block(label, error)


def _read_email_bucket(
    read_inbox_fn,
    *,
    label: str,
    limit: int,
    query: str,
    warning_context: str,
) -> tuple[str, bool]:
    return _shared_fetch_email_bucket(
        read_inbox_fn,
        label=label,
        limit=limit,
        query=query,
        warning_context=warning_context,
        logger=_logger,
        log_prefix="read_email",
    )


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

    block, creds_failed = _read_email_bucket(
        read_inbox,
        label="[EMAIL INBOX — unread]",
        limit=10,
        query="is:unread",
        warning_context="inbox",
    )
    parts.append(block)

    if not creds_failed:
        block, _ = _read_email_bucket(
            read_inbox,
            label="[EMAIL SPAM — recent]",
            limit=10,
            query="in:spam",
            warning_context="spam",
        )
        parts.append(block)

        parts.append(
            fetched_at_footer(
                "Triage: personal/important emails first; skip obvious "
                "promo/marketing UNLESS the user asked about junk / spam / "
                "promotions — then summarize from the SPAM bucket. Quote sender "
                "and subject. Honor any specific sender or count the user named."
            )
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
