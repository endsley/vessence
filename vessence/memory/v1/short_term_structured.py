"""Structured short-term memory JSON and flattening helpers."""
from __future__ import annotations

from typing import Any
import json
import re

from jane.json_scanner import find_json_object_end


EXTRACT_KEYS = (
    "purpose",
    "scope",
    "outcome",
    "current_status",
    "facts",
    "decisions",
    "open_loops",
    "artifacts",
    "people",
    "time_refs",
)
LABEL_ORDER = [
    ("purpose", "Point"),
    ("scope", "Scope"),
    ("outcome", "Outcome"),
    ("current_status", "Current status"),
    ("decisions", "Decisions"),
    ("open_loops", "Open loops"),
    ("artifacts", "Artifacts"),
    ("facts", "Facts"),
    ("people", "People"),
    ("time_refs", "Time"),
]


def empty_extracted() -> dict[str, list[str]]:
    return {key: [] for key in EXTRACT_KEYS}


def parse_json_blob(blob: str) -> dict[str, list[str]] | None:
    """Tolerant JSON parse: strips code fences and finds the first object."""
    if not blob:
        return None
    text = blob.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    start = text.find("{")
    if start == -1:
        return None

    end = find_json_object_end(text, start)
    if end is None:
        return None

    try:
        obj = json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(obj, dict):
        return None

    out = empty_extracted()
    for key in EXTRACT_KEYS:
        value = obj.get(key, [])
        if isinstance(value, list):
            out[key] = [str(item).strip() for item in value if str(item).strip()]
        elif isinstance(value, str):
            value = value.strip()
            if value:
                out[key] = [value]
    return out


def should_skip(extracted: dict[str, list[str]]) -> bool:
    """Keep only notes with concrete work detail, decisions, open loops, or artifacts."""
    if not extracted:
        return True
    return not (
        bool(extracted.get("purpose"))
        or bool(extracted.get("scope"))
        or bool(extracted.get("outcome"))
        or bool(extracted.get("current_status"))
        or bool(extracted.get("decisions"))
        or bool(extracted.get("open_loops"))
        or bool(extracted.get("artifacts"))
    )


def flatten_to_note(extracted: dict[str, list[str]]) -> str:
    """Render labeled note lines, skipping empty categories."""
    parts: list[str] = []
    for key, label in LABEL_ORDER:
        items = extracted.get(key) or []
        items_clean = [str(item).strip() for item in items if str(item).strip()]
        if not items_clean:
            continue
        parts.append(f"{label}: {'; '.join(items_clean)}")
    return "\n".join(parts).strip()


def flatten_to_search_text(extracted: dict[str, list[str]]) -> str:
    """Return label-stripped text used as the embedding input."""
    parts: list[str] = []
    for key, _label in LABEL_ORDER:
        for item in extracted.get(key) or []:
            text = str(item).strip()
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def metadata_join_items(items: list[str], cap: int = 8) -> str:
    return " | ".join(str(item).strip() for item in (items or [])[:cap] if str(item).strip())


def flatten_to_metadata(kind: str, extracted: dict[str, list[str]]) -> dict[str, Any]:
    """Build Chroma-compatible primitive metadata for a structured note."""
    return {
        "turn_kind": kind,
        "has_open_loop": bool(extracted.get("open_loops")),
        "has_decision": bool(extracted.get("decisions")),
        "has_artifact": bool(extracted.get("artifacts")),
        "has_work_detail": bool(
            extracted.get("purpose")
            or extracted.get("scope")
            or extracted.get("outcome")
            or extracted.get("current_status")
        ),
        "work_purpose": metadata_join_items(extracted.get("purpose") or [], cap=4),
        "work_scope": metadata_join_items(extracted.get("scope") or [], cap=4),
        "work_outcome": metadata_join_items(extracted.get("outcome") or [], cap=4),
        "current_status": metadata_join_items(extracted.get("current_status") or [], cap=4),
        "artifact_paths": metadata_join_items(extracted.get("artifacts") or []),
        "person_names": metadata_join_items(extracted.get("people") or []),
        "time_refs": metadata_join_items(extracted.get("time_refs") or []),
        "n_purpose": len(extracted.get("purpose") or []),
        "n_scope": len(extracted.get("scope") or []),
        "n_outcome": len(extracted.get("outcome") or []),
        "n_current_status": len(extracted.get("current_status") or []),
        "n_facts": len(extracted.get("facts") or []),
        "n_decisions": len(extracted.get("decisions") or []),
        "n_open_loops": len(extracted.get("open_loops") or []),
    }


def short_term_memory_metadata(
    *,
    session_id: str,
    timestamp: str,
    expires_at: str,
    raw_text: str,
    note: str,
    extracted_meta: dict[str, Any],
) -> dict[str, Any]:
    """Build the full Chroma metadata shape for a structured short-term note."""
    return {
        "session_id": session_id,
        "timestamp": timestamp,
        "expires_at": expires_at,
        "memory_type": "short_term",
        "author": "conversation_manager",
        "topic": "turn_memory",
        "role": "turn",
        "raw_chars": len(raw_text),
        "summary_chars": len(note),
        **extracted_meta,
    }
