from memory.v1.long_term_promotion import (
    archivist_memory_metadata,
    memory_merge_prompt,
    merge_candidates_from_query_result,
)


def test_merge_candidates_from_query_result_extracts_ids_docs_and_default_distance():
    assert merge_candidates_from_query_result(None) == []
    assert merge_candidates_from_query_result({"documents": [[]]}) == []

    candidates = merge_candidates_from_query_result(
        {
            "ids": [["id-1", "id-2"]],
            "documents": [["First memory", "Second memory"]],
            "distances": [[0.1234]],
        }
    )

    assert candidates == [
        {"id": "id-1", "doc": "First memory", "dist": 0.1234},
        {"id": "id-2", "doc": "Second memory", "dist": 1.0},
    ]


def test_memory_merge_prompt_preserves_memory_architect_contract():
    prompt = memory_merge_prompt(
        "Project: vessence",
        "New memory content",
        [
            {"id": "id-1", "doc": "Existing memory", "dist": 0.25},
            {"id": "id-2", "doc": "Older memory", "dist": 1.0},
        ],
    )

    assert prompt.startswith("You are a Memory Architect")
    assert "New Memory Category: Project: vessence" in prompt
    assert "New Memory Content: New memory content" in prompt
    assert "Match 1 (ID: id-1, Distance: 0.2500):\nExisting memory" in prompt
    assert "Match 2 (ID: id-2, Distance: 1.0000):\nOlder memory" in prompt
    assert '{ "decision": "MERGE" | "NEW"' in prompt


def test_archivist_memory_metadata_adds_user_fields_and_optional_status():
    assert archivist_memory_metadata(
        session_id="session-1",
        category="Decision",
        timestamp="2026-07-02T12:00:00",
        is_user_memory=False,
        user_name="chieh",
    ) == {
        "source": "conversation_archivist",
        "session_id": "session-1",
        "topic": "Decision",
        "timestamp": "2026-07-02T12:00:00",
    }

    assert archivist_memory_metadata(
        session_id="session-1",
        category="Identity Evolution",
        timestamp="2026-07-02T12:00:00",
        is_user_memory=True,
        user_name="chieh",
        status="updated_thematic",
    ) == {
        "source": "conversation_archivist",
        "session_id": "session-1",
        "topic": "Identity Evolution",
        "timestamp": "2026-07-02T12:00:00",
        "status": "updated_thematic",
        "user_id": "chieh",
        "memory_type": "long_term",
        "author": "archivist",
    }
