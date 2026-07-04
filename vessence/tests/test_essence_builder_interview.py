from agent_skills import essence_builder
from agent_skills.essence_builder import EssenceInterviewState
from agent_skills.essence_builder_interview import (
    extract_essence_name,
    format_questions,
    numbered_questions,
    progress_summary,
    section_display_name,
    section_intro,
    spec_document,
)


def test_essence_builder_uses_interview_helpers():
    assert essence_builder._section_display_name_helper is section_display_name
    assert essence_builder._extract_essence_name_helper is extract_essence_name
    assert essence_builder._format_questions_from_config is format_questions
    assert essence_builder._section_intro_from_config is section_intro
    assert essence_builder._progress_summary is progress_summary
    assert essence_builder._spec_document is spec_document


def test_section_display_name_preserves_bounds_fallback():
    assert section_display_name(0) == "Identity & Personality"
    assert section_display_name(11) == "Review & Approve"
    assert section_display_name(99) == "Section 99"


def test_format_questions_and_section_intro_preserve_optional_layout():
    questions = {
        0: {
            "required_questions": ["Required one?", "Required two?"],
            "optional_questions": ["Optional one?"],
        }
    }

    assert numbered_questions(["One?", "Two?"], start=3) == ["3. One?", "4. Two?"]
    assert format_questions(questions, 0, include_optional=False) == "1. Required one?\n2. Required two?"
    assert format_questions(questions, 0, include_optional=True) == (
        "1. Required one?\n"
        "2. Required two?\n"
        "\n"
        "Optional — answer these if relevant:\n"
        "3. Optional one?"
    )
    assert section_intro(["identity_personality"], questions, 0).startswith(
        "--- **Section 1/1: Identity & Personality** ---\n\n1. Required one?"
    )


def test_extract_essence_name_preserves_quote_colon_and_truncation_rules():
    assert extract_essence_name('Essence name: "Tax Helper"') == "Tax Helper"
    assert extract_essence_name("called 'Fitness Coach'") == "Fitness Coach"
    assert extract_essence_name("Name: Budget Buddy") == "Budget Buddy"
    assert extract_essence_name("x" * 80) == "x" * 60


def test_progress_summary_and_spec_document_preserve_public_output_shape():
    assert progress_summary(["identity_personality", "knowledge_base"], {0}, 1) == (
        "Sections completed: 1/2 — Identity & Personality done, next: Knowledge Base"
    )
    assert spec_document(
        ["identity_personality", "knowledge_base", "review_approve"],
        {"identity_personality": "Identity answer"},
        "Tax Helper",
    ) == (
        "# Essence Spec: Tax Helper\n"
        "\n"
        "## 1. Identity & Personality\n"
        "\n"
        "Identity answer\n"
        "\n"
        "## 2. Knowledge Base\n"
        "\n"
        "_Not yet answered._\n"
    )


def test_public_progress_and_spec_use_extracted_helpers():
    state = EssenceInterviewState(
        current_section=1,
        completed_sections={0},
        answers={"identity_personality": "Identity answer"},
        essence_name="Tax Helper",
    )

    assert essence_builder.get_progress(state).startswith("Sections completed: 1/12")
    assert essence_builder.generate_spec_document(state).startswith("# Essence Spec: Tax Helper")
