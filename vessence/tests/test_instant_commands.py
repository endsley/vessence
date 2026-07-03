from jane_web.instant_commands import (
    commands_markdown,
    cron_jobs_markdown,
    instant_command_kind,
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
