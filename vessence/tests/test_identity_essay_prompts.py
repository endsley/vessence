from agent_skills.identity_essay_prompts import (
    NO_SELF_ESSAY_PLACEHOLDER,
    NO_USER_ESSAY_PLACEHOLDER,
    amber_identity_prompt,
    jane_identity_prompt,
    memories_text_from_documents,
    user_identity_prompt,
)


def test_memories_text_from_documents_joins_with_newlines_and_truncates():
    assert memories_text_from_documents(["alpha", "beta"], max_chars=20) == "alpha\nbeta"
    assert memories_text_from_documents(["abc", "def"], max_chars=5) == "abc\nd"


def test_user_identity_prompt_uses_existing_essay_or_placeholder():
    prompt = user_identity_prompt("", "memory one")

    assert "collective consciousness" in prompt
    assert NO_USER_ESSAY_PLACEHOLDER in prompt
    assert "memory one" in prompt

    prompt_with_existing = user_identity_prompt("old essay", "memory two")
    assert "old essay" in prompt_with_existing
    assert NO_USER_ESSAY_PLACEHOLDER not in prompt_with_existing


def test_jane_and_amber_prompts_keep_distinct_identity_roles():
    jane_prompt = jane_identity_prompt("", "shared memory")
    amber_prompt = amber_identity_prompt("", "shared memory")

    assert "I am Jane" in jane_prompt
    assert "CLI-bound builder" in jane_prompt
    assert NO_SELF_ESSAY_PLACEHOLDER in jane_prompt
    assert "shared memory" in jane_prompt

    assert "I am Amber" in amber_prompt
    assert "multimodal agent" in amber_prompt
    assert NO_SELF_ESSAY_PLACEHOLDER in amber_prompt
    assert "shared memory" in amber_prompt
