from jane_web.stage3_injections import strip_stage3_injections


def test_strip_stage3_injections_preserves_empty_input():
    assert strip_stage3_injections("") == ""


def test_strip_stage3_injections_removes_class_protocol_block():
    message = "<class_protocol name='x'>hidden</class_protocol>\n\nUser question"

    assert strip_stage3_injections(message) == "User question"


def test_strip_stage3_injections_removes_extracted_params_until_blank_line():
    message = "[EXTRACTED PARAMS]\naction: read\n\nRead my email"

    assert strip_stage3_injections(message) == "Read my email"


def test_strip_stage3_injections_removes_conversation_state_block():
    message = (
        "[CURRENT CONVERSATION STATE]\n"
        "pending: timer\n"
        "[END CURRENT CONVERSATION STATE]\n"
        "Continue that"
    )

    assert strip_stage3_injections(message) == "Continue that"


def test_strip_stage3_injections_removes_voice_hint():
    message = "(voice request — your answer will be read aloud)\nTell me the weather"

    assert strip_stage3_injections(message) == "Tell me the weather"


def test_strip_stage3_injections_removes_combined_injections():
    message = (
        "<class_protocol>hidden</class_protocol>\n"
        "[EXTRACTED PARAMS]\nfoo: bar\n\n"
        "[CURRENT CONVERSATION STATE]\nstate\n[END CURRENT CONVERSATION STATE]\n"
        "(voice request — aloud)\n"
        "Real prompt"
    )

    assert strip_stage3_injections(message) == "Real prompt"
