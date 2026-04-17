"""docs_tools.py — Google Docs API integration for Jane.

Read and edit Google Docs using the user's OAuth token. The Docs API
scope (https://www.googleapis.com/auth/documents) is requested during
Google Sign-In alongside Gmail and Calendar scopes.

Usage from Jane's brain / handlers:
    from agent_skills.docs_tools import read_doc, append_item, remove_item, replace_text

For the TODO list specifically:
    from agent_skills.docs_tools import todo_add_item, todo_remove_item
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from agent_skills.email_oauth import refresh_token_if_needed

_logger = logging.getLogger(__name__)

_DEFAULT_TODO_DOC_ID = os.environ.get(
    "TODO_DOC_ID", "1xYuVx0vATpUqqnaAzkh1kQD-LjzT1tvBGcEysx9uuIU"
)


def _service(user_id: str | None = None):
    token_data = refresh_token_if_needed(user_id)
    if token_data is None:
        raise RuntimeError(
            "No Google credentials available. Sign in with Google first."
        )
    granted = set(token_data.get("scope", "").split())
    docs_scopes = {
        "https://www.googleapis.com/auth/documents",
    }
    if not (granted & docs_scopes):
        raise RuntimeError(
            "Google Docs scope not granted. Please re-sign in with Google "
            "to grant Docs access."
        )
    creds = Credentials(
        token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("docs", "v1", credentials=creds, cache_discovery=False)


def read_doc(doc_id: str | None = None, user_id: str | None = None) -> dict[str, Any]:
    """Read a Google Doc and return its title + plain text content."""
    doc_id = doc_id or _DEFAULT_TODO_DOC_ID
    svc = _service(user_id)
    doc = svc.documents().get(documentId=doc_id).execute()
    title = doc.get("title", "")
    body = doc.get("body", {})
    text = _extract_text(body)
    return {"title": title, "text": text, "doc_id": doc_id}


def _extract_text(body: dict) -> str:
    """Walk the Docs body JSON and extract plain text."""
    parts = []
    for elem in body.get("content", []):
        para = elem.get("paragraph")
        if not para:
            continue
        for pe in para.get("elements", []):
            tr = pe.get("textRun")
            if tr:
                parts.append(tr.get("content", ""))
    return "".join(parts)


def _find_end_of_section(text: str, section_name: str) -> int | None:
    """Find the character index at the end of a section (before the next
    section header or end of doc). Used for appending items."""
    lines = text.split("\n")
    in_section = False
    char_offset = 0
    last_content_end = None

    for line in lines:
        line_len = len(line) + 1  # +1 for newline
        stripped = line.strip()
        if stripped.lower() == section_name.lower():
            in_section = True
            char_offset += line_len
            continue
        if in_section:
            if stripped and not re.match(r"^\s*(?:\d+[.)]|\-|\*|•)\s+", line) and stripped:
                is_header = True
                # Check if next non-blank line is a list item
                # If so, this is a new section header — stop
                if is_header and last_content_end is not None:
                    return last_content_end
            if stripped:
                last_content_end = char_offset + line_len
        char_offset += line_len

    return last_content_end or char_offset


def append_text(
    doc_id: str,
    text: str,
    index: int | None = None,
    user_id: str | None = None,
) -> bool:
    """Append text at a specific index, or at the end of the doc."""
    svc = _service(user_id)
    if index is None:
        doc = svc.documents().get(documentId=doc_id).execute()
        body = doc.get("body", {})
        content = body.get("content", [])
        if content:
            index = content[-1].get("endIndex", 1) - 1
        else:
            index = 1

    requests = [
        {
            "insertText": {
                "location": {"index": index},
                "text": text,
            }
        }
    ]
    svc.documents().batchUpdate(
        documentId=doc_id, body={"requests": requests}
    ).execute()
    return True


def replace_text(
    doc_id: str,
    old_text: str,
    new_text: str,
    user_id: str | None = None,
) -> bool:
    """Find and replace text in a Google Doc."""
    svc = _service(user_id)
    requests = [
        {
            "replaceAllText": {
                "containsText": {
                    "text": old_text,
                    "matchCase": True,
                },
                "replaceText": new_text,
            }
        }
    ]
    result = svc.documents().batchUpdate(
        documentId=doc_id, body={"requests": requests}
    ).execute()
    replies = result.get("replies", [{}])
    replaced = replies[0].get("replaceAllText", {}).get("occurrencesChanged", 0)
    _logger.info("replace_text: %d occurrences changed", replaced)
    return replaced > 0


def delete_text(
    doc_id: str,
    text_to_delete: str,
    user_id: str | None = None,
) -> bool:
    """Delete specific text from a Google Doc (replace with empty string)."""
    return replace_text(doc_id, text_to_delete, "", user_id)


# ── TODO-specific helpers ─────────────────────────────────────────────────

def todo_add_item(
    item_text: str,
    category: str,
    doc_id: str | None = None,
    user_id: str | None = None,
) -> str:
    """Add a numbered item to a category in the TODO doc.

    Reads the doc, finds the section, appends after the last item.
    Returns a confirmation message.
    """
    doc_id = doc_id or _DEFAULT_TODO_DOC_ID
    doc_data = read_doc(doc_id, user_id)
    full_text = doc_data["text"]

    lines = full_text.split("\n")
    in_section = False
    last_item_num = 0
    insert_after_line = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.lower() == category.lower():
            in_section = True
            continue
        if in_section:
            m = re.match(r"^\s*(\d+)[.)]\s+", line)
            if m:
                last_item_num = int(m.group(1))
                insert_after_line = line
            elif stripped and not re.match(r"^\s*(?:\-|\*|•)\s+", line):
                break

    if insert_after_line is None:
        return f"Could not find category '{category}' in the doc."

    new_item = f"\n{last_item_num + 1}. {item_text}"
    success = replace_text(
        doc_id,
        insert_after_line,
        insert_after_line + new_item,
        user_id,
    )

    if success:
        return f"Added item #{last_item_num + 1} to {category}: {item_text}"
    return f"Failed to add item to {category}."


def todo_remove_item(
    item_text: str,
    category: str | None = None,
    doc_id: str | None = None,
    user_id: str | None = None,
) -> str:
    """Remove an item from the TODO doc by matching its text.

    Uses fuzzy matching — the item_text only needs to be a substring.
    Returns a confirmation message.
    """
    doc_id = doc_id or _DEFAULT_TODO_DOC_ID
    doc_data = read_doc(doc_id, user_id)
    full_text = doc_data["text"]

    target = item_text.lower().strip()
    for line in full_text.split("\n"):
        stripped = line.strip()
        if re.match(r"^\s*(?:\d+[.)]|\-|\*|•)\s+", line):
            item_body = re.sub(r"^\s*(?:\d+[.)]|\-|\*|•)\s+", "", line).strip()
            if target in item_body.lower():
                success = delete_text(doc_id, line + "\n", user_id)
                if success:
                    return f"Removed: {item_body}"
                return f"Found the item but failed to delete it."

    return f"Could not find an item matching '{item_text}' in the doc."
