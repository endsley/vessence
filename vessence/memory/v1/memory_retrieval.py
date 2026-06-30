#!/usr/bin/env python3
import datetime
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from jane.sanitizers import strip_client_tool_markers as _strip_client_tool_markers


class silence_stderr_fd:
    def __enter__(self):
        self.py_stdout = sys.stdout
        self.py_stderr = sys.stderr
        self.null_file = open(os.devnull, "w")
        sys.stdout = self.null_file
        sys.stderr = self.null_file
        self.stdout_fd = os.dup(1)
        self.stderr_fd = os.dup(2)
        self.null_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(self.null_fd, 1)
        os.dup2(self.null_fd, 2)

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.dup2(self.stdout_fd, 1)
        os.dup2(self.stderr_fd, 2)
        os.close(self.null_fd)
        os.close(self.stdout_fd)
        os.close(self.stderr_fd)
        sys.stdout = self.py_stdout
        sys.stderr = self.py_stderr
        # Do not close null_file here: some ML loaders keep a reference to the
        # Python stream and flush asynchronously during teardown.


os.environ.setdefault("ORT_LOGGING_LEVEL", "3")
os.environ.setdefault("ONNXRUNTIME_EXECUTION_PROVIDERS", '["CPUExecutionProvider"]')
with silence_stderr_fd():
    import chromadb


from chromadb.utils import embedding_functions

import json
import logging

from jane.config import (
    get_chroma_client,
    CHROMA_COLLECTION_FILE_INDEX,
    CHROMA_COLLECTION_LONG_TERM,
    CHROMA_COLLECTION_SHORT_TERM,
    CHROMA_COLLECTION_USER_MEMORIES,
    CHROMA_FILE_INDEX_MAX_DISTANCE,
    CHROMA_LONG_TERM_MAX_DISTANCE,
    CHROMA_LONG_TERM_LIMIT,
    CHROMA_PERMANENT_MAX_DISTANCE,
    CHROMA_SEARCH_LIMIT,
    CHROMA_SHORT_TERM_MAX_DISTANCE,
    CHROMA_SHORT_TERM_LIMIT,
    CHROMA_USER_MAX_DISTANCE,
    MEMORY_SUMMARY_CACHE_MAX_ENTRIES,
    MEMORY_SUMMARY_CACHE_SIMILARITY,
    MEMORY_SUMMARY_CACHE_TTL_SECS,
    VECTOR_DB_LONG_TERM,
    VECTOR_DB_SHORT_TERM,
    VECTOR_DB_FILE_INDEX,
    VECTOR_DB_USER_MEMORIES,
    DYNAMIC_QUERY_MARKERS_PATH,
)

logger = logging.getLogger(__name__)


@dataclass
class MemorySummaryCacheEntry:
    normalized_query: str
    query_embedding: list[float]
    summary: str
    created_at: datetime.datetime


_cache_lock = threading.Lock()
_query_embedding_fn = None
_memory_summary_cache: dict[str, list[MemorySummaryCacheEntry]] = {}

_STATIC_PERSONAL_MARKERS = (
    "my ", "do you know", "favorite", "office", "instrument", "sport", "restaurant",
    "wife", "daughter", "play", "piano", "name", "prefer",
)
_STATIC_PROJECT_MARKERS = (
    "task", "project", "status", "transition", "migration", "bug", "fix", "implement",
    "patch", "code", "repo", "architecture", "website", "deploy", "service", "cron",
    "backup", "memory", "optimiz", "todo", "slow", "performance",
)

# ── Dynamic query markers (refreshed by janitor, reloaded on file change) ─────
_dynamic_markers_lock = threading.Lock()
_dynamic_markers_mtime: float = 0.0
_dynamic_personal: tuple[str, ...] = ()
_dynamic_project: tuple[str, ...] = ()
_dynamic_file: tuple[str, ...] = ()


def _reload_dynamic_markers_if_changed() -> None:
    """Check mtime of the dynamic markers JSON; reload if it changed."""
    global _dynamic_markers_mtime, _dynamic_personal, _dynamic_project, _dynamic_file
    try:
        mtime = os.path.getmtime(DYNAMIC_QUERY_MARKERS_PATH)
    except OSError:
        return  # file doesn't exist yet — janitor hasn't run
    if mtime == _dynamic_markers_mtime:
        return
    with _dynamic_markers_lock:
        if mtime == _dynamic_markers_mtime:
            return  # double-check after acquiring lock
        try:
            with open(DYNAMIC_QUERY_MARKERS_PATH, "r") as f:
                data = json.load(f)
            _dynamic_personal = tuple(data.get("personal_markers", []))
            _dynamic_project = tuple(data.get("project_markers", []))
            _dynamic_file = tuple(data.get("file_markers", []))
            _dynamic_markers_mtime = mtime
            logger.info(
                "Reloaded dynamic query markers: %d personal, %d project, %d file.",
                len(_dynamic_personal), len(_dynamic_project), len(_dynamic_file),
            )
        except Exception as e:
            logger.warning("Failed to reload dynamic query markers: %s", e)


