"""Pure helpers for Google Doc TODO parsing and cache payloads."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any


LOGIN_WALL_MARKERS = (
    "<html",
    "<!DOCTYPE html",
    "Sign in - Google Accounts",
    "google.com/accounts",
    "ServiceLogin",
)

TODO_TITLE_LINES = ("todo list", "todos", "to do list")

LIST_MARKER_RE = re.compile(r"^\s*(?:\d+[.)]|\-|\*|•)\s+")


def export_url(doc_id: str) -> str:
    return f"https://docs.google.com/document/d/{doc_id}/export?format=txt"


def decode_doc_body(body_bytes: bytes) -> str:
    try:
        return body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return body_bytes.decode("utf-8", errors="replace")


def is_login_wall_body(
    body: str,
    markers: Sequence[str] = LOGIN_WALL_MARKERS,
    *,
    sample_chars: int = 2000,
) -> bool:
    body_lower = body[:sample_chars].lower()
    return any(marker.lower() in body_lower for marker in markers)


def strip_doc_bom(text: str) -> str:
    return text[1:] if text.startswith("\ufeff") else text


def is_todo_title_line(index: int, line: str) -> bool:
    return index == 0 and line.strip().lower() in TODO_TITLE_LINES


def list_item_text(raw_line: str) -> str | None:
    if not LIST_MARKER_RE.match(raw_line):
        return None
    return LIST_MARKER_RE.sub("", raw_line).strip()


def next_nonblank_index(lines: list[str], start: int) -> int:
    index = start
    while index < len(lines) and not lines[index].strip():
        index += 1
    return index


def is_category_header(lines: list[str], index: int) -> bool:
    next_index = next_nonblank_index(lines, index + 1)
    return next_index < len(lines) and list_item_text(lines[next_index]) is not None


def parse_categories(text: str) -> list[dict[str, Any]]:
    # Strip UTF-8 BOM that Google's export sometimes prepends.
    text = strip_doc_bom(text)
    lines = text.splitlines()
    result: list[dict[str, Any]] = []
    i = 0
    n = len(lines)

    while i < n:
        raw = lines[i]
        line = raw.strip()
        if not line:
            i += 1
            continue

        # Skip the doc title on its own line if present at top.
        if is_todo_title_line(i, line):
            i += 1
            continue

        item_text = list_item_text(raw)
        if item_text is not None:
            # List item without a preceding header: attach to last category
            # or synthesize an "Uncategorized" bucket.
            if not result:
                result.append({"name": "Uncategorized", "items": []})
            result[-1]["items"].append(item_text)
            i += 1
            continue

        # Potential header: only confirm if the next non-blank line is a
        # list marker. This guards against free prose being treated as a
        # new category.
        if is_category_header(lines, i):
            result.append({"name": line, "items": []})
            i = next_nonblank_index(lines, i + 1)
            continue

        # Line isn't a header: drop it to keep prose and footer noise out.
        i += 1

    return result


def todo_item_count(categories: list[dict[str, Any]]) -> int:
    return sum(len(category["items"]) for category in categories)


def build_todo_cache_payload(
    categories: list[dict[str, Any]],
    raw_text: str,
    doc_id: str,
    *,
    fetched_at: str,
) -> dict[str, Any]:
    return {
        "fetched_at": fetched_at,
        "doc_id": doc_id,
        "source_url": export_url(doc_id),
        "categories": categories,
        "raw_text": raw_text,
    }
