"""Build formatted memory context sections from retrieved fact lines."""
from __future__ import annotations

from memory.v1.memory_text import dedupe_fact_lines


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
    global_seen: set[str] = set()
    permanent_facts = dedupe_fact_lines(permanent_facts, global_seen)
    long_term_facts = dedupe_fact_lines(long_term_facts, global_seen)
    jane_long_term_facts = dedupe_fact_lines(jane_long_term_facts, global_seen)
    short_term_facts = dedupe_fact_lines(short_term_facts, global_seen)
    file_index_facts = dedupe_fact_lines(file_index_facts, global_seen)
    legacy_short_term_facts = dedupe_fact_lines(legacy_short_term_facts, global_seen)
    essence_facts = dedupe_fact_lines(essence_facts, global_seen)

    sections: list[str] = []
    if permanent_facts:
        sections.append("## Permanent Memory\n" + "\n".join(permanent_facts))
    if long_term_facts:
        label = "## Long-Term Memory (current user)" if use_user_memory else "## Long-Term Memory (shared)"
        sections.append(label + "\n" + "\n".join(long_term_facts))
    if jane_long_term_facts:
        sections.append("## Long-Term Memory (Jane archived)\n" + "\n".join(jane_long_term_facts))
    if short_term_facts:
        sections.append(
            "## Short-Term Memory  <- highest recency, treat as most current\n"
            + "\n".join(short_term_facts)
        )
    if file_index_facts:
        sections.append(
            "## File Index Memory  <- only for file/vault lookup questions\n"
            + "\n".join(file_index_facts)
        )
    if legacy_short_term_facts:
        sections.append(
            "## Short-Term Memory (legacy forgettable)\n"
            + "\n".join(legacy_short_term_facts)
        )
    if essence_facts:
        sections.append("## Essence Memory\n" + "\n".join(essence_facts))
    return sections
