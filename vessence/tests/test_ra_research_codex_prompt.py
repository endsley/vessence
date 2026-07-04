import json

from agent_skills import ra_research_cron
from agent_skills.ra_research_codex_prompt import (
    CODEX_AUTOMATION_SYSTEM_PROMPT,
    CODEX_PROMPT_PREFIX,
    codex_model_policy,
    codex_required_output_contract,
    codex_safety_boundary,
    codex_synthesis_instructions,
    codex_synthesis_payload,
    codex_synthesis_prompt,
    non_json_codex_result,
    source_ids_from_summaries,
)


def test_ra_research_cron_uses_codex_prompt_helpers():
    assert ra_research_cron._CODEX_AUTOMATION_SYSTEM_PROMPT is CODEX_AUTOMATION_SYSTEM_PROMPT
    assert ra_research_cron._codex_synthesis_payload is codex_synthesis_payload
    assert ra_research_cron._codex_synthesis_prompt is codex_synthesis_prompt
    assert ra_research_cron._non_json_codex_result is non_json_codex_result


def test_codex_synthesis_payload_preserves_contract_shape():
    payload = codex_synthesis_payload(
        mission_statement="Mission",
        smart_model_label="frontier",
        smart_provider="codex",
        previous_compressed_context="Previous",
        new_summaries=[{"source_id": "new1"}, {}],
        summaries=[
            {
                "source_id": "s1",
                "title": "Title",
                "main_findings": ["Finding"],
                "actionable_implications": ["Action"],
            }
        ],
    )

    assert payload["mission"] == "Mission"
    assert "frontier" in payload["model_policy"]
    assert "codex" in payload["model_policy"]
    assert payload["previous_compressed_context"] == "Previous"
    assert payload["new_source_ids_this_run"] == ["new1", ""]
    assert payload["all_cached_source_summaries"][0]["source_id"] == "s1"
    assert payload["required_output"]["format"] == "strict JSON object only"
    assert "useful_report_markdown" in payload["required_output"]["keys"]


def test_source_ids_from_summaries_preserves_missing_source_slots():
    assert source_ids_from_summaries([{"source_id": "new1"}, {}, {"source_id": "new3"}]) == [
        "new1",
        "",
        "new3",
    ]


def test_codex_payload_contract_helpers_preserve_safety_policy_and_required_keys():
    assert "not giving medical advice" in codex_safety_boundary()
    assert "frontier" in codex_model_policy("frontier", "codex")
    assert "codex" in codex_model_policy("frontier", "codex")
    instructions = codex_synthesis_instructions()
    assert instructions[0].startswith("Re-read everything found so far")
    assert instructions[-1].startswith("Do not make the report a source dump")
    contract = codex_required_output_contract()
    assert contract["format"] == "strict JSON object only"
    assert "recommendation_scheme_markdown" in contract["keys"]
    assert contract["keys"]["discoveries"] == ["high-signal discoveries or changed beliefs this run"]


def test_codex_synthesis_prompt_preserves_prefix_and_non_ascii_json():
    payload = {"mission": "Café"}
    prompt = codex_synthesis_prompt(payload)

    assert prompt.startswith(CODEX_PROMPT_PREFIX)
    assert "Café" in prompt
    assert json.loads(prompt[len(CODEX_PROMPT_PREFIX):]) == payload


def test_non_json_codex_result_preserves_fallback_shape_and_truncation():
    result = non_json_codex_result("Mission", "x" * 12001)

    assert result == {
        "mission_restatement": "Mission",
        "compressed_context": "x" * 12000,
        "recommendation_scheme_markdown": "",
        "recommendation_plan_markdown": "",
        "discoveries": ["Codex returned non-JSON output; raw response cached."],
        "open_questions": [],
        "safety_flags": [],
    }
