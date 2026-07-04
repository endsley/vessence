from jane_web.jane_v2.classes.delete_email import metadata


def test_delete_email_block_uses_id_fallback_for_delete_tool() -> None:
    block = metadata._format_email_block(
        "[EMAIL INBOX - unread]",
        [{"id": "msg-fallback", "sender": "Alice", "subject": "Dinner", "date": "2026-07-03"}],
    )

    assert "1. id=msg-fallback [2026-07-03] Alice" in block


def test_delete_email_bucket_formats_message_ids_for_delete_tool() -> None:
    block, creds_failed = metadata._delete_email_bucket(
        lambda **_kwargs: [
            {
                "message_id": "msg-1",
                "sender": "Store",
                "subject": "Sale",
                "snippet": "Half off",
                "date": "2026-07-03",
                "is_unread": True,
            }
        ],
        label="[EMAIL PROMOTIONS - recent]",
        limit=15,
        query="category:promotions",
        warning_context="promo",
    )

    assert creds_failed is False
    assert block == (
        "[EMAIL PROMOTIONS - recent]\n"
        "1. id=msg-1 [2026-07-03] Store (unread)\n"
        "   Subject: Sale\n"
        "   Snippet: Half off\n"
        "[END]"
    )


def test_delete_email_bucket_marks_gmail_setup_failure() -> None:
    def fail_runtime(**_kwargs):
        raise RuntimeError("missing token")

    block, creds_failed = metadata._delete_email_bucket(
        fail_runtime,
        label="[EMAIL INBOX - unread]",
        limit=10,
        query="is:unread",
        warning_context="inbox",
    )

    assert creds_failed is True
    assert "Gmail not set up: missing token" in block
    assert "sign in with Google" in block


def test_delete_email_bucket_reports_general_fetch_failure() -> None:
    def fail_general(**_kwargs):
        raise ValueError("bad query")

    block, creds_failed = metadata._delete_email_bucket(
        fail_general,
        label="[EMAIL SPAM - recent]",
        limit=15,
        query="in:spam",
        warning_context="spam",
    )

    assert creds_failed is False
    assert block == "[EMAIL SPAM - recent]\nFetch failed: bad query\n[END]"
