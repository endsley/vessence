from agent_skills import user_manager
from agent_skills.user_manager_helpers import (
    DEFAULT_CAPABILITIES,
    config_with_defaults,
    default_user_config,
    initial_seed_facts,
    normalize_plain_user_id,
    personality_description,
    validate_capabilities,
)


def test_user_manager_uses_extracted_helpers():
    assert user_manager._normalize_plain_user_id is normalize_plain_user_id
    assert user_manager._validate_capabilities is validate_capabilities
    assert user_manager._default_user_config is default_user_config
    assert user_manager._config_with_defaults is config_with_defaults
    assert user_manager._initial_seed_facts is initial_seed_facts
    assert user_manager._personality_description is personality_description


def test_normalize_plain_user_id_preserves_whitespace_dot_and_empty_rules():
    assert normalize_plain_user_id("") == "user"
    assert normalize_plain_user_id("  Jane Doe  ") == "jane_doe"
    assert normalize_plain_user_id("jane.doe") == "jane_doe"


def test_validate_capabilities_dedupes_filters_and_falls_back():
    assert validate_capabilities(["chat", "bad", "email", "chat"]) == ["chat", "email"]
    assert validate_capabilities(["bad"]) == list(DEFAULT_CAPABILITIES)
    assert validate_capabilities(None) == list(DEFAULT_CAPABILITIES)


def test_default_and_existing_config_defaults():
    assert default_user_config("jane") == {
        "user_id": "jane",
        "personality": "default",
        "memory_namespace": "jane",
        "capabilities": list(DEFAULT_CAPABILITIES),
        "managed": False,
    }
    config = config_with_defaults(
        {"memory_chromadb_path": "/memory"},
        "managed",
        "/vault",
    )
    assert config == {
        "memory_chromadb_path": "/memory",
        "user_id": "managed",
        "personality": "default",
        "memory_namespace": "managed",
        "capabilities": list(DEFAULT_CAPABILITIES),
        "vault_root_path": "/vault",
        "managed": True,
    }


def test_initial_seed_facts_and_personality_description():
    assert initial_seed_facts("Chieh", ["likes concise answers"]) == [
        "The active user's display name is Chieh.",
        "This user has a private Jane memory space separate from other users.",
        "Jane should learn this user's preferences, history, and working context independently.",
        "likes concise answers",
    ]
    assert personality_description("Friendly Jane\nMore text") == "Friendly Jane"
    assert personality_description("") == ""
