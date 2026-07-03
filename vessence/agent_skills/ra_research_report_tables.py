"""Evidence-table row helpers for RA research report markdown."""

from __future__ import annotations

from typing import Any

from agent_skills.ra_research_text import clean_text


EMPTY_EVIDENCE_ROW = "| No sources processed yet | | | |"


def markdown_cell(value: Any, *, max_chars: int | None = None, escape_pipe: bool = True) -> str:
    text = clean_text(str(value or ""))
    if max_chars is not None:
        text = text[:max_chars]
    return text.replace("|", "\\|") if escape_pipe else text


def action_plan_evidence_rows(summaries: list[dict[str, Any]]) -> list[str]:
    rows = [
        "| {source} | {type} | {scope} | {implication} |".format(
            source=markdown_cell(f"`{summary.get('source_id', '')}` {clean_text(summary.get('title', ''))[:90]}"),
            type=markdown_cell(summary.get("study_type", ""), max_chars=40),
            scope=markdown_cell(summary.get("evidence_scope", ""), max_chars=40),
            implication=markdown_cell(str(summary.get("remission_relevance", "")), max_chars=180),
        )
        for summary in summaries[:40]
    ]
    return rows or [EMPTY_EVIDENCE_ROW]


def recommendation_scheme_evidence_rows(summaries: list[dict[str, Any]]) -> list[str]:
    rows = [
        "| {title} | {scope} | {relevance} | {path} |".format(
            title=markdown_cell(summary.get("title", ""), max_chars=110),
            scope=markdown_cell(summary.get("evidence_scope", ""), escape_pipe=False),
            relevance=markdown_cell(summary.get("remission_relevance", ""), max_chars=180),
            path=summary.get("artifact_dir", ""),
        )
        for summary in summaries[:30]
    ]
    return rows or [EMPTY_EVIDENCE_ROW]
