from memory.v1.janitor_report import (
    forgettable_purged_count,
    janitor_history_entry,
    janitor_report_payload,
    merge_count,
    topics_processed_payload,
    topics_with_merges,
)


def _common():
    return {
        "run_timestamp": "2026-07-02T12:00:00",
        "total_reduced": 3,
        "merge_log": [
            {"collection": "user_memories", "topic": "Project", "ids": ["a"]},
            {"collection": "long_term", "topic": "Decision", "ids": ["b"]},
            {"collection": "user_memories", "topic": "Project", "ids": ["c"]},
        ],
        "expired_purged": 2,
        "old_forgettable_purged": 4,
        "conversation_archival": {"status": "ok"},
        "known_junk_deleted": {"user": {"deleted": 1}},
        "exact_duplicate_deleted": {"user": {"deleted": 2}},
        "normalization_result": {"rewritten": 1},
    }


def test_janitor_report_derived_field_helpers_preserve_shapes():
    values = _common()

    assert forgettable_purged_count(2, 4) == 6
    assert merge_count(values["merge_log"]) == 3
    assert topics_processed_payload(
        user_collection_name="user_collection",
        user_topics={"alpha": [], "beta": []},
        long_term_collection_name="long_collection",
        long_term_topics={"decision": []},
    ) == {
        "user_collection": ["alpha", "beta"],
        "long_collection": ["decision"],
    }
    assert sorted(topics_with_merges(values["merge_log"])) == [
        "long_term::Decision",
        "user_memories::Project",
    ]


def test_janitor_report_payload_preserves_existing_report_shape():
    values = _common()
    report = janitor_report_payload(
        **values,
        permanent_count=7,
        user_topics={"alpha": [], "beta": []},
        long_term_topics={"decision": []},
        user_collection_name="user_collection",
        long_term_collection_name="long_collection",
        delete_quarantine_log="/tmp/quarantine.jsonl",
        log_files_purged=5,
        self_improve_reports_purged=6,
        image_cluster_result={"disabled": True},
    )

    assert report["last_run"] == "2026-07-02T12:00:00"
    assert report["vectors_reduced"] == 3
    assert report["merges_performed"] == 3
    assert report["forgettable_memories_purged"] == 6
    assert report["forgettable_expired_by_ttl"] == 2
    assert report["forgettable_expired_by_age"] == 4
    assert report["permanent_memories_protected"] == 7
    assert report["topics_processed"] == {
        "user_collection": ["alpha", "beta"],
        "long_collection": ["decision"],
    }
    assert report["delete_quarantine_log"] == "/tmp/quarantine.jsonl"
    assert report["image_clustering"] == {"disabled": True}
    assert report["merge_details"] is values["merge_log"]


def test_janitor_history_entry_preserves_append_only_shape():
    values = _common()
    history = janitor_history_entry(**values)

    assert history["timestamp"] == "2026-07-02T12:00:00"
    assert history["vectors_reduced"] == 3
    assert history["merges_performed"] == 3
    assert history["forgettable_purged"] == 6
    assert sorted(history["topics_with_merges"]) == [
        "long_term::Decision",
        "user_memories::Project",
    ]
    assert history["conversation_archival"] == {"status": "ok"}
    assert history["merges"] is values["merge_log"]
