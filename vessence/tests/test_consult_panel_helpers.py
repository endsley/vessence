from agent_skills import consult_panel
from agent_skills.consult_panel_helpers import (
    CliInvocation,
    build_consult_prompt,
    cli_invocation,
    prompt_with_context,
    should_consider_cli,
    should_use_stdin,
    synthesize_results,
)


def test_consult_panel_uses_extracted_helpers():
    assert consult_panel._build_consult_prompt is build_consult_prompt
    assert consult_panel._cli_invocation is cli_invocation
    assert consult_panel._prompt_with_context is prompt_with_context
    assert consult_panel._should_consider_cli is should_consider_cli
    assert consult_panel._synthesize_results is synthesize_results


def test_should_consider_cli_excludes_caller_and_skip_set():
    assert not should_consider_cli("claude", "claude", set())
    assert not should_consider_cli("ollama", "", {"ollama"})
    assert should_consider_cli("codex", "claude", {"ollama"})


def test_prompt_with_context_preserves_separator_format():
    assert prompt_with_context("Question?") == "Question?"
    assert prompt_with_context("Question?", "ctx") == "Question?\n\n---\nContext:\nctx"


def test_should_use_stdin_threshold_is_strictly_greater_than_limit():
    assert not should_use_stdin("x" * 4000)
    assert should_use_stdin("x" * 4001)


def test_cli_invocation_matches_existing_cli_command_shapes():
    assert cli_invocation("gemini", "/bin/gemini", "short") == CliInvocation(
        ["/bin/gemini", "-p", "short"]
    )
    assert cli_invocation("codex", "/bin/codex", "short") == CliInvocation(
        ["/bin/codex", "exec", "short"]
    )
    assert cli_invocation("claude", "/bin/claude", "short") == CliInvocation(
        ["/bin/claude", "-p", "short", "--output-format", "text"]
    )
    long_prompt = "x" * 4001
    assert cli_invocation("gemini", "/bin/gemini", long_prompt) == CliInvocation(
        ["/bin/gemini"],
        long_prompt,
    )
    assert cli_invocation("codex", "/bin/codex", long_prompt) == CliInvocation(
        ["/bin/codex", "exec", "-"],
        long_prompt,
    )
    assert cli_invocation("claude", "/bin/claude", long_prompt) == CliInvocation(
        ["/bin/claude", "-p", "-", "--output-format", "text"],
        long_prompt,
    )
    assert cli_invocation("unknown", "/bin/unknown", "short") is None


def test_build_consult_prompt_applies_known_mode_prefixes_only():
    review = build_consult_prompt("Check this", "review")

    assert review.startswith("You are reviewing code written by another AI.")
    assert review.endswith("\n\nCheck this")
    assert build_consult_prompt("Check this", "unknown") == "Check this"


def test_synthesize_results_preserves_no_response_message():
    assert synthesize_results([], "claude") == (
        "No peer models responded. Proceeding with own judgment."
    )
    assert synthesize_results([{"name": "codex", "error": "missing"}], "claude") == (
        "No peer models responded. Proceeding with own judgment."
    )


def test_synthesize_results_includes_successes_failures_and_synthesis():
    text = synthesize_results(
        [
            {"name": "gemini", "response": "Looks good", "elapsed": 1.2},
            {"name": "codex", "response": "Watch edge cases", "elapsed": 2.3},
            {"name": "claude", "error": "not installed"},
        ],
        "jane",
    )

    assert "## AI Panel Consultation (called by jane)" in text
    assert "### Gemini (1.2s)" in text
    assert "Looks good" in text
    assert "### Codex (2.3s)" in text
    assert "### Unavailable" in text
    assert "- claude: not installed" in text
    assert "Received 2 peer opinion(s)." in text
