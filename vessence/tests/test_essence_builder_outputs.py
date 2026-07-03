from agent_skills import essence_builder
from agent_skills.essence_builder_outputs import (
    custom_tools_stub,
    essence_layout_payload,
    onboarding_payload,
    should_write_custom_functions,
)


def test_essence_builder_uses_output_helpers():
    assert essence_builder._custom_tools_stub is custom_tools_stub
    assert essence_builder._essence_layout_payload is essence_layout_payload
    assert essence_builder._onboarding_payload is onboarding_payload
    assert essence_builder._should_write_custom_functions is should_write_custom_functions


def test_should_write_custom_functions_preserves_existing_no_values():
    assert should_write_custom_functions("Build a scraper") is True
    assert should_write_custom_functions("") is False
    assert should_write_custom_functions(" none ") is False
    assert should_write_custom_functions("N/A") is False
    assert should_write_custom_functions("NO") is False


def test_custom_tools_stub_preserves_existing_text_shape():
    assert custom_tools_stub("Tax Helper", "Do taxes") == (
        '"""\n'
        "Custom tools for Tax Helper\n"
        "\n"
        "Based on spec:\n"
        "Do taxes\n"
        "\n"
        'TODO: Implement the functions described above.\n'
        '"""\n'
    )


def test_essence_layout_payload_preserves_component_shape_and_note_limit():
    payload = essence_layout_payload("dashboard", "x" * 501)

    assert payload == {
        "type": "dashboard",
        "components": [
            {
                "id": "main",
                "type": "dashboard_panel",
                "position": "main",
            }
        ],
        "notes": "x" * 500,
    }


def test_onboarding_payload_preserves_shape_and_note_limit():
    assert onboarding_payload(["Start"], "y" * 501) == {
        "onboarding": {
            "conversation_starters": ["Start"],
            "steps": [],
            "notes": "y" * 500,
        }
    }
