import json

import pytest

from llm_brain.v1 import standing_brain


class FakeSecretStore:
    def __init__(self, unlocked, secrets=None):
        self._unlocked = unlocked
        self._secrets = secrets or {}

    def is_unlocked(self):
        return self._unlocked

    def get(self, key):
        return self._secrets.get(key)


class FakeBrain:
    alive = True
    consecutive_failures = 0
    turn_count = 0


def test_standing_brain_command_builds_claude_web_permission_hook(tmp_path):
    hooks_dir = tmp_path / "hooks"
    hook_script = hooks_dir / "permission_gate.py"
    env = {
        "CLAUDE_BIN": "/opt/bin/claude",
        "JANE_WEB_PERMISSIONS": "1",
        "PYTHON_BIN": "/opt/bin/python",
    }

    cmd = standing_brain._standing_brain_command(
        "claude",
        "claude-test-model",
        environ=env,
        binary_resolver=lambda _name: None,
        hook_file_exists=lambda path: path == str(hook_script),
        module_dir=tmp_path,
        python_executable="/fallback/python",
    )

    assert cmd[:7] == [
        "/opt/bin/claude",
        "--print",
        "--verbose",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
    ]
    assert cmd[7:] == [
        "--model",
        "claude-test-model",
        "--dangerously-skip-permissions",
        "--settings",
        cmd[-1],
    ]
    settings = json.loads(cmd[-1])
    hook = settings["hooks"]["PreToolUse"][0]["hooks"][0]
    assert hook == {
        "type": "command",
        "command": f"/opt/bin/python {hook_script}",
        "timeout": 300,
    }


def test_standing_brain_command_preserves_provider_shapes():
    resolver = {"gemini": "/opt/bin/gemini", "codex": "/opt/bin/codex"}.get

    assert standing_brain._standing_brain_command(
        "gemini",
        "gemini-test-model",
        environ={},
        binary_resolver=resolver,
    ) == [
        "/opt/bin/gemini",
        "--approval-mode",
        "yolo",
        "--output-format",
        "text",
        "--model",
        "gemini-test-model",
    ]

    assert standing_brain._standing_brain_command(
        "openai",
        "gpt-test-model",
        environ={},
        binary_resolver=resolver,
    ) == [
        "/opt/bin/codex",
        "exec",
        "--model",
        "gpt-test-model",
        "--approval-mode",
        "full-auto",
    ]


def test_standing_brain_command_rejects_unknown_provider():
    with pytest.raises(RuntimeError, match="Unknown provider: unknown"):
        standing_brain._standing_brain_command("unknown", "model", environ={})


def test_prompt_and_stdin_payload_helpers_preserve_wire_formats():
    assert standing_brain._prompt_for_turn("hello", "system", 0) == "system\n\nUser: hello\nJane:"
    assert standing_brain._prompt_for_turn("hello", "system", 1) == "hello"
    assert standing_brain._prompt_for_turn("hello", "", 0) == "hello"

    claude_payload = json.loads(
        standing_brain._stdin_payload_for_provider("claude", "full message", None)
    )
    assert claude_payload == {
        "type": "user",
        "message": {"role": "user", "content": "full message"},
        "session_id": "default",
        "parent_tool_use_id": None,
    }
    assert standing_brain._stdin_payload_for_provider("gemini", "full message", "ignored") == (
        "full message\n"
    )


def test_claude_tool_description_and_result_preview_helpers():
    assert standing_brain._claude_tool_use_description(
        {"name": "Read", "input": {"file_path": "/tmp/example.txt"}}
    ) == "📖 Reading /tmp/example.txt"
    assert standing_brain._claude_tool_use_description(
        {"name": "Grep", "input": {"pattern": "needle" * 30}}
    ).startswith("🔍 Searching for \"needle")
    assert standing_brain._claude_tool_use_description(
        {"name": "CustomTool", "input": "not-a-dict"}
    ) == "🔧 Using CustomTool"

    assert standing_brain._claude_tool_result_preview([
        {"type": "text", "text": " first "},
        {"type": "image", "data": "..."},
        {"type": "text", "text": "second"},
    ]) == "↳ first \nsecond"
    long_preview = standing_brain._claude_tool_result_preview("x" * 501)
    assert long_preview == f"↳ {'x' * 500} … (501 chars total)"
    assert standing_brain._claude_tool_result_preview("") is None


def test_claude_thinking_lines_preserve_filtering_and_truncation():
    assert standing_brain._claude_thinking_lines(
        " tiny\n useful thought \n" + ("x" * 301),
    ) == [
        "useful thought",
        "x" * 300,
    ]


