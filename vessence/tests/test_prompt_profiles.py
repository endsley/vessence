from context_builder.v1 import context_builder
from context_builder.v1.prompt_profiles import (
    _classify_prompt_profile,
    _profile_for_intent_level,
    _profile_for_message_category,
)


def test_profile_for_tool_mode_uses_only_tool_context_override():
    profile = _profile_for_intent_level("tool_mode", tool_context="SMS rules")

    assert profile.name == "tool_mode"
    assert profile.include_user_background is True
    assert profile.include_memory_summary is False
    assert profile.include_tool_protocols is False
    assert profile.tool_context_override == "SMS rules"


def test_profile_for_data_greeting_and_simple_modes_preserve_flags():
    data = _profile_for_intent_level("data_mode")
    greeting = _profile_for_intent_level("greeting")
    simple = _profile_for_intent_level("simple", file_context="file.md")

    assert data.name == "data_mode"
    assert data.include_user_background is True
    assert data.include_memory_summary is False
    assert data.include_tool_protocols is False
    assert greeting.name == "greeting"
    assert greeting.include_user_background is False
    assert greeting.include_memory_summary is False
    assert greeting.include_tool_protocols is False
    assert simple.name == "simple_query"
    assert simple.include_file_context is True
    assert simple.include_memory_summary is False


def test_profile_for_unknown_intent_level_defers_to_message_classifier():
    assert _profile_for_intent_level("unknown") is None
    assert _classify_prompt_profile("where is my PDF?").name == "file_lookup"


def test_classify_prompt_profile_preserves_message_category_order():
    file_profile = _profile_for_message_category("show the vault file")
    project_profile = _profile_for_message_category("debug the API endpoint")
    factual_profile = _profile_for_message_category("who is Amy?")
    casual_profile = _profile_for_message_category("tell me more about that")

    assert file_profile.name == "file_lookup"
    assert file_profile.include_file_context is True
    assert file_profile.include_code_map is True
    assert project_profile.name == "project_work"
    assert project_profile.include_task_state is True
    assert project_profile.include_conversation_summary is True
    assert factual_profile.name == "factual_personal"
    assert factual_profile.include_user_background is True
    assert casual_profile.name == "casual_followup"
    assert casual_profile.include_memory_summary is True


def test_profile_for_message_category_uses_injected_research_decider_for_project_work():
    profile = _profile_for_message_category(
        "refactor the API endpoint",
        research_decider=lambda message: "API" in message,
    )

    assert profile.name == "project_work"
    assert profile.include_research is True


def test_classify_prompt_profile_still_dispatches_explicit_then_message_profiles():
    assert _classify_prompt_profile("ignored", intent_level="greeting").name == "greeting"
    assert _classify_prompt_profile("show the vault file").name == "file_lookup"


def test_context_builder_reexports_prompt_profile_helpers():
    assert context_builder._classify_prompt_profile is _classify_prompt_profile
    assert context_builder._profile_for_intent_level is _profile_for_intent_level
    assert context_builder._profile_for_message_category is _profile_for_message_category
