from agent_skills import dead_code_auditor
from agent_skills.dead_code_policy import (
    auto_delete_eligibility,
    in_hard_skip,
    is_pytest_discovery_file,
)


def test_dead_code_auditor_uses_extracted_policy_helpers():
    assert dead_code_auditor._in_hard_skip is in_hard_skip
    assert dead_code_auditor.is_pytest_discovery_file is is_pytest_discovery_file
    assert dead_code_auditor._auto_delete_eligibility is auto_delete_eligibility


def test_in_hard_skip_uses_prefix_matching():
    prefixes = ("android/", "node_modules/", "configs/")
    assert in_hard_skip("android/app/src/Main.kt", prefixes)
    assert in_hard_skip("node_modules/pkg/index.js", prefixes)
    assert not in_hard_skip("agent_skills/tool.py", prefixes)


def test_is_pytest_discovery_file_matches_test_code_test_modules_only():
    assert is_pytest_discovery_file("test_code/test_generated.py")
    assert not is_pytest_discovery_file("test_code/helper.py")
    assert not is_pytest_discovery_file("tests/test_real_suite.py")
    assert not is_pytest_discovery_file("agent_skills/test_tool.py")


def _eligible(**overrides):
    params = {
        "rel_path": "agent_skills/old_tool.py",
        "filename": "old_tool.py",
        "size_bytes": 10_000,
        "line_count": 100,
        "age_days": 60.0,
        "hard_keep": {"main.py"},
        "max_auto_delete_lines": 500,
        "auto_delete_age_days": 60,
        "dynamically_imported": False,
    }
    params.update(overrides)
    return auto_delete_eligibility(**params)


def test_auto_delete_eligibility_enforces_documented_root_and_safety_guards():
    assert _eligible() == (True, "eligible")
    assert _eligible(rel_path="context_builder/v1/old_tool.py") == (
        False,
        "outside_auto_delete_roots",
    )
    assert _eligible(filename="main.py") == (False, "hard_keep")
    assert _eligible(dynamically_imported=True) == (False, "dynamically_imported")
    assert _eligible(size_bytes=500 * 200 + 1) == (False, "too_large_bytes")
    assert _eligible(line_count=501) == (False, "too_many_lines")
    assert _eligible(age_days=59.9) == (False, "too_new")
