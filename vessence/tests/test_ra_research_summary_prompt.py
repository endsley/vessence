import json

from agent_skills import ra_research_cron
from agent_skills.ra_research_summary_prompt import (
    REQUIRED_SUMMARY_SCHEMA,
    SUMMARY_SYSTEM_PROMPT,
    summary_prompt_payload,
    summary_user_prompt,
)


def test_ra_research_cron_uses_summary_prompt_helpers():
    assert ra_research_cron._SUMMARY_SYSTEM_PROMPT is SUMMARY_SYSTEM_PROMPT
    assert ra_research_cron._summary_user_prompt is summary_user_prompt


def test_summary_system_prompt_preserves_evidence_reviewer_contract():
    assert "evidence reviewer" in SUMMARY_SYSTEM_PROMPT
    assert "not providing medical care" in SUMMARY_SYSTEM_PROMPT
    assert "Return one valid JSON object and no prose." in SUMMARY_SYSTEM_PROMPT


def test_summary_prompt_payload_preserves_required_schema_and_source_limit():
    payload = summary_prompt_payload(
        "Mission",
        {"source_id": "src", "title": "T"},
        "abstract_only",
        "Citation",
        "x" * 24001,
    )

    assert payload["mission"] == "Mission"
    assert payload["task"] == "Summarize this source for an RA remission/asymptomatic-state recommendation scheme."
    assert payload["required_schema"]["evidence_scope"] == "abstract_only"
    assert payload["required_schema"]["technology_implications"] == (
        REQUIRED_SUMMARY_SCHEMA["technology_implications"]
    )
    assert payload["source_metadata"] == {"source_id": "src", "title": "T"}
    assert payload["citation"] == "Citation"
    assert payload["source_text"] == "x" * 24000


def test_summary_user_prompt_uses_non_ascii_json_output():
    text = summary_user_prompt(
        "Mission",
        {"title": "Café"},
        "full_text",
        "Citation",
        "Résumé",
    )

    assert "Café" in text
    assert "Résumé" in text
    assert json.loads(text)["required_schema"]["evidence_scope"] == "full_text"
