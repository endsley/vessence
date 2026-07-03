import pytest

from agent_skills import edu_homework_audit
from agent_skills.edu_homework_audit_rules import (
    auto_answer_unsupported_issue,
    grader_canonical_mismatch_issue,
    unreliable_verdict_issue,
    validate_audit_mode,
    validate_local_base_url,
)


def test_edu_homework_audit_uses_rule_helpers():
    assert edu_homework_audit.validate_audit_mode is validate_audit_mode
    assert edu_homework_audit.validate_local_base_url is validate_local_base_url
    assert edu_homework_audit.auto_answer_unsupported_issue is auto_answer_unsupported_issue
    assert edu_homework_audit.grader_canonical_mismatch_issue is grader_canonical_mismatch_issue
    assert edu_homework_audit.unreliable_verdict_issue is unreliable_verdict_issue


def test_validate_audit_mode_preserves_mode_and_reuse_attempt_errors():
    validate_audit_mode("full-grade", reuse_attempt=False)
    validate_audit_mode("audit-only", reuse_attempt=True)
    with pytest.raises(ValueError, match="mode must be full-grade or audit-only"):
        validate_audit_mode("dry-run", reuse_attempt=False)
    with pytest.raises(ValueError, match="--reuse-attempt requires --mode audit-only"):
        validate_audit_mode("full-grade", reuse_attempt=True)


def test_validate_local_base_url_allows_only_local_hosts():
    validate_local_base_url("http://localhost:8501", db_port=3307)
    validate_local_base_url("http://127.0.0.1:8501", db_port=3307)
    validate_local_base_url("http://[::1]:8501", db_port=3307)
    with pytest.raises(RuntimeError, match="DB connection is hardcoded to localhost:3307"):
        validate_local_base_url("https://classes.example.test", db_port=3307)


def test_auto_answer_unsupported_issue_preserves_error_shape():
    issue = auto_answer_unsupported_issue(ValueError("bad answer"))

    assert issue == {
        "severity": "med",
        "kind": "auto_answer_unsupported",
        "message": "ValueError: bad answer",
    }


def test_grader_and_unreliable_verdict_issues_preserve_messages():
    mismatch = grader_canonical_mismatch_issue("[1; 2]", "Expected vector")
    stale = unreliable_verdict_issue("stale")

    assert mismatch["severity"] == "high"
    assert mismatch["kind"] == "grader_canonical_mismatch"
    assert "Submitted '[1; 2]'; feedback: Expected vector" in mismatch["message"]
    assert stale == {
        "severity": "high",
        "kind": "verdict_stale",
        "message": (
            "Submission verdict was 'stale' (concurrent "
            "writer? attempt locked? unexpected response?) "
            "— audit data for this question is unreliable."
        ),
    }
