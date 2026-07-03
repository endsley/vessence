from agent_skills import process_watchdog
from agent_skills.process_watchdog_policy import (
    command_is_protected,
    docker_container_is_too_old,
    parse_docker_ps_tts_line,
    parse_running_for_minutes,
)


def test_process_watchdog_exposes_policy_helpers_as_compatibility_aliases():
    assert process_watchdog._parse_minutes is parse_running_for_minutes
    assert process_watchdog._parse_docker_ps_tts_line is parse_docker_ps_tts_line
    assert process_watchdog._docker_container_is_too_old is docker_container_is_too_old
    assert process_watchdog._command_is_protected is command_is_protected


def test_parse_running_for_minutes_handles_common_docker_duration_text():
    assert parse_running_for_minutes("15 minutes") == 15
    assert parse_running_for_minutes("1 minute ago") == 1
    assert parse_running_for_minutes("45 seconds") == 0
    assert parse_running_for_minutes("2 hours") == 120
    assert parse_running_for_minutes("3 days") == 3 * 24 * 60
    assert parse_running_for_minutes("2 weeks") == 2 * 7 * 24 * 60
    assert parse_running_for_minutes("About a minute") == 1
    assert parse_running_for_minutes("Less than a second") == 0
    assert parse_running_for_minutes("not a duration") == 0


def test_docker_container_is_too_old_preserves_strict_threshold():
    assert not docker_container_is_too_old("10 minutes", 10)
    assert docker_container_is_too_old("11 minutes", 10)
    assert docker_container_is_too_old("1 hour", 10)
    assert docker_container_is_too_old("1 day", 10)


def test_parse_docker_ps_tts_line_preserves_existing_split_shape():
    assert parse_docker_ps_tts_line("abc123 15 minutes focused_tts") == (
        "abc123",
        "15 minutes",
        "focused_tts",
    )
    assert parse_docker_ps_tts_line("abc123 About a minute focused_tts") == (
        "abc123",
        "About a minute",
        "focused_tts",
    )
    assert parse_docker_ps_tts_line("abc123") == ("abc123", "", "")
    assert parse_docker_ps_tts_line("   ") is None


def test_command_is_protected_matches_case_insensitive_substrings():
    protected = {"chrome", "jane", "ollama"}
    assert command_is_protected("/usr/bin/google-chrome --type=renderer", protected)
    assert command_is_protected("python -m jane_web.main", protected)
    assert command_is_protected("/usr/bin/OLLAMA serve", protected)
    assert not command_is_protected("python worker.py", protected)