def _get_personal_markers() -> tuple[str, ...]:
    _reload_dynamic_markers_if_changed()
    return _STATIC_PERSONAL_MARKERS + _dynamic_personal


def _get_project_markers() -> tuple[str, ...]:
    _reload_dynamic_markers_if_changed()
    return _STATIC_PROJECT_MARKERS + _dynamic_project


def _get_file_markers() -> tuple[str, ...]:
    _reload_dynamic_markers_if_changed()
    return _dynamic_file  # static file markers are in _is_file_query already


LOW_SIGNAL_SHARED_PREFIXES = (
    "prompt list verbatim",
    "logged in with google",
    "user logged in with google account",
    "shortcut: yolo",
    "ui includes yolo shortcut",
    "main pre-response latency points",
    "still here. what do you want to work on next?",
    "noise_check_ok",
)
LOW_SIGNAL_SHORT_TERM_META_PREFIX_PATTERNS = (
    r"^i need clarification\b",
    r"^there(?:'|’)s no conversation turn to summarize\b",
    r"^no action needed\b",
    r"^i notice there(?:'|’)s a mismatch here\b",
)
LOW_SIGNAL_SHORT_TERM_PROTOCOL_PATTERNS = (
    r"^\[context snapshot\b",
    r"^\*{0,2}\s*class protocol:",
    r"<class_protocol\b",
    r"\[extracted params\]",
    r"\[current conversation state\]",
    r"\[standing brain mode\]",
    r"\bclass protocol metadata\b",
    r"\bdocumentation \(belongs in code/config\)\b",
    r"\bprovided (?:class )?protocol\b",
    r"\bclass protocol you provided\b",
    r"\bnew turn.*class protocol metadata\b",
)


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _normalize_query(query: str) -> str:
    return " ".join(str(query or "").strip().lower().split())


def _get_query_embedding_fn():
    """Get the BGE-small-en-v1.5 embedding model (cached singleton)."""
    global _query_embedding_fn
    if _query_embedding_fn is None:
        try:
            from sentence_transformers import SentenceTransformer
            _query_embedding_fn = SentenceTransformer('BAAI/bge-small-en-v1.5')
        except Exception:
            # Fallback to ONNX MiniLM if BGE fails
            with silence_stderr_fd():
                _query_embedding_fn = embedding_functions.ONNXMiniLM_L6_V2(
                    preferred_providers=["CPUExecutionProvider"]
                )
    return _query_embedding_fn


def _embed_query_text(query: str) -> list[float] | None:
    normalized = _normalize_query(query)
    if not normalized:
        return None
    try:
        model = _get_query_embedding_fn()
        # BGE (SentenceTransformer) vs ONNX (ChromaDB embedding function)
        if hasattr(model, 'encode'):
            vectors = model.encode([normalized]).tolist()
        else:
            with silence_stderr_fd():
                vectors = model([normalized])
    except Exception:
        return None
    if not vectors:
        return None
    return [float(v) for v in vectors[0]]


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return -1.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a <= 0 or norm_b <= 0:
        return -1.0
    return dot / (norm_a * norm_b)


def _prune_cache_entries(entries: list[MemorySummaryCacheEntry]) -> list[MemorySummaryCacheEntry]:
    if not entries:
        return []
    cutoff = _utcnow() - datetime.timedelta(seconds=MEMORY_SUMMARY_CACHE_TTL_SECS)
    fresh = [entry for entry in entries if entry.created_at >= cutoff]
    fresh.sort(key=lambda entry: entry.created_at, reverse=True)
    return fresh[:MEMORY_SUMMARY_CACHE_MAX_ENTRIES]


def _lookup_cached_memory_summary(session_id: str, query_embedding: list[float]) -> str | None:
    with _cache_lock:
        entries = _prune_cache_entries(_memory_summary_cache.get(session_id, []))
        if not entries:
            _memory_summary_cache.pop(session_id, None)
            return None
        _memory_summary_cache[session_id] = entries

        best_match = None
        best_similarity = -1.0
        for entry in entries:
            similarity = _cosine_similarity(query_embedding, entry.query_embedding)
            if similarity >= MEMORY_SUMMARY_CACHE_SIMILARITY and similarity > best_similarity:
                best_similarity = similarity
                best_match = entry.summary
        return best_match


