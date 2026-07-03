"""In-process short-TTL cache for assembled memory sections."""

from __future__ import annotations

import threading
import time

SectionsCacheKey = tuple[str, str, str, str, str]

_SECTIONS_CACHE: dict[SectionsCacheKey, tuple[float, list[str]]] = {}
_SECTIONS_CACHE_LOCK = threading.Lock()
_SECTIONS_CACHE_TTL_S = 60.0
_SECTIONS_CACHE_MAX_ENTRIES = 64


def sections_cache_get(key: SectionsCacheKey) -> list[str] | None:
    with _SECTIONS_CACHE_LOCK:
        entry = _SECTIONS_CACHE.get(key)
        if not entry:
            return None
        ts, sections = entry
        if time.time() - ts > _SECTIONS_CACHE_TTL_S:
            _SECTIONS_CACHE.pop(key, None)
            return None
        return list(sections)


def sections_cache_put(key: SectionsCacheKey, sections: list[str]) -> None:
    with _SECTIONS_CACHE_LOCK:
        if len(_SECTIONS_CACHE) >= _SECTIONS_CACHE_MAX_ENTRIES:
            # Evict oldest entry (cheap; cache stays small).
            oldest_key = min(_SECTIONS_CACHE, key=lambda k: _SECTIONS_CACHE[k][0])
            _SECTIONS_CACHE.pop(oldest_key, None)
        _SECTIONS_CACHE[key] = (time.time(), list(sections))
