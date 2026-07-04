from agent_skills import essence_builder
from agent_skills.essence_builder import EssenceInterviewState, generate_manifest
from agent_skills.essence_builder_manifest import manifest_from_answers
from agent_skills.essence_builder_parsing import (
    candidate_mentioned,
    credentials_from_answer,
    extract_list_from_answer,
    extract_model_id,
    extract_quoted_strings,
    extract_role_title,
    extract_section_fragment,
    sanitize_essence_folder_name,
    select_permissions,
    select_shared_skills,
    select_ui_type,
    trigger_list_from_answer,
)


def test_essence_builder_preserves_private_parsing_aliases():
    assert essence_builder._extract_role_title is extract_role_title
    assert essence_builder._extract_list_from_answer is extract_list_from_answer
    assert essence_builder._extract_quoted_strings is extract_quoted_strings
    assert essence_builder._extract_section_fragment is extract_section_fragment
    assert essence_builder._manifest_from_answers is manifest_from_answers


def test_extract_role_title_preserves_marker_and_fallback_rules():
    assert extract_role_title("Role title: accountant.") == "the accountant"
    assert extract_role_title("This should act as the tutor for students.") == "the tutor"
    assert extract_role_title("No explicit role here") == "the specialist"


def test_extract_list_from_answer_uses_keyword_lines_and_bullets():
    assert extract_list_from_answer(
        "Provides: tax_preparation, document_analysis\n- audit reports",
        "provide",
    ) == ["tax_preparation", "document_analysis", "audit reports"]


def test_extract_quoted_strings_prefers_quotes_then_bullets():
    assert extract_quoted_strings('"Review my file" and "Draft a memo"') == [
        "Review my file",
        "Draft a memo",
    ]
    assert extract_quoted_strings("- Review file\n2. Draft memo") == [
        "Review file",
        "Draft memo",
    ]


def test_extract_section_fragment_keeps_matching_lines_or_default():
    assert extract_section_fragment("Style: concise\nRules: cite sources", "style") == "- Style: concise"
    assert extract_section_fragment("No matching line", "style") == (
        "- (To be refined based on interview answers)"
    )


def test_manifest_parse_helpers_preserve_selection_rules():
    assert candidate_mentioned("use screen control", "screen_control")
    assert candidate_mentioned("use screen_control", "screen_control")
    assert not candidate_mentioned("use clipboard", "screen_control")
    assert select_shared_skills("Use memory read write and web search") == [
        "memory_read_write",
        "web_search",
    ]
    assert select_ui_type("A dashboard with forms") == "dashboard"
    assert select_permissions("Needs internet and screen control") == [
        "internet",
        "screen_control",
    ]
    assert extract_model_id("Use Gemini Flash") == "gemini-flash"
    assert extract_model_id("Use something unknown") == "claude-sonnet-4-6"


def test_trigger_credentials_and_folder_name_helpers():
    assert trigger_list_from_answer("Daily at 9am") == [
        {"condition": "custom", "description": "Daily at 9am"}
    ]
    assert trigger_list_from_answer("n/a") == []
    assert credentials_from_answer("Required API key for service") == [
        {
            "name": "CUSTOM_API_KEY",
            "description": "Required API key for service",
            "required": True,
        }
    ]
    assert credentials_from_answer("No credentials") == [
        {
            "name": "CUSTOM_API_KEY",
            "description": "No credentials",
            "required": False,
        }
    ]
    assert sanitize_essence_folder_name("Tax-Coach 2026!") == "tax_coach_2026"
    assert sanitize_essence_folder_name("!!!") == "new_essence"


def test_generate_manifest_uses_extracted_parsing_rules():
    state = EssenceInterviewState(
        essence_name="Tax Coach",
        answers={
            "identity_personality": "Role title: accountant",
            "knowledge_base": "Tax knowledge",
            "shared_skills": "memory read write, web search",
            "ui_paradigm": "dashboard",
            "permissions_credentials": "Required API key with internet",
            "capabilities_declaration": "Provides: tax_preparation\nConsumes: file_storage",
            "preferred_model": "gpt 4o",
            "interaction_patterns": '"Review taxes"',
            "triggers_automations": "Monthly reminder",
        },
    )

    manifest = generate_manifest(state)

    assert manifest["role_title"] == "the accountant"
    assert manifest["shared_skills"] == ["memory_read_write", "web_search"]
    assert manifest["ui"]["type"] == "dashboard"
    assert manifest["permissions"] == ["internet"]
    assert manifest["external_credentials"][0]["required"] is True
    assert manifest["capabilities"] == {
        "provides": ["tax_preparation"],
        "consumes": ["file_storage"],
    }
    assert manifest["preferred_model"]["model_id"] == "gpt-4o"
    assert manifest["interaction_patterns"]["conversation_starters"] == ["Review taxes"]
    assert manifest["interaction_patterns"]["proactive_triggers"] == [
        {"condition": "custom", "description": "Monthly reminder"}
    ]


def test_manifest_from_answers_preserves_defaults_and_truncation_rules():
    manifest = manifest_from_answers(
        "Long Helper",
        {
            "identity_personality": "No role marker",
            "knowledge_base": "k" * 250,
            "preferred_model": "Use unknown model because " + ("r" * 320),
        },
    )

    assert manifest["essence_name"] == "Long Helper"
    assert manifest["role_title"] == "the specialist"
    assert manifest["description"] == "k" * 200
    assert manifest["preferred_model"] == {
        "model_id": "claude-sonnet-4-6",
        "reasoning": ("Use unknown model because " + ("r" * 320))[:300],
    }
    assert manifest["permissions"] == []
    assert manifest["external_credentials"] == []
    assert manifest["capabilities"] == {"provides": [], "consumes": []}
    assert manifest["ui"] == {"type": "chat", "entry_layout": "ui/layout.json"}
    assert manifest["shared_skills"] == []
    assert manifest["interaction_patterns"] == {
        "conversation_starters": [],
        "proactive_triggers": [],
    }
