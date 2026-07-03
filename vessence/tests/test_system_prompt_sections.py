from context_builder.v1.system_prompt_sections import default_operational_sections


def test_default_operational_sections_preserve_order_and_key_headings():
    sections = default_operational_sections()

    assert [section.splitlines()[0] for section in sections] == [
        "## Standing Brain Mode — IMPORTANT OVERRIDE",
        "## Response Format — Acknowledgment",
        "## Delegation — When to Use Subagents",
        "## Rich Content Tags",
        "## Music Playback",
        "## Available Tools",
        "Prefer the user's most recent explicit message when it conflicts with older memory.",
        "## Conversational Hygiene (IMPORTANT)",
    ]
    assert "{{navigate:Life Librarian}}" in sections[3]
    assert "[MUSIC_PLAY:id]" in sections[4]
    assert "create_event" in sections[-1]


def test_default_operational_sections_returns_fresh_list():
    sections = default_operational_sections()
    sections.append("mutated")

    assert "mutated" not in default_operational_sections()
