"""Build formatted memory context sections from retrieved fact lines."""
from __future__ import annotations

from memory.v1.memory_text import dedupe_fact_lines


def memory_section(label: str, facts: list[str]) -> str:
    return label + "\n" + "\n".join(facts)


def dedupe_memory_fact_groups(*fact_groups: list[str]) -> tuple[list[str], ...]:
    global_seen: set[str] = set()
    return tuple(dedupe_fact_lines(facts, global_seen) for facts in fact_groups)


def build_memory_sections_from_facts(
    *,
    permanent_facts: list[str],
    long_term_facts: list[str],
    jane_long_term_facts: list[str],
    short_term_facts: list[str],
    file_index_facts: list[str],
    legacy_short_term_facts: list[str],
    essence_facts: list[str],
    use_user_memory: bool,
) -> list[str]:
    """Apply cross-section dedupe and format sections in retrieval priority order."""
    (
        permanent_facts,
        long_term_facts,
        jane_long_term_facts,
        short_term_facts,
        file_index_facts,
        legacy_short_term_facts,
        essence_facts,
    ) = dedupe_memory_fact_groups(
        permanent_facts,
        long_term_facts,
        jane_long_term_facts,
        short_term_facts,
        file_index_facts,
        legacy_short_term_facts,
        essence_facts,
    )

    sections: list[str] = []
    if permanent_facts:
        sections.append(memory_section("## Permanent Memory", permanent_facts))
    if long_term_facts:
        label = "## Long-Term Memory (current user)" if use_user_memory else "## Long-Term Memory (shared)"
        sections.append(memory_section(label, long_term_facts))
    if jane_long_term_facts:
        sections.append(memory_section("## Long-Term Memory (Jane archived)", jane_long_term_facts))
    if short_term_facts:
        sections.append(memory_section("## Short-Term Memory  <- highest recency, treat as most current", short_term_facts))
    if file_index_facts:
        sections.append(memory_section("## File Index Memory  <- only for file/vault lookup questions", file_index_facts))
    if legacy_short_term_facts:
        sections.append(memory_section("## Short-Term Memory (legacy forgettable)", legacy_short_term_facts))
    if essence_facts:
        sections.append(memory_section("## Essence Memory", essence_facts))
    return sections
