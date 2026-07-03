"""Codex synthesis prompt helpers for RA research."""

from __future__ import annotations

import json
from typing import Any

from agent_skills.ra_research_text import compact_summary_payload


CODEX_AUTOMATION_SYSTEM_PROMPT = (
    "You are a careful medical-literature synthesis assistant. "
    "You do not provide medical advice; you build a traceable research dossier."
)

CODEX_PROMPT_PREFIX = (
    "You are Jane's highest-judgment RA research synthesis pass. You are a careful "
    "medical-literature synthesis assistant, not a treating clinician. Output strict JSON only.\n\n"
)


def codex_synthesis_payload(
    *,
    mission_statement: str,
    smart_model_label: str,
    smart_provider: str,
    previous_compressed_context: str,
    new_summaries: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "mission": mission_statement,
        "safety_boundary": (
            "You are building a traceable research dossier, not giving medical advice. "
            "Do not recommend unsupervised medication, biologic/JAK inhibitor, steroid, NSAID, "
            "supplement, diet, or treatment changes. Frame concrete next steps as clinician "
            "discussion points or tracking tasks."
        ),
        "model_policy": (
            f"Use the smartest available Jane model for this task. Current configured frontier model label: "
            f"{smart_model_label}. Provider requested by cron: {smart_provider}."
        ),
        "instructions": [
            "Re-read everything found so far from the compressed context and source summaries.",
            "Reiterate the mission: help Kathia reach an asymptomatic state/sustained remission; investigate cure/drug-free remission carefully without promising it.",
            "Compress everything learned so far into a concise context summary for the next cron run.",
            "Update the recommendation scheme using only cached evidence summaries.",
            "Combine all cached research into a practical recommendation plan with specific categories: tests/labs/imaging to discuss, food/diet, lifestyle, medications/medical strategy, supplements only if evidence/safety supports clinician discussion, and emerging technologies such as vagus-nerve stimulation.",
            "For every recommendation, include evidence strength, source IDs, why it might help symptoms/remission, safety caveats, and whether it is actionable at home now, a tracking/logging step, or only a clinician discussion point.",
            "Be medically conservative: no unsupervised medication, supplement, or treatment changes.",
            "Preserve source IDs and artifact paths so Jane can trace every claim.",
            "Make the app-facing report useful to Chieh: start with what changed, what matters, what is low-value/noise, what to ask Kathia's rheumatologist, what to track, and what to research next.",
            "Do not make the report a source dump. A source should appear in the app report only when it changes a decision, clarifies a question, or is explicitly categorized as low-value/noise.",
        ],
        "previous_compressed_context": previous_compressed_context,
        "new_source_ids_this_run": [s.get("source_id", "") for s in new_summaries],
        "all_cached_source_summaries": compact_summary_payload(summaries, limit=90),
        "required_output": {
            "format": "strict JSON object only",
            "keys": {
                "mission_restatement": "short paragraph",
                "compressed_context": "Markdown context for next run, <=2500 words",
                "recommendation_scheme_markdown": "full Markdown scheme with sections: Status, Safety Boundary, Working Model, Recommendation Scheme, Tracking Checklist, Clinician Questions, Evidence Register, New Evidence This Run, Next Research Questions",
                "recommendation_plan_markdown": "action-oriented Markdown with sections: Executive Summary, At-Home Actions Now, Tracking Steps, Tests To Discuss, Food/Diet Options, Lifestyle Changes, Medical Strategy Questions, Emerging Technology/Neuromodulation, What Not To Do Without Clinician, Evidence Matrix, What Would Change This Plan",
                "useful_report_markdown": "brief Markdown for Chieh's phone with sections: Bottom Line, What Changed This Run, Most Useful Findings, Questions For Rheumatologist, What To Track, Low-Value Or Noisy Sources, Next Run Focus",
                "discoveries": ["high-signal discoveries or changed beliefs this run"],
                "open_questions": ["specific research questions for future runs"],
                "safety_flags": ["risks or places requiring rheumatologist discussion"],
            },
        },
    }


def codex_synthesis_prompt(prompt_payload: dict[str, Any]) -> str:
    return CODEX_PROMPT_PREFIX + json.dumps(prompt_payload, ensure_ascii=False)


def non_json_codex_result(mission_statement: str, response: str) -> dict[str, Any]:
    return {
        "mission_restatement": mission_statement,
        "compressed_context": response[:12000],
        "recommendation_scheme_markdown": "",
        "recommendation_plan_markdown": "",
        "discoveries": ["Codex returned non-JSON output; raw response cached."],
        "open_questions": [],
        "safety_flags": [],
    }
