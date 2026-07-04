"""Candidate filtering helpers for nearest-memory preloads."""

from __future__ import annotations

import re
from typing import Iterable

from memory.v1.low_signal_memory import (
    is_low_signal_shared_memory,
    is_low_signal_short_term_memory,
)
from memory.v1.memory_text import (
    age_days,
    extract_content_key,
    fmt_memory,
    is_expired,
    is_none_content,
    is_too_old,
)
from memory.v1.query_intent import is_file_index_record

NearestCandidate = tuple[int, float, str, str, str]

_QUERY_TERM_STOPWORDS = {"what", "when", "about", "with", "from", "that", "this", "were", "have"}
RECENT_SHORT_TERM_PROMOTION_DAYS = 14
RECENT_SHORT_TERM_MIN_OVERLAP = 0.35


def nearest_query_terms(normalized_query: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-z0-9_./-]+", normalized_query)
        if len(term) >= 4 and term not in _QUERY_TERM_STOPWORDS
    }


def lexical_overlap(doc: str, query_terms: Iterable[str]) -> float:
    terms = set(query_terms)
    if not terms:
        return 0.0
    text = str(doc or "").lower()
    hits = sum(1 for term in terms if term in text)
    return hits / len(terms)


def _candidate_distance(distance: float | None) -> float | None:
    if distance is None:
        return None
    try:
        return float(distance)
    except (TypeError, ValueError):
        return None


def _promotes_recent_short_term(source: str, age: float | None, overlap: float) -> bool:
    return (
        source == "short_term"
        and age is not None
        and age <= RECENT_SHORT_TERM_PROMOTION_DAYS
        and overlap >= RECENT_SHORT_TERM_MIN_OVERLAP
    )


def _blocks_user_memory_candidate(doc: str, meta: dict, memory_type: str) -> bool:
    if is_file_index_record(doc, meta) or is_low_signal_shared_memory(doc, meta):
        return True
    if memory_type in {"forgettable", "short_term"}:
        return is_low_signal_short_term_memory(doc, meta)
    return meta.get("topic") == "prompt_queue"


def _blocks_short_term_candidate(
    doc: str,
    meta: dict,
    *,
    promoted_recent_short_term: bool,
) -> bool:
    return (
        (not promoted_recent_short_term and is_too_old(meta))
        or is_low_signal_short_term_memory(doc, meta)
    )


def nearest_memory_candidate(
    source: str,
    doc: str,
    meta: dict | None,
    distance: float | None,
    *,
    query_terms: set[str],
    max_distance: float,
    min_lexical_overlap: float,
) -> NearestCandidate | None:
    dist = _candidate_distance(distance)
    if dist is None:
        return None

    meta = dict(meta or {})
    if is_expired(meta) or is_none_content(doc):
        return None

    age = age_days(meta)
    overlap = lexical_overlap(doc, query_terms)
    promoted_recent_short_term = _promotes_recent_short_term(source, age, overlap)
    if dist > max_distance and not promoted_recent_short_term:
        return None
    if not promoted_recent_short_term and query_terms and overlap < min_lexical_overlap:
        return None

    memory_type = str(meta.get("memory_type", "long_term"))
    if source == "user_memories":
        if _blocks_user_memory_candidate(doc, meta, memory_type):
            return None

    if source == "short_term":
        if _blocks_short_term_candidate(
            doc,
            meta,
            promoted_recent_short_term=promoted_recent_short_term,
        ):
            return None

    meta["distance"] = dist
    priority = 0 if promoted_recent_short_term else 1
    return (priority, dist, source, extract_content_key(doc), fmt_memory(doc, meta))


def nearest_candidates_from_rows(
    source: str,
    docs: Iterable[str],
    metas: Iterable[dict | None],
    distances: Iterable[float | None],
    *,
    query_terms: set[str],
    max_distance: float,
    min_lexical_overlap: float,
) -> list[NearestCandidate]:
    candidates: list[NearestCandidate] = []
    for doc, meta, distance in zip(docs, metas, distances):
        candidate = nearest_memory_candidate(
            source,
            doc,
            meta,
            distance,
            query_terms=query_terms,
            max_distance=max_distance,
            min_lexical_overlap=min_lexical_overlap,
        )
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def select_nearest_memory_lines(candidates: list[NearestCandidate], limit: int) -> list[str]:
    candidates = sorted(candidates, key=lambda item: (item[0], item[1]))
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
