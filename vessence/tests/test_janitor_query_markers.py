from memory.v1.janitor_query_markers import dynamic_query_marker_payload, marker_labels_from_metadatas


def test_marker_labels_from_metadatas_normalizes_topics_and_subtopics():
    labels = marker_labels_from_metadatas([
        {"topic": " Identity ", "subtopic": " Office_Setup "},
        {"topic": "general", "subtopic": "unknown"},
        {"topic": "", "subtopic": None},
        None,
    ])

    assert labels == {"identity", "office_setup"}


def test_dynamic_query_marker_payload_splits_personal_project_and_file_markers():
    payload = dynamic_query_marker_payload(
        user_labels={"identity", "project: vessence", "music"},
        long_term_labels={"architectural milestones"},
        short_term_labels={"recent refactor"},
        file_labels={"vault note", "project: vessence"},
        updated_at="2026-07-02T12:00:00",
    )

    assert payload == {
        "personal_markers": ["identity", "music"],
        "project_markers": [
            "architectural milestones",
            "project: vessence",
            "recent refactor",
        ],
        "file_markers": ["project: vessence", "vault note"],
        "updated_at": "2026-07-02T12:00:00",
    }
