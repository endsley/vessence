from agent_skills import sms_helpers
from agent_skills.sms_helper_rules import (
    STOP_PREFIXES,
    alias_match_from_row,
    contact_lookup_from_rows,
    draft_is_expired,
    draft_payload_from_row,
    escape_sql_like,
    expired_draft_cutoff_text,
    normalize_name,
)


class Row(dict):
    def __getitem__(self, key):
        return dict.__getitem__(self, key)


def test_sms_helpers_keeps_private_normalizer_and_stop_prefixes():
    assert sms_helpers._normalize_name is normalize_name
    assert sms_helpers._STOP_PREFIXES is STOP_PREFIXES


def test_normalize_name_strips_one_stop_prefix_and_collapses_whitespace():
    assert normalize_name(" My   Wife ") == "wife"
    assert normalize_name("to my wife") == "my wife"
    assert normalize_name(None) == ""


def test_escape_sql_like_preserves_existing_escape_order():
    assert escape_sql_like(r"a\b%c_") == r"a\\b\%c\_"


def test_alias_match_from_row_uses_normalized_alias_when_display_missing():
    assert alias_match_from_row(
        Row({"phone_number": "+1555", "display_name": None}),
        "wife",
    ) == {
        "phone_number": "+1555",
        "display_name": "wife",
        "source": "alias",
    }
    assert alias_match_from_row(Row({"phone_number": "", "display_name": "Wife"}), "wife") is None


def test_contact_lookup_from_rows_collapses_duplicate_display_names():
    result = contact_lookup_from_rows(
        [
            Row({"display_name": "Alex Chen", "phone_number": "+1"}),
            Row({"display_name": "Alex Chen", "phone_number": "+2"}),
        ]
    )

    assert result.match == {
        "phone_number": "+1",
        "display_name": "Alex Chen",
        "source": "contacts",
    }
    assert result.ambiguous_count == 0


def test_contact_lookup_from_rows_reports_ambiguity_count():
    result = contact_lookup_from_rows(
        [
            Row({"display_name": "John Adams", "phone_number": "+1"}),
            Row({"display_name": "John Baker", "phone_number": "+2"}),
        ]
    )

    assert result.match is None
    assert result.ambiguous_count == 2
    assert contact_lookup_from_rows([]).match is None


def test_draft_expiry_and_cutoff_preserve_strict_ttl_boundary():
    assert not draft_is_expired(700, now=1000, ttl_seconds=300)
    assert draft_is_expired(699, now=1000, ttl_seconds=300)
    assert expired_draft_cutoff_text(1000.9, 300) == "700"


def test_draft_payload_from_row_preserves_public_shape():
    assert draft_payload_from_row(
        Row(
            {
                "draft_id": "abc",
                "phone_number": "+1555",
                "display_name": "Mom",
                "body": "hello",
            }
        )
    ) == {
        "draft_id": "abc",
        "phone_number": "+1555",
        "display_name": "Mom",
        "body": "hello",
    }
