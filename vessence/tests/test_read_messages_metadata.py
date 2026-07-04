from jane_web.jane_v2.classes.read_messages import metadata


def test_read_messages_instruction_text_preserves_triage_and_readback_guidance() -> None:
    text = metadata._read_messages_instruction_text()

    assert "SENT = user's outgoing messages, RECEIVED = incoming" in text
    assert "Classify each as important (personal/contact) or spam/promo" in text
    assert "Quote contact messages verbatim" in text
    assert "Use body text from resolved links when available" in text
    assert "TalkingPoints content could not be opened automatically" in text
