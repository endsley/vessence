"""docs_tools.py — Google Docs API integration for Jane.

Read and edit Google Docs using the user's OAuth token. The Docs API
scope (https://www.googleapis.com/auth/documents) is requested during
Google Sign-In alongside Gmail and Calendar scopes.

Usage from Jane's brain / handlers:
    from agent_skills.docs_tools import read_doc, append_item, remove_item, replace_text

For the TODO list specifically:
    from agent_skills.docs_tools import todo_add_item, todo_remove_item, todo_add_category
"""
from __future__ import annotations

import logging
import os
from typing import Any

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from agent_skills.docs_editing_helpers import (
    build_insert_text_request,
    build_replace_all_text_request,
    build_todo_category_section,
    extract_text as _extract_text,
    find_end_of_section as _find_end_of_section,
    plan_todo_add_item,
    plan_todo_remove_item,
    todo_category_exists,
)
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

    requests = [build_insert_text_request(index, text)]
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
    requests = [build_replace_all_text_request(old_text, new_text)]
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
    """Add an item to a category in the TODO doc.

    Reads the doc, finds the section, and appends after the last item.
    Supports both numbered lists and the live TODO doc's plain-line format.
    Returns a confirmation message.
    """
    doc_id = doc_id or _DEFAULT_TODO_DOC_ID
    doc_data = read_doc(doc_id, user_id)
    full_text = doc_data["text"]

    plan = plan_todo_add_item(full_text, item_text, category)
    if plan is None:
        return f"Could not find category '{category}' in the doc."

    success = replace_text(
        doc_id,
        plan.old_text,
        plan.new_text,
        user_id,
    )

    if success:
        return plan.success_message
    return plan.failure_message


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

    plan = plan_todo_remove_item(full_text, item_text, category)
    if plan is not None:
        success = replace_text(doc_id, plan.old_text, plan.new_text, user_id)
        if success:
            return plan.success_message
        return plan.failure_message

    return f"Could not find an item matching '{item_text}' in the doc."


def todo_add_category(
    category_name: str,
    doc_id: str | None = None,
    user_id: str | None = None,
) -> str:
    """Add a new category section to the TODO doc.

    Appends a header + '1. Nothing' placeholder at the end of the doc.
    Returns a confirmation message.
    """
    doc_id = doc_id or _DEFAULT_TODO_DOC_ID
    doc_data = read_doc(doc_id, user_id)
    full_text = doc_data["text"]

    if todo_category_exists(full_text, category_name):
        return f"Category '{category_name}' already exists."

    new_section = build_todo_category_section(category_name)
    success = append_text(doc_id, new_section, user_id=user_id)
    if success:
        return f"Added new category: {category_name}"
    return f"Failed to add category '{category_name}'."
