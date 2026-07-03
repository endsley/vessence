from memory.v1.janitor_theme_dedupe import (
    cross_session_theme_deletion_id,
    short_term_theme_entries,
)


def test_short_term_theme_entries_extracts_theme_rows():
    entries = short_term_theme_entries(
        {
            "ids": ["turn", "theme"],
            "documents": ["turn doc", "theme doc"],
            "metadatas": [
                {"memory_type": "short_term_turn"},
                {
                    "memory_type": "short_term_theme",
                    "session_id": "session-1",
                    "last_updated_at": "2026-07-02T12:00:00",
                },
            ],
        }
    )

    assert entries == [
        {
            "id": "theme",
            "document": "theme doc",
            "session_id": "session-1",
            "last_updated_at": "2026-07-02T12:00:00",
        }
    ]


def test_cross_session_theme_deletion_id_keeps_newer_theme():
    theme = {
        "id": "theme-a",
        "session_id": "session-a",
        "last_updated_at": "2026-07-02T12:00:00",
    }

    assert cross_session_theme_deletion_id(
        theme,
        neighbor_id="theme-b",
        neighbor_meta={"session_id": "session-b", "last_updated_at": "2026-07-02T11:00:00"},
        distance=0.05,
        similarity_threshold=0.10,
    ) == "theme-b"
    assert cross_session_theme_deletion_id(
        theme,
        neighbor_id="theme-b",
        neighbor_meta={"session_id": "session-b", "last_updated_at": "2026-07-02T13:00:00"},
        distance=0.05,
        similarity_threshold=0.10,
    ) == "theme-a"


def test_cross_session_theme_deletion_id_skips_same_self_session_and_far_neighbors():
    theme = {"id": "theme-a", "session_id": "session-a", "last_updated_at": ""}

    assert cross_session_theme_deletion_id(
        theme,
        neighbor_id="theme-a",
        neighbor_meta={"session_id": "session-b"},
        distance=0.01,
        similarity_threshold=0.10,
    ) is None
    assert cross_session_theme_deletion_id(
        theme,
        neighbor_id="theme-b",
        neighbor_meta={"session_id": "session-a"},
        distance=0.01,
        similarity_threshold=0.10,
    ) is None
    assert cross_session_theme_deletion_id(
        theme,
        neighbor_id="theme-b",
        neighbor_meta={"session_id": "session-b"},
        distance=0.11,
        similarity_threshold=0.10,
    ) is None
