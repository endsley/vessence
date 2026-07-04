"""Short-lived semantic summary cache for memory retrieval."""

from __future__ import annotations

import datetime
import threading
from dataclasses import dataclass

from jane.config import (
    MEMORY_SUMMARY_CACHE_MAX_ENTRIES,
    MEMORY_SUMMARY_CACHE_SIMILARITY,
    MEMORY_SUMMARY_CACHE_TTL_SECS,
)


@dataclass
class MemorySummaryCacheEntry:
    normalized_query: str
    query_embedding: list[float]
    summary: str
    created_at: datetime.datetime


_cache_lock = threading.Lock()
_memory_summary_cache: dict[str, list[MemorySummaryCacheEntry]] = {}
_CACHE_MAX_SESSIONS = 50  # hard cap on number of sessions in cache


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def normalize_query(query: str) -> str:
    return " ".join(str(query or "").strip().lower().split())


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return -1.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a <= 0 or norm_b <= 0:
        return -1.0
    return dot / (norm_a * norm_b)


def prune_cache_entries(entries: list[MemorySummaryCacheEntry]) -> list[MemorySummaryCacheEntry]:
    if not entries:
        return []
    cutoff = utcnow() - datetime.timedelta(seconds=MEMORY_SUMMARY_CACHE_TTL_SECS)
    fresh = [entry for entry in entries if entry.created_at >= cutoff]
    fresh.sort(key=lambda entry: entry.created_at, reverse=True)
    return fresh[:MEMORY_SUMMARY_CACHE_MAX_ENTRIES]


def session_last_used_at(entries: list[MemorySummaryCacheEntry]) -> datetime.datetime:
    return max((entry.created_at for entry in entries), default=utcnow())


def lookup_cached_memory_summary(session_id: str, query_embedding: list[float]) -> str | None:
    with _cache_lock:
        entries = prune_cache_entries(_memory_summary_cache.get(session_id, []))
        if not entries:
            _memory_summary_cache.pop(session_id, None)
            return None
        _memory_summary_cache[session_id] = entries

        best_match = None
        best_similarity = -1.0
        for entry in entries:
            similarity = cosine_similarity(query_embedding, entry.query_embedding)
            if similarity >= MEMORY_SUMMARY_CACHE_SIMILARITY and similarity > best_similarity:
                best_similarity = similarity
                best_match = entry.summary
        return best_match


def store_cached_memory_summary(session_id: str, query: str, query_embedding: list[float], summary: str) -> None:
    if not session_id or not query_embedding or not summary:
        return
    with _cache_lock:
        entries = prune_cache_entries(_memory_summary_cache.get(session_id, []))
        entries.insert(
            0,
            MemorySummaryCacheEntry(
                normalized_query=normalize_query(query),
                query_embedding=query_embedding,
                summary=summary,
                created_at=utcnow(),
            ),
        )
        _memory_summary_cache[session_id] = entries[:MEMORY_SUMMARY_CACHE_MAX_ENTRIES]
        # Evict oldest sessions if cache grows beyond cap.
        if len(_memory_summary_cache) > _CACHE_MAX_SESSIONS:
            sorted_sessions = sorted(
                _memory_summary_cache.keys(),
                key=lambda sid: session_last_used_at(_memory_summary_cache[sid]),
            )
            while len(_memory_summary_cache) > _CACHE_MAX_SESSIONS:
                _memory_summary_cache.pop(sorted_sessions.pop(0), None)


def invalidate_memory_summary_cache(session_id: str | None = None) -> None:
    with _cache_lock:
        if session_id:
            _memory_summary_cache.pop(session_id, None)
        else:
            _memory_summary_cache.clear()
