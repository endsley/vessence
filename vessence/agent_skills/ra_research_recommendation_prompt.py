"""Recommendation-scheme prompt helpers for RA research."""

from __future__ import annotations

import json
from typing import Any

from agent_skills.ra_research_text import compact_summary_payload


RECOMMENDATION_SYSTEM_PROMPT = (
    "You are Jane's medical literature synthesis assistant for rheumatoid arthritis research. "
    "Your output is a cautious research plan for Chieh to discuss with Kathia and her rheumatologist. "
    "Never instruct medication changes. Distinguish strong guideline evidence from weak adjunct evidence. "
    "Be concrete about what to track, what to ask the clinician, and what evidence has been saved."
)

RECOMMENDATION_PROMPT_PREFIX = (
    "Regenerate the living RA remission/asymptomatic-state recommendation scheme as Markdown. "
    "Required sections: Status, Safety Boundary, Current Working Model, Recommendation Scheme, "
    "Tracking Checklist, Clinician Questions, Evidence Register, New Evidence This Run, "
    "Next Research Questions. The loop status is ongoing until Chieh reports Kathia is asymptomatic "
    "or stops the cron. Use only the evidence summaries below.\n\n"
)

SAFETY_NOTE = (
    "Safety note: this is a research dossier, not medical advice. Medication and supplement "
    "changes must be discussed with Kathia's rheumatologist.\n\n"
)


def recommendation_user_prompt(
    *,
    generated_at: str,
    mission_statement: str,
    new_summaries: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
) -> str:
    return RECOMMENDATION_PROMPT_PREFIX + json.dumps(
        {
            "generated_at": generated_at,
            "mission": mission_statement,
            "new_source_ids_this_run": [s.get("source_id") for s in new_summaries],
            "summaries": compact_summary_payload(summaries, limit=80),
        },
        ensure_ascii=False,
    )


def has_safety_guard_text(generated: str) -> bool:
    text = generated.lower()
    return "medical advice" in text or "rheumatologist" in text


def ensure_safety_note(generated: str) -> str:
    if not has_safety_guard_text(generated):
        return SAFETY_NOTE + generated
    return generated
