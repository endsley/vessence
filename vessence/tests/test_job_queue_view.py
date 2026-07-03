from agent_skills import show_job_queue
from agent_skills.job_queue_view import (
    PRIORITY_LABEL,
    PRIORITY_SORT,
    STATUS_ICON,
    format_markdown_table_data,
    parse_job_file_content,
)


def test_show_job_queue_uses_extracted_view_helpers() -> None:
    assert show_job_queue.PRIORITY_LABEL is PRIORITY_LABEL
    assert show_job_queue.PRIORITY_SORT is PRIORITY_SORT
    assert show_job_queue.STATUS_ICON is STATUS_ICON
    assert show_job_queue._parse_job_file_content is parse_job_file_content
    assert show_job_queue._format_markdown_table_data is format_markdown_table_data


def test_parse_job_file_content_builds_display_row_for_pending_job() -> None:
    content = (
        "# Job: Demo\n"
        "Status: pending\n"
        "Priority: high\n\n"
        "## Objective\n"
        "Ship the refactor. Then do more details.\n"
    )

    assert parse_job_file_content(content, "001_demo.md") == {
        "num": "001",
        "file": "001_demo.md",
        "name": "Demo",
        "status": "pending",
        "status_icon": "⏳",
        "priority": "high",
        "priority_label": "🔴 High",
        "summary": "Ship the refactor.",
        "result": "Awaiting execution",
    }


def test_parse_job_file_content_handles_completed_result_and_fallbacks() -> None:
    content = "Status: completed\nPriority: strange\n\n## Result\nDone\n"
    assert parse_job_file_content(content, "002_missing_name.md") == {
        "num": "002",
        "file": "002_missing_name.md",
        "name": "002_missing_name.md",
        "status": "completed",
        "status_icon": "✅",
        "priority": "strange",
        "priority_label": "strange",
        "summary": "",
        "result": "Done",
    }


def test_format_markdown_table_data_uses_columns_and_fallback_cells() -> None:
    row = parse_job_file_content(
        "# Job: Demo\nStatus: pending\nPriority: low\n\n## Objective\nDo it",
        "003_demo.md",
    )
    data = {"columns": ["#", "Job", "Status", "Result"], "jobs": [row], "count": 1}

    assert format_markdown_table_data(data, ["#", "Job"]) == (
        "**Job Queue: 1 job**\n\n"
        "| # | Job | Status | Result |\n"
        "| --- | --- | --- | --- |\n"
        "| 003 | Demo | ⏳ pending | Awaiting execution |"
    )
    assert format_markdown_table_data({"jobs": [], "count": 0}, ["#", "Job"]) == (
        "Job queue is empty."
    )
