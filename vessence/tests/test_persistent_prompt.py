from jane_web.persistent_prompt import latest_user_prompt_from_transcript, persistent_turn_prompt


def test_latest_user_prompt_from_transcript_uses_newest_user_turn():
    transcript = "User: old\nJane: done\nUser: new question\nJane:"

    assert latest_user_prompt_from_transcript(transcript) == "new question"


def test_latest_user_prompt_from_transcript_handles_assistant_marker():
    transcript = "User: new question\nAssistant: pending"

    assert latest_user_prompt_from_transcript(transcript) == "new question"


def test_persistent_turn_prompt_fresh_session_sends_full_context_without_code_map():
    calls = []

    prompt, code_map_loaded = persistent_turn_prompt(
        system_prompt="system",
        transcript="User: hi",
        is_fresh=True,
        code_map_loader=lambda text: calls.append(text) or (text, True),
    )

    assert prompt == "system\n\nUser: hi"
    assert code_map_loaded is False
    assert calls == []


def test_persistent_turn_prompt_skip_context_sends_transcript_without_code_map():
    calls = []

    prompt, code_map_loaded = persistent_turn_prompt(
        system_prompt="",
        transcript="summary\nUser: hi",
        is_fresh=False,
        code_map_loader=lambda text: calls.append(text) or (text, True),
    )

    assert prompt == "summary\nUser: hi"
    assert code_map_loaded is False
    assert calls == []


def test_persistent_turn_prompt_warm_session_sends_latest_user_prompt_through_loader():
    prompt, code_map_loaded = persistent_turn_prompt(
        system_prompt="system",
        transcript="User: old\nJane: done\nUser: refactor this\nJane:",
        is_fresh=False,
        code_map_loader=lambda text: (f"CODEMAP\n{text}", True),
    )

    assert prompt == "CODEMAP\nrefactor this"
    assert code_map_loaded is True
