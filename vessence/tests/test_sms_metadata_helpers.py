from jane_web.jane_v2.classes import sms_metadata_helpers
from jane_web.jane_v2.classes.delete_messages import metadata as delete_messages_metadata
from jane_web.jane_v2.classes.read_messages import metadata as read_messages_metadata
from jane_web.jane_v2.classes.sms_metadata_helpers import (
    format_message_timestamp,
    format_synced_message_line,
    message_direction_label,
    message_kind,
)


class FakeDateTime:
    def strftime(self, _fmt):
        return "07/04 09:30 AM"


def test_sms_metadata_modules_use_shared_line_formatter() -> None:
    assert read_messages_metadata._format_synced_message_line is sms_metadata_helpers.format_synced_message_line
    assert delete_messages_metadata._format_synced_message_line is sms_metadata_helpers.format_synced_message_line


def test_format_message_timestamp_preserves_existing_compact_display() -> None:
    assert format_message_timestamp(123000, fromtimestamp_fn=lambda timestamp: FakeDateTime()) == (
        "7/04 09:30 AM"
    )


def test_format_synced_message_line_handles_sent_received_and_kind_labels() -> None:
    sent = format_synced_message_line(
        2,
        {"timestamp_ms": 123000, "sender": "Me → Kathia", "is_contact": 1, "msg_type": "personal"},
        "See you soon",
        fromtimestamp_fn=lambda timestamp: FakeDateTime(),
    )
    received = format_synced_message_line(
        3,
        {"timestamp_ms": 123000, "sender": "", "is_contact": 0, "msg_type": ""},
        "Promo body",
        fromtimestamp_fn=lambda timestamp: FakeDateTime(),
    )

    assert sent == "2. [7/04 09:30 AM] (SENT by user to Kathia) (contact): See you soon"
    assert received == "3. [7/04 09:30 AM] (RECEIVED from Unknown) (unknown): Promo body"
    assert message_direction_label("Alice") == "RECEIVED from Alice"
    assert message_kind({"is_contact": False, "msg_type": "spam"}) == "spam"
