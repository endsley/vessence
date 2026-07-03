from jane_web.client_tool_json import find_json_object_end


def test_find_json_object_end_handles_nested_objects_and_marker_like_strings():
    text = '{"body":"literal }] text","nested":{"count":2}}] trailing'

    assert find_json_object_end(text) == len('{"body":"literal }] text","nested":{"count":2}}')


def test_find_json_object_end_handles_escaped_quotes_and_later_text():
    text = '{"body":"say \\"hi\\"","ok":true}]]'

    assert find_json_object_end(text) == len('{"body":"say \\"hi\\"","ok":true}')


def test_find_json_object_end_returns_none_for_non_object_or_unbalanced_text():
    assert find_json_object_end("", 0) is None
    assert find_json_object_end("[1,2,3]", 0) is None
    assert find_json_object_end('{"missing":"close"', 0) is None
    assert find_json_object_end('xx{"ok":true}', -1) is None


def test_find_json_object_end_respects_start_offset():
    text = 'prefix {"ok":{"nested":true}} suffix'

    assert find_json_object_end(text, len("prefix ")) == len('prefix {"ok":{"nested":true}}')
