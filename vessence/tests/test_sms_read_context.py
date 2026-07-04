from jane_web.sms_read_context import (
    SmsReadQuery,
    add_sms_display_times,
    fetch_sms_readback_messages,
    sms_inbox_context,
    sms_read_error_context,
    sms_read_query_from_router_response,
    sms_task_context,
    sms_task_error_context,
)


def test_sms_read_query_from_router_response_preserves_legacy_defaults_and_limit_cap():
    assert sms_read_query_from_router_response(None).__dict__ == {
        "days": 5,
        "limit": 30,
        "sender_filter": None,
    }
    assert sms_read_query_from_router_response("read_messages 12").__dict__ == {
        "days": 5,
        "limit": 12,
        "sender_filter": None,
    }
    assert sms_read_query_from_router_response("read_inbox Kathia").__dict__ == {
        "days": 5,
        "limit": 30,
        "sender_filter": "kathia",
    }
    assert sms_read_query_from_router_response("read_inbox Kathia 99").__dict__ == {
        "days": 5,
        "limit": 50,
        "sender_filter": "kathia 99",
    }


def test_add_sms_display_times_mutates_records_and_ignores_bad_timestamps():
    class FakeDateTime:
        def strftime(self, fmt):
            return f"formatted:{fmt}"

    messages = [{"timestamp_ms": 123000}, {"timestamp_ms": "bad"}]

    assert add_sms_display_times(
        messages,
        fromtimestamp_fn=lambda timestamp: FakeDateTime() if timestamp == 123 else (_ for _ in ()).throw(ValueError),
    ) is messages
    assert messages[0]["time"] == "formatted:%b %d %I:%M %p"
    assert "time" not in messages[1]


def test_fetch_sms_readback_messages_uses_unfiltered_query_and_annotates_rows():
    class FakeDateTime:
        def strftime(self, fmt):
            return f"time:{fmt}"

    class FakeResult:
        def fetchall(self):
            return [
                {
                    "sender": "A",
                    "body": "Hello",
                    "timestamp_ms": 123000,
                    "is_read": 0,
                    "is_contact": 1,
                    "msg_type": "personal",
                }
            ]

    class FakeConn:
        def __init__(self):
            self.calls = []

        def execute(self, sql, params):
            self.calls.append((sql, params))
            return FakeResult()

    conn = FakeConn()

    messages = fetch_sms_readback_messages(
        conn,
        SmsReadQuery(days=2, limit=7, sender_filter=None),
        now_fn=lambda: 200000,
        enrich_fn=lambda rows: [dict(row, body_for_readback=row["body"]) for row in rows],
        fromtimestamp_fn=lambda timestamp: FakeDateTime() if timestamp == 123 else None,
    )

    assert conn.calls[0][1] == (27200000, 7)
    assert "WHERE timestamp_ms > ?" in conn.calls[0][0]
    assert "sender LIKE" not in conn.calls[0][0]
    assert messages == [
        {
            "sender": "A",
            "body": "Hello",
            "timestamp_ms": 123000,
            "is_read": 0,
            "is_contact": 1,
            "msg_type": "personal",
            "body_for_readback": "Hello",
            "time": "time:%b %d %I:%M %p",
        }
    ]


def test_fetch_sms_readback_messages_uses_sender_filter_query():
    class FakeConn:
        def __init__(self):
            self.calls = []

        def execute(self, sql, params):
            self.calls.append((sql, params))
            return self

        def fetchall(self):
            return []

    conn = FakeConn()

    assert fetch_sms_readback_messages(
        conn,
        SmsReadQuery(days=5, limit=30, sender_filter="kathia"),
        now_fn=lambda: 500000,
        enrich_fn=lambda rows: [dict(row) for row in rows],
    ) == []
    assert conn.calls[0][1] == (68000000, "%kathia%", "%kathia%", 30)
    assert "sender LIKE ? OR body LIKE ?" in conn.calls[0][0]


def test_sms_task_context_preserves_v2_text_shape():
    context = sms_task_context([
        {
            "sender": "Kathia",
            "body_for_readback": "Dinner?",
            "body_resolution": "sms_body",
            "msg_type": "personal",
        }
    ])

    assert context.startswith("[SMS INBOX DATA")
    assert '"sender": "Kathia"' in context
    assert "msg_type guide: personal=important contacts" in context
    assert "Use body_for_readback as the text to read to the user." in context
    assert sms_task_context([]) == (
        "[SMS INBOX DATA]\nNo text messages found in the last 5 days.\n[END SMS INBOX DATA]"
    )
    assert sms_task_error_context(RuntimeError("db down")) == (
        "[SMS ERROR]\nFailed to fetch messages: db down\n[END SMS ERROR]"
    )


def test_sms_inbox_context_preserves_message_json_and_readback_instructions():
    context = sms_inbox_context([
        {
            "sender": "Kathia",
            "body_for_readback": "Dinner?",
            "body_resolution": "plain_text",
            "msg_type": "personal",
        }
    ])

    assert context.startswith("\n\n[SMS INBOX DATA")
    assert '"sender": "Kathia"' in context
    assert "Use body_for_readback as the text to read to the user." in context
    assert "Group personal messages by sender." in context


def test_sms_inbox_context_and_error_context_preserve_fallback_text():
    empty_context = sms_inbox_context([])
    assert "No text messages found in the last 5 days." in empty_context
    assert "open the Vessence app" in empty_context

    error_context = sms_read_error_context(RuntimeError("db down"))
    assert "Failed to fetch messages from DB: db down" in error_context
    assert error_context.endswith("[END SMS ERROR]")
