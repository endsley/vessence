from memory.v1.janitor_consolidation import (
    consolidated_memory_metadata,
    consolidation_prompt,
    consolidation_topic_candidates,
    group_consolidation_topics,
)


USER = "user_memories"
LONG = "long_term_knowledge"


def row(row_id: str, doc: str, topic: str = "topic", **meta):
    return {"id": row_id, "doc": doc, "meta": {"topic": topic, **meta}}


def test_group_consolidation_topics_preserves_user_memory_skip_rules():
    grouped = group_consolidation_topics(
        [
            row("junk", "junk doc"),
            row("permanent", "permanent doc", memory_type="permanent"),
            row("short-term", "short-term doc", memory_type="short_term"),
            row("saved-file", "Saved file 'a.txt'", memory_type="long_term"),
            row("location", "Location: somewhere", memory_type="long_term"),
            row("file-path", "file path doc", memory_type="long_term", file_path="a.txt"),
            row("a", "first", memory_type="long_term"),
            row("b", "second", topic="other", memory_type="long_term"),
        ],
        collection_name=USER,
        user_collection_name=USER,
        classify_junk=lambda doc, _meta, _collection: "junk" if doc == "junk doc" else None,
    )

    assert grouped.permanent_count == 1
    assert {topic: [item["id"] for item in rows] for topic, rows in grouped.topic_groups.items()} == {
        "topic": ["a"],
        "other": ["b"],
    }


def test_consolidation_topic_candidates_require_three_rows():
    assert consolidation_topic_candidates(
        {
            "two": [row("a", "one"), row("b", "two")],
            "three": [row("c", "one"), row("d", "two"), row("e", "three")],
        }
    ) == ["three"]


def test_consolidation_prompt_includes_topic_and_fact_payload():
    prompt = consolidation_prompt(
        "topic",
        [
            row("a", "first", subtopic="alpha"),
            row("b", "second"),
        ],
    )

    assert "ONLY merge facts that are truly redundant" in prompt
    assert "FACTS FOR TOPIC 'topic'" in prompt
    assert '"id": "a"' in prompt
    assert '"subtopic": "alpha"' in prompt
    assert '"subtopic": "General"' in prompt


def test_consolidated_memory_metadata_preserves_collection_specific_shape():
    user_meta = consolidated_memory_metadata(
        collection_name=USER,
        user_collection_name=USER,
        topic="topic",
        old_rows=[row("a", "first", user_id="child")],
        new_subtopic="sub",
        now_iso="2026-07-02T12:00:00",
        default_user_id="default",
    )
    long_meta = consolidated_memory_metadata(
        collection_name=LONG,
        user_collection_name=USER,
        topic="topic",
        old_rows=[row("a", "first")],
        new_subtopic="sub",
        now_iso="2026-07-02T12:00:00",
        default_user_id="default",
    )

    assert user_meta == {
        "author": "janitor",
        "status": "compressed",
        "topic": "topic",
        "timestamp": "2026-07-02T12:00:00",
        "memory_type": "long_term",
        "user_id": "child",
        "subtopic": "sub",
    }
    assert long_meta == {
        "author": "janitor",
        "status": "compressed",
        "topic": "topic",
        "timestamp": "2026-07-02T12:00:00",
        "source": "janitor",
    }
