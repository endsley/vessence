#!/usr/bin/env python3
"""Build a compact Jane startup digest from docs plus live Vessence memory."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import onnxruntime
# Silence the ONNX runtime warnings before chromadb import
onnxruntime.set_default_logger_severity(3)

import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jane.config import VAULT_DIR, VESSENCE_DATA_HOME, VESSENCE_HOME, VECTOR_DB_DIR

DATA_ROOT = Path(os.environ.get("JANE_DATA_ROOT", os.environ.get("JANE_AMBIENT_ROOT", VESSENCE_DATA_HOME)))
VESSENCE_ROOT = Path(VESSENCE_HOME)
DOCS_DIR = Path(VAULT_DIR) / "documents"
VECTOR_ROOT = Path(VECTOR_DB_DIR)

USER_MEMORIES = ("user_memories", VECTOR_ROOT, "user_memories")
SHORT_TERM = ("short_term_memory", VECTOR_ROOT / "short_term_memory", "short_term_memory")
LONG_TERM = ("long_term_knowledge", VECTOR_ROOT / "long_term_memory", "long_term_knowledge")

QUERY_SET = [
    "who is the user and who is Jane in relation to the user",
    "recent updates current status active work project vessence jane vault website docker public release",
    "family wife daughter important personal facts relationships preferences",
    "technical priorities architecture memory system jane wrapper prompt queue adk ollama chromadb",
]


@dataclass
class MemoryStore:
    label: str
    path: Path
    collection: str


def read_text(path: Path, limit: int = 2200) -> str:
    if not path.exists():
        return "(missing)"
    return path.read_text(encoding="utf-8", errors="replace")[:limit].strip()


def first_paragraph(text: str, limit: int = 700) -> str:
    text = text.strip()
    if not text:
        return "(empty)"
    para = text.split("\n\n", 1)[0].strip()
    return para[:limit]


def parse_ts(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    try:
        raw = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def age_label(value: object) -> str:
    dt = parse_ts(value)
    if not dt:
        return "unknown age"
    delta = datetime.now(timezone.utc) - dt
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def get_collection(store: MemoryStore):
    client = chromadb.PersistentClient(path=str(store.path))
    return client.get_collection(store.collection)


def collection_count(store: MemoryStore) -> str:
    try:
        return str(get_collection(store).count())
    except Exception as exc:
        return f"error: {exc}"


def recent_entries(store: MemoryStore, limit: int = 5) -> list[str]:
    try:
        col = get_collection(store)
        data = col.get(include=["documents", "metadatas"])
    except Exception as exc:
        return [f"(error: {exc})"]

    rows = []
    for doc, meta in zip(data.get("documents", []), data.get("metadatas", [])):
        meta = meta or {}
        ts = meta.get("timestamp") or meta.get("created_at") or meta.get("expires_at")
        rows.append((parse_ts(ts) or datetime.min.replace(tzinfo=timezone.utc), doc, meta))

    rows.sort(key=lambda item: item[0], reverse=True)
    out = []
    for _, doc, meta in rows[:limit]:
        ts = meta.get("timestamp") or meta.get("created_at") or "no-timestamp"
        topic = meta.get("topic") or meta.get("source") or meta.get("memory_type") or "general"
        out.append(f"- [{str(ts)[:19]} | {age_label(ts)}] ({topic}) {str(doc).strip()[:220]}")
    return out or ["(no entries)"]


def query_entries(stores: list[MemoryStore], query: str, limit: int = 3) -> list[str]:
    lines = []
    for store in stores:
        try:
            col = get_collection(store)
            n = min(limit, col.count())
            if n <= 0:
                continue
            result = col.query(query_texts=[query], n_results=n, include=["documents", "metadatas"])
            docs = result.get("documents", [[]])[0]
            metas = result.get("metadatas", [[]])[0]
            if not docs:
                continue
            lines.append(f"- {store.label}:")
            for doc, meta in zip(docs, metas):
                meta = meta or {}
                ts = meta.get("timestamp") or meta.get("created_at") or "no-timestamp"
                topic = meta.get("topic") or meta.get("source") or meta.get("memory_type") or "general"
                lines.append(f"  [{str(ts)[:19]} | {age_label(ts)}] ({topic}) {str(doc).strip()[:220]}")
        except Exception as exc:
            lines.append(f"- {store.label}: error: {exc}")
    return lines or ["- no matches"]


def main() -> None:
    stores = [
        MemoryStore(*USER_MEMORIES),
        MemoryStore(*SHORT_TERM),
        MemoryStore(*LONG_TERM),
    ]

    print("# Jane Startup Digest")
    print()
    print(f"- Data root: `{DATA_ROOT}`")
    print(f"- Vessence root: `{VESSENCE_ROOT}`")
    print(f"- Vault root: `{Path(VAULT_DIR)}`")
    print(f"- Generated: `{datetime.now().astimezone().isoformat(timespec='seconds')}`")
    print()

    print("## Identity")
    print(f"- User: {first_paragraph(read_text(DOCS_DIR / 'chieh_identity_essay.txt'))}")
    print(f"- Jane: {first_paragraph(read_text(DOCS_DIR / 'jane_identity_essay.txt'))}")
    user_profile = DATA_ROOT / "user_profile.md"
    if user_profile.exists():
        print(f"- user_profile.md: {first_paragraph(read_text(user_profile, 1200), 500)}")
    print()

    print("## Priority Docs")
    print(f"- TODO_PROJECTS.md: {first_paragraph(read_text(VESSENCE_ROOT / 'configs' / 'TODO_PROJECTS.md', 1600), 500)}")
    print(f"- active_spec.md: {first_paragraph(read_text(VESSENCE_ROOT / 'configs' / 'project_specs' / 'active_spec.md', 1200), 500)}")
    print(f"- current_task_state.json: {read_text(VESSENCE_ROOT / 'configs' / 'project_specs' / 'current_task_state.json', 400)}")
    print()

    print("## Prompt Queue")
    print(read_text(DOCS_DIR / "prompt_list.md", 1800))
    print()

    print("## Memory Store Counts")
    for store in stores:
        print(f"- {store.label}: `{store.path}` -> {collection_count(store)}")
    print()

    print("## Most Recent Memory Entries")
    for store in stores:
        print(f"### {store.label}")
        for line in recent_entries(store):
            print(line)
    print()

    print("## Query-Based Recall")
    for query in QUERY_SET:
        print(f"### {query}")
        for line in query_entries(stores, query):
            print(line)
        print()


if __name__ == "__main__":
    main()
