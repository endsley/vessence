import datetime as dt
from pathlib import Path

from agent_skills import nightly_code_auditor
from agent_skills.nightly_code_audit_helpers import (
    audit_branch_name,
    audit_fix_prompt,
    audit_report_stash_name,
    audit_sleep_window_allowed,
    audit_test_generation_prompt,
    auto_audit_test_path,
    default_auditor_state,
    fix_attempt_declined,
    integration_contract_context,
    nonblank_porcelain_lines,
    parse_whitelist_modules,
    pick_next_module_in_rotation,
    unexpected_porcelain_changes,
)


def test_nightly_code_auditor_uses_extracted_helpers():
    assert nightly_code_auditor._parse_whitelist_modules is parse_whitelist_modules
    assert nightly_code_auditor._pick_next_module_in_rotation is pick_next_module_in_rotation
    assert nightly_code_auditor._unexpected_porcelain_changes is unexpected_porcelain_changes
    assert nightly_code_auditor._audit_test_generation_prompt is audit_test_generation_prompt
    assert nightly_code_auditor._audit_fix_prompt is audit_fix_prompt
    assert nightly_code_auditor._fix_attempt_declined is fix_attempt_declined
    assert nightly_code_auditor._audit_sleep_window_allowed is audit_sleep_window_allowed


def test_parse_whitelist_modules_keeps_safe_and_careful_rows_only():
    text = "\n".join([
        "| Module | Spec | Safety |",
        "| --- | --- | --- |",
        "| `agent_skills/a.py` | core audit | safe |",
        "| `agent_skills/b.py` | risky audit | careful |",
        "| `agent_skills/c.py` | no | unsafe |",
    ])

    assert parse_whitelist_modules(text) == [
        {"path": "agent_skills/a.py", "spec": "core audit", "safety": "safe"},
        {"path": "agent_skills/b.py", "spec": "risky audit", "safety": "careful"},
    ]


def test_default_state_and_rotation_mutates_last_index_with_wraparound():
    state = default_auditor_state()
    modules = [{"path": "a.py"}, {"path": "b.py"}]

    assert pick_next_module_in_rotation(modules, state) == {"path": "a.py"}
    assert state["last_index"] == 0
    assert pick_next_module_in_rotation(modules, state) == {"path": "b.py"}
    assert state["last_index"] == 1
    assert pick_next_module_in_rotation(modules, state) == {"path": "a.py"}
    assert state["last_index"] == 0


def test_audit_sleep_window_allowed_preserves_force_and_hour_bounds():
    assert audit_sleep_window_allowed([], dt.datetime(2026, 7, 2, 1, 0))
    assert audit_sleep_window_allowed([], dt.datetime(2026, 7, 2, 6, 59))
    assert not audit_sleep_window_allowed([], dt.datetime(2026, 7, 2, 7, 0))
    assert not audit_sleep_window_allowed([], dt.datetime(2026, 7, 2, 0, 59))
    assert audit_sleep_window_allowed(["--force"], dt.datetime(2026, 7, 2, 12, 0))


def test_porcelain_helpers_ignore_expected_outputs_and_git_backups_only():
    lines = nonblank_porcelain_lines(
        " M configs/doc_drift_report.md\n"
        "?? .git.backup.123\n"
        " M agent_skills/nightly_code_auditor.py\n"
        "\n"
    )

    assert lines == [
        " M configs/doc_drift_report.md",
        "?? .git.backup.123",
        " M agent_skills/nightly_code_auditor.py",
    ]
    assert unexpected_porcelain_changes(lines) == [
        " M agent_skills/nightly_code_auditor.py"
    ]


def test_generated_names_preserve_formats():
    now = dt.datetime(2026, 7, 2, 3, 4, 5)

    assert audit_report_stash_name(now) == "auditor-pre-report-stash-20260702-030405"
    assert audit_branch_name(now) == "auto-audit/2026-07-02-0304"
    assert auto_audit_test_path("agent_skills/example_tool.py", Path("/tmp/tests")) == (
        Path("/tmp/tests") / "auto_audit_example_tool.py"
    )


def test_integration_contract_context_includes_contract_file_only_on_match():
    integrations = "Producer: agent_skills/example_tool.py\nContract: shape stable"

    context = integration_contract_context("agent_skills/example_tool.py", integrations)

    assert "CROSS-STACK INTEGRATION CONTRACTS" in context
    assert integrations in context
    assert integration_contract_context("agent_skills/other.py", integrations) == ""


def test_audit_test_generation_prompt_contains_contract_and_truncates_code():
    module = {
        "path": "agent_skills/example_tool.py",
        "spec": "example spec",
        "safety": "safe",
    }
    target_test_path = Path("/tmp/tests/auto_audit_example_tool.py")
    prompt = audit_test_generation_prompt(
        module,
        "a" * 8001 + "TAIL",
        target_test_path,
        integrations="\n\nCONTRACTS",
    )

    assert "MODULE PATH: agent_skills/example_tool.py" in prompt
    assert "SPEC SOURCE: example spec\n\nCONTRACTS" in prompt
    assert f"Write a comprehensive pytest file at {target_test_path}" in prompt
    assert "a" * 8000 in prompt
    assert "TAIL" not in prompt
    assert "STRUCTURAL INVARIANTS" in prompt


def test_audit_fix_prompt_contains_attempt_policy_and_truncates_inputs():
    prompt = audit_fix_prompt(
        "agent_skills/example_tool.py",
        "c" * 6001 + "CODETAIL",
        "o" * 3001 + "OUTPUTTAIL",
        attempt=2,
        max_fix_attempts=3,
    )

    assert "failing for module: agent_skills/example_tool.py" in prompt
    assert "c" * 6000 in prompt
    assert "CODETAIL" not in prompt
    assert "o" * 3000 in prompt
    assert "OUTPUTTAIL" not in prompt
    assert "ATTEMPT 2 of 3." in prompt
    assert "Do NOT modify the test file." in prompt
    assert "output: TEST_WRONG" in prompt
    assert "output: GIVE_UP" in prompt


def test_fix_attempt_declined_detects_provider_stop_markers():
    assert fix_attempt_declined("TEST_WRONG")
    assert fix_attempt_declined("I choose GIVE_UP for this one")
    assert not fix_attempt_declined("patched file successfully")
