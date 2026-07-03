"""Summary cache and artifact helpers for the RA research cron."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_skills.ra_research_text import clean_text


def read_json_dict(path: Path) -> dict[str, Any] | None:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def load_cached_summary(path: Path) -> tuple[dict[str, Any] | None, bool]:
    summary = read_json_dict(path) if path.exists() else None
    reusable = bool(summary and not summary.get("needs_llm_review"))
    return summary, reusable


def finalize_summary_for_cache(
    summary: dict[str, Any],
    record: dict[str, Any],
    *,
    artifact_dir: Path,
    evidence_scope: str,
    cache_key: str,
    summarized_at: str,
    citation: str,
) -> dict[str, Any]:
    summary.setdefault("source_id", record["source_id"])
    summary.setdefault("title", record.get("title", ""))
    summary.setdefault("citation", citation)
    summary.setdefault("url", record.get("url", ""))
    summary.setdefault("evidence_scope", evidence_scope)
    summary["artifact_dir"] = str(artifact_dir)
    summary["cache_key"] = cache_key
    summary["summarized_at"] = summarized_at
    return summary


def build_processed_source_entry(
    record: dict[str, Any],
    *,
    source_id: str,
    artifact_dir: Path,
    summary_dir: Path,
    evidence_scope: str,
    cache_key: str,
    processed_at: str,
) -> dict[str, Any]:
    return {
        "title": record.get("title", ""),
        "url": record.get("url", ""),
        "processed_at": processed_at,
        "artifact_dir": str(artifact_dir),
        "summary_path": str(summary_dir / f"{source_id}.json"),
        "evidence_scope": evidence_scope,
        "cache_key": cache_key,
    }


def readable_text_from_artifact(artifact_dir: Path) -> str:
    for name in ("full_text.txt", "readable_text.txt", "abstract.txt"):
        path = artifact_dir / name
        if path.exists():
            try:
                return path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
    return ""


def summary_to_markdown(summary: dict[str, Any]) -> str:
    def list_md(values: Any) -> str:
        if isinstance(values, list) and values:
            return "\n".join(f"- {clean_text(str(value))}" for value in values if str(value).strip())
        if values:
            return f"- {clean_text(str(values))}"
        return "- None captured."

    return (
        f"# {summary.get('title', 'Untitled source')}\n\n"
        f"- Source ID: `{summary.get('source_id', '')}`\n"
        f"- Citation: {summary.get('citation', '')}\n"
        f"- URL: {summary.get('url', '')}\n"
        f"- Evidence scope: {summary.get('evidence_scope', '')}\n"
        f"- Study type: {summary.get('study_type', '')}\n"
        f"- Saved artifact directory: `{summary.get('artifact_dir', '')}`\n\n"
        f"## Population\n"
        f"{summary.get('population', '')}\n\n"
        f"## Intervention Or Exposure\n"
        f"{summary.get('intervention_or_exposure', '')}\n\n"
        f"## Main Findings\n"
        f"{list_md(summary.get('main_findings'))}\n\n"
        f"## Remission Relevance\n"
        f"{summary.get('remission_relevance', '')}\n\n"
        f"## Actionable Implications\n"
        f"{list_md(summary.get('actionable_implications'))}\n\n"
        f"## Tests Or Monitoring\n"
        f"{list_md(summary.get('tests_or_monitoring'))}\n\n"
        f"## Food / Diet Implications\n"
        f"{list_md(summary.get('food_diet_implications'))}\n\n"
        f"## Lifestyle Implications\n"
        f"{list_md(summary.get('lifestyle_implications'))}\n\n"
        f"## Technology Implications\n"
        f"{list_md(summary.get('technology_implications'))}\n\n"
        f"## Safety Concerns\n"
        f"{list_md(summary.get('safety_concerns'))}\n\n"
        f"## Limitations\n"
        f"{list_md(summary.get('limitations'))}\n\n"
        f"## Clinician Discussion Points\n"
        f"{list_md(summary.get('clinician_discussion_points'))}\n"
    )
