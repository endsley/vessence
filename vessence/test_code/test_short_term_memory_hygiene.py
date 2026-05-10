from memory.v1.conversation_manager import ConversationManager
from memory.v1.memory_retrieval import _is_low_signal_short_term_memory


def test_prepare_thematic_turn_skips_protocol_metadata_chatter():
    user_msg = """
    <class_protocol name="delegate_opus">
    route to standing brain
    </class_protocol>
    [EXTRACTED PARAMS]
    class=delegate_opus
    """
    assistant_msg = (
        'I need clarification. The "new turn" you provided is class protocol '
        "metadata, not actual conversation content."
    )

    assert ConversationManager._prepare_thematic_turn(user_msg, assistant_msg) == ""


def test_prepare_thematic_turn_keeps_real_conversation_content():
    user_msg = "When is my next medical appointment?"
    assistant_msg = "Your next appointment is May 14 at 10 AM."

    prepared = ConversationManager._prepare_thematic_turn(user_msg, assistant_msg)

    assert "User: When is my next medical appointment?" in prepared
    assert "Jane: Your next appointment is May 14 at 10 AM." in prepared


def test_bad_thematic_output_is_rejected():
    assert ConversationManager._looks_like_bad_thematic_output(
        "No action needed. The read_calendar class protocol you provided is documentation."
    )
    assert ConversationManager._looks_like_bad_thematic_output(
        "**Class Protocol: Read Calendar** The class handles calendar reads."
    )
    assert not ConversationManager._looks_like_bad_thematic_output(
        "I need clarification from the client about the API key rotation window."
    )
    assert not ConversationManager._looks_like_bad_thematic_output(
        "User asked for the next medical appointment. Jane found May 14 at 10 AM."
    )


def test_low_signal_short_term_memory_filters_legacy_context_snapshots():
    assert _is_low_signal_short_term_memory(
        "[Context snapshot 2026-04-20T01:24:36Z] Updated pipeline and tests.",
        {"topic": "context_snapshot", "memory_type": "short_term"},
    )


def test_low_signal_short_term_memory_filters_protocol_chatter():
    assert _is_low_signal_short_term_memory(
        "I need clarification. The new turn you provided is class protocol metadata.",
        {"memory_type": "short_term_theme"},
    )
    assert _is_low_signal_short_term_memory(
        "User asked for urgent todo items. Jane returned two urgent tasks.",
        {"memory_type": "short_term_theme"},
    )
    assert not _is_low_signal_short_term_memory(
        "User asked for urgent todo items. Jane returned two urgent tasks.",
        {"memory_type": "short_term"},
    )
    assert not _is_low_signal_short_term_memory(
        "I need clarification from the clinic about whether the appointment moved to Thursday.",
        {"memory_type": "short_term"},
    )


def test_resolve_archival_topic_uses_existing_theme_id():
    manager = ConversationManager.__new__(ConversationManager)
    registry = [
        {
            "theme_id": "project_vessence",
            "title": "Project: vessence",
            "description": "Vessence work",
        }
    ]

    topic = manager._resolve_archival_topic(
        {
            "kind": "theme",
            "existing_theme_id": "project_vessence",
            "new_theme_title": "",
            "atomic_topic": "",
        },
        registry,
    )

    assert topic == "Project: vessence"


def test_resolve_archival_topic_registers_new_theme_title():
    manager = ConversationManager.__new__(ConversationManager)
    manager._register_new_theme = lambda title, description="": {
        "theme_id": "theme_123",
        "title": title,
        "description": description,
        "built_in": 0,
    }
    registry = []

    topic = manager._resolve_archival_topic(
        {
            "kind": "theme",
            "existing_theme_id": "",
            "new_theme_title": "Claude CLI Memory Flow",
            "atomic_topic": "",
        },
        registry,
    )

    assert topic == "Claude CLI Memory Flow"
    assert registry[0]["theme_id"] == "theme_123"
    assert registry[0]["title"] == "Claude CLI Memory Flow"
