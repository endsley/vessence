#!/usr/bin/env python3
"""Query the live Ambient ChromaDB stores using the current Vessence code.

Includes a disk-based similarity cache so repeated/similar queries across
Claude Code hook invocations skip the Gemma librarian call entirely.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("VESSENCE_HOME", str(Path(__file__).resolve().parents[1])))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent_skills.memory.v1.memory_retrieval import build_memory_sections
from jane.config import VECTOR_DB_DIR, VESSENCE_DATA_HOME

LIVE_VECTOR_ROOT = Path(VECTOR_DB_DIR)
search_memory.VECTOR_DB_USER_MEMORIES = str(LIVE_VECTOR_ROOT)
search_memory.VECTOR_DB_SHORT_TERM = str(LIVE_VECTOR_ROOT / "short_term_memory")
search_memory.VECTOR_DB_LONG_TERM = str(LIVE_VECTOR_ROOT / "long_term_memory")

CACHE_FILE = Path(VESSENCE_DATA_HOME) / "data" / "memory_hook_cache.json"
CACHE_TTL_SECS = 300  # 5 minutes
CACHE_MAX_ENTRIES = 20
CACHE_SIMILARITY_THRESHOLD = 0.92


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a <= 0 or norm_b <= 0:
        return -1.0
    return dot / (norm_a * norm_b)


def _embed_query(query: str) -> list[float] | None:
    try:
        from agent_skills.memory.v1.memory_retrieval import _embed_query_text
        return _embed_query_text(query)
    except Exception:
        return None


def _load_cache() -> list[dict]:
    if not CACHE_FILE.exists():
        return []
    try:
        entries = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        now = time.time()
        return [e for e in entries if now - e.get("ts", 0) < CACHE_TTL_SECS]
    except Exception:
        return []


def _save_cache(entries: list[dict]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    trimmed = sorted(entries, key=lambda e: e.get("ts", 0), reverse=True)[:CACHE_MAX_ENTRIES]
    try:
        CACHE_FILE.write_text(json.dumps(trimmed), encoding="utf-8")
    except Exception:
        pass


def _lookup_cache(query_embedding: list[float], entries: list[dict]) -> str | None:
    for entry in entries:
        cached_emb = entry.get("emb")
        if not cached_emb:
            continue
        sim = _cosine_similarity(query_embedding, cached_emb)
        if sim >= CACHE_SIMILARITY_THRESHOLD:
            return entry.get("summary")
    return None


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Query live Ambient ChromaDB memory stores")
    parser.add_argument("query", nargs="*", default=["session", "start"], help="Query text")
    parser.add_argument("--essence-path", default=None, help="Path to essence ChromaDB directory")
    args = parser.parse_args()
    query = " ".join(args.query).strip() or "session start"
    essence_path = args.essence_path

    # Try cache lookup first
    query_embedding = _embed_query(query)
    if query_embedding:
        cache_entries = _load_cache()
        cached = _lookup_cache(query_embedding, cache_entries)
        if cached:
            print(cached)
            return 0

    # Cache miss — retrieve from ChromaDB (direct sections, no Ollama librarian)
    sections = build_memory_sections(query, assistant_name="Jane", essence_chromadb_path=essence_path)
    if not sections:
        print("No relevant context found.")
        return 0
    summary = "\n\n".join(sections)

    # Store in cache for next call
    if query_embedding and summary and summary != "No relevant context found.":
        cache_entries = _load_cache()
        cache_entries.insert(0, {
            "query": query[:200],
            "emb": query_embedding,
            "summary": summary,
            "ts": time.time(),
        })
        _save_cache(cache_entries)

    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
