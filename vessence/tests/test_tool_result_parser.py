from jane_web.jane_v2.tool_result_parser import (
    _leading_tool_result_marker_bounds,
    extract_tool_results,
    strip_tool_result_prefix,
)


def test_leading_tool_result_marker_bounds_handles_spaces_and_malformed_markers():
    message = '  [TOOL_RESULT: {"tool":"x","data":{"ok":true}} ] ask'

    json_start, json_end, marker_end = _leading_tool_result_marker_bounds(message)

    assert message[json_start:json_end] == '{"tool":"x","data":{"ok":true}}'
    assert message[marker_end] == "]"
    assert _leading_tool_result_marker_bounds("ask jane") is None
    assert _leading_tool_result_marker_bounds('[TOOL_RESULT:{"tool":"x"} missing close]') is None


def test_extract_tool_results_uses_shared_scanner_for_nested_json_and_string_markers():
    message = (
        '[TOOL_RESULT:{"tool":"messages.fetch_unread","status":"ok",'
        '"data":{"body":"literal }] text","nested":{"count":2}}}] '
        "what changed?"
    )

    cleaned, results = extract_tool_results(message)

    assert cleaned == "what changed?"
    assert results == [
        {
            "tool": "messages.fetch_unread",
            "status": "ok",
            "data": {"body": "literal }] text", "nested": {"count": 2}},
        }
    ]


def test_extract_tool_results_strips_multiple_leading_markers():
    message = (
        '  [TOOL_RESULT: {"tool":"one"} ] '
        '[TOOL_RESULT:{"tool":"two","data":{"ok":true}}] continue'
    )

    cleaned, results = extract_tool_results(message)

    assert cleaned == "continue"
    assert results == [
        {"tool": "one"},
        {"tool": "two", "data": {"ok": True}},
    ]


def test_extract_tool_results_leaves_malformed_marker_visible():
    message = '[TOOL_RESULT:{"tool":"x"} missing close] hello'

    cleaned, results = extract_tool_results(message)

    assert cleaned == message
    assert results == []


def test_strip_tool_result_prefix_returns_only_cleaned_text():
    assert strip_tool_result_prefix('[TOOL_RESULT:{"tool":"x"}] ask jane') == "ask jane"
