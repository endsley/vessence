"""Pure helpers for long-term memory normalization."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any


NORMALIZED_STYLE_V2 = "long_term_normalized_v2"


def empty_normalization_result() -> dict[str, int]:
    return {
        "reviewed": 0,
        "rewritten": 0,
        "split": 0,
        "deleted_originals": 0,
        "unchanged": 0,
    }


def long_term_normalization_candidates(
    rows: list[dict[str, Any]],
    *,
    theme_topics: Iterable[str],
    review_threshold: int,
    limit: int,
    classify_junk: Callable[[dict[str, Any]], str | None],
) -> list[dict[str, Any]]:
    theme_topic_set = set(theme_topics)
    candidates: list[dict[str, Any]] = []
    for row in rows:
        metadata = row.get("meta") or {}
        doc = str(row.get("doc") or "")
        if not metadata.get("topic"):
            continue
        if metadata.get("topic") in theme_topic_set:
            continue
        if classify_junk(row):
            continue
        if len(doc.strip()) <= review_threshold:
            continue
        if metadata.get("normalized_style") == NORMALIZED_STYLE_V2:
            continue
        candidates.append(row)
        if len(candidates) >= limit:
            break
    return candidates


def split_normalization_prompt(row: dict[str, Any], doc: str) -> str:
    return (
        "Split this long-term memory into 2-6 atomic durable memories.\n"
        "Return ONLY valid JSON: {\"memories\": [\"...\", \"...\"]}\n"
        "Each item must be short, standalone, and preserve only durable facts, "
        "decisions, root causes, fixes, lessons, or reusable references.\n\n"
        f"Topic: {(row.get('meta') or {}).get('topic')}\n"
        f"Memory:\n{doc}"
    )


def split_plan_memories(
    plan: dict[str, Any],
    *,
    max_chars: int,
    max_items: int,
) -> list[str]:
    return [
        str(item).strip()[:max_chars]
        for item in (plan.get("memories") or [])
        if str(item).strip()
    ][:max_items]


def rewrite_normalization_prompt(row: dict[str, Any], doc: str, *, max_chars: int) -> str:
    return (
        "Rewrite this long-term memory into one compact durable memory.\n"
        f"- Keep under {max_chars} characters\n"
        "- Keep only reusable facts, decisions, fixes, root causes, lessons, or references\n"
        "- Remove transcript chatter, filler, or temporary status\n\n"
        f"Topic: {(row.get('meta') or {}).get('topic')}\n"
        f"Memory:\n{doc}"
    )


def split_normalized_metadatas(
    row: dict[str, Any],
    memories: list[str],
    *,
    now_iso: str,
) -> list[dict[str, Any]]:
    raw_chars = len(str(row.get("doc") or "").strip())
    total = len(memories)
    return [
        {
            **(row.get("meta") or {}),
            "raw_chars": raw_chars,
            "summary_chars": len(memory),
            "normalized_style": NORMALIZED_STYLE_V2,
            "normalized_from": row["id"],
            "normalized_part": index,
            "normalized_parts_total": total,
            "timestamp": now_iso,
        }
        for index, memory in enumerate(memories, start=1)
    ]


def rewritten_normalized_metadata(
    row: dict[str, Any],
    rewritten: str,
    *,
    now_iso: str,
) -> dict[str, Any]:
    return {
        **(row.get("meta") or {}),
        "raw_chars": len(str(row.get("doc") or "").strip()),
        "summary_chars": len(rewritten),
        "normalized_style": NORMALIZED_STYLE_V2,
        "timestamp": now_iso,
    }