def test_brain_process_environment_tracks_vault_lock_state_without_mutating_base_env():
    base_env = {"EXISTING": "1", "OPENAI_API_KEY": "from-process"}

    locked = standing_brain._brain_process_environment(base_env, FakeSecretStore(unlocked=False))
    assert locked.env == base_env
    assert locked.env is not base_env
    assert locked.injected_count == 0
    assert locked.spawned_locked is True

    unlocked = standing_brain._brain_process_environment(
        base_env,
        FakeSecretStore(
            unlocked=True,
            secrets={
                "OPENAI_API_KEY": "from-vault",
                "GOOGLE_CLIENT_ID": "",
                "ANTHROPIC_API_KEY": "anthropic",
            },
        ),
    )
    assert unlocked.env["OPENAI_API_KEY"] == "from-vault"
    assert unlocked.env["ANTHROPIC_API_KEY"] == "anthropic"
    assert "GOOGLE_CLIENT_ID" not in unlocked.env
    assert unlocked.injected_count == 2
    assert unlocked.spawned_locked is False
    assert base_env["OPENAI_API_KEY"] == "from-process"


def test_should_restart_for_unlocked_store_requires_locked_spawned_process():
    brain = FakeBrain()
    assert standing_brain._should_restart_for_unlocked_store(False, brain) is False

    brain._spawned_locked = False
    assert standing_brain._should_restart_for_unlocked_store(True, brain) is False

    brain._spawned_locked = True
    assert standing_brain._should_restart_for_unlocked_store(True, brain) is True

    brain.alive = False
    assert standing_brain._should_restart_for_unlocked_store(True, brain) is False
    assert standing_brain._should_restart_for_unlocked_store(True, None) is False


def test_brain_restart_reason_preserves_priority_order():
    brain = FakeBrain()
    assert standing_brain._brain_restart_reason(
        brain,
        max_failures=3,
        max_turns=10,
    ) is None

    brain.turn_count = 10
    assert standing_brain._brain_restart_reason(
        brain,
        max_failures=3,
        max_turns=10,
    ) == "hit 10 turns, refreshing context"

    brain.consecutive_failures = 3
    assert standing_brain._brain_restart_reason(
        brain,
        max_failures=3,
        max_turns=10,
    ) == "hit 3 consecutive failures"

    brain.alive = False
    assert standing_brain._brain_restart_reason(
        brain,
        max_failures=3,
        max_turns=10,
    ) == "dead"


def test_provider_switch_planning_helpers_preserve_cli_and_install_shapes():
    assert standing_brain._provider_cli_name("claude") == "claude"
    assert standing_brain._provider_cli_name("openai") == "codex"
    assert standing_brain._provider_cli_name("other") == "other"
    assert standing_brain._brain_install_script_path({"VESSENCE_HOME": "/app/vessence"}) == (
        "/app/vessence/docker/jane/install_brain.sh"
    )
    assert standing_brain._brain_install_env("gemini", {"EXISTING": "1"}) == {
        "EXISTING": "1",
        "JANE_BRAIN": "gemini",
    }


def test_provider_model_prefers_provider_env_then_defaults():
    assert standing_brain._provider_model("openai", {"JANE_MODEL_OPENAI": "gpt-current"}) == (
        "gpt-current"
    )
    assert standing_brain._provider_model("gemini", {}) == standing_brain._DEFAULT_MODELS["gemini"]
    assert standing_brain._provider_model("unknown", {}) == "gemini-2.5-pro"


def test_provider_from_env_lines_reads_valid_brain_value_only():
    assert standing_brain._provider_from_env_lines([
        "# JANE_BRAIN=claude",
        "OTHER=value",
        "JANE_BRAIN = openai",
    ]) == "openai"
    assert standing_brain._provider_from_env_lines(["JANE_BRAIN=invalid"]) is None
    assert standing_brain._provider_from_env_lines(["JANE_BRAIN=codex"]) == "openai"
    assert standing_brain._provider_from_env_lines([""]) is None


def test_provider_switch_result_preserves_auth_and_success_messages():
    assert standing_brain._provider_switch_result(
        provider="gemini",
        model="gemini-model",
        was_installed=False,
        needs_auth=False,
    ) == {
        "ok": True,
        "provider": "gemini",
        "model": "gemini-model",
        "was_installed": False,
        "needs_auth": False,
        "message": "Switched to gemini (gemini-model)",
    }
    assert standing_brain._provider_switch_result(
        provider="claude",
        model="claude-model",
        was_installed=True,
        needs_auth=True,
    ) == {
        "ok": True,
        "provider": "claude",
        "model": "claude-model",
        "was_installed": True,
        "needs_auth": True,
        "auth_url": None,
        "message": "claude CLI needs authentication. Use the login flow to authenticate.",
    }
