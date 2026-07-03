"""Report builders for the education homework auditor."""
from __future__ import annotations

from agent_skills.edu_homework_report_parts import (
    flagged_findings,
    flagged_question_block,
    homework_audit_counts,
    per_question_summary_row,
)


def build_homework_audit_markdown(report: dict) -> str:
    findings = report["findings"]
    counts = homework_audit_counts(findings)
    score = report["summary"].get("score")

    lines: list[str] = []
    lines.append(
        f"# HW Audit — {report['section_label']} · "
        f"{report['assignment']['title']} (assignment #{report['assignment']['id']})"
    )
    lines.append("")
    lines.append(f"- Mode: **{report['mode']}**")
    lines.append(f"- Student: `{report['student_email']}` (account {report['account_id']})")
    lines.append(f"- Attempt: `{report['attempt_id']}`")
    if report["mode"] == "full-grade":
        lines.append(f"- Score: **{score}** ({counts['correct']}/{counts['total']} correct)")
    lines.append(f"- Issues flagged: **{counts['issues']}** ({counts['high']} high-severity)")
    if report["summary"].get("llm_review_error"):
        lines.append(f"- LLM review: SKIPPED — {report['summary']['llm_review_error']}")
    lines.append("")

    lines.append("## Per-question summary")
    lines.append("")
    lines.append("| # | Key | Type | Verdict | Issues |")
    lines.append("|---|---|---|---|---|")
    for finding in findings:
        lines.append(per_question_summary_row(finding))
    lines.append("")

    flagged = flagged_findings(findings)
    if flagged:
        lines.append("## Flagged questions")
        lines.append("")
        for finding in flagged:
            lines.extend(flagged_question_block(finding))

    return "\n".join(lines)
