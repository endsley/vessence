from agent_skills import research_analyzer, research_assistant
from agent_skills.research_result_helpers import (
    analyzer_error_result,
    analyzer_missing_file_result,
    analyzer_no_solution_result,
    analyzer_result_from_model_content,
    extract_json_text,
    parse_research_note_json,
)


def test_research_scripts_expose_result_helpers():
    assert research_analyzer._analyzer_error_result is analyzer_error_result
    assert research_analyzer._analyzer_missing_file_result is analyzer_missing_file_result
    assert research_analyzer._analyzer_result_from_model_content is analyzer_result_from_model_content
    assert research_assistant._parse_research_note_json is parse_research_note_json


def test_analyzer_result_shapes_preserve_existing_contract():
    assert analyzer_missing_file_result() == {
        "confidence": "low",
        "cause": "File not found",
        "fix": "",
        "source": "",
        "found": False,
    }
    assert analyzer_no_solution_result() == {
        "confidence": "low",
        "cause": "No clear solution in data",
        "fix": "",
        "source": "",
        "found": False,
    }
    assert analyzer_error_result("boom") == {
        "confidence": "low",
        "cause": "Analysis Error: boom",
        "fix": "",
        "source": "",
        "found": False,
    }


def test_analyzer_result_from_model_content_handles_no_solution_and_success_json():
    assert analyzer_result_from_model_content("NO_SOLUTION_FOUND") == analyzer_no_solution_result()
    assert analyzer_result_from_model_content('{"confidence": "high", "cause": "C", "fix": "F"}') == {
        "confidence": "high",
        "cause": "C",
        "fix": "F",
        "found": True,
    }


def test_research_note_json_extraction_strips_code_fences():
    assert extract_json_text('```json\n{"cause": "C"}\n```').strip() == '{"cause": "C"}'
    assert extract_json_text('```\n{"cause": "C"}\n```').strip() == '{"cause": "C"}'
    assert parse_research_note_json('```json\n{"cause": "C", "fix": "F"}\n```') == {
        "cause": "C",
        "fix": "F",
    }
