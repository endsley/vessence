from agent_skills import prompt_queue_runner
from agent_skills.prompt_queue_docs import (
    delete_prompt_entry,
    parse_prompt_chunk,
    parse_status_prefix,
    parse_prompt_list,
    prompt_body_lines,
    prompt_entry_chunks,
    prompt_summary,
    remove_completed_prompt_entries,
    render_prompt_status_update,
    render_completed_archive_section,
    renumber_prompt_entries,
)


def test_prompt_queue_runner_reexports_prompt_summary_helper():
    assert prompt_queue_runner.prompt_summary is prompt_summary


def test_prompt_entry_parser_helpers_preserve_status_and_body_boundaries():
    content = "# Queue\n\n1. [new]\nFirst\n\n   - note\n\n2. [completed] Done\n---\n"

    assert prompt_entry_chunks(content) == [
        "# Queue",
        "1. [new]\nFirst\n\n   - note",
        "2. [completed] Done\n---",
    ]
    assert parse_status_prefix("[COMPLETE] Done") == ("complete", "Done")
    assert parse_status_prefix("No tag") == ("pending", "No tag")
    assert prompt_body_lines("Inline", ["body", "   - old note", "ignored"]) == ["Inline", "body"]
    assert prompt_body_lines("", ["body", "---", "ignored"]) == ["body"]
    assert parse_prompt_chunk("bad chunk") is None
    assert parse_prompt_chunk("2. [incomplete]\nRetry this\n") == {
        "index": 2,
        "text": "Retry this",
        "status": "incomplete",
    }


def test_parse_prompt_list_preserves_multiline_text_and_statuses():
    content = """1. [new]
First line
second line

   - old note

2. [COMPLETE] Inline done
---

3. [incomplete]
Retry this
"""

    assert parse_prompt_list(content) == [
        {"index": 1, "text": "First line\nsecond line", "status": "pending"},
        {"index": 2, "text": "Inline done", "status": "complete"},
        {"index": 3, "text": "Retry this", "status": "incomplete"},
    ]


def test_render_prompt_status_update_replaces_old_notes():
    content = """1. [new]
Do the thing

   - old note
2. [new]
Next
"""

    assert render_prompt_status_update(content, 1, "complete", "Done") == (
        "1. [completed]\n"
        "Do the thing\n"
        "\n"
        "   - Done\n"
        "\n"
        "2. [new]\n"
        "Next\n"
    )


def test_delete_and_renumber_prompt_entries():
    content = """1. [new]
First

2. [new]
Second

3. [new]
Third
"""

    deleted = delete_prompt_entry(content, 2)

    assert renumber_prompt_entries(deleted) == (
        "1. [new]\n"
        "First\n"
        "\n"
        "2. [new]\n"
        "Third\n"
    )


def test_render_completed_archive_section_preserves_existing_archive_shape():
    completed = [
        {"index": 2, "text": "Second prompt"},
        {"index": 4, "text": "Fourth\nprompt"},
    ]

    assert render_completed_archive_section(completed, "2026-07-02") == (
        "\n\n## Archived 2026-07-02\n"
        "\n"
        "### Prompt #2\n\n"
        "Second prompt\n\n"
        "---\n"
        "### Prompt #4\n\n"
        "Fourth\nprompt\n\n"
        "---\n"
    )


def test_remove_completed_prompt_entries_preserves_header_and_renumbers():
    content = """# Queue

1. [new]
First

2. [completed]
Second

3. [incomplete]
Third

4. [completed]
Fourth
"""

    assert remove_completed_prompt_entries(content, {2, 4}) == (
        "# Queue\n"
        "\n"
        "\n"
        "1. [new]\n"
        "First\n"
        "\n"
        "2. [incomplete]\n"
        "Third\n"
    )


def test_prompt_summary_preserves_existing_truncation_markers():
    text = "Sentence one. Sentence two is long enough to truncate."

    assert prompt_summary(text, max_chars=23) == (
        "Sentence one.\n"
        "_(prompt continues…)_"
    )
    assert prompt_summary("x" * 20, max_chars=10) == "xxxxxxxxxx…"
