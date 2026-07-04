from llm_brain.v1.persistent_gemini import _gemini_session_key, _gemini_startup_failure


def test_gemini_session_key_matches_manager_storage_key():
    assert _gemini_session_key("user", "session") == "user:session"


def test_gemini_startup_failure_uses_trimmed_buffer_or_returncode_fallback():
    assert str(_gemini_startup_failure("  auth failed  ", 2)) == (
        "Persistent Gemini failed during startup: auth failed"
    )
    assert str(_gemini_startup_failure("  ", 7)) == (
        "Persistent Gemini failed during startup: Gemini exited with code 7"
    )


def test_gemini_startup_failure_truncates_long_startup_buffer():
    error = _gemini_startup_failure("x" * 400, 1)

    assert str(error) == f"Persistent Gemini failed during startup: {'x' * 300}"
