from agent_skills import ra_research_cron
from agent_skills.ra_research_codex_outputs import (
    codex_synthesis_markdown,
    compressed_context_document,
    selected_codex_markdown,
)


def test_ra_research_cron_uses_codex_output_helpers():
    assert ra_research_cron._codex_synthesis_markdown is codex_synthesis_markdown
    assert ra_research_cron._compressed_context_document is compressed_context_document
    assert ra_research_cron._selected_codex_markdown is selected_codex_markdown


def test_codex_synthesis_markdown_preserves_section_shape():
    markdown = codex_synthesis_markdown(
        "20260702",
        {
            "mission_restatement": "Mission",
            "discoveries": ["Discovery"],
            "safety_flags": ["Flag"],
            "open_questions": ["Question"],
            "compressed_context": "Context",
        },
        "Fallback mission",
    )

    assert markdown == (
        "# Codex RA Synthesis 20260702\n"
        "\n"
        "## Mission Restatement\n"
        "Mission\n"
        "\n"
        "## Discoveries\n"
        "- Discovery\n"
        "\n"
        "## Safety Flags\n"
        "- Flag\n"
        "\n"
        "## Open Questions\n"
        "- Question\n"
        "\n"
        "## Compressed Context\n"
        "Context\n"
    )


def test_codex_synthesis_markdown_uses_mission_fallback():
    assert "Fallback mission" in codex_synthesis_markdown("run", {}, "Fallback mission")


def test_compressed_context_document_preserves_header_shape():
    assert compressed_context_document("Context", "2026-07-02T12:00:00") == (
        "# RA Research Compressed Context\n"
        "\n"
        "Updated: 2026-07-02T12:00:00\n"
        "\n"
        "Context\n"
    )


def test_selected_codex_markdown_preserves_threshold_and_newline_behavior():
    assert selected_codex_markdown(
        {"recommendation_scheme_markdown": "x" * 799},
        "recommendation_scheme_markdown",
        "fallback",
    ) == "fallback"
    assert selected_codex_markdown(
        {"recommendation_scheme_markdown": "  " + ("x" * 800) + "  "},
        "recommendation_scheme_markdown",
        "fallback",
    ) == ("x" * 800) + "\n"
