import tomllib

from startup_code import install_codex_memory as installer


def test_installer_configures_memory_coordination_hooks_and_mcp_servers():
    patched = installer.patch_config('model = "test-model"\n')
    parsed = tomllib.loads(patched)

    assert "model_instructions_file" in patched
    assert "[[hooks.SessionStart]]" in patched
    assert "[[hooks.SubagentStart]]" in patched
    assert "[[hooks.UserPromptSubmit]]" in patched
    assert "[[hooks.PostToolUse]]" in patched
    assert "[[hooks.Stop]]" in patched
    assert "[[hooks.SubagentStop]]" in patched
    assert "[mcp_servers.jane-memory]" in patched
    assert "[mcp_servers.jane-coordination]" in patched
    assert "hooks = true" in patched
    assert parsed["model"] == "test-model"
    assert "model" not in parsed["features"]
    assert installer.patch_config(patched) == patched


def test_installer_repairs_root_keys_misplaced_under_features():
    broken = """[features]
hooks = true

model = "gpt-test"
model_reasoning_effort = "high"
[projects."/tmp"]
trust_level = "trusted"
"""

    parsed = tomllib.loads(installer.patch_config(broken))

    assert parsed["model"] == "gpt-test"
    assert parsed["model_reasoning_effort"] == "high"
    assert parsed["features"] == {"hooks": True}


def test_generated_hook_injects_board_context_and_heartbeats_tools():
    script = installer.hook_script()

    assert 'event_name == "PostToolUse"' in script
    assert '"heartbeat"' in script
    assert 'event_name == "SubagentStop"' in script
    assert 'event_name == "Stop"' in script
    assert '"finish"' in script
    assert '"--all"' in script
    assert '"context"' in script
    assert '"additionalContext": "\\n\\n".join(contexts)' in script
    assert "code_coordination.py" in script


def test_persistent_instructions_require_scoped_coordination():
    instructions = installer.instructions_text()

    assert "Shared Code Coordination (MANDATORY)" in instructions
    assert "post_code_task" in instructions
    assert "finish_code_task" in instructions
    assert "arbitrary agent-count limit" in instructions
    assert "project-wide `agent_skills.code_lock.code_edit_lock` only" in instructions


def test_installer_preserves_existing_non_jane_instructions_file():
    original = """model_instructions_file = "/tmp/custom-instructions.md"
model = "gpt-test"
"""

    patched = installer.patch_config(original)
    parsed = tomllib.loads(patched)

    assert parsed["model_instructions_file"] == "/tmp/custom-instructions.md"
    assert installer.patch_config(patched) == patched
