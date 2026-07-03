"""Pure result helpers for server-side email tool execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EmailSendRequest:
    to: str
    subject: str
    body: str
    from_email: str | None


def format_inbox_emails(emails: Sequence[Mapping[str, Any]]) -> str:
    if not emails:
        return "\n\nNo unread emails found."

    lines = [f"\n\nFound {len(emails)} email(s):\n"]
    for email in emails:
        status = "NEW" if email.get("is_unread") else "read"
        lines.append(f"- [{status}] From: {email['sender']} — {email['subject']}")
        if email.get("snippet"):
            lines.append(f"  Preview: {email['snippet'][:150]}")
    return "\n".join(lines)


def format_email_readback(email_data: Mapping[str, Any]) -> str:
    body = (email_data.get("body") or "")[:2000]
    return (
        f"\n\nEmail from {email_data.get('sender', '?')}:\n"
        f"Subject: {email_data.get('subject', '?')}\n"
        f"Date: {email_data.get('date', '?')}\n\n"
        f"{body}"
    )


def format_email_search_results(
    query: str,
    emails: Sequence[Mapping[str, Any]],
) -> str:
    if not emails:
        return f"\n\nNo emails found for query: {query}"

    lines = [f"\n\nSearch results ({len(emails)} emails):\n"]
    for email in emails:
        lines.append(f"- From: {email['sender']} — {email['subject']}")
    return "\n".join(lines)


def prepare_send_email_args(args: Mapping[str, Any]) -> tuple[EmailSendRequest | None, str | None]:
    to = (args.get("to") or "").strip()
    subject = (args.get("subject") or "").strip()
    body = (args.get("body") or "").strip()
    from_email = (
        args.get("from_email")
        or args.get("from")
        or args.get("sender")
        or ""
    ).strip() or None

    if not to:
        return None, "\n\nEmail not sent: no recipient address provided."
    if not body:
        return None, "\n\nEmail not sent: empty body."

    return EmailSendRequest(
        to=to,
        subject=subject,
        body=body,
        from_email=from_email,
    ), None


def format_sent_email_status(
    result: Mapping[str, Any],
    request: EmailSendRequest,
) -> tuple[str, str]:
    sender = result.get("from_email") or request.from_email or "default Gmail account"
    return sender, f"\n\n[Email sent from {sender} to {request.to}.]"
