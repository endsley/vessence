"""Codex synthesis output helpers for RA research."""

from __future__ import annotations

import textwrap
from typing import Any

from agent_skills.ra_research_report_markdown import list_to_markdown


def codex_synthesis_markdown(
    run_id: str,
    codex_result: dict[str, Any],
    mission_statement: str,
) -> str:
    discoveries = codex_result.get("discoveries") or []
    open_questions = codex_result.get("open_questions") or []
    safety_flags = codex_result.get("safety_flags") or []
    return textwrap.dedent(
        f"""\
        # Codex RA Synthesis {run_id}

        ## Mission Restatement
        {codex_result.get('mission_restatement', mission_statement)}

        ## Discoveries
        {list_to_markdown(discoveries)}

        ## Safety Flags
        {list_to_markdown(safety_flags)}

        ## Open Questions
        {list_to_markdown(open_questions)}

        ## Compressed Context
        {codex_result.get('compressed_context', '')}
        """
    ).strip() + "\n"


def compressed_context_document(compressed_context: str, updated_label: str) -> str:
    return f"# RA Research Compressed Context\n\nUpdated: {updated_label}\n\n{compressed_context}\n"


def selected_codex_markdown(
    codex_result: dict[str, Any],
    key: str,
    fallback: str,
    *,
    min_chars: int = 800,
) -> str:
    generated = str(codex_result.get(key) or "").strip()
    if len(generated) < min_chars:
        return fallback
    return generated + "\n"
