from jane_web.server_data_contexts import (
    _calendar_range_override_from_message,
    _email_limit_from_router_response,
    _email_sender_query_from_router_response,
    calendar_delegate_context,
    calendar_delegate_credentials_error_context,
    calendar_delegate_error_context,
    calendar_range_from_router_response,
    calendar_task_context,
    calendar_task_credentials_error_context,
    calendar_task_error_context,
    email_delegate_context,
    email_delegate_credentials_error_context,
    email_delegate_error_context,
    email_read_query_from_router_response,
    email_task_context,
    email_task_credentials_error_context,
    email_task_error_context,
)


def test_email_router_response_parsers_preserve_limit_and_sender_defaults():
    assert _email_limit_from_router_response("", default_limit=10, max_limit=20) == 10
    assert _email_limit_from_router_response("read_email 7", default_limit=10, max_limit=20) == 7
    assert _email_limit_from_router_response("read_email 99", default_limit=10, max_limit=20) == 20
    assert _email_sender_query_from_router_response("", "is:unread") == "is:unread"
    assert _email_sender_query_from_router_response(
        "read_email from:bob@example.com",
        "is:unread",
    ) == "from:bob@example.com"


def test_email_read_query_from_router_response_preserves_limit_and_sender_rules():
    assert email_read_query_from_router_response(None).__dict__ == {
        "limit": 10,
        "query": "is:unread",
    }
    assert email_read_query_from_router_response("read_email 3").__dict__ == {
        "limit": 3,
        "query": "is:unread",
    }
    assert email_read_query_from_router_response("read_email 99 from:bob@example.com").__dict__ == {
        "limit": 20,
        "query": "from:bob@example.com",
    }


def test_email_task_context_preserves_v2_shapes():
    emails = [{"from": "a@example.com", "subject": "Hello"}]

    assert email_task_context(emails) == (
        "[EMAIL INBOX DATA \u2014 fetched server-side]\n"
        "[\n"
        "  {\n"
        "    \"from\": \"a@example.com\",\n"
        "    \"subject\": \"Hello\"\n"
        "  }\n"
        "]\n"
        "[END EMAIL INBOX DATA]"
    )
    assert email_task_context([]) == (
        "[EMAIL INBOX DATA]\nNo unread emails found.\n[END EMAIL INBOX DATA]"
    )
    assert email_task_credentials_error_context(RuntimeError("missing token")) == (
        "[EMAIL ERROR]\nGmail not set up: missing token\n[END EMAIL ERROR]"
    )
    assert email_task_error_context(RuntimeError("boom")) == (
        "[EMAIL ERROR]\nFailed to fetch emails: boom\n[END EMAIL ERROR]"
    )


def test_email_delegate_context_preserves_legacy_shapes():
    context = email_delegate_context([{"from": "a@example.com", "subject": "Hello"}])

    assert context.startswith("\n\n[EMAIL INBOX DATA \u2014 fetched server-side just now]\n")
    assert '"subject": "Hello"' in context
    assert "Summarize these emails for the user." in context
    assert email_delegate_context([]) == (
        "\n\n[EMAIL INBOX DATA \u2014 fetched server-side just now]\n"
        "No unread emails found.\n"
        "[END EMAIL INBOX DATA]\n\n"
        "Tell the user their inbox is clear."
    )
    assert "Gmail is not set up yet: missing token" in email_delegate_credentials_error_context(
        RuntimeError("missing token")
    )
    assert email_delegate_error_context(RuntimeError("boom")) == (
        "\n\n[EMAIL ERROR]\n"
        "Failed to fetch emails: boom\n"
        "Apologize and suggest trying again.\n"
        "[END EMAIL ERROR]"
    )


def test_calendar_range_from_router_response_preserves_legacy_precedence():
    assert calendar_range_from_router_response(None, "") == "today"
    assert calendar_range_from_router_response("next", "") == "next"
    assert calendar_range_from_router_response("today", "what about tomorrow") == "tomorrow"
    assert calendar_range_from_router_response("today", "show this week") == "this_week"
    assert calendar_range_from_router_response("today", "show next week") == "next_week"
    assert calendar_range_from_router_response("today", "show weekend") == "weekend"
    assert calendar_range_from_router_response("today", "show this weekend") == "this_week"
    assert calendar_range_from_router_response("today", "what is coming up") == "next"


def test_calendar_range_override_from_message_preserves_legacy_precedence():
    assert _calendar_range_override_from_message("") is None
    assert _calendar_range_override_from_message("what about tomorrow") == "tomorrow"
    assert _calendar_range_override_from_message("show this week") == "this_week"
    assert _calendar_range_override_from_message("show next week") == "next_week"
    assert _calendar_range_override_from_message("show weekend") == "weekend"
    assert _calendar_range_override_from_message("show this weekend") == "this_week"
    assert _calendar_range_override_from_message("next 7 days") == "next"


def test_calendar_task_context_preserves_v2_shapes():
    events = [{"summary": "Dentist", "start": "2026-07-03T09:00:00"}]

    context = calendar_task_context(events, "today")

    assert context.startswith("[CALENDAR DATA \u2014 range=today, fetched server-side]\n")
    assert '"summary": "Dentist"' in context
    assert context.endswith("[END CALENDAR DATA]")
    assert calendar_task_context([], "tomorrow") == (
        "[CALENDAR DATA \u2014 range=tomorrow]\n"
        "No events found.\n[END CALENDAR DATA]"
    )
    assert calendar_task_credentials_error_context(RuntimeError("no auth")) == (
        "[CALENDAR ERROR]\nGoogle Calendar not set up: no auth\n[END CALENDAR ERROR]"
    )
    assert calendar_task_error_context(RuntimeError("boom")) == (
        "[CALENDAR ERROR]\nFailed to fetch calendar: boom\n[END CALENDAR ERROR]"
    )


def test_calendar_delegate_context_preserves_legacy_shapes():
    context = calendar_delegate_context([{"summary": "Dentist"}], "today")

    assert context.startswith("\n\n[CALENDAR DATA \u2014 range=today, fetched server-side just now]\n")
    assert '"summary": "Dentist"' in context
    assert "Summarize these events naturally." in context
    assert calendar_delegate_context([], "next_week") == (
        "\n\n[CALENDAR DATA \u2014 range=next_week, fetched server-side just now]\n"
        "No events found.\n"
        "[END CALENDAR DATA]\n\n"
        "Tell the user their next week is clear."
    )
    assert "Google Calendar is not set up: no auth" in calendar_delegate_credentials_error_context(
        RuntimeError("no auth")
    )
    assert calendar_delegate_error_context(RuntimeError("boom")) == (
        "\n\n[CALENDAR ERROR]\n"
        "Failed to fetch calendar: boom\n"
        "Apologize and suggest trying again.\n"
        "[END CALENDAR ERROR]"
    )
