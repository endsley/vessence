"""Pure text helpers for prompt queue memory/log entries."""

from __future__ import annotations

from collections.abc import Iterable


def truncate_with_ellipsis(text: str, limit: int) -> str:
    return text[:limit] + ("..." if len(text) > limit else "")


def mutation_prompt_summary(prompt_text: str) -> str:
    if not prompt_text:
        return ""
    return truncate_with_ellipsis(prompt_text, 80)


def completion_fact(
    prompt_index: int,
    prompt_text: str,
    result: str,
    date_str: str,
) -> str:
    return (
        f"Prompt queue item {prompt_index} processed autonomously on {date_str}. "
        f"Status: SUCCESS. "
        f"Prompt: {truncate_with_ellipsis(prompt_text, 100)}. "
        f"Result summary: {truncate_with_ellipsis(result, 300)}"
    )


def prompt_queue_chroma_purge_script(
    short_term_db: str,
    completed_indices: Iterable[int],
) -> str:
    indices = sorted(int(index) for index in completed_indices)
    return (
        "import os; os.environ['ORT_LOGGING_LEVEL']='3'\n"
        "from jane.config import get_chroma_client\n"
        f"client = get_chroma_client(path={str(short_term_db)!r})\n"
        "col = client.get_or_create_collection('short_term_memory')\n"
        f"indices = {indices!r}\n"
        "results = col.get(where={'topic': 'prompt_queue'}, include=['metadatas'])\n"
        "to_delete = [id for id, meta in zip(results['ids'], results['metadatas'])\n"
        "             if any(meta.get('subtopic','') == f'item_{i}' for i in indices)]\n"
        "if to_delete:\n"
        "    col.delete(ids=to_delete)\n"
        "    print(f'Deleted {len(to_delete)} ChromaDB entries')\n"
    )
