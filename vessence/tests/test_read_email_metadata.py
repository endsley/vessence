from jane_web.jane_v2.classes.read_email import metadata


def test_read_email_block_omits_message_ids_even_when_present() -> None:
    block = metadata._format_email_block(
        "[EMAIL INBOX - unread]",
        [{"id": "msg-1", "sender": "Alice", "subject": "Dinner", "date": "2026-07-03"}],
    )

    assert "id=msg-1" not in block
    assert "1. [2026-07-03] Alice" in block


def test_read_email_bucket_formats_successful_results() -> None:
    block, creds_failed = metadata._read_email_bucket(
        lambda **_kwargs: [
            {
                "sender": "Alice",
                "subject": "Dinner",
                "snippet": "See you soon",
                "date": "2026-07-03",
                "is_unread": True,
            }
        ],
        label="[EMAIL INBOX - unread]",
        limit=10,
        query="is:unread",
        warning_context="inbox",
    )

    assert creds_failed is False
    assert block == (
        "[EMAIL INBOX - unread]\n"
        "1. [2026-07-03] Alice (unread)\n"
        "   Subject: Dinner\n"
        "   Snippet: See you soon\n"
        "[END]"
    )


def test_read_email_bucket_marks_gmail_setup_failure() -> None:
    def fail_runtime(**_kwargs):
        raise RuntimeError("missing token")

    block, creds_failed = metadata._read_email_bucket(
        fail_runtime,
        label="[EMAIL INBOX - unread]",
        limit=10,
        query="is:unread",
        warning_context="inbox",
    )

    assert creds_failed is True
    assert "Gmail not set up: missing token" in block
    assert "sign in with Google" in block


def test_read_email_bucket_reports_general_fetch_failure() -> None:
    def fail_general(**_kwargs):
        raise ValueError("bad query")

    block, creds_failed = metadata._read_email_bucket(
        fail_general,
        label="[EMAIL SPAM - recent]",
        limit=10,
        query="in:spam",
        warning_context="spam",
    )

    assert creds_failed is False
    assert block == "[EMAIL SPAM - recent]\nFetch failed: bad query\n[END]"
