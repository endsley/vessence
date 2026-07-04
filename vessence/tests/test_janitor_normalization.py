from memory.v1.janitor_normalization import (
    NORMALIZED_STYLE_V2,
    empty_normalization_result,
    long_term_normalization_candidates,
    raw_doc_chars,
    rewrite_normalization_prompt,
    rewritten_normalized_metadata,
    split_plan_memories,
    split_normalization_prompt,
    split_normalized_metadatas,
)


def row(row_id: str, doc: str, topic: str | None = "Decision", **meta):
    metadata = {**meta}
    if topic is not None:
        metadata["topic"] = topic
    return {"id": row_id, "doc": doc, "meta": metadata}


def test_empty_normalization_result_preserves_report_counter_shape():
    assert empty_normalization_result() == {
        "reviewed": 0,
        "rewritten": 0,
        "split": 0,
        "deleted_originals": 0,
        "unchanged": 0,
    }
    first = empty_normalization_result()
    second = empty_normalization_result()
    first["reviewed"] = 1
    assert second["reviewed"] == 0


def test_long_term_normalization_candidates_preserve_existing_filters():
    long_doc = "x" * 20
    junk = row("junk", long_doc)

    candidates = long_term_normalization_candidates(
        [
            row("missing-topic", long_doc, topic=None),
            row("theme", long_doc, topic="Project: vessence"),
            junk,
            row("short", "x" * 10),
            row("already", long_doc, normalized_style=NORMALIZED_STYLE_V2),
            row("eligible", long_doc),
            row("limited-out", long_doc),
        ],
        theme_topics={"Project: vessence"},
        review_threshold=10,
        limit=1,
        classify_junk=lambda item: "junk" if item["id"] == "junk" else None,
    )

    assert [item["id"] for item in candidates] == ["eligible"]


def test_normalization_prompts_preserve_split_and_rewrite_contracts():
    source = row("source", "original long memory", topic="Decision")

    split_prompt = split_normalization_prompt(source, source["doc"])
    assert "Split this long-term memory into 2-6 atomic durable memories." in split_prompt
    assert 'Return ONLY valid JSON: {"memories": ["...", "..."]}' in split_prompt
    assert "Topic: Decision" in split_prompt
    assert "Memory:\noriginal long memory" in split_prompt

    rewrite_prompt = rewrite_normalization_prompt(source, source["doc"], max_chars=500)
    assert "Rewrite this long-term memory into one compact durable memory." in rewrite_prompt
    assert "- Keep under 500 characters" in rewrite_prompt
    assert "- Remove transcript chatter, filler, or temporary status" in rewrite_prompt
    assert "Topic: Decision" in rewrite_prompt


def test_split_plan_memories_preserves_llm_plan_cleanup_behavior():
    memories = split_plan_memories(
        {
            "memories": [
                " first memory ",
                "",
                "x" * 10,
                None,
                "last item is over limit",
            ]
        },
        max_chars=5,
        max_items=3,
    )

    assert memories == ["first", "xxxxx", "None"]


def test_split_normalized_metadatas_preserve_split_shape():
    source = row("source", "original long memory", subtopic="root")
    assert raw_doc_chars(row("source", " original long memory ", subtopic="root")) == len(
        "original long memory"
    )
    assert raw_doc_chars({"id": "missing"}) == 0

    metadatas = split_normalized_metadatas(
        source,
        ["first", "second memory"],
        now_iso="2026-07-02T12:00:00",
    )

    assert metadatas == [
        {
            "topic": "Decision",
            "subtopic": "root",
            "raw_chars": len("original long memory"),
            "summary_chars": len("first"),
            "normalized_style": NORMALIZED_STYLE_V2,
            "normalized_from": "source",
            "normalized_part": 1,
            "normalized_parts_total": 2,
            "timestamp": "2026-07-02T12:00:00",
        },
        {
            "topic": "Decision",
            "subtopic": "root",
            "raw_chars": len("original long memory"),
            "summary_chars": len("second memory"),
            "normalized_style": NORMALIZED_STYLE_V2,
            "normalized_from": "source",
            "normalized_part": 2,
            "normalized_parts_total": 2,
            "timestamp": "2026-07-02T12:00:00",
        },
    ]


def test_rewritten_normalized_metadata_preserves_rewrite_shape():
    metadata = rewritten_normalized_metadata(
        row("source", " original long memory ", subtopic="root"),
        "short memory",
        now_iso="2026-07-02T12:00:00",
    )

    assert metadata == {
        "topic": "Decision",
        "subtopic": "root",
        "raw_chars": len("original long memory"),
        "summary_chars": len("short memory"),
        "normalized_style": NORMALIZED_STYLE_V2,
        "timestamp": "2026-07-02T12:00:00",
    }
