from llm_brain.v1.persistent_claude import (
    ClaudePersistentManager,
    _claude_message_usage,
    _claude_result_usage,
    _claude_session_key,
    _claude_tool_status_message,
)


LABELS = ClaudePersistentManager._TOOL_LABELS


def test_claude_session_key_matches_manager_storage_key():
    assert _claude_session_key("user", "session") == "user:session"


def test_claude_tool_status_message_formats_file_tools_by_basename():
    assert _claude_tool_status_message(
        "Read",
        {"file_path": "/home/chieh/ambient/vessence/main.py"},
        LABELS,
    ) == "Reading file: main.py"


def test_claude_tool_status_message_formats_bash_description_and_command():
    assert _claude_tool_status_message(
        "Bash",
        {"description": "Run tests", "command": "pytest tests -q"},
        LABELS,
    ) == "Running command: Run tests\tcmd:pytest tests -q"
    assert _claude_tool_status_message(
        "Bash",
        {"command": "x" * 80},
        LABELS,
    ) == f"Running command: {'x' * 60}"


def test_claude_tool_status_message_formats_search_and_web_tools():
    pattern = "class ConversationManager" + "x" * 80
    assert _claude_tool_status_message(
        "Grep",
        {"pattern": pattern},
        LABELS,
    ) == f"Searching code: {pattern[:50]}"
    assert _claude_tool_status_message(
        "WebFetch",
        {"url": "https://example.test/long/path"},
        LABELS,
    ) == "Fetching webpage: https://example.test/long/path"


def test_claude_tool_status_message_falls_back_to_tool_name():
    assert _claude_tool_status_message("UnknownTool", {}, LABELS) == "UnknownTool"


def test_claude_message_usage_preserves_assistant_event_shape():
    assert _claude_message_usage({
        "model": "claude-test",
        "usage": {"input_tokens": 12, "output_tokens": 3},
    }) == {
        "input_tokens": 12,
        "output_tokens": 3,
        "model": "claude-test",
    }
    assert _claude_message_usage({"usage": ["bad"]}) is None
    assert _claude_message_usage({}) is None


def test_claude_result_usage_preserves_model_fallback():
    current = {"input_tokens": 1, "output_tokens": 2, "model": "from-message"}

    assert _claude_result_usage(
        {"usage": {"input_tokens": 10, "output_tokens": 5}},
        current,
    ) == {
        "input_tokens": 10,
        "output_tokens": 5,
        "model": "from-message",
    }
    assert _claude_result_usage(
        {"model": "from-result", "usage": {"input_tokens": 10}},
        current,
    ) == {
        "input_tokens": 10,
        "output_tokens": 0,
        "model": "from-result",
    }
    assert _claude_result_usage({"usage": "bad"}, current) is None
