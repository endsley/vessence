from context_builder.v1 import context_builder
from context_builder.v1.recent_history import build_user_transcript, format_recent_history


def test_format_recent_history_labels_roles_and_normalizes_content():
    history = [
        {"role": "user", "content": " hello\n there "},
        {"role": "assistant", "content": "Hi   Chieh"},
        {"role": "system", "content": " ignored role still user "},
        {"role": "assistant", "content": ""},
    ]

    assert format_recent_history(history) == (
        "User: hello there\n"
        "Jane: Hi Chieh\n"
        "User: ignored role still user"
    )


def test_format_recent_history_uses_last_turns_and_max_chars():
    history = [
        {"role": "user", "content": f"turn {index}"}
        for index in range(8)
    ]

    assert format_recent_history(history, max_turns=3) == (
        "User: turn 5\n"
        "User: turn 6\n"
        "User: turn 7"
    )
    assert format_recent_history([{"role": "assistant", "content": "123456789"}], max_chars=9) == "Jane: 12..."
    assert format_recent_history([{"role": "assistant", "content": "123456789"}], max_chars=5) == ""


def test_context_builder_reexports_recent_history_helper():
    assert context_builder._format_recent_history is format_recent_history
    assert context_builder._build_user_transcript is build_user_transcript


def test_build_user_transcript_preserves_recent_history_block_shape():
    assert build_user_transcript("What next?", "") == "User: What next?\n\nJane:"
    assert build_user_transcript("What next?", "User: prior\nJane: answer") == (
        "Recent Conversation:\n"
        "User: prior\n"
        "Jane: answer\n"
        "\n"
        "User: What next?\n"
        "\n"
        "Jane:"
    )
