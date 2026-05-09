#!/usr/bin/env python3
"""claude_stop_short_term.py — unified short-term writer for Claude Code (Jane CLI).

Wired in as a Stop hook so each Claude Code turn gets the SAME structured
extraction as Jane web. Both surfaces now write through
``memory.v1.short_term_extractor.build_short_term_note`` (Haiku-backed,
per-kind extraction with skip-gate). Replaces the old freeform Ollama
summarizer that lived in ``llm_summarize.py`` (deleted) and an orphan
pattern-matcher in ``stop_hook_memory.py`` (no longer wired).

Hook input on stdin: ``{"session_id": "...", "transcript_path": "...", "stop_hook_active": bool}``
Schema match: same metadata + ``summary_style="structured_short_term_v1"``
as the web writer; only ``author`` differs (``"claude_code_stop_hook"``).
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import uuid
from pathlib import Path

_HOME = Path.home()
_AMBIENT = Path(os.environ.get("AMBIENT_BASE", str(_HOME / "ambient")))
VESSENCE_HOME = os.environ.get("VESSENCE_HOME", str(_AMBIENT / "vessence"))
sys.path.insert(0, VESSENCE_HOME)


def _read_stdin() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def _find_transcript(data: dict) -> Path | None:
    """Prefer the explicit transcript_path Claude Code provides; fall back to
    locating the JSONL by session_id under ~/.claude/projects/."""
    tp = data.get("transcript_path")
    if tp and Path(tp).exists():
        return Path(tp)
    sid = data.get("session_id")
    if not sid:
        return None
    for f in (_HOME / ".claude" / "projects").rglob(f"{sid}.jsonl"):
        return f
    return None


def _get_last_turn(transcript: Path) -> tuple[str, str]:
    """Return (user_msg, assistant_msg) for the most recent complete turn.
    Walks the JSONL transcript in reverse and grabs the latest non-empty
    user + assistant texts."""
    try:
        lines = transcript.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    except Exception:
        return "", ""
    user_msg = assistant_msg = ""
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except Exception:
            continue
        msg = entry.get("message", {})
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, list):
            text = " ".join(
                c.get("text", "") for c in content
                if isinstance(c, dict) and c.get("type") == "text"
            ).strip()
        else:
            text = str(content).strip()
        if not text:
            continue
        # Cap each side so we don't shovel the entire conversation into Haiku.
        if not assistant_msg and role == "assistant":
            assistant_msg = text[:4000]
        elif not user_msg and role == "user":
            user_msg = text[:2000]
        if user_msg and assistant_msg:
            break
    return user_msg, assistant_msg


def _strip_protocol(s: str) -> str:
    """Light cleaner mirroring ConversationManager._strip_injected_metadata —
    drops common protocol blocks before extraction so they don't pollute the
    LLM prompt."""
    if not s:
        return ""
    import re
    patterns = [
        r"<system-reminder>.*?</system-reminder>",
        r"<class_protocol>.*?</class_protocol>",
        r"\[EXTRACTED PARAMS\].*?\[/EXTRACTED PARAMS\]",
        r"\[CALENDAR DATA\].*?\[/CALENDAR DATA\]",
        r"\[EMAIL INBOX DATA\].*?\[/EMAIL INBOX DATA\]",
        r"<command-name>.*?</command-name>",
        r"<command-message>.*?</command-message>",
        r"<command-args>.*?</command-args>",
        r"<local-command-stdout>.*?</local-command-stdout>",
        r"<task-notification>.*?</task-notification>",
    ]
    for p in patterns:
        s = re.sub(p, "", s, flags=re.DOTALL)
    return s.strip()


def main() -> int:
    data = _read_stdin()

    # Avoid recursion if our own write triggered a stop event.
    if data.get("stop_hook_active"):
        return 0

    transcript = _find_transcript(data)
    if not transcript:
        return 0

    user_msg, assistant_msg = _get_last_turn(transcript)
    if not user_msg and not assistant_msg:
        return 0

    # Build the structured note via the shared extractor.
    try:
        from memory.v1.short_term_extractor import build_short_term_note
        from jane.config import (
            VECTOR_DB_SHORT_TERM,
            CHROMA_COLLECTION_SHORT_TERM,
            SHORT_TERM_TTL_DAYS,
            get_chroma_client,
        )
    except Exception:
        return 0  # vessence env not available — degrade silently

    try:
        note, search_text, extracted_meta, skip = build_short_term_note(
            user_msg, assistant_msg, cleaner=_strip_protocol,
        )
    except Exception:
        return 0  # extractor crash — degrade silently
    if skip or not note.strip():
        return 0

    # Embed the label-stripped form for sharper retrieval; display = labeled.
    embeddings = None
    try:
        from memory.v1.embedding_helpers import embed_one
        embeddings = [embed_one(search_text)]
    except Exception:
        pass  # fall back to ChromaDB's default embedding on the labeled note

    # Write with the same schema the web writer uses.
    try:
        client = get_chroma_client(path=VECTOR_DB_SHORT_TERM)
        col = client.get_or_create_collection(name=CHROMA_COLLECTION_SHORT_TERM)
        now = datetime.datetime.utcnow()
        meta = {
            "session_id": data.get("session_id", "claude_code"),
            "timestamp": now.isoformat(),
            "expires_at": (now + datetime.timedelta(days=SHORT_TERM_TTL_DAYS)).isoformat(),
            "memory_type": "short_term",
            "author": "claude_code_stop_hook",
            "topic": "turn_memory",
            "role": "turn",
            "raw_chars": len(user_msg) + len(assistant_msg),
            "summary_chars": len(note),
            **extracted_meta,
        }
        kwargs = dict(ids=[str(uuid.uuid4())], documents=[note], metadatas=[meta])
        if embeddings is not None:
            kwargs["embeddings"] = embeddings
        col.add(**kwargs)
    except Exception:
        return 0  # ChromaDB unavailable / locked — degrade silently
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
