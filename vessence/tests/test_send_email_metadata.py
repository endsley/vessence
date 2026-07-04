from jane_web.jane_v2.classes.send_email import metadata


def test_sender_account_line_formats_accounts_and_empty_state() -> None:
    assert metadata._sender_account_line(["a@example.com", "b@example.com"]) == (
        "a@example.com, b@example.com"
    )
    assert metadata._sender_account_line([]) == "no stored Gmail sender tokens yet"


def test_send_email_rules_include_sender_accounts_and_confirmation_policy() -> None:
    rules = metadata._send_email_rules("chieh@example.com")

    assert "Available sender accounts: chieh@example.com." in rules
    assert "WAIT for an explicit yes" in rules
    assert "NEVER guess a recipient address" in rules


def test_recent_inbox_block_formats_recent_email_rows() -> None:
    block = metadata._recent_inbox_block(
        lambda **_kwargs: [
            {
                "sender": "Alice",
                "subject": "Dinner",
                "date": "2026-07-03",
            }
        ]
    )

    assert block == (
        "[EMAIL INBOX — recent (for recipient lookup / threading)]\n"
        "1. [2026-07-03] Alice\n"
        "   Subject: Dinner\n"
        "[END]"
    )


def test_send_email_lookup_block_omits_snippets_and_unread_tags() -> None:
    block = metadata._format_email_block(
        "[EMAIL INBOX]",
        [
            {
                "sender": "Alice",
                "subject": "Dinner",
                "snippet": "See you soon",
                "date": "2026-07-03",
                "is_unread": True,
            }
        ],
    )

    assert block == (
        "[EMAIL INBOX]\n"
        "1. [2026-07-03] Alice\n"
        "   Subject: Dinner\n"
        "[END]"
    )


def test_recent_inbox_block_reports_gmail_setup_errors() -> None:
    def fail_runtime(**_kwargs):
        raise RuntimeError("missing token")

    block = metadata._recent_inbox_block(fail_runtime)

    assert "Gmail not set up: missing token" in block
    assert "sign in with Google" in block


def test_recent_inbox_block_reports_general_fetch_errors() -> None:
    def fail_general(**_kwargs):
        raise ValueError("bad query")

    assert metadata._recent_inbox_block(fail_general) == (
        "[EMAIL INBOX — recent]\nFetch failed: bad query\n[END]"
    )
