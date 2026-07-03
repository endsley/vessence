from memory.v1.low_signal_memory import is_low_signal_shared_memory, is_low_signal_short_term_memory


def test_shared_memory_filter_drops_empty_prefix_and_noise_topics():
    assert is_low_signal_shared_memory("", {})
    assert is_low_signal_shared_memory("Logged in with Google account chieh.t.wu@gmail.com", {})
    assert is_low_signal_shared_memory("Useful-looking text", {"topic": "performance_logs"})
    assert not is_low_signal_shared_memory("Kathia prefers morning appointments.", {"topic": "family"})


def test_short_term_filter_drops_context_snapshots_and_theme_records():
    assert is_low_signal_short_term_memory("Real content", {"topic": "context_snapshot"})
    assert is_low_signal_short_term_memory("Real content", {"memory_type": "short_term_theme"})


def test_short_term_filter_drops_protocol_metadata_chatter():
    assert is_low_signal_short_term_memory("**Class Protocol:** read_calendar", {"memory_type": "short_term"})
    assert is_low_signal_short_term_memory("<class_protocol name='x'>metadata</class_protocol>", {})
    assert is_low_signal_short_term_memory(
        "I need clarification. The new turn includes class protocol metadata.",
        {"memory_type": "short_term"},
    )
    assert is_low_signal_short_term_memory(
        "User message [EXTRACTED PARAMS] class=read_calendar",
        {"memory_type": "short_term"},
    )


def test_short_term_filter_keeps_real_content_with_protocol_words():
    assert not is_low_signal_short_term_memory(
        "We discussed class protocol metadata as a documentation cleanup task.",
        {"memory_type": "short_term"},
    )
    assert not is_low_signal_short_term_memory(
        "I need clarification from the clinic about Thursday's appointment.",
        {"memory_type": "short_term"},
    )
