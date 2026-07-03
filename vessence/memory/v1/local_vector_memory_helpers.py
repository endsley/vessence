"""Pure helpers for local_vector_memory.py."""

from __future__ import annotations

from collections.abc import Sequence


RECENT_FORGETTABLE_HEADING = (
    "## Recent/Forgettable Memory  ← highest recency, treat as most current"
)


def is_forgettable_expired(meta: dict, now_iso: str) -> bool:
    expires_at = meta.get("expires_at", "")
    if not expires_at:
        return False
    try:
        return str(expires_at) < now_iso
    except Exception:
        return False


def format_memory_fact(doc: str, meta: dict) -> str:
    timestamp = meta.get("timestamp", meta.get("created_at", "Unknown Time"))
    topic = meta.get("topic", "General")
    expires_at = meta.get("expires_at", "")
    expiry_str = f", expires {str(expires_at)[:10]}" if expires_at else ""
    return f"[{str(timestamp)[:19]}] ({topic}{expiry_str}): {doc}"


def bucket_memory_facts(
    documents: Sequence[str],
    metadatas: Sequence[dict],
    *,
    now_iso: str,
) -> tuple[list[str], list[str], list[str]]:
    permanent_facts: list[str] = []
    long_term_facts: list[str] = []
    forgettable_facts: list[str] = []

    for index, doc in enumerate(documents):
        meta = metadatas[index]
        memory_type = meta.get("memory_type", "long_term")
        if memory_type == "forgettable":
            if not is_forgettable_expired(meta, now_iso):
                forgettable_facts.append(format_memory_fact(doc, meta))
        elif memory_type == "permanent":
            permanent_facts.append(format_memory_fact(doc, meta))
        else:
            long_term_facts.append(format_memory_fact(doc, meta))

    return permanent_facts, long_term_facts, forgettable_facts


def memory_tier_sections(
    permanent_facts: Sequence[str],
    long_term_facts: Sequence[str],
    forgettable_facts: Sequence[str],
) -> list[str]:
    sections = []
    if permanent_facts:
        sections.append("## Permanent Memory\n" + "\n".join(permanent_facts))
    if long_term_facts:
        sections.append("## Long-Term Memory\n" + "\n".join(long_term_facts))
    if forgettable_facts:
        sections.append(
            RECENT_FORGETTABLE_HEADING
            + "\n"
            + "\n".join(forgettable_facts)
        )
    return sections


def librarian_system_instruction(user_name: str) -> str:
    return (
        f"You are the Memory Librarian for {user_name}'s assistant. "
        "Your task is to analyze the provided tiered memories relative to the user's query. "
        "Synthesize a single, high-fidelity, and concise summary of all relevant facts. "
        "Rules:\n"
        "1. Recency priority: Recent/Forgettable > Long-Term > Permanent. "
        "When facts contradict, the more recent tier wins.\n"
        "2. 'Recent/Forgettable Memory' captures recent work, changes, and discoveries — "
        "always surface these if even tangentially relevant.\n"
        "3. Ignore noise that is clearly irrelevant to the query.\n"
        "4. If no memories are relevant, respond with 'No relevant context found.'\n"
        "5. Respond only with the synthesized summary."
    )


def librarian_user_prompt(query: str, facts_block: str) -> str:
    return f"User Query: {query}\n\nMemory Tiers:\n{facts_block}"
