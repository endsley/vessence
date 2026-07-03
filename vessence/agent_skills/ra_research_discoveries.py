"""Discovery log rendering helpers for RA research."""

from __future__ import annotations

from typing import Any

from agent_skills.ra_research_report_markdown import list_to_markdown


def discovery_block(
    run_id: str,
    timestamp_label: str,
    mission_statement: str,
    discoveries: Any,
    safety_flags: Any,
    open_questions: Any,
) -> str:
    return (
        f"\n## Run {run_id} — {timestamp_label}\n\n"
        f"Mission: {mission_statement}\n\n"
        f"### Discoveries\n{list_to_markdown(discoveries)}\n\n"
        f"### Safety Flags\n{list_to_markdown(safety_flags)}\n\n"
        f"### Open Questions\n{list_to_markdown(open_questions)}\n"
    )
