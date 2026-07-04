import datetime

from agent_skills import audit_auto_fixer
from agent_skills.audit_auto_fix_prompt import (
    AUDIT_FIX_ANALYSIS_PROMPT_TEMPLATE,
    build_audit_fix_analysis_prompt,
)
from agent_skills.audit_auto_fix_helpers import (
    FORBIDDEN_PATTERNS,
    SAFE_EXTENSIONS,
    _fixed_result_row,
    _fixed_results_section_lines,
    _fix_result_file_name,
    _not_applicable_result_line,
    _not_applicable_results_section_lines,
    _reverted_result_line,
    _reverted_results_section_lines,
    _skipped_result_row,
    _skipped_results_section_lines,
    audit_report_candidates,
    circuit_breaker_skip_results,
    extract_json_array_text,
    fix_content_preflight_result,
    fix_issue_preflight_result,
    generate_fix_report_markdown,
    initial_fix_result,
    is_safe_auto_fix_path,
    latest_audit_report,
    partition_fix_results,
    result_status_counts,
    todays_audit_report,
)


def test_audit_auto_fixer_exposes_policy_constants_and_helpers():
    assert audit_auto_fixer.SAFE_EXTENSIONS is SAFE_EXTENSIONS
    assert audit_auto_fixer.FORBIDDEN_PATTERNS is FORBIDDEN_PATTERNS
    assert audit_auto_fixer.AUDIT_FIX_ANALYSIS_PROMPT_TEMPLATE is AUDIT_FIX_ANALYSIS_PROMPT_TEMPLATE
    assert audit_auto_fixer.build_audit_fix_analysis_prompt is build_audit_fix_analysis_prompt
    assert audit_auto_fixer._latest_audit_report is latest_audit_report
    assert audit_auto_fixer._todays_audit_report is todays_audit_report
    assert audit_auto_fixer._initial_fix_result is initial_fix_result
    assert audit_auto_fixer._fix_issue_preflight_result is fix_issue_preflight_result
    assert audit_auto_fixer._fix_content_preflight_result is fix_content_preflight_result
    assert audit_auto_fixer._circuit_breaker_skip_results is circuit_breaker_skip_results


def test_build_audit_fix_analysis_prompt_preserves_safety_contract():
    prompt = build_audit_fix_analysis_prompt("## audit body", "/repo/vessence")

    assert AUDIT_FIX_ANALYSIS_PROMPT_TEMPLATE.format(
        report_text="## audit body",
        vessence_home="/repo/vessence",
    ) == prompt
    assert "Output ONLY a JSON array" in prompt
    assert "NEVER include crontab modifications" in prompt
    assert "NEVER include file deletions" in prompt
    assert "absolute (starting with /repo/vessence/)" in prompt
    assert '"/repo/vessence/configs/CRON_JOBS.md"' in prompt
    assert "## audit body" in prompt


def test_is_safe_auto_fix_path_checks_forbidden_patterns_extension_and_existence():
    assert is_safe_auto_fix_path("/repo/configs/README.md", exists=True)
    assert not is_safe_auto_fix_path("/repo/.env", exists=True)
    assert not is_safe_auto_fix_path("/repo/configs/secret_notes.md", exists=True)
    assert not is_safe_auto_fix_path("/repo/image.png", exists=True)
    assert not is_safe_auto_fix_path("/repo/configs/README.md", exists=False)


def test_extract_json_array_text_handles_fences_and_preamble():
    assert extract_json_array_text('```json\n[{"a": 1}]\n```') == '[{"a": 1}]'
    assert extract_json_array_text('preamble\n[{"a": 1}]\ntrailing') == '[{"a": 1}]'
    assert extract_json_array_text("not json") == "not json"


def test_initial_fix_result_preserves_apply_fix_result_shape_defaults():
    assert initial_fix_result({}) == {
        "issue": "Unknown",
        "file": "Unknown",
        "category": "unknown",
        "status": "skipped",
        "reason": "",
    }

    assert initial_fix_result({
        "issue": "Bad path",
        "file": "/repo/a.py",
        "category": "code_fix",
    }) == {
        "issue": "Bad path",
        "file": "/repo/a.py",
        "category": "code_fix",
        "status": "skipped",
        "reason": "",
    }


