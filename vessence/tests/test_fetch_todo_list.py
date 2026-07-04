from datetime import datetime
import json

from agent_skills import fetch_todo_list


def test_fetched_at_timestamp_preserves_zulu_shape(monkeypatch):
    monkeypatch.setattr(
        fetch_todo_list,
        "_utcnow",
        lambda: datetime(2026, 7, 4, 1, 2, 3, 456789),
    )

    assert fetch_todo_list._fetched_at_timestamp() == "2026-07-04T01:02:03Z"


def test_write_cache_uses_fetched_at_helper(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_todo_list, "_fetched_at_timestamp", lambda: "2026-07-04T01:02:03Z")
    cache_path = tmp_path / "todo_cache.json"

    written = fetch_todo_list.write_cache(
        [{"name": "Immediate", "items": ["Deal with email."]}],
        "raw todo text",
        "doc123",
        path=cache_path,
    )

    assert written == cache_path
    assert json.loads(cache_path.read_text(encoding="utf-8")) == {
        "fetched_at": "2026-07-04T01:02:03Z",
        "doc_id": "doc123",
        "source_url": "https://docs.google.com/document/d/doc123/export?format=txt",
        "categories": [{"name": "Immediate", "items": ["Deal with email."]}],
        "raw_text": "raw todo text",
    }
