from jane_web.jane_v2.fifo_records import build_fifo_turn_record


def test_build_fifo_turn_record_preserves_base_fields_and_optional_markers():
    record = build_fifo_turn_record(
        user_prompt="hello",
        jane_response="hi",
        summary="hello -> hi",
        stage="stage3",
        intent="send message",
        privacy="local_only",
        confidence="High",
    )

    assert record == {
        "user_text": "hello",
        "assistant_text": "hi",
        "summary": "hello -> hi",
        "stage": "stage3",
        "intent": "send message",
        "privacy": "local_only",
        "confidence": "High",
    }


def test_build_fifo_turn_record_merges_structured_without_none_values():
    record = build_fifo_turn_record(
        user_prompt="u",
        jane_response="j",
        summary="s",
        handler_structured={"pending_action": "sms", "ignored": None},
    )

    assert record["pending_action"] == "sms"
    assert "ignored" not in record


def test_build_fifo_turn_record_normalizes_extras():
    record = build_fifo_turn_record(
        user_prompt="u",
        jane_response="j",
        summary="s",
        extras={
            "client_tools": [
                {"name": "send_sms", "args": {"to": "Amy"}},
                {"tool": "open_url"},
            ],
            "conversation_end": True,
            "evidence": {"required": True},
        },
    )

    assert record["tool_results"] == [
        {"name": "send_sms", "args": {"to": "Amy"}},
        {"name": "open_url", "args": {}},
    ]
    assert record["metadata"] == {
        "conversation_end": True,
        "evidence": {"required": True},
    }
