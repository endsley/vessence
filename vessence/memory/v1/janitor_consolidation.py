"""Pure helpers for janitor memory consolidation."""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConsolidationGroups:
    topic_groups: dict[str, list[dict[str, Any]]]
    permanent_count: int


def group_consolidation_topics(
    rows: list[dict[str, Any]],
    *,
    collection_name: str,
    user_collection_name: str,
    classify_junk: Callable[[str, dict[str, Any], str], str | None],
) -> ConsolidationGroups:
    topic_groups: dict[str, list[dict[str, Any]]] = {}
    permanent_count = 0

    for row in rows:
        metadata = row["meta"]
        doc = row["doc"]
        if classify_junk(doc, metadata, collection_name):
            continue

        if collection_name == user_collection_name:
            mem_type = metadata.get("memory_type", "")
            skip = (
                mem_type == "permanent" or
                mem_type in ("forgettable", "short_term", "short_term_theme") or
                "Saved file '" in doc or
                "Location: " in doc or
                metadata.get("file_path") is not None
            )
            if skip:
                if mem_type == "permanent":
                    permanent_count += 1
                continue

        topic = metadata.get("topic", "General")
        topic_groups.setdefault(topic, []).append(row)

    return ConsolidationGroups(topic_groups=topic_groups, permanent_count=permanent_count)


def consolidation_topic_candidates(topic_groups: dict[str, list[dict[str, Any]]]) -> list[str]:
    return [topic for topic, memories in topic_groups.items() if len(memories) >= 3]


def consolidation_prompt(topic: str, memories: list[dict[str, Any]]) -> str:
    facts = [
        {
            "id": memory["id"],
            "text": memory["doc"],
            "subtopic": memory["meta"].get("subtopic", "General"),
        }
        for memory in memories
    ]
    return f"""
You are a careful Memory Curator for a personal AI system. Below is a list of facts for the topic: '{topic}'.

YOUR RULES:
1. ONLY merge facts that are truly redundant — they describe the EXACT SAME knowledge, just worded differently.
2. If two facts share a topic but describe DIFFERENT things, they are NOT redundant. Leave them alone.
3. When merging, preserve ALL specific details from both facts. Do not lose any information.
4. If a subtopic exists, keep the most specific one.
5. When in doubt, do NOT merge.
6. Facts that are the ONLY one about their specific subject must NEVER appear in a merge.

Return your response as a JSON object. The "merges" array should ONLY contain groups of truly redundant facts.
If no facts are redundant, return {{"merges": []}}.

{{
  "merges": [
    {{
      "original_ids": ["id1", "id2"],
      "new_fact": "Comprehensive merged fact preserving all details",
      "new_subtopic": "Most specific subtopic or empty string"
    }}
  ]
}}

FACTS FOR TOPIC '{topic}':
{json.dumps(facts, indent=2)}
"""


def consolidated_memory_metadata(
    *,
    collection_name: str,
    user_collection_name: str,
    topic: str,
    old_rows: list[dict[str, Any]],
    new_subtopic: str,
    now_iso: str,
    default_user_id: str,
) -> dict[str, Any]:
    metadata = {
        "author": "janitor",
        "status": "compressed",
        "topic": topic,
        "timestamp": now_iso,
    }
    if collection_name == user_collection_name:
        metadata["memory_type"] = "long_term"
        metadata["user_id"] = old_rows[0]["meta"].get("user_id", default_user_id)
        if new_subtopic:
            metadata["subtopic"] = new_subtopic
    else:
        metadata["source"] = "janitor"
    return metadata
