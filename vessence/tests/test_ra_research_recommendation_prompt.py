import json

from agent_skills import ra_research_cron
from agent_skills.ra_research_recommendation_prompt import (
    RECOMMENDATION_PROMPT_PREFIX,
    RECOMMENDATION_SYSTEM_PROMPT,
    SAFETY_NOTE,
    ensure_safety_note,
    recommendation_user_prompt,
)


def test_ra_research_cron_uses_recommendation_prompt_helpers():
    assert ra_research_cron._RECOMMENDATION_SYSTEM_PROMPT is RECOMMENDATION_SYSTEM_PROMPT
    assert ra_research_cron._recommendation_user_prompt is recommendation_user_prompt
    assert ra_research_cron._ensure_safety_note is ensure_safety_note


def test_recommendation_user_prompt_preserves_payload_and_non_ascii_json():
    prompt = recommendation_user_prompt(
        generated_at="2026-07-02T12:00:00",
        mission_statement="Mission",
        new_summaries=[{"source_id": "new1"}, {}],
        summaries=[{"source_id": "s1", "title": "Café", "main_findings": ["Finding"]}],
    )

    assert prompt.startswith(RECOMMENDATION_PROMPT_PREFIX)
    payload = json.loads(prompt[len(RECOMMENDATION_PROMPT_PREFIX):])
    assert payload["generated_at"] == "2026-07-02T12:00:00"
    assert payload["mission"] == "Mission"
    assert payload["new_source_ids_this_run"] == ["new1", None]
    assert payload["summaries"][0]["title"] == "Café"
    assert "Café" in prompt


def test_ensure_safety_note_preserves_existing_guard_condition():
    assert ensure_safety_note("Already mentions medical advice.") == "Already mentions medical advice."
    assert ensure_safety_note("Already mentions rheumatologist.") == "Already mentions rheumatologist."
    assert ensure_safety_note("No guard here.") == SAFETY_NOTE + "No guard here."
