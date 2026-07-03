"""Small formatting helpers for homework audit markdown reports."""

from __future__ import annotations

import json
from typing import Any


def homework_audit_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(findings),
        "correct": sum(1 for finding in findings if finding["verdict"] == "correct"),
        "issues": sum(len(finding["issues"]) for finding in findings),
        "high": sum(
            1
            for finding in findings
            for issue in finding["issues"]
            if issue["severity"] == "high"
        ),
    }


def verdict_cell(verdict: str | None) -> str:
    verdict = verdict or "—"
    if verdict == "correct":
        return "OK"
    if verdict == "incorrect":
        return "**WRONG**"
    return verdict


def issue_count_cell(issues: list[dict[str, Any]]) -> str:
    issue_count = len(issues)
    if issue_count == 0:
        return "—"
    if any(issue["severity"] == "high" for issue in issues):
        return f"**{issue_count}**"
    return str(issue_count)


def per_question_summary_row(finding: dict[str, Any]) -> str:
    return (
        f"| {finding['n']} | `{finding['key']}` | {finding['answer_type'] or 'default'} "
        f"| {verdict_cell(finding['verdict'])} | {issue_count_cell(finding['issues'])} |"
    )


def flagged_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [finding for finding in findings if finding["issues"] or finding["error"]]


def flagged_question_block(finding: dict[str, Any]) -> list[str]:
    lines = [
        f"### Q{finding['n']} — `{finding['key']}` ({finding['answer_type'] or 'default'})",
        "",
        "**Prompt (visible text):**",
        "",
        "> " + (finding["prompt_text"][:500] or "<empty>"),
        "",
        f"- Canonical solution: `{json.dumps(finding['solution'])}`",
    ]
    if finding["submitted_response"] is not None:
        lines.append(f"- Submitted: `{finding['submitted_response']}`")
    if finding["verdict"]:
        lines.append(f"- Verdict: **{finding['verdict']}**")
    if finding["feedback_text"]:
        lines.append(f"- Server feedback: {finding['feedback_text']}")
    if finding["error"]:
        lines.append(f"- Error: `{finding['error']}`")
    if finding["issues"]:
        lines.append("- Issues:")
        for issue in finding["issues"]:
            lines.append(f"  - **[{issue['severity']}/{issue['kind']}]** {issue['message']}")
    lines.append("")
    return lines
