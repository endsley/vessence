from agent_skills.edu_homework_report import build_homework_audit_markdown
from agent_skills.edu_homework_report_parts import (
    flagged_findings,
    flagged_question_block,
    homework_audit_counts,
    issue_count_cell,
    per_question_summary_row,
    verdict_cell,
)


def report():
    return {
        "section_id": 33,
        "section_label": "DS3000 / 01 / 2026",
        "assignment": {"id": 7, "title": "Vectors"},
        "mode": "full-grade",
        "student_email": "student@example.com",
        "account_id": 10,
        "attempt_id": 99,
        "summary": {"score": 50, "llm_review_error": "not configured"},
        "findings": [
            {
                "n": 1,
                "key": "q1",
                "answer_type": "number",
                "verdict": "correct",
                "issues": [],
                "error": None,
                "prompt_text": "Compute the value.",
                "solution": 4,
                "submitted_response": "4",
                "feedback_text": "",
            },
            {
                "n": 2,
                "key": "q2",
                "answer_type": "",
                "verdict": "incorrect",
                "issues": [
                    {"severity": "high", "kind": "unbalanced_math", "message": "Odd dollar count"},
                ],
                "error": "format unsupported",
                "prompt_text": "Broken prompt",
                "solution": {"x": 1},
                "submitted_response": None,
                "feedback_text": "Expected a vector.",
            },
        ],
    }


def test_build_homework_audit_markdown_summarizes_score_and_issue_counts():
    markdown = build_homework_audit_markdown(report())

    assert markdown.startswith("# HW Audit — DS3000 / 01 / 2026 · Vectors")
    assert "- Score: **50** (1/2 correct)" in markdown
    assert "- Issues flagged: **1** (1 high-severity)" in markdown
    assert "- LLM review: SKIPPED — not configured" in markdown
    assert "| 1 | `q1` | number | OK | — |" in markdown
    assert "| 2 | `q2` | default | **WRONG** | **1** |" in markdown


def test_build_homework_audit_markdown_includes_flagged_question_details():
    markdown = build_homework_audit_markdown(report())

    assert "## Flagged questions" in markdown
    assert "### Q2 — `q2` (default)" in markdown
    assert "> Broken prompt" in markdown
    assert '- Canonical solution: `{"x": 1}`' in markdown
    assert "- Server feedback: Expected a vector." in markdown
    assert "- Error: `format unsupported`" in markdown
    assert "  - **[high/unbalanced_math]** Odd dollar count" in markdown


def test_homework_report_part_helpers_preserve_counts_and_cells():
    findings = report()["findings"]
    low_issue = [{"severity": "low", "kind": "note", "message": "Minor"}]

    assert homework_audit_counts(findings) == {"total": 2, "correct": 1, "issues": 1, "high": 1}
    assert verdict_cell("correct") == "OK"
    assert verdict_cell("incorrect") == "**WRONG**"
    assert verdict_cell(None) == "—"
    assert issue_count_cell([]) == "—"
    assert issue_count_cell(low_issue) == "1"
    assert issue_count_cell(findings[1]["issues"]) == "**1**"
    assert per_question_summary_row(findings[0]) == "| 1 | `q1` | number | OK | — |"
    assert [finding["key"] for finding in flagged_findings(findings)] == ["q2"]


def test_flagged_question_block_preserves_optional_sections_and_empty_prompt_fallback():
    finding = report()["findings"][1] | {
        "prompt_text": "",
        "submitted_response": "submitted",
        "feedback_text": "",
        "error": None,
    }

    block = flagged_question_block(finding)

    assert block[:7] == [
        "### Q2 — `q2` (default)",
        "",
        "**Prompt (visible text):**",
        "",
        "> <empty>",
        "",
        '- Canonical solution: `{"x": 1}`',
    ]
    assert "- Submitted: `submitted`" in block
    assert "- Verdict: **incorrect**" in block
    assert "- Server feedback:" not in "\n".join(block)
    assert "- Error:" not in "\n".join(block)
