"""Prompt construction for RA source summaries."""

from __future__ import annotations

import json
from typing import Any


SUMMARY_SYSTEM_PROMPT = (
    "You are an evidence reviewer helping Jane maintain a rheumatoid arthritis remission research dossier. "
    "You are not providing medical care. Extract only what is supported by the supplied source. "
    "If the source is abstract-only, state that limitation plainly. "
    "Return one valid JSON object and no prose."
)

REQUIRED_SUMMARY_SCHEMA = {
    "source_id": "string",
    "title": "string",
    "citation": "string",
    "url": "string",
    "evidence_scope": "string",
    "study_type": "guideline|RCT|cohort|systematic_review|mechanistic|case_series|other",
    "population": "string",
    "intervention_or_exposure": "string",
    "main_findings": ["short bullets"],
    "remission_relevance": "how this affects remission/asymptomatic strategy",
    "safety_concerns": ["risks, contraindications, uncertainty"],
    "actionable_implications": ["clinician-discussion or lifestyle-tracking ideas only"],
    "tests_or_monitoring": ["labs, imaging, biomarkers, symptom scores, clinician measurements mentioned"],
    "food_diet_implications": ["food, diet, nutrition, supplement implications if any"],
    "lifestyle_implications": ["exercise, sleep, stress, oral health, smoking, weight/metabolic implications if any"],
    "technology_implications": ["vagus nerve stimulation, neuromodulation, wearables, digital monitoring, other technology implications if any"],
    "limitations": ["limitations"],
    "clinician_discussion_points": ["questions for rheumatologist"],
}


def summary_prompt_payload(
    mission: str,
    record: dict[str, Any],
    evidence_scope: str,
    citation: str,
    readable_text: str,
    *,
    max_source_chars: int = 24000,
) -> dict[str, Any]:
    schema = dict(REQUIRED_SUMMARY_SCHEMA)
    schema["evidence_scope"] = evidence_scope
    return {
        "mission": mission,
        "task": "Summarize this source for an RA remission/asymptomatic-state recommendation scheme.",
        "required_schema": schema,
        "source_metadata": record,
        "citation": citation,
        "source_text": readable_text[:max_source_chars],
    }


def summary_user_prompt(
    mission: str,
    record: dict[str, Any],
    evidence_scope: str,
    citation: str,
    readable_text: str,
) -> str:
    return json.dumps(
        summary_prompt_payload(mission, record, evidence_scope, citation, readable_text),
        ensure_ascii=False,
    )