_CACHE_MAX_SESSIONS = 50  # hard cap on number of sessions in cache


def _store_cached_memory_summary(session_id: str, query: str, query_embedding: list[float], summary: str) -> None:
    if not session_id or not query_embedding or not summary:
        return
    with _cache_lock:
        entries = _prune_cache_entries(_memory_summary_cache.get(session_id, []))
        entries.insert(0, MemorySummaryCacheEntry(
            normalized_query=_normalize_query(query),
            query_embedding=query_embedding,
            summary=summary,
            created_at=_utcnow(),
        ))
        _memory_summary_cache[session_id] = entries[:MEMORY_SUMMARY_CACHE_MAX_ENTRIES]
        # Evict oldest sessions if cache grows beyond cap
        if len(_memory_summary_cache) > _CACHE_MAX_SESSIONS:
            # Find and remove sessions with the oldest entries
            sorted_sessions = sorted(
                _memory_summary_cache.keys(),
                key=lambda sid: max((e.created_at for e in _memory_summary_cache[sid]), default=_utcnow()),
            )
            while len(_memory_summary_cache) > _CACHE_MAX_SESSIONS:
                _memory_summary_cache.pop(sorted_sessions.pop(0), None)


def invalidate_memory_summary_cache(session_id: str | None = None) -> None:
    with _cache_lock:
        if session_id:
            _memory_summary_cache.pop(session_id, None)
        else:
            _memory_summary_cache.clear()


def _is_expired(meta: dict) -> bool:
    expires_at = (meta or {}).get("expires_at")
    if not expires_at:
        return False

    now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
    if isinstance(expires_at, (int, float)):
        return expires_at < now_ts

    try:
        expires_dt = datetime.datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        if expires_dt.tzinfo is None:
            expires_dt = expires_dt.replace(tzinfo=datetime.timezone.utc)
        return expires_dt.timestamp() < now_ts
    except Exception:
        return False


def _is_too_old(meta: dict, max_days: int = 3) -> bool:
    """Return True if the entry is older than max_days. Entries without timestamps pass through."""
    ts_str = (meta or {}).get("timestamp", (meta or {}).get("created_at", ""))
    if not ts_str:
        return False
    try:
        ts = datetime.datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=datetime.timezone.utc)
        age_days = (datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds() / 86400
        return age_days > max_days
    except Exception:
        return False


def _age_days(meta: dict) -> float | None:
    ts_str = (meta or {}).get("timestamp", (meta or {}).get("created_at", ""))
    if not ts_str:
        return None
    try:
        ts = datetime.datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=datetime.timezone.utc)
        return (datetime.datetime.now(datetime.timezone.utc) - ts).total_seconds() / 86400
    except Exception:
        return None


def _is_none_content(doc: str) -> bool:
    """Return True if the document content is a None/empty sentinel."""
    stripped = (doc or "").strip()
    return stripped in ("None", "none", "", "null", "N/A")


def _recency_label(ts_str: str) -> str:
    if not ts_str or ts_str == "Unknown Time":
        return "unknown age"
    try:
        ts = datetime.datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=datetime.timezone.utc)
        delta = datetime.datetime.now(datetime.timezone.utc) - ts
        secs = delta.total_seconds()
        if secs < 0:
            return "just now"
        if secs < 3600:
            return f"{int(secs // 60)}m ago"
        if secs < 86400:
            return f"{int(secs // 3600)}h ago"
        return f"{int(secs // 86400)}d ago"
    except Exception:
        return "unknown age"


def _fmt_memory(doc: str, meta: dict | None) -> str:
    meta = meta or {}
    ts = meta.get("timestamp", meta.get("created_at", ""))
    topic = meta.get("topic", meta.get("source", "General"))
    dist = meta.get("distance")
    age = _recency_label(ts) if ts else "unknown age"
    dist_str = f" (Dist: {dist:.4f})" if dist is not None else ""
    return f"[{age}] ({topic}){dist_str}: {doc}"


def _extract_content_key(line: str) -> str:
    """Extract the content portion of a formatted memory line for dedup comparison.

    Formatted lines look like: '[8d ago] (topic) (Dist: 0.1234): actual content...'
    We strip the metadata prefix and normalize whitespace so the same content
    from different collections (with different ages/distances) is recognized as
    a duplicate.
    """
    text = str(line)
    # Strip everything up to and including the last '): ' prefix
    idx = text.rfind("): ")
    if idx != -1:
        text = text[idx + 3:]
    return " ".join(text.split()).lower()[:120]


