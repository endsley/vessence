from memory.v1 import janitor_memory


def test_quarantine_entries_for_rows_preserves_delete_record_shape() -> None:
    rows = [
        {"id": "a", "doc": "Fact A", "meta": {"topic": "one"}},
        {"id": "b", "doc": "Fact B", "meta": {}},
    ]

    assert janitor_memory._quarantine_entries_for_rows(
        "long_term",
        rows,
        "duplicate",
        deleted_at="2026-07-03T12:00:00",
    ) == [
        {
            "deleted_at": "2026-07-03T12:00:00",
            "collection": "long_term",
            "reason": "duplicate",
            "id": "a",
            "doc": "Fact A",
            "meta": {"topic": "one"},
        },
        {
            "deleted_at": "2026-07-03T12:00:00",
            "collection": "long_term",
            "reason": "duplicate",
            "id": "b",
            "doc": "Fact B",
            "meta": {},
        },
    ]


def test_delete_rows_with_quarantine_writes_backup_before_delete(monkeypatch) -> None:
    rows = [
        {"id": "a", "doc": "Fact A", "meta": {"topic": "one"}},
        {"id": "b", "doc": "Fact B", "meta": {}},
    ]
    quarantine_batches = []

    class FakeCollection:
        def __init__(self):
            self.deleted_ids = []

        def delete(self, *, ids):
            self.deleted_ids.append(ids)

    collection = FakeCollection()
    monkeypatch.setattr(janitor_memory, "_utcnow_iso", lambda: "2026-07-03T12:00:00")
    monkeypatch.setattr(
        janitor_memory,
        "_append_quarantine_entries",
        lambda entries: quarantine_batches.append(entries) or len(entries),
    )

    deleted = janitor_memory._delete_rows_with_quarantine(
        collection,
        "long_term",
        rows,
        "duplicate",
    )

    assert deleted == 2
    assert collection.deleted_ids == [["a", "b"]]
    assert quarantine_batches == [
        janitor_memory._quarantine_entries_for_rows(
            "long_term",
            rows,
            "duplicate",
            deleted_at="2026-07-03T12:00:00",
        )
    ]
