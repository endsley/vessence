"""User background selection helpers for Jane context construction."""
from __future__ import annotations

import json
from pathlib import Path

from context_builder.v1.prompt_profiles import AI_CODING_KEYWORDS, MUSIC_KEYWORDS, _message_lower


PERSONAL_FACTS_FILE = "user_profile_facts.json"


def _load_personal_facts(data_root: Path) -> dict:
    path = data_root / PERSONAL_FACTS_FILE
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _format_fact_snippet(fact: dict) -> str:
    label = str(fact.get("label", "")).strip()
    value = str(fact.get("value", "")).strip()
    if not label or not value:
        return ""
    return f"{label}: {value}"


def _select_user_background(message: str, personal_facts: dict) -> str:
    lowered = _message_lower(message)
    snippets: list[str] = []

    for fact in personal_facts.get("always", []):
        if isinstance(fact, dict):
            snippet = _format_fact_snippet(fact)
            if snippet:
                snippets.append(snippet)

    topical_groups = []
    if any(keyword in lowered for keyword in AI_CODING_KEYWORDS):
        topical_groups.append("ai_coding")
    if any(keyword in lowered for keyword in MUSIC_KEYWORDS):
        topical_groups.append("music")
    if "teach" in lowered or "student" in lowered or "class" in lowered or "lecture" in lowered:
        topical_groups.append("teaching")

    topic_map = personal_facts.get("topic_map", {})
    for group in topical_groups:
        for fact in topic_map.get(group, []):
            if isinstance(fact, dict):
                snippet = _format_fact_snippet(fact)
                if snippet and snippet not in snippets:
                    snippets.append(snippet)

    return "\n".join(snippets)
