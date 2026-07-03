"""Source identity and fallback-summary helpers for RA research."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_skills.ra_research_text import clean_text


def source_cache_key(record: dict[str, Any]) -> str:
    for key in ("pmid", "pmcid", "doi", "source_id", "url"):
        value = str(record.get(key) or "").strip()
        if value:
            return value
    return record["source_id"]


def citation_for(record: dict[str, Any]) -> str:
    authors = record.get("authors") or []
    author_part = ", ".join(authors[:3])
    if len(authors) > 3:
        author_part += " et al."
    return " ".join(
        part
        for part in [
            author_part,
            f"({record.get('published')})" if record.get("published") else "",
            record.get("title", ""),
            record.get("journal", ""),
            f"PMID:{record.get('pmid')}" if record.get("pmid") else "",
            f"DOI:{record.get('doi')}" if record.get("doi") else "",
        ]
        if part
    )


def fallback_summary_payload(
    record: dict[str, Any],
    evidence_scope: str,
    artifact_dir: Path,
    text: str,
    *,
    summarized_at: str,
) -> dict[str, Any]:
    first_sentence = clean_text(text).split(". ")[0][:500]
    return {
        "source_id": record["source_id"],
        "title": record.get("title", ""),
        "citation": citation_for(record),
        "url": record.get("url", ""),
        "evidence_scope": evidence_scope,
        "study_type": ", ".join(record.get("publication_types", [])[:4]) or record.get("kind", "unknown"),
        "population": "Not extracted by fallback summarizer.",
        "intervention_or_exposure": "Not extracted by fallback summarizer.",
        "main_findings": [first_sentence] if first_sentence else [],
        "remission_relevance": "Needs manual/LLM review; source was saved and cached.",
        "safety_concerns": [],
        "actionable_implications": [],
        "tests_or_monitoring": [],
        "food_diet_implications": [],
        "lifestyle_implications": [],
        "technology_implications": [],
        "limitations": ["Fallback summary because local LLM was unavailable or returned invalid JSON."],
        "clinician_discussion_points": [],
        "artifact_dir": str(artifact_dir),
        "needs_llm_review": True,
        "summarized_at": summarized_at,
    }