def _dedupe_fact_lines(lines: list[str], global_seen: set[str] | None = None) -> list[str]:
    """Deduplicate formatted memory lines.

    If *global_seen* is provided, it is checked AND updated so that the same
    content appearing in a later section is dropped.  This enables cross-section
    dedup when the same set is passed to every call.
    """
    local_seen: set[str] = set()
    deduped: list[str] = []
    for line in lines:
        key = _extract_content_key(line)
        if key in local_seen:
            continue
        if global_seen is not None and key in global_seen:
            continue
        local_seen.add(key)
        if global_seen is not None:
            global_seen.add(key)
        deduped.append(line)
    return deduped


def _query_collection(client_path: str, collection_name: str, query: str, limit: int, query_embedding: list[float] | None = None) -> tuple[list[str], list[dict], list[float | None]]:
    if not os.path.exists(client_path):
        return [], [], []

    try:
        with silence_stderr_fd():
            client = get_chroma_client(path=client_path)
            collection = client.get_collection(name=collection_name)
        n_results = min(limit, collection.count())
        if n_results <= 0:
            return [], [], []
        with silence_stderr_fd():
            # Use pre-computed embedding if available (200x faster than query_texts)
            if query_embedding:
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"],
                )
            else:
                results = collection.query(
                    query_texts=[query],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"],
                )
        docs = (results.get("documents") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]
        return docs, metas, distances
    except Exception:
        return [], [], []


def _within_distance(distance: float | None, max_distance: float | None) -> bool:
    if distance is None or max_distance is None:
        return True
    try:
        return float(distance) <= float(max_distance)
    except Exception:
        return True


def _is_file_index_record(doc: str, meta: dict | None) -> bool:
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


def _is_file_query(query: str) -> bool:
    q = (query or "").lower()
    static_file_markers = (
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
    return any(marker in q for marker in static_file_markers + _get_file_markers())


def _classify_query_intent(query: str) -> str:
    q = (query or "").lower().strip()
    if _is_file_query(q):
        return "file_lookup"
    if any(marker in q for marker in _get_project_markers()):
        return "project_work"
    if any(marker in q for marker in _get_personal_markers()) or (len(q) <= 40 and "?" in q):
        return "personal_lookup"
    return "general"


def _ds3000_lecture_subtopics(query: str) -> list[str]:
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


def _get_ds3000_lecture_anchors(subtopics: list[str]) -> list[tuple[str, dict]]:
    if not subtopics or not os.path.exists(VECTOR_DB_USER_MEMORIES):
        return []
    try:
        with silence_stderr_fd():
            client = get_chroma_client(path=VECTOR_DB_USER_MEMORIES)
            collection = client.get_collection(name=CHROMA_COLLECTION_USER_MEMORIES)
            results = collection.get(
                where={"topic": "ds3000_lecture_notes"},
                include=["documents", "metadatas"],
            )
    except Exception:
        return []

    wanted = set(subtopics)
    anchors: list[tuple[str, dict]] = []
    for doc, meta in zip(results.get("documents", []), results.get("metadatas", [])):
        meta = meta or {}
        if meta.get("subtopic") in wanted and not _is_expired(meta) and not _is_none_content(doc):
            anchors.append((doc, meta))
    return anchors


def _is_low_signal_shared_memory(doc: str, meta: dict | None) -> bool:
    text = str(doc or "").strip().lower()
    if not text:
        return True
    if any(text.startswith(prefix) for prefix in LOW_SIGNAL_SHARED_PREFIXES):
        return True
    topic = str((meta or {}).get("topic", "")).lower()
    if topic in {"prompt_list", "audit_flow", "performance_logs"}:
        return True
    return False


def _is_low_signal_short_term_memory(doc: str, meta: dict | None) -> bool:
    text = re.sub(r"\s+", " ", str(doc or "")).strip()
    topic = str((meta or {}).get("topic", "")).strip().lower()
    memory_type = str((meta or {}).get("memory_type", "")).strip().lower()
    if memory_type == "short_term_theme":
        return True
    if topic == "context_snapshot":
        return True
    protocol_hit = any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in LOW_SIGNAL_SHORT_TERM_PROTOCOL_PATTERNS
    )
    if not protocol_hit:
        return False
    if re.search(r"^\*{0,2}\s*class protocol:", text, re.IGNORECASE):
        return True
    return any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in LOW_SIGNAL_SHORT_TERM_META_PREFIX_PATTERNS
    ) or any(
        marker in text.lower()
        for marker in (
            "<class_protocol",
            "[extracted params]",
            "[current conversation state]",
            "[standing brain mode]",
        )
    )


