"""fetch_todo_list.py — pull Chieh's Google Doc TODO, parse, cache.

Runs on a cron every 30 min. Downloads the plain-text export of the
configured Google Doc, parses the category headers + items, writes a
JSON cache at $VESSENCE_DATA_HOME/todo_list_cache.json. Jane's Stage 2
todo_list handler reads that cache directly, so the doc's truth becomes
instantly available to voice/chat without waiting on network I/O at
query time.

Config:
    TODO_DOC_ID         — Google Doc file ID (required; no default).
    TODO_CACHE_PATH     — override cache file path. Default:
                          $VESSENCE_DATA_HOME/todo_list_cache.json

Public sharing required: the doc must be shared as "Anyone with the
link — Viewer" (or more permissive). Private docs will 401/redirect
to a login page. We detect login-page HTML and fail fast with a clear
log message so the cache isn't overwritten with garbage.

Format of the cache:
    {
      "fetched_at": "2026-04-16T20:30:00Z",
      "doc_id": "1xYu...",
      "source_url": "https://docs.google.com/document/d/.../export?format=txt",
      "categories": [
        {"name": "Do it Immediately", "items": ["Deal with some important email."]},
        {"name": "For the clinic", "items": ["Curtain rods ...", "..."]},
        ...
      ],
      "raw_text": "<entire plain-text export, for debugging>"
    }
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
import sys
import urllib.request
from pathlib import Path

logger = logging.getLogger("fetch_todo_list")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

_VESSENCE_DATA_HOME = Path(os.environ.get(
    "VESSENCE_DATA_HOME",
    str(Path.home() / "ambient" / "vessence-data"),
))
_DEFAULT_CACHE = _VESSENCE_DATA_HOME / "todo_list_cache.json"

# Default doc ID points at Chieh's personal TODO. Can be overridden via env.
_DEFAULT_DOC_ID = "1xYuVx0vATpUqqnaAzkh1kQD-LjzT1tvBGcEysx9uuIU"


def _cache_path() -> Path:
    return Path(os.environ.get("TODO_CACHE_PATH", str(_DEFAULT_CACHE)))


def _doc_id() -> str:
    return os.environ.get("TODO_DOC_ID", _DEFAULT_DOC_ID)


def _export_url(doc_id: str) -> str:
    return f"https://docs.google.com/document/d/{doc_id}/export?format=txt"


# Headers indicating the response is a login wall rather than doc text.
_LOGIN_WALL_MARKERS = (
    "<html",
    "<!DOCTYPE html",
    "Sign in - Google Accounts",
    "google.com/accounts",
    "ServiceLogin",
)


def fetch_doc_text(doc_id: str | None = None, timeout: int = 30) -> str:
    """Download the plain-text export. Raises RuntimeError on failure.

    Follows the 307 redirect to the `docstext.googleusercontent.com`
    signed URL automatically (urllib handles it).
    """
    doc_id = doc_id or _doc_id()
    url = _export_url(doc_id)
    logger.info("Fetching TODO doc: %s", url)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Vessence-Jane-TodoFetcher/1.0",
            "Accept": "text/plain, text/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} fetching {url}")
        body_bytes = resp.read()
    try:
        body = body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        body = body_bytes.decode("utf-8", errors="replace")

    # Detect login-wall HTML — common when the doc isn't publicly shared.
    body_lower = body[:2000].lower()
    if any(m.lower() in body_lower for m in _LOGIN_WALL_MARKERS):
        raise RuntimeError(
            "Received HTML login page instead of doc text. "
            "Verify the doc is shared as 'Anyone with the link — Viewer'."
        )

    if not body.strip():
        raise RuntimeError("Empty body from doc export — doc may be empty or private.")
    return body


# ── Parser ───────────────────────────────────────────────────────────────────
#
# Doc structure is simple: single-line category headers (no markdown)
# followed by numbered list items, with blank lines between categories.
# Example:
#
#     Do it Immediately
#     1. Deal with some important email.
#
#
#     For my students
#     1. Write the recommendation letter
#
# A line is treated as a category header when it:
#   - is non-empty
#   - doesn't start with a list marker (number., -, *, •, tab)
#   - the following non-blank line starts with a list marker
#
# List items are extracted as the text after the marker. Items span only
# a single line (this matches the current doc style; if Chieh starts
# using multi-line items later, extend the parser).

_LIST_MARKER_RE = re.compile(r"^\s*(?:\d+[.)]|\-|\*|•)\s+")


def parse_categories(text: str) -> list[dict]:
    # Strip UTF-8 BOM that Google's export sometimes prepends.
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.splitlines()
    result: list[dict] = []
    i = 0
    n = len(lines)

    while i < n:
        raw = lines[i]
        line = raw.strip()
        if not line:
            i += 1
            continue

        # Skip the doc title "TODO list" on its own line if present at top.
        if i == 0 and line.lower() in ("todo list", "todos", "to do list"):
            i += 1
            continue

        if _LIST_MARKER_RE.match(raw):
            # List item without a preceding header — attach to last category
            # or synthesize an "Uncategorized" bucket.
            if not result:
                result.append({"name": "Uncategorized", "items": []})
            result[-1]["items"].append(_LIST_MARKER_RE.sub("", raw).strip())
            i += 1
            continue

        # Potential header: only confirm if the NEXT non-blank line is a
        # list marker. This guards against free prose being treated as a
        # new category.
        j = i + 1
        while j < n and not lines[j].strip():
            j += 1
        if j < n and _LIST_MARKER_RE.match(lines[j]):
            result.append({"name": line, "items": []})
            i = j
            continue

        # Line isn't a header — drop it (keeps prose + footer noise out).
        i += 1

    return result


def write_cache(
    categories: list[dict],
    raw_text: str,
    doc_id: str,
    path: Path | None = None,
) -> Path:
    path = path or _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "doc_id": doc_id,
        "source_url": _export_url(doc_id),
        "categories": categories,
        "raw_text": raw_text,
    }
    # Atomic write: temp file + os.replace. Protects the handler from
    # reading a half-written cache if the fetcher is killed mid-write.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp, path)
    return path


def main() -> int:
    try:
        doc_id = _doc_id()
        text = fetch_doc_text(doc_id)
        cats = parse_categories(text)
        total_items = sum(len(c["items"]) for c in cats)
        if not cats or total_items == 0:
            logger.warning(
                "Parsed 0 categories/items — cache left unchanged. "
                "Raw body starts with: %r", text[:200],
            )
            return 1
        path = write_cache(cats, text, doc_id)
        logger.info(
            "TODO cache updated: %d categories, %d items → %s",
            len(cats), total_items, path,
        )
        return 0
    except Exception as e:
        logger.error("Fetch failed: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
