from jane_web.tts_contract import (
    enforce_tts_output_contract,
    normalize_tts_text,
    split_tts_sentences,
    take_short_tts_spoken,
    tts_spoken_source_and_trailing,
)


def test_normalize_tts_text_strips_tool_music_and_markup():
    raw = (
        "<spoken>Hello</spoken> [[CLIENT_TOOL:contacts.sms_send:{\"draft_id\":\"d1\"}]] "
        "[MUSIC_PLAY:test] <visual>Chart</visual>"
    )

    assert normalize_tts_text(raw) == "Hello Chart"


def test_split_tts_sentences_preserves_common_abbreviations():
    sentences = split_tts_sentences("Mrs. Buono replied. Dr. Smith called.")

    assert sentences == ["Mrs. Buono replied.", "Dr. Smith called."]


def test_take_short_tts_spoken_returns_first_two_sentences_and_detail():
    spoken, detail = take_short_tts_spoken("One. Two. Three.")

    assert spoken == "One. Two."
    assert detail == "Three."


def test_tts_spoken_source_and_trailing_preserves_preface_and_fallbacks():
    assert tts_spoken_source_and_trailing("Plain answer.") == ("Plain answer.", "")
    assert tts_spoken_source_and_trailing("<spoken>Hello.</spoken><visual>Chart</visual>") == (
        "Hello.",
        "<visual>Chart</visual>",
    )
    assert tts_spoken_source_and_trailing("Preface <spoken>Hello.</spoken> trailing") == (
        "Preface Hello.",
        "trailing",
    )


def test_enforce_tts_output_contract_wraps_spoken_and_moves_detail():
    enforced = enforce_tts_output_contract(
        "<spoken>One. Two. Three.</spoken><visual>Chart</visual>",
        "session-abcdef",
        "test",
    )

    assert enforced == "<spoken>One. Two.</spoken>\n\nThree. Chart"


def test_enforce_tts_output_contract_empty_response_stays_empty():
    assert enforce_tts_output_contract("   ", "session-abcdef", "test") == ""