# In-process short-TTL cache so back-to-back callers (e.g. pipeline.py's
# `_apply_evidence_policy` followed by jane_proxy's context builder, both
# running for the same turn) don't re-embed and re-query Chroma for the
# identical prompt. Keyed by (query, assistant_name, essence_path).
_SECTIONS_CACHE: dict[tuple[str, str, str, str, str], tuple[float, list[str]]] = {}
_SECTIONS_CACHE_LOCK = threading.Lock()
_SECTIONS_CACHE_TTL_S = 60.0
_SECTIONS_CACHE_MAX_ENTRIES = 64


def _sections_cache_get(key: tuple[str, str, str, str, str]) -> list[str] | None:
    import time as _t
    with _SECTIONS_CACHE_LOCK:
        entry = _SECTIONS_CACHE.get(key)
        if not entry:
            return None
        ts, sections = entry
        if _t.time() - ts > _SECTIONS_CACHE_TTL_S:
            _SECTIONS_CACHE.pop(key, None)
            return None
        return list(sections)


def _sections_cache_put(key: tuple[str, str, str, str, str], sections: list[str]) -> None:
    import time as _t
    with _SECTIONS_CACHE_LOCK:
        if len(_SECTIONS_CACHE) >= _SECTIONS_CACHE_MAX_ENTRIES:
            # Evict oldest entry (cheap; cache stays small).
            oldest_key = min(_SECTIONS_CACHE, key=lambda k: _SECTIONS_CACHE[k][0])
            _SECTIONS_CACHE.pop(oldest_key, None)
        _SECTIONS_CACHE[key] = (_t.time(), list(sections))


