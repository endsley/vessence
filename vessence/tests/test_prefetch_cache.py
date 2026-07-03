from jane_web.prefetch_cache import PrefetchMemoryCache


def test_prefetch_cache_get_and_freshness_respect_ttl_boundary():
    now = 100.0
    cache = PrefetchMemoryCache(ttl_seconds=60, time_fn=lambda: now)

    assert not cache.is_fresh("s1")
    assert cache.get("s1") == ""

    cache.store("s1", "memory")
    assert cache.is_fresh("s1")
    assert cache.get("s1") == "memory"

    now = 160.0
    assert not cache.is_fresh("s1")
    assert cache.get("s1") == ""


def test_prefetch_cache_store_prunes_expired_entries_only_when_over_cap():
    now = 0.0
    cache = PrefetchMemoryCache(ttl_seconds=50, max_entries=2, time_fn=lambda: now)
    cache.store("old1", "one")
    now = 10.0
    cache.store("old2", "two")

    now = 100.0
    cache.store("new", "three")

    assert set(cache.entries) == {"new"}


def test_prefetch_cache_does_not_evict_fresh_entries_when_over_cap():
    now = 0.0
    cache = PrefetchMemoryCache(ttl_seconds=1000, max_entries=1, time_fn=lambda: now)
    cache.store("one", "1")
    now = 1.0
    cache.store("two", "2")

    assert set(cache.entries) == {"one", "two"}
