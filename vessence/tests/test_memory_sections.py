from memory.v1.memory_sections import (
    build_memory_sections_from_facts,
    dedupe_memory_fact_groups,
    memory_section,
)


def test_memory_section_helpers_preserve_format_and_cross_group_dedupe():
    assert memory_section("## Label", ["one", "two"]) == "## Label\none\ntwo"
    assert dedupe_memory_fact_groups(
        ["(a): Same fact.", "(a): Same fact."],
        ["(b): Same fact.", "(b): New fact."],
    ) == (
        ["(a): Same fact."],
        ["(b): New fact."],
    )


def test_build_memory_sections_from_facts_preserves_order_and_labels():
    sections = build_memory_sections_from_facts(
        permanent_facts=["(permanent) Keep this."],
        long_term_facts=["(family) Long term."],
        jane_long_term_facts=["(archive) Jane memory."],
        short_term_facts=["(recent) Short term."],
        file_index_facts=["(file) File hit."],
        legacy_short_term_facts=["(legacy) Legacy short."],
        essence_facts=["(essence) Essence fact."],
        use_user_memory=True,
    )

    assert sections == [
        "## Permanent Memory\n(permanent) Keep this.",
        "## Long-Term Memory (current user)\n(family) Long term.",
        "## Long-Term Memory (Jane archived)\n(archive) Jane memory.",
        "## Short-Term Memory  <- highest recency, treat as most current\n(recent) Short term.",
        "## File Index Memory  <- only for file/vault lookup questions\n(file) File hit.",
        "## Short-Term Memory (legacy forgettable)\n(legacy) Legacy short.",
        "## Essence Memory\n(essence) Essence fact.",
    ]


def test_build_memory_sections_from_facts_uses_shared_label_for_shared_memory():
    sections = build_memory_sections_from_facts(
        permanent_facts=[],
        long_term_facts=["(project) Shared long term."],
        jane_long_term_facts=[],
        short_term_facts=[],
        file_index_facts=[],
        legacy_short_term_facts=[],
        essence_facts=[],
        use_user_memory=False,
    )

    assert sections == ["## Long-Term Memory (shared)\n(project) Shared long term."]


def test_build_memory_sections_from_facts_dedupes_across_priority_order():
    sections = build_memory_sections_from_facts(
        permanent_facts=["(permanent): Same fact.", "(permanent): Same fact."],
        long_term_facts=["(family): Same fact.", "(family): Different fact."],
        jane_long_term_facts=[],
        short_term_facts=["(recent): Different fact.", "(recent): New fact."],
        file_index_facts=[],
        legacy_short_term_facts=[],
        essence_facts=["(essence): New fact."],
        use_user_memory=True,
    )

    assert sections == [
        "## Permanent Memory\n(permanent): Same fact.",
        "## Long-Term Memory (current user)\n(family): Different fact.",
        "## Short-Term Memory  <- highest recency, treat as most current\n(recent): New fact.",
    ]


def test_build_memory_sections_from_facts_returns_empty_when_no_facts():
    assert build_memory_sections_from_facts(
        permanent_facts=[],
        long_term_facts=[],
        jane_long_term_facts=[],
        short_term_facts=[],
        file_index_facts=[],
        legacy_short_term_facts=[],
        essence_facts=[],
        use_user_memory=False,
    ) == []
