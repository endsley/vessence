"""Shared email metadata helpers for read/delete class escalation blocks."""
from __future__ import annotations

import logging
from collections.abc import Callable


def format_email_block(
    label: str,
    emails: list[dict],
    *,
    include_message_id: bool = False,
    include_snippet: bool = True,
    include_unread_tag: bool = True,
) -> str:
    if not emails:
        return f"{label}\nNone.\n[END]"

    lines = [label]
    for index, email in enumerate(emails, 1):
        lines.extend(
            email_row_lines(
                index,
                email,
                include_message_id=include_message_id,
                include_snippet=include_snippet,
                include_unread_tag=include_unread_tag,
            )
        )
    lines.append("[END]")
    return "\n".join(lines)


def email_row_lines(
    index: int,
    email: dict,
    *,
    include_message_id: bool = False,
    include_snippet: bool = True,
    include_unread_tag: bool = True,
) -> list[str]:
    sender = (email.get("sender") or "Unknown")[:80]
    subject = (email.get("subject") or "(no subject)")[:120]
    snippet = (email.get("snippet") or "").strip()[:200]
    when = (email.get("date") or "").strip()[:40]
    unread_tag = " (unread)" if include_unread_tag and email.get("is_unread") else ""
    id_part = ""
    if include_message_id:
        msg_id = (email.get("message_id") or email.get("id") or "").strip()
        id_part = f"id={msg_id} "

    lines = [f"{index}. {id_part}[{when}] {sender}{unread_tag}"]
    lines.append(f"   Subject: {subject}")
    if include_snippet and snippet:
        lines.append(f"   Snippet: {snippet}")
    return lines


def gmail_setup_error_block(error: Exception) -> str:
    return (
        "[EMAIL ERROR]\n"
        f"Gmail not set up: {error}\n"
        "Tell the user they need to sign in with Google on the Vessence "
        "web UI to enable email access.\n[END]"
    )


def email_fetch_failed_block(label: str, error: Exception) -> str:
    return f"{label}\nFetch failed: {error}\n[END]"


def fetch_email_bucket(
    read_inbox_fn: Callable[..., list[dict]],
    *,
    label: str,
    limit: int,
    query: str,
    warning_context: str,
    logger: logging.Logger,
    log_prefix: str,
    include_message_id: bool = False,
) -> tuple[str, bool]:
    try:
        emails = read_inbox_fn(limit=limit, query=query)
        return format_email_block(label, emails, include_message_id=include_message_id), False
    except RuntimeError as e:
        return gmail_setup_error_block(e), True
    except Exception as e:
        logger.warning("%s escalation: %s fetch failed: %s", log_prefix, warning_context, e)
        return email_fetch_failed_block(label, e), False
