import sys
import types

from jane_web.email_tool_results import (
    format_email_readback,
    format_email_search_results,
    format_inbox_emails,
    format_sent_email_status,
    prepare_send_email_args,
    requested_sender_email,
)
from jane_web import server_email_tools
from jane_web.server_email_tools import execute_email_tool_serverside


def test_server_email_tools_use_extracted_result_helpers():
    assert server_email_tools._format_inbox_emails is format_inbox_emails
    assert server_email_tools._format_email_readback is format_email_readback
    assert server_email_tools._format_email_search_results is format_email_search_results
    assert server_email_tools._prepare_send_email_args is prepare_send_email_args
    assert server_email_tools._format_sent_email_status is format_sent_email_status
    assert set(server_email_tools._EMAIL_TOOL_EXECUTORS) == {
        "email.read_inbox",
        "email.read",
        "email.search",
        "email.send",
        "email.delete",
    }


def _install_email_tools(monkeypatch, **funcs):
    module = types.ModuleType("agent_skills.email_tools")
    for name, func in funcs.items():
        setattr(module, name, func)
    monkeypatch.setitem(sys.modules, "agent_skills.email_tools", module)


def test_requested_sender_email_preserves_alias_precedence_and_blank_default():
    assert requested_sender_email({
        "from_email": " primary@example.com ",
        "from": "fallback@example.com",
        "sender": "sender@example.com",
    }) == "primary@example.com"
    assert requested_sender_email({"from": " fallback@example.com "}) == "fallback@example.com"
    assert requested_sender_email({"sender": " sender@example.com "}) == "sender@example.com"
    assert requested_sender_email({"from_email": "   "}) is None


def test_read_inbox_formats_results(monkeypatch):
    _install_email_tools(
        monkeypatch,
        read_inbox=lambda limit, query: [
            {
                "is_unread": True,
                "sender": "a@example.com",
                "subject": "Alpha",
                "snippet": "hello",
            },
            {
                "is_unread": False,
                "sender": "b@example.com",
                "subject": "Beta",
                "snippet": "",
            },
        ],
    )

    text = execute_email_tool_serverside(
        {"tool": "email.read_inbox", "args": {"limit": 2, "query": "is:unread"}}
    )

    assert "Found 2 email(s)" in text
    assert "- [NEW] From: a@example.com — Alpha" in text
    assert "Preview: hello" in text
    assert "- [read] From: b@example.com — Beta" in text


def test_read_inbox_empty_result(monkeypatch):
    _install_email_tools(monkeypatch, read_inbox=lambda limit, query: [])

    assert (
        execute_email_tool_serverside({"tool": "email.read_inbox", "args": {}})
        == "\n\nNo unread emails found."
    )


def test_send_email_validation_and_success(monkeypatch):
    sent = []

    def send_email(**kwargs):
        sent.append(kwargs)
        return {"message_id": "m1", "from_email": kwargs["from_email"]}

    _install_email_tools(monkeypatch, send_email=send_email)

    assert (
        execute_email_tool_serverside({"tool": "email.send", "args": {"body": "hi"}})
        == "\n\nEmail not sent: no recipient address provided."
    )
    assert (
        execute_email_tool_serverside({"tool": "email.send", "args": {"to": "x@example.com"}})
        == "\n\nEmail not sent: empty body."
    )
    text = execute_email_tool_serverside(
        {
            "tool": "email.send",
            "args": {
                "to": "x@example.com",
                "subject": "Hi",
                "body": "Hello",
                "from_email": "me@example.com",
            },
        }
    )

    assert text == "\n\n[Email sent from me@example.com to x@example.com.]"
    assert sent == [
        {
            "to": "x@example.com",
            "subject": "Hi",
            "body": "Hello",
            "from_email": "me@example.com",
        }
    ]


def test_delete_email_validation_and_success(monkeypatch):
    deleted = []
    _install_email_tools(monkeypatch, delete_email=lambda msg_id: deleted.append(msg_id))

    assert (
        execute_email_tool_serverside({"tool": "email.delete", "args": {}})
        == "\n\nEmail not deleted: no message_id provided."
    )
    assert (
        execute_email_tool_serverside({"tool": "email.delete", "args": {"message_id": "m1"}})
        == "\n\n[Email m1 moved to trash.]"
    )
    assert deleted == ["m1"]


def test_runtime_error_reports_gmail_not_set_up(monkeypatch):
    def read_inbox(limit, query):
        raise RuntimeError("missing token")

    _install_email_tools(monkeypatch, read_inbox=read_inbox)

    text = execute_email_tool_serverside({"tool": "email.read_inbox", "args": {}})

    assert "Gmail is not set up yet" in text


def test_unknown_and_generic_error(monkeypatch):
    assert execute_email_tool_serverside({"tool": "email.unknown", "args": {}}) == ""

    def read_email(_msg_id):
        raise ValueError("boom")

    _install_email_tools(monkeypatch, read_email=read_email)

    assert (
        execute_email_tool_serverside({"tool": "email.read", "args": {"message_id": "m1"}})
        == "\n\nEmail error: boom"
    )
