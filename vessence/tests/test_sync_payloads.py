from jane_web.sync_payloads import contact_alias_values, contact_insert_values, message_insert_values


def test_contact_insert_values_strips_fields_and_preserves_existing_none_contact_id_behavior():
    assert contact_insert_values(
        {
            "display_name": " Kathia ",
            "phone_number": " +15551234567 ",
            "email": " kathia@example.com ",
            "is_primary": True,
            "contact_id": None,
        },
        "2026-07-02 12:00:00",
    ) == (
        "Kathia",
        "+15551234567",
        "kathia@example.com",
        1,
        "None",
        "2026-07-02 12:00:00",
    )


def test_contact_insert_values_skips_blank_display_name_and_normalizes_empty_optional_fields():
    assert contact_insert_values({"display_name": "   "}, "now") is None
    assert contact_insert_values({"display_name": "Name", "phone_number": "", "email": ""}, "now") == (
        "Name",
        None,
        None,
        0,
        None,
        "now",
    )


def test_contact_alias_values_strips_required_fields_and_preserves_display_name():
    assert contact_alias_values(
        {
            "alias": "  wife  ",
            "phone_number": "  +155501  ",
            "display_name": "  Kathia  ",
        }
    ) == ("wife", "+155501", "  Kathia  ")


def test_contact_alias_values_requires_alias_and_phone_number():
    assert contact_alias_values({"alias": "wife", "phone_number": "   "}) is None
    assert contact_alias_values({"alias": "   ", "phone_number": "+155501"}) is None


def test_message_insert_values_normalizes_fields_and_passes_is_contact_to_classifier():
    calls = []

    def classify(body, is_contact):
        calls.append((body, is_contact))
        return "personal" if is_contact else "unknown"

    assert message_insert_values(
        {
            "sender": " +15551234567 ",
            "body": " hello ",
            "timestamp_ms": 123,
            "is_read": False,
            "is_contact": True,
        },
        "2026-07-02 12:00:00",
        classify_message=classify,
    ) == (
        "+15551234567",
        "hello",
        123,
        0,
        1,
        "personal",
        "2026-07-02 12:00:00",
    )
    assert calls == [("hello", True)]


def test_message_insert_values_skips_blank_sender_or_falsey_timestamp():
    classify = lambda body, is_contact: "unknown"

    assert message_insert_values({"sender": "", "timestamp_ms": 123}, "now", classify_message=classify) is None
    assert message_insert_values({"sender": "A", "timestamp_ms": 0}, "now", classify_message=classify) is None
