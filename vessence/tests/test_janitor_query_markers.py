import json
import logging

from memory.v1 import janitor_memory
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


def test_refresh_dynamic_query_markers_writes_payload_and_logs_counts(tmp_path, monkeypatch, caplog):
    collections = {
        janitor_memory.CHROMA_COLLECTION_USER_MEMORIES: [
            {"topic": "identity", "subtopic": "project: vessence"},
        ],
        janitor_memory.CHROMA_COLLECTION_LONG_TERM: [
            {"topic": "architecture", "subtopic": ""},
        ],
        janitor_memory.CHROMA_COLLECTION_SHORT_TERM: [
            {"topic": "recent refactor", "subtopic": ""},
        ],
        janitor_memory.CHROMA_COLLECTION_FILE_INDEX: [
            {"topic": "vault note", "subtopic": ""},
        ],
    }

    class FakeCollection:
        def __init__(self, metadatas):
            self._metadatas = metadatas

        def get(self, include):
            assert include == ["metadatas"]
            return {"metadatas": self._metadatas}

    class FakeClient:
        def get_collection(self, name):
            return FakeCollection(collections[name])

    output_path = tmp_path / "dynamic_query_markers.json"
    monkeypatch.setattr(janitor_memory, "get_chroma_client", lambda path: FakeClient())
    monkeypatch.setattr(janitor_memory, "DYNAMIC_QUERY_MARKERS_PATH", str(output_path))
    caplog.set_level(logging.INFO, logger="memory_janitor")

    payload = janitor_memory.refresh_dynamic_query_markers()

    assert json.loads(output_path.read_text(encoding="utf-8")) == payload
    assert payload["personal_markers"] == ["identity"]
    assert payload["project_markers"] == [
        "architecture",
        "project: vessence",
        "recent refactor",
    ]
    assert payload["file_markers"] == ["vault note"]
    assert "Dynamic query markers refreshed: 1 personal, 3 project, 1 file." in caplog.text
    assert "Could not write dynamic query markers" not in caplog.text
