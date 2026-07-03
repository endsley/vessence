from memory.v1.local_vector_memory_helpers import (
    RECENT_FORGETTABLE_HEADING,
    bucket_memory_facts,
    format_memory_fact,
    is_forgettable_expired,
    librarian_system_instruction,
    librarian_user_prompt,
    memory_tier_sections,
)


def test_forgettable_expiry_uses_iso_string_boundary():
    assert is_forgettable_expired({"expires_at": "2026-07-01T00:00:00"}, "2026-07-02T00:00:00")
    assert not is_forgettable_expired({"expires_at": "2026-07-03T00:00:00"}, "2026-07-02T00:00:00")
    assert not is_forgettable_expired({}, "2026-07-02T00:00:00")


def test_format_memory_fact_preserves_timestamp_topic_and_expiry_shape():
    assert format_memory_fact(
        "Remember this",
        {
            "timestamp": "2026-07-02T12:34:56.789",
            "topic": "project",
            "expires_at": "2026-07-09T00:00:00",
        },
    ) == "[2026-07-02T12:34:56] (project, expires 2026-07-09): Remember this"

    assert format_memory_fact("Fallback", {"created_at": "2026-01-01T00:00:00"}) == (
        "[2026-01-01T00:00:00] (General): Fallback"
    )


def test_bucket_memory_facts_filters_expired_forgettable_and_keeps_tiers():
    docs = ["permanent", "long", "recent", "expired"]
    metas = [
        {"memory_type": "permanent", "topic": "a"},
        {"memory_type": "long_term", "topic": "b"},
        {"memory_type": "forgettable", "topic": "c", "expires_at": "2026-07-03"},
        {"memory_type": "forgettable", "topic": "d", "expires_at": "2026-07-01"},
    ]

    permanent, long_term, forgettable = bucket_memory_facts(
        docs,
        metas,
        now_iso="2026-07-02",
    )

    assert [line.split(": ")[1] for line in permanent] == ["permanent"]
    assert [line.split(": ")[1] for line in long_term] == ["long"]
    assert [line.split(": ")[1] for line in forgettable] == ["recent"]


def test_memory_tier_sections_and_librarian_prompts_preserve_headings():
    sections = memory_tier_sections(["p1"], ["l1"], ["f1"])

    assert sections == [
        "## Permanent Memory\np1",
        "## Long-Term Memory\nl1",
        f"{RECENT_FORGETTABLE_HEADING}\nf1",
    ]
    assert "Memory Librarian for Chieh's assistant" in librarian_system_instruction("Chieh")
    assert librarian_user_prompt("query", "facts") == "User Query: query\n\nMemory Tiers:\nfacts"
