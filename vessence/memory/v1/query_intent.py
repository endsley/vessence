"""Pure query intent helpers for memory retrieval."""

from __future__ import annotations

import re

from memory.v1.query_markers import get_file_markers, get_personal_markers, get_project_markers

STATIC_FILE_MARKERS = (
    "file",
    "folder",
    "document",
    "pdf",
    "image",
    "photo",
    "audio",
    "video",
    "vault",
    "path",
    "where is that file",
    "where's that file",
    "where did i save",
    "where is the file",
    "where's the file",
    "do i have a file",
    "find a file",
    "find the file",
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".png",
    ".jpg",
)


def is_file_index_record(doc: str, meta: dict | None) -> bool:
    meta = meta or {}
    topic = str(meta.get("topic", "")).lower()
    subtopic = str(meta.get("subtopic", "")).lower()
    memory_type = str(meta.get("memory_type", "")).lower()
    source = str(meta.get("source", "")).lower()
    text = str(doc or "").lower()
    return (
        topic in {"vault_file", "file_index"}
        or subtopic == "vault_file"
        or memory_type == "file_index"
        or source == "vault"
        or text.startswith("vault file:")
        or text.startswith("saved file '")
        or text.startswith("a file named '")
        or text.startswith("the user has a file named '")
        or text.startswith("the user has and stores ")
        or " stored at " in text and "/vault/" in text
        or " saved in the '" in text
        or " location: documents/" in text
    )


def is_file_query(query: str) -> bool:
    q = (query or "").lower()
    return any(marker in q for marker in STATIC_FILE_MARKERS + get_file_markers())


def classify_query_intent(query: str) -> str:
    q = (query or "").lower().strip()
    if is_file_query(q):
        return "file_lookup"
    if any(marker in q for marker in get_project_markers()):
        return "project_work"
    if any(marker in q for marker in get_personal_markers()) or (len(q) <= 40 and "?" in q):
        return "personal_lookup"
    return "general"


def ds3000_lecture_subtopics(query: str) -> list[str]:
    """Return exact DS3000 lecture-anchor subtopics mentioned in a query."""
    q = (query or "").lower()
    if "ds3000" not in q and "lecture" not in q:
        return []

    subtopics: list[str] = []

    def add(value: str) -> None:
        if value and value not in subtopics:
            subtopics.append(value)

    for match in re.finditer(r"\b(?:ds\s*3000|ds3000)?\s*lecture\s*0*(\d{1,2})(a?)\b", q):
        number = int(match.group(1))
        suffix = match.group(2) or ""
        if 1 <= number <= 99:
            add(f"lecture_{number}{suffix}")

    if re.search(r"\bappendix\b", q):
        add("appendix")

    if (
        "ds3000" in q
        and "lecture" in q
        and any(marker in q for marker in ("series", "index", "all lectures", "entire lecture"))
    ):
        add("series_index")

    return subtopics