def build_memory_sections(
    query: str,
    assistant_name: str = "Jane",
    essence_chromadb_path: str | None = None,
    user_memory_path: str | None = None,
    user_id: str | None = None,
) -> list[str]:
    cache_key = (
        query or "",
        assistant_name or "",
        essence_chromadb_path or "",
        user_memory_path or "",
        user_id or "",
    )
    cached = _sections_cache_get(cache_key)
    if cached is not None:
        return cached

    intent = _classify_query_intent(query)
    use_user_memory = bool(user_memory_path and os.path.exists(user_memory_path))
    use_shared = not use_user_memory
    use_jane_long_term = (
        not use_user_memory
        and assistant_name.strip().lower() != "amber"
        and intent in {"project_work", "general"}
    )
    use_short_term = not use_user_memory  # Managed users use their private memory plus live session history.
    use_file_index = intent == "file_lookup" and not use_user_memory
    use_essence = bool(essence_chromadb_path and os.path.exists(essence_chromadb_path))

    # Pre-compute embedding ONCE — pass to all queries to avoid re-embedding
    with silence_stderr_fd():
        query_emb = _embed_query_text(query)

    # --- Submit all applicable queries in parallel ---
    futures: dict[str, "Future"] = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        if use_user_memory or use_shared:
            futures["user_memories"] = executor.submit(
                _query_collection,
                user_memory_path if use_user_memory else VECTOR_DB_USER_MEMORIES,
                CHROMA_COLLECTION_USER_MEMORIES,
                query,
                CHROMA_SEARCH_LIMIT,
                query_emb,
            )
        if use_jane_long_term:
            futures["jane_long_term"] = executor.submit(
                _query_collection,
                VECTOR_DB_LONG_TERM,
                CHROMA_COLLECTION_LONG_TERM,
                query,
                CHROMA_LONG_TERM_LIMIT,
                query_emb,
            )
        if use_short_term:
            futures["short_term"] = executor.submit(
                _query_collection,
                VECTOR_DB_SHORT_TERM,
                CHROMA_COLLECTION_SHORT_TERM,
                query,
                CHROMA_SHORT_TERM_LIMIT,
                query_emb,
            )
        if use_file_index:
            futures["file_index"] = executor.submit(
                _query_collection,
                VECTOR_DB_FILE_INDEX,
                CHROMA_COLLECTION_FILE_INDEX,
                query,
                min(8, CHROMA_SEARCH_LIMIT),
                query_emb,
            )
        if use_essence:
            futures["essence"] = executor.submit(
                _query_collection,
                essence_chromadb_path,
                "essence_knowledge",
                query,
                CHROMA_SEARCH_LIMIT,
            )

    # --- Collect results, gracefully handling per-query failures ---
    def _safe_get(future_key: str) -> tuple[list[str], list[dict], list[float | None]]:
        if future_key not in futures:
            return [], [], []
        try:
            return futures[future_key].result()
        except Exception:
            return [], [], []

    # -- user_memories (shared or managed-user private Chroma) --
    permanent_facts: list[str] = []
    long_term_facts: list[str] = []
    legacy_short_term_facts: list[str] = []

    exact_ds3000_anchors = []
    if use_shared:
        exact_ds3000_anchors = _get_ds3000_lecture_anchors(_ds3000_lecture_subtopics(query))
        long_term_facts.extend(_fmt_memory(doc, meta) for doc, meta in exact_ds3000_anchors)

    if use_user_memory or use_shared:
        docs, metas, distances = _safe_get("user_memories")
        for doc, meta, distance in zip(docs, metas, distances):
            meta = meta or {}
            meta = {**meta, "distance": distance}
            memory_type = meta.get("memory_type", "long_term")
            if _is_file_index_record(doc, meta):
                continue
            if _is_low_signal_shared_memory(doc, meta):
                continue
            # Per-tier distance thresholds: permanent rules always pass,
            # other tiers use tighter thresholds to cut low-relevance noise.
            if memory_type == "permanent":
                if not _within_distance(distance, CHROMA_PERMANENT_MAX_DISTANCE):
                    continue
                permanent_facts.append(_fmt_memory(doc, meta))
            elif memory_type in {"forgettable", "short_term"}:
                if not _within_distance(distance, CHROMA_SHORT_TERM_MAX_DISTANCE):
                    continue
                if not _is_expired(meta) and not _is_low_signal_short_term_memory(doc, meta):
                    legacy_short_term_facts.append(_fmt_memory(doc, meta))
            else:
                if not _within_distance(distance, CHROMA_USER_MAX_DISTANCE):
                    continue
                # Skip prompt_queue entries from auto-injection — they're noise for
                # most queries; retrieve them explicitly when needed via search.
                if meta.get("topic") == "prompt_queue":
                    continue
                if meta.get("topic") == "ds3000_lecture_notes" and any(
                    doc == anchor_doc for anchor_doc, _anchor_meta in exact_ds3000_anchors
                ):
                    continue
                long_term_facts.append(_fmt_memory(doc, meta))

    if use_shared and use_short_term:
        try:
            with silence_stderr_fd():
                client = get_chroma_client(path=VECTOR_DB_USER_MEMORIES)
                collection = client.get_collection(name=CHROMA_COLLECTION_USER_MEMORIES)
                extra_results = collection.get(
                    where={"memory_type": "forgettable"},
                    include=["documents", "metadatas"],
                )
            extra_ids = extra_results.get("ids", [])
            extra_docs = extra_results.get("documents", [])
            extra_metas = extra_results.get("metadatas", [])
            for extra_id, extra_doc, extra_meta in zip(extra_ids, extra_docs, extra_metas):
                if _is_expired(extra_meta):
                    continue
                if _is_none_content(extra_doc) or _is_low_signal_short_term_memory(extra_doc, extra_meta):
                    continue
                legacy_short_term_facts.append(_fmt_memory(extra_doc, extra_meta))
        except Exception:
            pass

    # -- jane long-term --
    jane_long_term_facts: list[str] = []
    if use_jane_long_term:
        jane_lt_docs, jane_lt_metas, jane_lt_distances = _safe_get("jane_long_term")
        jane_long_term_facts = [
            _fmt_memory(doc, {**(meta or {}), "distance": distance})
            for doc, meta, distance in zip(jane_lt_docs, jane_lt_metas, jane_lt_distances)
            if not _is_expired(meta or {}) and _within_distance(distance, CHROMA_LONG_TERM_MAX_DISTANCE)
        ]

    # -- short-term (semantic match + recency boost) --
    short_term_facts: list[str] = []
    if use_short_term:
        st_docs, st_metas, st_distances = _safe_get("short_term")
        short_term_facts = [
            _fmt_memory(doc, {**(meta or {}), "distance": distance})
            for doc, meta, distance in zip(st_docs, st_metas, st_distances)
            if not _is_expired(meta or {}) and not _is_too_old(meta or {}) and not _is_none_content(doc)
            and not _is_low_signal_short_term_memory(doc, meta or {})
            and _within_distance(distance, CHROMA_SHORT_TERM_MAX_DISTANCE)
        ]
        # Recency boost: always include the N most recent short-term entries
        # regardless of semantic similarity, so recent changes never get missed.
        try:
            _st_path = VECTOR_DB_SHORT_TERM
            if os.path.exists(_st_path):
                with silence_stderr_fd():
                    _st_client = get_chroma_client(path=_st_path)
                    _st_col = _st_client.get_collection(name=CHROMA_COLLECTION_SHORT_TERM)
                _all = _st_col.get(include=["documents", "metadatas"], limit=min(200, _st_col.count()))
                if _all["documents"]:
                    _recent = sorted(
                        zip(_all["documents"], _all["metadatas"]),
                        key=lambda x: x[1].get("timestamp", "") if x[1] else "",
                        reverse=True,
                    )[:3]  # top 3 most recent (was 8)
                    _existing_texts = {f.split(") ", 1)[-1][:80] for f in short_term_facts}
                    for doc, meta in _recent:
                        if not _is_expired(meta or {}) and not _is_too_old(meta or {}) and not _is_none_content(doc) and not _is_low_signal_short_term_memory(doc, meta or {}):
                            formatted = _fmt_memory(doc, meta or {})
                            # Dedupe against semantic results
                            if formatted.split(") ", 1)[-1][:80] not in _existing_texts:
                                short_term_facts.append(formatted)
                                _existing_texts.add(formatted.split(") ", 1)[-1][:80])
        except Exception:
            pass  # recency boost is best-effort

    # -- file index --
    file_index_facts: list[str] = []
    if use_file_index:
        fi_docs, fi_metas, fi_distances = _safe_get("file_index")
        file_index_facts = [
            _fmt_memory(doc, {**(meta or {}), "distance": distance})
            for doc, meta, distance in zip(fi_docs, fi_metas, fi_distances)
            if not _is_expired(meta or {}) and _within_distance(distance, CHROMA_FILE_INDEX_MAX_DISTANCE)
        ]

    # -- essence memory --
    essence_facts: list[str] = []
    if use_essence:
        ess_docs, ess_metas, ess_distances = _safe_get("essence")
        essence_facts = [
            _fmt_memory(doc, {**(meta or {}), "distance": distance})
            for doc, meta, distance in zip(ess_docs, ess_metas, ess_distances)
            if not _is_expired(meta or {}) and _within_distance(distance, CHROMA_USER_MAX_DISTANCE)
        ]

    # --- Build sections (same format as before) ---
    # Cross-section dedup: a shared set ensures the same content from different
    # collections is only injected once.  Order matters — higher-priority
    # sections are deduped first so they "claim" the content.
    _global_seen: set[str] = set()
    sections: list[str] = []
    permanent_facts = _dedupe_fact_lines(permanent_facts, _global_seen)
    long_term_facts = _dedupe_fact_lines(long_term_facts, _global_seen)
    jane_long_term_facts = _dedupe_fact_lines(jane_long_term_facts, _global_seen)
    short_term_facts = _dedupe_fact_lines(short_term_facts, _global_seen)
    file_index_facts = _dedupe_fact_lines(file_index_facts, _global_seen)
    legacy_short_term_facts = _dedupe_fact_lines(legacy_short_term_facts, _global_seen)
    essence_facts = _dedupe_fact_lines(essence_facts, _global_seen)
    if permanent_facts:
        sections.append("## Permanent Memory\n" + "\n".join(permanent_facts))
    if long_term_facts:
        section_label = "## Long-Term Memory (current user)" if use_user_memory else "## Long-Term Memory (shared)"
        sections.append(section_label + "\n" + "\n".join(long_term_facts))
    if jane_long_term_facts:
        sections.append("## Long-Term Memory (Jane archived)\n" + "\n".join(jane_long_term_facts))
    if short_term_facts:
        sections.append(
            "## Short-Term Memory  <- highest recency, treat as most current\n"
            + "\n".join(short_term_facts)
        )
    if file_index_facts:
        sections.append(
            "## File Index Memory  <- only for file/vault lookup questions\n"
            + "\n".join(file_index_facts)
        )
    if legacy_short_term_facts:
        sections.append(
            "## Short-Term Memory (legacy forgettable)\n"
            + "\n".join(legacy_short_term_facts)
        )
    if essence_facts:
        sections.append("## Essence Memory\n" + "\n".join(essence_facts))
    _sections_cache_put(cache_key, sections)
    return sections


