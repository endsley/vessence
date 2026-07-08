from memory.v1 import conversation_manager
from memory.v1.conversation_archival import (
    TRIAGE_DECISIONS,
    archivist_triage_prompt,
    conversation_summary_prompt,
    normalize_triage_decision,
    select_archivist_model,
    should_reject_generated_summary,
    should_wait_for_smart_archival,
    triage_prefilter_decision,
)


def test_conversation_manager_uses_archival_helpers():
    assert conversation_manager.triage_prefilter_decision is triage_prefilter_decision
    assert conversation_manager.archivist_triage_prompt is archivist_triage_prompt
    assert conversation_manager.normalize_triage_decision is normalize_triage_decision
    assert conversation_manager.conversation_summary_prompt is conversation_summary_prompt
    assert conversation_manager.select_archivist_model is select_archivist_model
    assert conversation_manager.should_reject_generated_summary is should_reject_generated_summary
    assert conversation_manager.should_wait_for_smart_archival is should_wait_for_smart_archival


def test_conversation_manager_utc_helpers_preserve_naive_iso_shape():
    assert conversation_manager._utcnow().tzinfo is None
    assert "T" in conversation_manager._utcnow_iso()


def test_triage_prefilter_discards_known_noise_case_insensitively():
    assert triage_prefilter_decision("  Gemini CLI update available: 1.2.3  ") == "Discard"
    assert triage_prefilter_decision("Jane/refactor status ping") == "Discard"
    assert triage_prefilter_decision("Chieh prefers behavior-preserving refactors.") is None


def test_archivist_triage_prompt_preserves_decision_contract():
    prompt = archivist_triage_prompt("Remember the edit lock before source changes.")

    assert "Respond with ONLY one word: 'Keep', 'Forgettable', or 'Discard'." in prompt
    assert "These will expire after about one month." in prompt
    assert prompt.endswith("Memory: Remember the edit lock before source changes.")
    assert TRIAGE_DECISIONS == {"Keep", "Forgettable", "Discard"}


def test_normalize_triage_decision_preserves_retry_fallback():
    assert normalize_triage_decision("Keep") == "Keep"
    assert normalize_triage_decision("Forgettable") == "Forgettable"
    assert normalize_triage_decision("Discard") == "Discard"
    assert normalize_triage_decision(" keep ") == "Retry"
    assert normalize_triage_decision("") == "Retry"


def test_conversation_summary_prompt_preserves_summary_contract():
    prompt = conversation_summary_prompt("User asked. Jane answered.")

    assert prompt.startswith("You are a summarizer. Output ONLY a concise factual summary")
    assert "Neutral, 3rd person, 2-4 sentences max." in prompt
    assert prompt.endswith("\n\nUser asked. Jane answered.")


def test_should_reject_generated_summary_uses_case_insensitive_substring_match():
    assert should_reject_generated_summary("I need clarification before summarizing.", ["need clarification"])
    assert not should_reject_generated_summary("They discussed refactoring.", ["need clarification"])


def test_archivist_scheduling_helpers_preserve_hour_and_idle_policy():
    assert should_wait_for_smart_archival(
        current_hour=23,
        idle_seconds=30,
        smart_after_hour=22,
        smart_idle_seconds=60,
    )
    assert not should_wait_for_smart_archival(
        current_hour=21,
        idle_seconds=30,
        smart_after_hour=22,
        smart_idle_seconds=60,
    )
    assert not should_wait_for_smart_archival(
        current_hour=23,
        idle_seconds=60,
        smart_after_hour=22,
        smart_idle_seconds=60,
    )
    assert select_archivist_model(
        current_hour=23,
        idle_seconds=60,
        smart_after_hour=22,
        smart_idle_seconds=60,
        default_model="default",
        smart_model="smart",
    ) == "smart"
    assert select_archivist_model(
        current_hour=23,
        idle_seconds=59,
        smart_after_hour=22,
        smart_idle_seconds=60,
        default_model="default",
        smart_model="smart",
    ) == "default"
