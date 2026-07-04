"""Pure text and compact-payload helpers for RA research cron."""

from __future__ import annotations

import json
import re
from typing import Any

from jane.json_scanner import find_json_object_end


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def text_value(value: Any, max_chars: int = 400) -> str:
    text = clean_text(str(value or ""))
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "..."


def list_values(values: Any, *, max_items: int = 5, max_chars: int = 220) -> list[str]:
    if isinstance(values, list):
        raw_values = values
    elif values:
        raw_values = [values]
    else:
        raw_values = []
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        text = text_value(value, max_chars)
        key = text.lower()
        if not text or key in seen:
            continue
        cleaned.append(text)
        seen.add(key)
        if len(cleaned) >= max_items:
            break
    return cleaned


def dedupe_summaries(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for summary in summaries:
        source_id = str(summary.get("source_id") or summary.get("title") or "").strip()
        if not source_id:
            continue
        key = source_id.lower()
        if key in seen:
            continue
        deduped.append(summary)
        seen.add(key)
    return deduped


def parse_json_from_text(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    cleaned = text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()
    start = cleaned.find("{")
    if start < 0:
        return None
    end = find_json_object_end(cleaned, start)
    if end is None:
        return None
    cleaned = cleaned[start:end]
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def compact_summary_record(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": text_value(summary.get("source_id", ""), 80),
        "title": text_value(summary.get("title", ""), 220),
        "citation": text_value(summary.get("citation", ""), 300),
        "url": text_value(summary.get("url", ""), 180),
        "scope": text_value(summary.get("evidence_scope", ""), 80),
        "type": text_value(summary.get("study_type", ""), 80),
        "findings": list_values(summary.get("main_findings"), max_items=4, max_chars=260),
        "relevance": text_value(summary.get("remission_relevance", ""), 320),
        "actions": list_values(summary.get("actionable_implications"), max_items=4, max_chars=240),
        "tests_or_monitoring": list_values(summary.get("tests_or_monitoring"), max_items=4, max_chars=220),
        "food_diet": list_values(summary.get("food_diet_implications"), max_items=3, max_chars=220),
        "lifestyle": list_values(summary.get("lifestyle_implications"), max_items=3, max_chars=220),
        "technology": list_values(summary.get("technology_implications"), max_items=3, max_chars=220),
        "safety": list_values(summary.get("safety_concerns"), max_items=4, max_chars=240),
        "limitations": list_values(summary.get("limitations"), max_items=4, max_chars=240),
        "clinician_questions": list_values(summary.get("clinician_discussion_points"), max_items=4, max_chars=240),
        "artifact_dir": text_value(summary.get("artifact_dir", ""), 240),
    }


def compact_summary_payload(summaries: list[dict[str, Any]], limit: int = 120) -> list[dict[str, Any]]:
    return [compact_summary_record(summary) for summary in summaries[:limit]]
