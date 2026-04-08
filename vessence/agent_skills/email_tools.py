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

from agent_skills.email_oauth import refresh_token_if_needed

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Service builder
# ---------------------------------------------------------------------------

def get_gmail_service(credentials_json: dict | None = None):
    """Build an authorized Gmail API service.

    Args:
        credentials_json: Token dict with access_token, refresh_token, etc.
            If None, loads from disk via email_oauth.

    Returns:
        googleapiclient.discovery.Resource for the Gmail API.

    Raises:
        RuntimeError: If no valid credentials are available.
    """
    token_data = credentials_json or refresh_token_if_needed()
    if token_data is None:
        raise RuntimeError(
            "No Gmail credentials available. Please sign in with Google first."
        )

    creds = Credentials(
        token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_headers(headers: list[dict]) -> dict[str, str]:
    """Extract common headers from a Gmail message header list."""
    result: dict[str, str] = {}
    for h in headers:
        name = h.get("name", "").lower()
        if name in ("from", "to", "cc", "bcc", "subject", "date"):
            result[name] = h.get("value", "")
    return result


def _extract_plain_body(payload: dict) -> str:
    """Recursively extract the plain-text body from a message payload."""
    mime_type = payload.get("mimeType", "")

    # Simple single-part message
    if mime_type == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    # Multipart — recurse into parts
    for part in payload.get("parts", []):
        text = _extract_plain_body(part)
        if text:
            return text

    # Fallback: if only HTML exists, return it stripped (better than nothing)
    if mime_type == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            # Crude tag stripping — fine for LLM consumption
            import re
            return re.sub(r"<[^>]+>", "", html).strip()

    return ""


def _extract_attachments(payload: dict) -> list[dict]:
    """List attachment metadata (name, size, mime type) without downloading."""
    attachments = []
    for part in payload.get("parts", []):
        filename = part.get("filename")
        if filename:
            attachments.append({
                "filename": filename,
                "mime_type": part.get("mimeType", ""),
                "size": part.get("body", {}).get("size", 0),
                "attachment_id": part.get("body", {}).get("attachmentId", ""),
            })
        # Recurse into nested multipart
        attachments.extend(_extract_attachments(part))
    return attachments


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


def send_email(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
) -> dict[str, str]:
    """Send an email via the Gmail API.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain text email body.
        cc: Optional CC recipients (comma-separated).
        bcc: Optional BCC recipients (comma-separated).

    Returns:
        Dict with: message_id, thread_id.
    """
    service = get_gmail_service()

    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    if cc:
        message["cc"] = cc
    if bcc:
        message["bcc"] = bcc

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    sent = service.users().messages().send(
        userId="me", body={"raw": raw},
    ).execute()

    _logger.info("Email sent: id=%s thread=%s", sent.get("id"), sent.get("threadId"))
    return {
        "message_id": sent.get("id", ""),
        "thread_id": sent.get("threadId", ""),
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
        result = send_email(to=sys.argv[2], subject=sys.argv[3], body=sys.argv[4])
        print(json.dumps(result, indent=2))
    elif action == "delete" and len(sys.argv) > 2:
        ok = delete_email(sys.argv[2])
        print("Deleted" if ok else "Failed")
    elif action == "search" and len(sys.argv) > 2:
        emails = search_emails(sys.argv[2])
        print(json.dumps(emails, indent=2, default=str))
    else:
        print("Usage: email_tools.py [inbox|read <id>|send <to> <subj> <body>|delete <id>|search <query>]")