def test_fix_issue_preflight_result_returns_terminal_validation_results():
    assert fix_issue_preflight_result(
        {"category": "skip", "fix_description": "manual review"},
        safe_to_modify=lambda _path: True,
    ) == {"status": "skipped", "reason": "manual review"}

    assert fix_issue_preflight_result(
        {"category": "code_fix", "file": "/repo/a.py", "search_text": "x"},
        safe_to_modify=lambda _path: True,
    ) == {
        "status": "skipped",
        "reason": "Missing file, search_text, or replacement_text",
    }

    assert fix_issue_preflight_result(
        {
            "category": "code_fix",
            "file": "/repo/a.py",
            "search_text": "same",
            "replacement_text": "same",
        },
        safe_to_modify=lambda _path: True,
    ) == {
        "status": "skipped",
        "reason": "search_text and replacement_text are identical",
    }

    assert fix_issue_preflight_result(
        {
            "category": "code_fix",
            "file": "/repo/secret.py",
            "search_text": "old",
            "replacement_text": "new",
        },
        safe_to_modify=lambda _path: False,
    ) == {
        "status": "skipped",
        "reason": "File not safe to modify: /repo/secret.py",
    }

    assert fix_issue_preflight_result(
        {
            "category": "code_fix",
            "file": "/repo/a.py",
            "search_text": "old",
            "replacement_text": "new",
        },
        safe_to_modify=lambda _path: True,
    ) is None


def test_fix_content_preflight_result_preserves_not_applicable_and_dry_run_statuses():
    issue = {
        "search_text": "old text",
        "replacement_text": "new text",
        "fix_description": "Replace old text",
    }

    assert fix_content_preflight_result(issue, "already new", dry_run=False) == {
        "status": "not_applicable",
        "reason": "Search text not found in file (may already be fixed)",
    }
    assert fix_content_preflight_result(issue, "old text", dry_run=True) == {
        "status": "would_fix",
        "reason": "Replace old text",
    }
    assert fix_content_preflight_result(issue, "old text", dry_run=False) is None


def test_audit_report_discovery_ignores_auto_fix_reports_and_prefers_latest(tmp_path):
    assert audit_report_candidates(tmp_path / "missing") == []

    older = tmp_path / "audit_2026-07-01.md"
    latest = tmp_path / "audit_2026-07-02_1300.md"
    today_older = tmp_path / "audit_2026-07-02.md"
    auto_fix = tmp_path / "auto_fix_2026-07-03.md"
    for path in (older, latest, today_older, auto_fix):
        path.write_text("report", encoding="utf-8")

    assert audit_report_candidates(tmp_path) == [latest, today_older, older]
    assert latest_audit_report(tmp_path) == latest
    assert todays_audit_report(tmp_path, datetime.date(2026, 7, 2)) == latest
    assert todays_audit_report(tmp_path, datetime.date(2026, 7, 3)) is None


def test_partition_and_count_fix_results():
    results = [
        {"status": "fixed"},
        {"status": "would_fix"},
        {"status": "skipped"},
        {"status": "not_applicable"},
        {"status": "reverted"},
    ]

    partitions = partition_fix_results(results)

    assert len(partitions["fixed"]) == 2
    assert result_status_counts(results) == {
        "fixed": 2,
        "skipped": 1,
        "not_applicable": 1,
        "reverted": 1,
    }


def test_circuit_breaker_skip_results_preserve_remaining_issue_shape():
    issues = [
        {"issue": "already processed", "file": "/repo/a.py", "category": "code_fix"},
        {"issue": "skip me", "file": "/repo/b.py", "category": "doc_update"},
        {"file": "/repo/c.py"},
    ]

    assert circuit_breaker_skip_results(
        issues,
        result_count=1,
        max_fixes_per_run=10,
    ) == [
        {
            "issue": "skip me",
            "file": "/repo/b.py",
            "category": "doc_update",
            "status": "skipped",
            "reason": "Circuit breaker: max 10 fixes per run",
        },
        {
            "issue": "Unknown",
            "file": "/repo/c.py",
            "category": "unknown",
            "status": "skipped",
            "reason": "Circuit breaker: max 10 fixes per run",
        },
    ]


