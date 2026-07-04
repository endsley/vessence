"""email_tools.py — Gmail API integration for Jane.

Provides read, send, and delete email capabilities using the user's
Gmail OAuth token.  The OAuth token is obtained during Google Sign-In
with the gmail.modify scope.

Usage from Jane's brain:
    [CLIENT_TOOL:email.read_inbox:{"limit": 10}]
    [CLIENT_TOOL:email.send:{"to": "bob@gmail.com", "subject": "Meeting", "body": "Hi Bob..."}]
    [CLIENT_TOOL:email.delete:{"message_id": "abc123"}]
"""
import base64
import logging
from email.mime.text import MIMEText
from typing import Any

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from agent_skills.email_oauth import list_gmail_token_users, refresh_token_if_needed
from agent_skills.email_message_helpers import (
    extract_attachments as _extract_attachments,
    extract_plain_body as _extract_plain_body,
    parse_headers as _parse_headers,
)

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Service builder
# ---------------------------------------------------------------------------

def get_gmail_service(
    credentials_json: dict | None = None,
    user_id: str | None = None,
):
    """Build an authorized Gmail API service.

    Args:
        credentials_json: Token dict with access_token, refresh_token, etc.
            If None, loads from disk via email_oauth.
        user_id: Optional Gmail account to load when credentials_json is None.

    Returns:
        googleapiclient.discovery.Resource for the Gmail API.

    Raises:
        RuntimeError: If no valid credentials are available.
    """
    token_data = credentials_json or refresh_token_if_needed(user_id)
    if token_data is None:
        if user_id:
            raise RuntimeError(
                f"No Gmail credentials available for {user_id}. "
                "Please sign in with Google first."
            )
        raise RuntimeError("No Gmail credentials available. Please sign in with Google first.")

    creds = Credentials(
        token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_inbox(limit: int = 10, query: str = "is:unread") -> list[dict[str, Any]]:
    """Read emails from the inbox.

    Args:
        limit: Maximum number of messages to return (default 10).
        query: Gmail search query (default "is:unread").

    Returns:
        List of dicts with: sender, subject, snippet, date, message_id, is_unread.
    """
    service = get_gmail_service()
    result = service.users().messages().list(
        userId="me", q=query, maxResults=limit
    ).execute()

    messages = result.get("messages", [])
    if not messages:
        return []

    emails = []
    for msg_stub in messages:
        msg = service.users().messages().get(
            userId="me", id=msg_stub["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()
        headers = _parse_headers(msg.get("payload", {}).get("headers", []))
        labels = msg.get("labelIds", [])
        emails.append({
            "sender": headers.get("from", ""),
            "subject": headers.get("subject", "(no subject)"),
            "snippet": msg.get("snippet", ""),
            "date": headers.get("date", ""),
            "message_id": msg["id"],
            "is_unread": "UNREAD" in labels,
        })

    return emails


def read_email(message_id: str) -> dict[str, Any]:
    """Read the full body of a specific email.

    Args:
        message_id: Gmail message ID.

    Returns:
        Dict with: sender, to, subject, date, body, attachments.
    """
    service = get_gmail_service()
    msg = service.users().messages().get(
        userId="me", id=message_id, format="full",
    ).execute()

    payload = msg.get("payload", {})
    headers = _parse_headers(payload.get("headers", []))
    body = _extract_plain_body(payload)
    attachments = _extract_attachments(payload)

    return {
        "sender": headers.get("from", ""),
        "to": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "subject": headers.get("subject", "(no subject)"),
        "date": headers.get("date", ""),
        "body": body,
        "attachments": attachments,
        "message_id": message_id,
        "thread_id": msg.get("threadId", ""),
    }


def _build_mime_email(
    *,
    body: str,
    sender: str,
    to: str,
    subject: str,
    cc: str | None = None,
    bcc: str | None = None,
) -> MIMEText:
    message = MIMEText(body)
    if sender:
        message["from"] = sender
    message["to"] = to
    message["subject"] = subject
    if cc:
        message["cc"] = cc
    if bcc:
        message["bcc"] = bcc
    return message


def send_email(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    from_email: str | None = None,
) -> dict[str, str]:
    """Send an email via the Gmail API.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain text email body.
        cc: Optional CC recipients (comma-separated).
        bcc: Optional BCC recipients (comma-separated).
        from_email: Optional authenticated Gmail account to send from.

    Returns:
        Dict with: message_id, thread_id, from_email.
    """
    token_data = refresh_token_if_needed(from_email)
    if token_data is None:
        if from_email:
            available = ", ".join(list_gmail_token_users()) or "none"
            raise RuntimeError(
                f"No Gmail credentials available for {from_email}. "
                f"Configured accounts: {available}. "
                "Please sign in with Google using that account first."
            )
        raise RuntimeError("No Gmail credentials available. Please sign in with Google first.")

    sender = token_data.get("user_id", from_email or "")
    service = get_gmail_service(token_data)

    message = _build_mime_email(
        body=body,
        sender=sender,
        to=to,
        subject=subject,
        cc=cc,
        bcc=bcc,
    )

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    sent = service.users().messages().send(
        userId="me", body={"raw": raw},
    ).execute()

    _logger.info(
        "Email sent: id=%s thread=%s from=%s",
        sent.get("id"),
        sent.get("threadId"),
        sender,
    )
    return {
        "message_id": sent.get("id", ""),
        "thread_id": sent.get("threadId", ""),
        "from_email": sender,
    }


def delete_email(message_id: str) -> bool:
    """Move an email to trash (not permanent delete).

    Args:
        message_id: Gmail message ID.

    Returns:
        True on success.
    """
    service = get_gmail_service()
    service.users().messages().trash(userId="me", id=message_id).execute()
    _logger.info("Email trashed: id=%s", message_id)
    return True


def search_emails(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search emails using Gmail query syntax.

    Args:
        query: Gmail search query (e.g. "from:bob subject:meeting").
        limit: Maximum number of results (default 10).

    Returns:
        Same format as read_inbox.
    """
    return read_inbox(limit=limit, query=query)


# ---------------------------------------------------------------------------
# CLI test entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(level=logging.INFO)

    action = sys.argv[1] if len(sys.argv) > 1 else "inbox"

    if action == "inbox":
        emails = read_inbox(limit=5)
        print(json.dumps(emails, indent=2, default=str))
    elif action == "read" and len(sys.argv) > 2:
        email = read_email(sys.argv[2])
        print(json.dumps(email, indent=2, default=str))
    elif action == "send" and len(sys.argv) > 4:
        from_email = sys.argv[5] if len(sys.argv) > 5 else None
        result = send_email(
            to=sys.argv[2],
            subject=sys.argv[3],
            body=sys.argv[4],
            from_email=from_email,
        )
        print(json.dumps(result, indent=2))
    elif action == "delete" and len(sys.argv) > 2:
        ok = delete_email(sys.argv[2])
        print("Deleted" if ok else "Failed")
    elif action == "search" and len(sys.argv) > 2:
        emails = search_emails(sys.argv[2])
        print(json.dumps(emails, indent=2, default=str))
    else:
        print("Usage: email_tools.py [inbox|read <id>|send <to> <subj> <body> [from_email]|delete <id>|search <query>]")
