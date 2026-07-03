import pytest

from agent_skills import omniparser_skill
from agent_skills.omniparser_output import (
    format_parsed_elements,
    json_text_from_output,
    parsed_result_from_output,
)


def test_omniparser_skill_uses_extracted_output_parser():
    assert omniparser_skill._parsed_result_from_output is parsed_result_from_output


def test_json_text_from_output_prefers_elements_object_and_falls_back_to_last_brace():
    assert json_text_from_output('warn\n{"elements": []}') == '{"elements": []}'
    assert json_text_from_output('warn\n{"other": true}') == '{"other": true}'
    assert json_text_from_output("no json") is None


def test_format_parsed_elements_preserves_existing_text_shape():
    assert format_parsed_elements(
        [
            {"type": "button", "bbox": [1, 2, 3, 4], "content": "Save"},
            {"type": "text"},
        ]
    ) == (
        "Element 0: button at [1, 2, 3, 4] - Content: Save\n"
        "Element 1: text at None - Content: None"
    )


def test_parsed_result_from_output_builds_service_result():
    result = parsed_result_from_output(
        'logs\n{"elements": [{"type": "button", "bbox": [1], "content": "Save"}], '
        '"labeled_image_base64": "abc"}'
    )

    assert result == {
        "labeled_image": "abc",
        "parsed_content": "Element 0: button at [1] - Content: Save",
        "elements": [{"type": "button", "bbox": [1], "content": "Save"}],
    }


def test_parsed_result_from_output_preserves_error_messages():
    with pytest.raises(Exception, match="Failed to find JSON"):
        parsed_result_from_output("no json")
    with pytest.raises(Exception, match="OmniParser API Error: bad"):
        parsed_result_from_output('{"error": "bad"}')
