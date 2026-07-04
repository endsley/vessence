from jane_web.instant_commands import (
    _table_command_response,
    commands_markdown,
    cron_jobs_markdown,
    instant_command_kind,
    instant_command_response,
    normalize_instant_command,
)


def test_instant_command_kind_matches_short_exact_phrases_only():
    assert normalize_instant_command(" Show Job Queue: ") == "show job queue"
    assert instant_command_kind(" Show Job Queue: ") == "job_queue"
    assert instant_command_kind("finished jobs") == "completed_jobs"
    assert instant_command_kind("show commands") == "commands"
    assert instant_command_kind("cron jobs") == "cron"
    assert instant_command_kind("please show job queue because I need more detail") is None
    assert instant_command_kind("what is the job queue status?") is None


def test_commands_markdown_preserves_reference_table():
    table = commands_markdown()

    assert table.startswith("| Command | What it does |")
    assert "| `show job queue:` | Shows jobs table |" in table
    assert "| `my commands:` | Shows this reference |" in table


def test_cron_jobs_markdown_filters_blank_and_comment_lines():
    assert cron_jobs_markdown("\n# comment\n\n") == "No active cron jobs."
    assert cron_jobs_markdown("# comment\n* * * * * echo hi\n") == "```\n* * * * * echo hi\n```"


def test_table_command_response_formats_empty_and_error_fallbacks():
    def helpers():
        return lambda: {"rows": [1]}, lambda data: f"rows={data['rows']}"

    def empty_helpers():
        return lambda: {}, lambda _data: ""

    def broken_helpers():
        raise RuntimeError("offline")

    assert _table_command_response(
        helpers,
        empty_message="empty",
        error_message="error",
    ) == "rows=[1]"
    assert _table_command_response(
        empty_helpers,
        empty_message="empty",
        error_message="error",
    ) == "empty"
    assert _table_command_response(
        broken_helpers,
        empty_message="empty",
        error_message="error",
    ) == "error"


def test_instant_command_response_formats_job_queue_with_injected_helpers():
    def helpers():
        return lambda: {"jobs": [1]}, lambda data: f"jobs={data['jobs']}"

    assert instant_command_response("job queue", job_queue_helpers=helpers) == "jobs=[1]"


def test_instant_command_response_preserves_empty_and_error_fallbacks():
    def empty_job_helpers():
        return lambda: {}, lambda _data: ""

    def broken_helpers():
        raise RuntimeError("offline")

    assert instant_command_response("job queue", job_queue_helpers=empty_job_helpers) == (
        "Job queue is empty."
    )
    assert instant_command_response("job queue", job_queue_helpers=broken_helpers) == (
        "Could not load job queue."
    )
    assert instant_command_response("completed jobs", completed_jobs_helpers=broken_helpers) == (
        "Could not load completed jobs."
    )


def test_instant_command_response_handles_commands_cron_and_non_commands():
    assert instant_command_response("commands").startswith("| Command | What it does |")
    assert instant_command_response("cron", crontab_stdout=lambda: "* * * * * echo hi\n") == (
        "```\n* * * * * echo hi\n```"
    )
    assert instant_command_response("cron", crontab_stdout=lambda: (_ for _ in ()).throw(OSError)) == (
        "Could not load cron jobs."
    )
    assert instant_command_response("what is the job queue status?") is None
