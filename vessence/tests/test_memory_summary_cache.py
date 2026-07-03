import datetime

import pytest

from memory.v1 import memory_summary_cache as cache


@pytest.fixture(autouse=True)
def clear_cache():
    cache.invalidate_memory_summary_cache()
    yield
    cache.invalidate_memory_summary_cache()


def entry(summary: str, seconds_ago: int, vector: list[float] | None = None) -> cache.MemorySummaryCacheEntry:
    return cache.MemorySummaryCacheEntry(
        normalized_query=summary.lower(),
        query_embedding=vector or [1.0, 0.0],
        summary=summary,
        created_at=cache.utcnow() - datetime.timedelta(seconds=seconds_ago),
    )


def test_normalize_query_and_cosine_similarity():
    assert cache.normalize_query("  Hello\nWORLD\t ") == "hello world"
    assert cache.cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cache.cosine_similarity([], [1.0]) == -1.0
    assert cache.cosine_similarity([1.0], [1.0, 0.0]) == -1.0
    assert cache.cosine_similarity([0.0, 0.0], [1.0, 0.0]) == -1.0


def test_prune_cache_entries_removes_expired_and_sorts_newest_first():
    expired_age = cache.MEMORY_SUMMARY_CACHE_TTL_SECS + 1
    entries = [
        entry("old", expired_age),
        entry("newer", 1),
        entry("older", 2),
    ]

    pruned = cache.prune_cache_entries(entries)

    assert [item.summary for item in pruned] == ["newer", "older"]


def test_store_and_lookup_cached_memory_summary_uses_best_similarity():
    cache.store_cached_memory_summary("session", "Query One", [1.0, 0.0], "first")
    cache.store_cached_memory_summary("session", "Query Two", [0.9, 0.1], "second")

    assert cache._memory_summary_cache["session"][0].normalized_query == "query two"
    assert cache.lookup_cached_memory_summary("session", [0.9, 0.1]) == "second"
    assert cache.lookup_cached_memory_summary("session", [0.0, 1.0]) is None


def test_lookup_prunes_expired_session_entries():
    cache._memory_summary_cache["session"] = [
        entry("expired", cache.MEMORY_SUMMARY_CACHE_TTL_SECS + 1),
    ]

    assert cache.lookup_cached_memory_summary("session", [1.0, 0.0]) is None
    assert "session" not in cache._memory_summary_cache


def test_store_ignores_empty_inputs_and_invalidate_can_clear_one_or_all():
    cache.store_cached_memory_summary("", "query", [1.0], "summary")
    cache.store_cached_memory_summary("session", "query", [], "summary")
    cache.store_cached_memory_summary("session", "query", [1.0], "")
    assert cache._memory_summary_cache == {}

    cache.store_cached_memory_summary("one", "query", [1.0], "summary")
    cache.store_cached_memory_summary("two", "query", [1.0], "summary")
    cache.invalidate_memory_summary_cache("one")
    assert set(cache._memory_summary_cache) == {"two"}
    cache.invalidate_memory_summary_cache()
    assert cache._memory_summary_cache == {}


def test_store_evicts_oldest_session_when_cache_exceeds_session_cap(monkeypatch):
    monkeypatch.setattr(cache, "_CACHE_MAX_SESSIONS", 2)
    cache.store_cached_memory_summary("oldest", "query", [1.0], "old")
    cache._memory_summary_cache["oldest"][0].created_at = cache.utcnow() - datetime.timedelta(seconds=20)
    cache.store_cached_memory_summary("middle", "query", [1.0], "middle")
    cache._memory_summary_cache["middle"][0].created_at = cache.utcnow() - datetime.timedelta(seconds=10)

    cache.store_cached_memory_summary("newest", "query", [1.0], "new")

    assert set(cache._memory_summary_cache) == {"middle", "newest"}