def test_fix_report_result_line_helpers_preserve_truncation_and_filename_policy():
    fixed = {
        "issue": "x" * 90,
        "file": "/repo/configs/README.md",
        "reason": "r" * 90,
    }
    skipped = {"issue": "Needs review", "file": "Unknown", "reason": "Human judgment"}
    not_applicable = {"issue": "a" * 110}
    reverted = {"issue": "b" * 90, "reason": "Fix introduced syntax error"}

    assert _fix_result_file_name(fixed) == "README.md"
    assert _fix_result_file_name(skipped) == "?"
    assert _fixed_result_row(fixed) == f"| {'x' * 80} | `README.md` | {'r' * 80} |"
    assert _skipped_result_row(skipped) == "| Needs review | Human judgment |"
    assert _not_applicable_result_line(not_applicable) == f"- {'a' * 100}"
    assert _reverted_result_line(reverted) == f"- **{'b' * 80}** — Fix introduced syntax error"


def test_fix_report_section_helpers_preserve_tables_and_empty_sections():
    fixed = {
        "issue": "Fix me",
        "file": "/repo/configs/README.md",
        "reason": "Updated wording",
    }
    skipped = {"issue": "Needs review", "reason": "Human judgment"}
    not_applicable = {"issue": "Already done"}
    reverted = {"issue": "Syntax broke", "reason": "Fix introduced syntax error"}

    assert _fixed_results_section_lines([fixed], dry_run=True) == [
        "## Would Fix (1)",
        "",
        "| Issue | File | Fix Applied |",
        "|-------|------|-------------|",
        "| Fix me | `README.md` | Updated wording |",
        "",
    ]
    assert _fixed_results_section_lines([fixed], dry_run=False)[0] == "## Fixed (1)"
    assert _fixed_results_section_lines([], dry_run=False) == []
    assert _skipped_results_section_lines([skipped]) == [
        "## Skipped (1)",
        "",
        "| Issue | Reason |",
        "|-------|--------|",
        "| Needs review | Human judgment |",
        "",
    ]
    assert _skipped_results_section_lines([]) == []
    assert _not_applicable_results_section_lines([not_applicable]) == [
        "## Already Fixed / Not Applicable (1)",
        "",
        "- Already done",
        "",
    ]
    assert _not_applicable_results_section_lines([]) == []
    assert _reverted_results_section_lines([reverted]) == [
        "## Reverted (1)",
        "",
        "- **Syntax broke** — Fix introduced syntax error",
        "",
    ]
    assert _reverted_results_section_lines([]) == []


def test_generate_fix_report_markdown_preserves_sections_and_truncation():
    results = [
        {
            "status": "would_fix",
            "issue": "x" * 90,
            "file": "/repo/configs/README.md",
            "reason": "r" * 90,
        },
        {
            "status": "skipped",
            "issue": "Needs review",
            "file": "Unknown",
            "reason": "Human judgment",
        },
        {
            "status": "not_applicable",
            "issue": "Already done",
            "file": "/repo/a.py",
            "reason": "",
        },
        {
            "status": "reverted",
            "issue": "Syntax broke",
            "file": "/repo/a.py",
            "reason": "Fix introduced syntax error",
        },
    ]

    report = generate_fix_report_markdown(
        "/repo/audit.md",
        results,
        dry_run=True,
        generated_at=datetime.datetime(2026, 7, 2, 12, 30),
    )

    assert report.startswith("# Auto-Fix Report — 2026-07-02 12:30 (DRY RUN)")
    assert "**Source audit:** `/repo/audit.md`" in report
    assert "## Would Fix (1)" in report
    assert f"| {'x' * 80} | `README.md` | {'r' * 80} |" in report
    assert "## Skipped (1)" in report
    assert "## Already Fixed / Not Applicable (1)" in report
    assert "- Already done" in report
    assert "## Reverted (1)" in report
    assert "- **Syntax broke** — Fix introduced syntax error" in report
