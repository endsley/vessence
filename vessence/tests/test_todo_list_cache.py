from jane_web.jane_v2.classes.todo_list import handler
from jane_web.jane_v2.classes.todo_list.cache import TODO_CACHE_PATH, load_todo_cache


def test_todo_handler_uses_extracted_cache_helpers() -> None:
    assert handler._CACHE_PATH is TODO_CACHE_PATH
    assert handler._load_cache is load_todo_cache


def test_load_todo_cache_returns_none_for_missing_or_invalid_cache(tmp_path) -> None:
    assert load_todo_cache(tmp_path / "missing.json") is None

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")

    assert load_todo_cache(invalid) is None


def test_load_todo_cache_reads_json_payload(tmp_path) -> None:
    cache = tmp_path / "todo_cache.json"
    cache.write_text('{"categories": [{"name": "For our Home", "items": ["Buy milk"]}]}', encoding="utf-8")

    assert load_todo_cache(cache) == {
        "categories": [{"name": "For our Home", "items": ["Buy milk"]}],
    }
