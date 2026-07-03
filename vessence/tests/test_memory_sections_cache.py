import pytest

from memory.v1 import memory_sections_cache as cache


@pytest.fixture(autouse=True)
def clear_cache():
    cache._SECTIONS_CACHE.clear()
    yield
    cache._SECTIONS_CACHE.clear()


def key(name: str) -> cache.SectionsCacheKey:
    return (name, "assistant", "essence", "user_memory", "user")


def test_sections_cache_put_and_get_copy_sections(monkeypatch):
    monkeypatch.setattr(cache.time, "time", lambda: 100.0)
    sections = ["one"]

    cache.sections_cache_put(key("a"), sections)
    sections.append("mutated")
    cached = cache.sections_cache_get(key("a"))
    assert cached == ["one"]

    cached.append("changed")
    assert cache.sections_cache_get(key("a")) == ["one"]


def test_sections_cache_get_expires_and_removes_old_entry(monkeypatch):
    now = 100.0
    monkeypatch.setattr(cache.time, "time", lambda: now)
    cache.sections_cache_put(key("a"), ["one"])

    now = 160.0
    assert cache.sections_cache_get(key("a")) == ["one"]

    now = 160.01
    assert cache.sections_cache_get(key("a")) is None
    assert key("a") not in cache._SECTIONS_CACHE


def test_sections_cache_put_evicts_oldest_entry_at_cap(monkeypatch):
    monkeypatch.setattr(cache, "_SECTIONS_CACHE_MAX_ENTRIES", 2)
    current_time = 100.0
    monkeypatch.setattr(cache.time, "time", lambda: current_time)
    cache.sections_cache_put(key("oldest"), ["old"])

    current_time = 110.0
    cache.sections_cache_put(key("middle"), ["middle"])

    current_time = 120.0
    cache.sections_cache_put(key("newest"), ["new"])

    assert set(cache._SECTIONS_CACHE) == {key("middle"), key("newest")}
