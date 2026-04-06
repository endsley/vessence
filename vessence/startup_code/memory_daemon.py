#!/usr/bin/env python3
"""Memory Daemon — persistent FastAPI server for fast ChromaDB memory queries.

Loads ChromaDB clients and the ONNX embedding model ONCE on startup, then serves
memory queries over HTTP on port 8083. Eliminates the ~1s import/model-load cost
that the previous fresh-process-per-query approach incurred.
"""

from __future__ import annotations

import datetime
import os
import sys
import threading
import time
from pathlib import Path

# Ensure Vessence root is on sys.path
ROOT = Path(os.environ.get("VESSENCE_HOME", str(Path(__file__).resolve().parents[1])))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("ORT_LOGGING_LEVEL", "3")
os.environ.setdefault("ONNXRUNTIME_EXECUTION_PROVIDERS", '["CPUExecutionProvider"]')

from fastapi import FastAPI
import uvicorn

app = FastAPI(title="Vessence Memory Daemon", docs_url=None, redoc_url=None)

# ---------- In-memory similarity cache ----------
CACHE_TTL_SECS = 300  # 5 minutes
CACHE_MAX_ENTRIES = 20
CACHE_SIMILARITY_THRESHOLD = 0.92

_cache_lock = threading.Lock()
_cache_entries: list[dict] = []


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a <= 0 or norm_b <= 0:
        return -1.0
    return dot / (norm_a * norm_b)


def _prune_cache() -> None:
    now = time.time()
    _cache_entries[:] = [e for e in _cache_entries if now - e.get("ts", 0) < CACHE_TTL_SECS]
    if len(_cache_entries) > CACHE_MAX_ENTRIES:
        _cache_entries[:] = sorted(_cache_entries, key=lambda e: e.get("ts", 0), reverse=True)[:CACHE_MAX_ENTRIES]


def _lookup_cache(query_embedding: list[float]) -> str | None:
    with _cache_lock:
        _prune_cache()
        for entry in _cache_entries:
            cached_emb = entry.get("emb")
            if not cached_emb:
                continue
            sim = _cosine_similarity(query_embedding, cached_emb)
            if sim >= CACHE_SIMILARITY_THRESHOLD:
                return entry.get("summary")
    return None


def _store_cache(query: str, query_embedding: list[float], summary: str) -> None:
    if not query_embedding or not summary:
        return
    with _cache_lock:
        _cache_entries.insert(0, {
            "query": query[:200],
            "emb": query_embedding,
            "summary": summary,
            "ts": time.time(),
        })
        _prune_cache()


# ---------- Startup: pre-load models ----------
@app.on_event("startup")
async def load_models():
    """Pre-load the ONNX embedding model and ChromaDB imports on startup."""
    from agent_skills.memory.v1.memory_retrieval import _embed_query_text, build_memory_sections  # noqa: F401
    import agent_skills.memory.v1.search_memory as search_memory  # noqa: F401
    from jane.config import VECTOR_DB_DIR  # noqa: F401

    # Warm up the ONNX model so first real query is fast
    _embed_query_text("warmup")


# ---------- Endpoints ----------
@app.get("/query")
async def query_memory(q: str, essence_path: str = ""):
    """Query ChromaDB memory stores and return formatted memory sections."""
    from agent_skills.memory.v1.memory_retrieval import _embed_query_text, build_memory_sections

    query = q.strip() or "session start"

    # Check in-memory cache first
    query_embedding = _embed_query_text(query)
    if query_embedding:
        cached = _lookup_cache(query_embedding)
        if cached:
            return {"result": cached}

    # Cache miss — query ChromaDB
    essence = essence_path.strip() or None
    if essence and not os.path.exists(essence):
        essence = None

    sections = build_memory_sections(query, assistant_name="Jane", essence_chromadb_path=essence)
    if not sections:
        return {"result": "No relevant context found."}

    summary = "\n\n".join(sections)

    # Store in cache
    if query_embedding and summary != "No relevant context found.":
        _store_cache(query, query_embedding, summary)

    return {"result": summary}


@app.get("/health")
async def health():
    import resource
    rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # KB to MB
    return {"status": "ok", "memory_mb": round(rss_mb, 1), "cache_entries": len(_cache_entries)}


# ---------- Memory overflow protection ----------
MAX_MEMORY_MB = 2000  # Auto-restart if RSS exceeds 2GB (BGE model uses ~1.3GB)

def _memory_watchdog():
    """Background thread that monitors memory usage and exits if too high."""
    import resource
    while True:
        time.sleep(300)  # Check every 5 minutes
        rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        if rss_mb > MAX_MEMORY_MB:
            import logging
            logging.warning(f"Memory daemon RSS={rss_mb:.0f}MB exceeds {MAX_MEMORY_MB}MB — exiting for systemd restart")
            os._exit(1)  # systemd will restart us with fresh memory

threading.Thread(target=_memory_watchdog, daemon=True).start()


@app.post("/cache/invalidate")
async def invalidate_cache():
    """Clear the in-memory similarity cache."""
    with _cache_lock:
        _cache_entries.clear()
    return {"status": "cleared"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8083, log_level="warning")
