#!/usr/bin/env python3
"""Build a compact Jane startup digest from docs plus live Vessence memory."""
from __future__ import annotations

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
BOOTSTRAP_TTL_SECONDS = 20 * 60
CACHE_FILE = Path(VESSENCE_DATA_HOME) / "startup_cache" / "jane_bootstrap_digest.md"

USER_MEMORIES = ("user_memories", VECTOR_ROOT, "user_memories")
SHORT_TERM = ("short_term_memory", VECTOR_ROOT / "short_term_memory", "short_term_memory")
LONG_TERM = ("long_term_knowledge", VECTOR_ROOT / "long_term_memory", "long_term_knowledge")

QUERY_SET = [
    "who is the user and who is Jane in relation to the user",
    "recent updates current status active work project vessence jane vault website docker public release",
    "family wife daughter important personal facts relationships preferences",
    "technical priorities architecture memory system jane wrapper prompt queue adk ollama chromadb",
]
CACHE_HEADER = "## JANE_BOOTSTRAP_GENERATED_UTC="


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


def _resolve_ttl() -> int:
    raw = os.environ.get("JANE_BOOTSTRAP_TTL_SECONDS", str(BOOTSTRAP_TTL_SECONDS))
    try:
        return max(0, int(raw))
    except Exception:
        return BOOTSTRAP_TTL_SECONDS


def _resolve_cache_file() -> Path:
    return Path(os.environ.get("JANE_BOOTSTRAP_CACHE", str(CACHE_FILE)))


def _parse_cached(lines: list[str], ttl: int) -> str | None:
    if ttl <= 0 or not lines:
        return None

    if not lines[0].startswith(CACHE_HEADER):
        return None

    stamp = lines[0].replace(CACHE_HEADER, "").strip()
    try:
        generated = datetime.fromisoformat(stamp)
    except Exception:
        return None

    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)

    age = datetime.now(timezone.utc) - generated
    if age.total_seconds() > ttl:
        return None

    return "\n".join(lines[1:])


def _read_cache(path: Path, ttl: int) -> str | None:
    if not path.exists() or ttl <= 0:
        return None
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return None
    return _parse_cached(lines, ttl)


def _write_cache(path: Path, content: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = f"{CACHE_HEADER}{datetime.now(timezone.utc).isoformat()}\n{content}\n"
        path.write_text(payload, encoding="utf-8")
    except Exception:
        return


def build_bootstrap_digest(ttl: int) -> str:
    stores = [
        MemoryStore(*USER_MEMORIES),
        MemoryStore(*SHORT_TERM),
        MemoryStore(*LONG_TERM),
    ]

    lines: list[str] = []
    lines.append("# Jane Startup Digest")
    lines.append("")
    lines.append(f"- Data root: `{DATA_ROOT}`")
    lines.append(f"- Vessence root: `{VESSENCE_ROOT}`")
    lines.append(f"- Vault root: `{Path(VAULT_DIR)}`")
    lines.append(f"- Generated: `{datetime.now().astimezone().isoformat(timespec='seconds')}`")
    lines.append("")

    lines.append("## Identity")
    lines.append(f"- User: {first_paragraph(read_text(DOCS_DIR / 'user_identity_essay.txt'))}")
    lines.append(f"- Jane: {first_paragraph(read_text(DOCS_DIR / 'jane_identity_essay.txt'))}")
    user_profile = DATA_ROOT / "user_profile.md"
    if user_profile.exists():
        lines.append(f"- user_profile.md: {first_paragraph(read_text(user_profile, 1200), 500)}")
    lines.append("")

    lines.append("## Priority Docs")
    lines.append(f"- TODO_PROJECTS.md: {first_paragraph(read_text(VESSENCE_ROOT / 'configs' / 'TODO_PROJECTS.md', 1600), 500)}")
    lines.append(f"- active_spec.md: {first_paragraph(read_text(VESSENCE_ROOT / 'configs' / 'project_specs' / 'active_spec.md', 1200), 500)}")
    lines.append(f"- current_task_state.json: {read_text(VESSENCE_ROOT / 'configs' / 'project_specs' / 'current_task_state.json', 400)}")
    lines.append("")

    lines.append("## Prompt Queue")
    lines.append(read_text(DOCS_DIR / "prompt_list.md", 1800))
    lines.append("")

    lines.append("## Memory Store Counts")
    for store in stores:
        lines.append(f"- {store.label}: `{store.path}` -> {collection_count(store)}")
    lines.append("")

    lines.append("## Most Recent Memory Entries")
    for store in stores:
        lines.append(f"### {store.label}")
        for line in recent_entries(store):
            lines.append(line)
    lines.append("")

    lines.append("## Query-Based Recall")
    for query in QUERY_SET:
        lines.append(f"### {query}")
        for line in query_entries(stores, query):
            lines.append(line)
        lines.append("")

    lines.append(f"TTL policy: cached for {ttl}s unless `JANE_BOOTSTRAP_TTL_SECONDS` overrides.")
    return "\n".join(lines)


def main() -> None:
    ttl = _resolve_ttl()
    cache_path = _resolve_cache_file()
    cached = _read_cache(cache_path, ttl)
    if cached:
        print(cached.rstrip("\n"))
        return

    digest = build_bootstrap_digest(ttl)
    print(digest)
    if ttl > 0:
        _write_cache(cache_path, digest)


if __name__ == "__main__":
    main()
