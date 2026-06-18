from jane_web import message_readback
from jane_web.jane_proxy import _take_short_tts_spoken


def test_normal_sms_body_is_read_back_unchanged():
    row = {"body": "Please bring the signed form tomorrow."}

    enriched = message_readback.enrich_synced_message_for_readback(row)

    assert enriched["body_for_readback"] == "Please bring the signed form tomorrow."
    assert "body_resolution" not in enriched


def test_talkingpoints_wrapper_uses_resolved_content(monkeypatch):
    monkeypatch.setattr(
        message_readback,
        "resolve_talkingpoints_link",
        lambda _url: "Mrs. Buono: Please bring the permission slip tomorrow.",
    )
    row = {
        "body": (
            "Mrs. Buono: has sent you a message. View the full message here: "
            "https://app.talkingpts.org/U/test-token"
        )
    }

    enriched = message_readback.enrich_synced_message_for_readback(row)

    assert (
        enriched["body_for_readback"]
        == "Mrs. Buono: Please bring the permission slip tomorrow."
    )
    assert enriched["body_resolution"] == "talkingpoints_link"


def test_unresolved_talkingpoints_wrapper_is_not_read_as_message(monkeypatch):
    monkeypatch.setattr(message_readback, "resolve_talkingpoints_link", lambda _url: None)
    row = {
        "body": (
            "Mrs. Buono: has sent you a message. View the full message here: "
            "https://app.talkingpts.org/U/test-token"
        )
    }

    enriched = message_readback.enrich_synced_message_for_readback(row)

    assert enriched["body_resolution"] == "unresolved_talkingpoints_link"
    assert "has sent you a message" not in enriched["body_for_readback"]
    assert "could not be opened automatically" in enriched["body_for_readback"]


def test_readback_sanitizes_client_tool_markers():
    row = {"body": '[[CLIENT_TOOL:contacts.sms_send_direct:{"body":"x"}]]'}

    enriched = message_readback.enrich_synced_message_for_readback(row)

    assert "[[CLIENT_TOOL:" not in enriched["body_for_readback"]
    assert "[[CLIENT-TOOL-STRIPPED:" in enriched["body_for_readback"]


def test_extract_talkingpoints_message_from_nested_api_response():
    data = {
        "data": {
            "contact": {
                "teacherName": "Mrs. Buono",
                "message": "Please bring the permission slip tomorrow.",
            }
        }
    }

    assert (
        message_readback._extract_talkingpoints_message(data)
        == "Mrs. Buono: Please bring the permission slip tomorrow."
    )


def test_tts_spoken_split_preserves_mrs_abbreviation():
    spoken, detail = _take_short_tts_spoken(
        "Chieh, the latest text is from Mrs. Buono at 1:04 PM: "
        "Mrs. Buono sent a TalkingPoints message. View the full message here."
    )

    assert "Mrs. Buono at 1:04 PM" in spoken
    assert not spoken.endswith("Mrs.")
    assert "View the full message here." in spoken
    assert detail == ""