def query_nearest_memory_lines(
    query: str,
    limit: int = 2,
    max_distance: float = 0.50,
    min_lexical_overlap: float = 0.34,
    assistant_name: str = "Jane",
    essence_chromadb_path: str | None = None,
    user_memory_path: str | None = None,
) -> list[str]:
    """Return the nearest formatted memory lines below a distance threshold.

    This is intentionally narrower than build_memory_sections(): it is for
    per-turn Codex preloading, where a small high-confidence prelude is better
    than broad memory recall.
    """
    normalized = _normalize_query(query)
    if not normalized or limit <= 0:
        return []

    intent = _classify_query_intent(query)
    use_user_memory = bool(user_memory_path and os.path.exists(user_memory_path))
    use_shared = not use_user_memory
    use_jane_long_term = (
        not use_user_memory
        and assistant_name.strip().lower() != "amber"
        and intent in {"project_work", "general"}
    )
    use_short_term = not use_user_memory
    use_file_index = intent == "file_lookup" and not use_user_memory
    use_essence = bool(essence_chromadb_path and os.path.exists(essence_chromadb_path))

    query_emb = _embed_query_text(query)
    query_terms = {
        term
        for term in re.findall(r"[a-z0-9_./-]+", normalized)
        if len(term) >= 4 and term not in {"what", "when", "about", "with", "from", "that", "this", "were", "have"}
    }
    candidates: list[tuple[int, float, str, str, str]] = []

    for doc, meta in _get_ds3000_lecture_anchors(_ds3000_lecture_subtopics(query)):
        candidates.append((0, 0.0, "user_memories", _extract_content_key(doc), _fmt_memory(doc, meta)))

    def _lexical_overlap(doc: str) -> float:
        if not query_terms:
            return 0.0
        text = str(doc or "").lower()
        hits = sum(1 for term in query_terms if term in text)
        return hits / len(query_terms)

    def _add_candidate(source: str, doc: str, meta: dict | None, distance: float | None) -> None:
        if distance is None:
            return
        try:
            dist = float(distance)
        except (TypeError, ValueError):
            return
        meta = dict(meta or {})
        if _is_expired(meta) or _is_none_content(doc):
            return
        age = _age_days(meta)
        overlap = _lexical_overlap(doc)
        promoted_recent_short_term = (
            source == "short_term"
            and age is not None
            and age <= 14
            and overlap >= 0.35
        )
        if dist > max_distance and not promoted_recent_short_term:
            return
        if not promoted_recent_short_term and query_terms and overlap < min_lexical_overlap:
            return
        memory_type = str(meta.get("memory_type", "long_term"))
        if source == "user_memories":
            if _is_file_index_record(doc, meta) or _is_low_signal_shared_memory(doc, meta):
                return
            if memory_type in {"forgettable", "short_term"}:
                if _is_low_signal_short_term_memory(doc, meta):
                    return
            elif meta.get("topic") == "prompt_queue":
                return
        if source == "short_term":
            if (not promoted_recent_short_term and _is_too_old(meta)) or _is_low_signal_short_term_memory(doc, meta):
                return
        meta["distance"] = dist
        priority = 0 if promoted_recent_short_term else 1
        candidates.append((priority, dist, source, _extract_content_key(doc), _fmt_memory(doc, meta)))

    query_specs: list[tuple[str, str, str, int]] = []
    if use_user_memory or use_shared:
        query_specs.append((
            "user_memories",
            user_memory_path if use_user_memory else VECTOR_DB_USER_MEMORIES,
            CHROMA_COLLECTION_USER_MEMORIES,
            max(CHROMA_SEARCH_LIMIT, limit * 4),
        ))
    if use_jane_long_term:
        query_specs.append((
            "jane_long_term",
            VECTOR_DB_LONG_TERM,
            CHROMA_COLLECTION_LONG_TERM,
            max(CHROMA_LONG_TERM_LIMIT, limit * 4),
        ))
    if use_short_term:
        query_specs.append((
            "short_term",
            VECTOR_DB_SHORT_TERM,
            CHROMA_COLLECTION_SHORT_TERM,
            max(CHROMA_SHORT_TERM_LIMIT, limit * 4),
        ))
    if use_file_index:
        query_specs.append((
            "file_index",
            VECTOR_DB_FILE_INDEX,
            CHROMA_COLLECTION_FILE_INDEX,
            max(8, limit * 4),
        ))
    if use_essence:
        query_specs.append((
            "essence",
            essence_chromadb_path or "",
            "essence_knowledge",
            max(CHROMA_SEARCH_LIMIT, limit * 4),
        ))

    # Run sequentially. The underlying Chroma/SentenceTransformer stack writes
    # to process-wide stdout/stderr during lazy loads; parallel lookups can race
    # the fd redirection and leak noise into Codex prompt preflight output.
    for source, path, collection, search_limit in query_specs:
        try:
            docs, metas, distances = _query_collection(
                path,
                collection,
                query,
                search_limit,
                query_emb,
            )
        except Exception:
            continue
        for doc, meta, distance in zip(docs, metas, distances):
            _add_candidate(source, doc, meta, distance)

    candidates.sort(key=lambda item: (item[0], item[1]))
    seen: set[str] = set()
    selected: list[str] = []
    for _priority, _dist, source, key, formatted in candidates:
        if key in seen:
            continue
        seen.add(key)
        selected.append(f"{source}: {formatted}")
        if len(selected) >= limit:
            break
    return selected
