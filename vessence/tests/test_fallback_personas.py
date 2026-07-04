from agent_skills.fallback_personas import (
    amber_capability_text,
    amber_fallback_persona,
    build_amber_persona,
    build_jane_persona,
    persona_essay_section,
    user_essay_title,
)


def test_persona_helper_sections_preserve_capability_and_essay_shapes():
    assert amber_capability_text(
        [
            {
                "name": "Calendar",
                "description": "Manage events",
                "tools": ["calendar"],
                "fallback_tag": "[CALENDAR]",
            },
            {
                "name": "Notes",
                "description": "Read notes",
                "tools": ["vault", "search"],
            },
        ]
    ) == (
        "- Calendar: Manage events (Tools: calendar)\n"
        "  IMPORTANT: To use this, say '[CALENDAR]' on a new line.\n"
        "- Notes: Read notes (Tools: vault, search)\n"
    )
    assert persona_essay_section("YOUR IDENTITY (Jane)", "Jane essay") == (
        "\n\n## YOUR IDENTITY (Jane):\nJane essay"
    )
    assert persona_essay_section("ABOUT USER", "") == ""
    assert user_essay_title("the user", "user") == "ABOUT USER (your user)"
    assert user_essay_title("Chieh") == "ABOUT CHIEH (your user)"


def test_build_amber_persona_preserves_manifest_sections_and_essays():
    manifest = {
        "identity": "Amber",
        "role": "clinic assistant.",
        "family_context": "Family context",
        "capabilities": [
            {
                "name": "Calendar",
                "description": "Manage events",
                "tools": ["calendar"],
                "fallback_tag": "[CALENDAR]",
            },
            {
                "name": "Notes",
                "description": "Read notes",
                "tools": ["vault", "search"],
            },
        ],
        "identity_rules": ["Stay warm"],
        "visuals": {"self": "amber.png", "colleague": "jane.png"},
    }

    persona = build_amber_persona(
        manifest,
        user_name="Chieh",
        amber_essay="Amber essay",
        user_essay="User essay",
        jane_essay="Jane essay",
    )

    assert persona.startswith(
        "You are Amber, clinic assistant. Family: Family context. "
        "You are currently an emergency fallback brain."
    )
    assert "- Calendar: Manage events (Tools: calendar)" in persona
    assert "IMPORTANT: To use this, say '[CALENDAR]' on a new line." in persona
    assert "- Notes: Read notes (Tools: vault, search)" in persona
    assert "\nIDENTITY RULES:\n- Stay warm\n" in persona
    assert "Your photo is 'amber.png'. Jane is 'jane.png'." in persona
    assert "stay in character as Chieh's assistant Amber." in persona
    assert "## YOUR IDENTITY (Amber):\nAmber essay" in persona
    assert "## ABOUT CHIEH (your user):\nUser essay" in persona
    assert "## ABOUT JANE (your colleague):\nJane essay" in persona


def test_amber_fallback_persona_preserves_basic_fallback_text():
    assert amber_fallback_persona("Chieh") == (
        "You are Amber, Chieh's assistant. You are currently in fallback mode."
    )


def test_build_jane_persona_appends_optional_identity_context():
    persona = build_jane_persona(
        user_name="Chieh",
        jane_essay="Jane essay",
        user_essay="User essay",
    )

    assert persona.startswith(
        "You are Jane, Chieh's technical expert and friend. "
        "You are currently acting as an emergency fallback"
    )
    assert "## YOUR IDENTITY (Jane):\nJane essay" in persona
    assert "## ABOUT CHIEH (your user):\nUser essay" in persona


def test_build_jane_persona_omits_empty_essay_sections():
    persona = build_jane_persona(user_name="the user")

    assert "## YOUR IDENTITY" not in persona
    assert "## ABOUT" not in persona


def test_persona_builders_allow_original_distinct_user_label_defaults():
    amber = build_amber_persona(
        {
            "identity": "Amber",
            "role": "assistant.",
            "family_context": "None",
            "capabilities": [],
            "visuals": {"self": "amber.png", "colleague": "jane.png"},
        },
        user_name="the user",
        essay_user_name="user",
        user_essay="User essay",
    )
    jane = build_jane_persona(
        user_name="the user",
        essay_user_name="user",
        user_essay="User essay",
    )

    assert "the user's assistant Amber" in amber
    assert "## ABOUT USER (your user):\nUser essay" in amber
    assert "Jane, the user's technical expert" in jane
    assert "## ABOUT USER (your user):\nUser essay" in jane
