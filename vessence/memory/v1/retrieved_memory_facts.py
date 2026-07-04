"""Convert retrieved memory rows into formatted fact lines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from memory.v1.low_signal_memory import (
    is_low_signal_shared_memory,
    is_low_signal_short_term_memory,
)
from memory.v1.memory_text import fmt_memory, is_expired, is_none_content, is_too_old
from memory.v1.query_intent import is_file_index_record


@dataclass(frozen=True)
class UserMemoryFacts:
    permanent: list[str]
    long_term: list[str]
    legacy_short_term: list[str]


def within_distance(distance: float | None, max_distance: float | None) -> bool:
    if distance is None or max_distance is None:
        return True
    try:
        return float(distance) <= float(max_distance)
    except Exception:
        return True


def _meta_with_distance(meta: dict | None, distance: float | None) -> dict:
    return {**(meta or {}), "distance": distance}


def _anchor_doc_set(exact_anchor_docs: Iterable[str] | None) -> set[str]:
    return {doc for doc in exact_anchor_docs or ()}


def user_memory_tier(memory_type: object) -> str:
    if memory_type == "permanent":
        return "permanent"
    if memory_type in {"forgettable", "short_term"}:
        return "legacy_short_term"
    return "long_term"


def include_long_term_user_memory_fact(
    doc: str,
    meta: dict,
    distance: float | None,
    *,
    max_distance: float | None,
    anchor_docs: set[str],
) -> bool:
    if not within_distance(distance, max_distance):
        return False
    if meta.get("topic") == "prompt_queue":
        return False
    return not (meta.get("topic") == "ds3000_lecture_notes" and doc in anchor_docs)


def _collect_expiring_distance_facts(
    docs: list[str],
    metas: list[dict],
    distances: list[float | None],
    *,
    max_distance: float | None,
) -> list[str]:
    return [
        fmt_memory(doc, _meta_with_distance(meta, distance))
        for doc, meta, distance in zip(docs, metas, distances)
        if not is_expired(meta or {}) and within_distance(distance, max_distance)
    ]


def collect_user_memory_facts(
    docs: list[str],
    metas: list[dict],
    distances: list[float | None],
    *,
    exact_anchor_docs: Iterable[str] | None = None,
    permanent_max_distance: float | None,
    short_term_max_distance: float | None,
    user_max_distance: float | None,
) -> UserMemoryFacts:
    permanent_facts: list[str] = []
    long_term_facts: list[str] = []
    legacy_short_term_facts: list[str] = []
    anchor_docs = _anchor_doc_set(exact_anchor_docs)

    for doc, raw_meta, distance in zip(docs, metas, distances):
        meta = _meta_with_distance(raw_meta, distance)
        tier = user_memory_tier(meta.get("memory_type", "long_term"))
        if is_file_index_record(doc, meta):
            continue
        if is_low_signal_shared_memory(doc, meta):
            continue
        if tier == "permanent":
            if within_distance(distance, permanent_max_distance):
                permanent_facts.append(fmt_memory(doc, meta))
        elif tier == "legacy_short_term":
            if (
                within_distance(distance, short_term_max_distance)
                and not is_expired(meta)
                and not is_low_signal_short_term_memory(doc, meta)
            ):
                legacy_short_term_facts.append(fmt_memory(doc, meta))
        else:
            if include_long_term_user_memory_fact(
                doc,
                meta,
                distance,
                max_distance=user_max_distance,
                anchor_docs=anchor_docs,
            ):
                long_term_facts.append(fmt_memory(doc, meta))

    return UserMemoryFacts(
        permanent=permanent_facts,
        long_term=long_term_facts,
        legacy_short_term=legacy_short_term_facts,
    )


def collect_jane_long_term_facts(
    docs: list[str],
    metas: list[dict],
    distances: list[float | None],
    *,
    max_distance: float | None,
) -> list[str]:
    return _collect_expiring_distance_facts(
        docs,
        metas,
        distances,
        max_distance=max_distance,
    )


def collect_short_term_semantic_facts(
    docs: list[str],
    metas: list[dict],
    distances: list[float | None],
    *,
    max_distance: float | None,
) -> list[str]:
    return [
        fmt_memory(doc, _meta_with_distance(meta, distance))
        for doc, meta, distance in zip(docs, metas, distances)
        if is_usable_short_term_fact(doc, meta)
        and within_distance(distance, max_distance)
    ]


def is_usable_short_term_fact(doc: str, meta: dict | None) -> bool:
    meta = meta or {}
    return (
        not is_expired(meta)
        and not is_too_old(meta)
        and not is_none_content(doc)
        and not is_low_signal_short_term_memory(doc, meta)
    )


def _fact_preview_key(formatted_fact: str) -> str:
    return formatted_fact.split(") ", 1)[-1][:80]


def recent_short_term_rows(
    docs: list[str],
    metas: list[dict | None],
    *,
    limit: int,
) -> list[tuple[str, dict | None]]:
    return sorted(
        zip(docs, metas),
        key=lambda row: row[1].get("timestamp", "") if row[1] else "",
        reverse=True,
    )[:limit]


def collect_short_term_with_recency_boost(
    semantic_facts: list[str],
    docs: list[str],
    metas: list[dict],
    *,
    limit: int = 3,
) -> list[str]:
    facts = list(semantic_facts)
    existing_texts = {_fact_preview_key(fact) for fact in facts}
    for doc, meta in recent_short_term_rows(docs, metas, limit=limit):
        meta = meta or {}
        if not is_usable_short_term_fact(doc, meta):
            continue
        formatted = fmt_memory(doc, meta)
        key = _fact_preview_key(formatted)
        if key in existing_texts:
            continue
        facts.append(formatted)
        existing_texts.add(key)
    return facts


def collect_file_index_facts(
    docs: list[str],
    metas: list[dict],
    distances: list[float | None],
    *,
    max_distance: float | None,
) -> list[str]:
    return _collect_expiring_distance_facts(
        docs,
        metas,
        distances,
        max_distance=max_distance,
    )


def collect_essence_facts(
    docs: list[str],
    metas: list[dict],
    distances: list[float | None],
    *,
    max_distance: float | None,
) -> list[str]:
    return _collect_expiring_distance_facts(
        docs,
        metas,
        distances,
        max_distance=max_distance,
    )
