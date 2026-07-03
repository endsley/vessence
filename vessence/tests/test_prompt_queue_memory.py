from agent_skills import prompt_queue_runner
from agent_skills.prompt_queue_memory import (
    completion_fact,
    mutation_prompt_summary,
    prompt_queue_chroma_purge_script,
    truncate_with_ellipsis,
)


def test_prompt_queue_runner_uses_memory_text_helpers():
    assert prompt_queue_runner._completion_fact is completion_fact
    assert prompt_queue_runner._mutation_prompt_summary is mutation_prompt_summary
    assert prompt_queue_runner._prompt_queue_chroma_purge_script is prompt_queue_chroma_purge_script


def test_truncate_with_ellipsis_preserves_existing_slicing_rule():
    assert truncate_with_ellipsis("abc", 5) == "abc"
    assert truncate_with_ellipsis("abcdef", 5) == "abcde..."


def test_mutation_prompt_summary_handles_empty_and_long_text():
    assert mutation_prompt_summary("") == ""
    assert mutation_prompt_summary("x" * 81) == ("x" * 80) + "..."


def test_completion_fact_preserves_existing_memory_text_shape():
    fact = completion_fact(
        7,
        "p" * 101,
        "r" * 301,
        "2026-07-02 12:34 UTC",
    )

    assert fact == (
        "Prompt queue item 7 processed autonomously on 2026-07-02 12:34 UTC. "
        "Status: SUCCESS. "
        f"Prompt: {'p' * 100}.... "
        f"Result summary: {'r' * 300}..."
    )


def test_prompt_queue_chroma_purge_script_imports_client_and_sorts_indices():
    script = prompt_queue_chroma_purge_script("/tmp/db's", {9, 2, 7})

    assert "from jane.config import get_chroma_client" in script
    assert "client = get_chroma_client(path=\"/tmp/db's\")" in script
    assert "indices = [2, 7, 9]" in script
    assert "where={'topic': 'prompt_queue'}" in script
    assert "meta.get('subtopic','') == f'item_{i}'" in script
