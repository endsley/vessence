from context_builder.v1 import context_builder
from context_builder.v1.context_sources import read_json_summary_file, read_text_file


def test_context_builder_uses_extracted_source_readers():
    assert context_builder._read_text_file is read_text_file
    assert context_builder._read_json_summary_file is read_json_summary_file


def test_read_text_file_handles_missing_nonfile_and_truncates(tmp_path):
    assert read_text_file(tmp_path / "missing.txt", 10) == ""
    assert read_text_file(tmp_path, 10) == ""

    path = tmp_path / "note.txt"
    path.write_text("  abcdef  ", encoding="utf-8")

    assert read_text_file(path, 3) == "a"


def test_read_json_summary_file_handles_bad_json_and_ascii_truncation(tmp_path):
    missing = tmp_path / "missing.json"
    bad = tmp_path / "bad.json"
    valid = tmp_path / "valid.json"
    bad.write_text("{", encoding="utf-8")
    valid.write_text('{"name":"Chieh","emoji":"✓"}', encoding="utf-8")

    assert read_json_summary_file(missing, 20) == ""
    assert read_json_summary_file(bad, 20) == ""
    assert read_json_summary_file(valid, 80) == '{"name": "Chieh", "emoji": "\\u2713"}'
    assert read_json_summary_file(valid, 10) == '{"name": "'


def test_context_runtime_loaders_preserve_task_and_personal_fact_policy(tmp_path, monkeypatch):
    context_builder._context_cache.clear()
    task_file = tmp_path / "configs" / "project_specs" / "current_task_state.json"
    task_file.parent.mkdir(parents=True)
    task_file.write_text('{"task":"Refactor"}', encoding="utf-8")

    task_profile = context_builder.PromptProfile("project", include_task_state=True)
    simple_profile = context_builder.PromptProfile("simple", include_task_state=False)

    assert context_builder._current_task_state_for_profile(simple_profile, tmp_path) == ""
    assert context_builder._current_task_state_for_profile(task_profile, tmp_path) == '{"task": "Refactor"}'

    calls = []
    monkeypatch.setattr(
        context_builder,
        "_load_personal_facts",
        lambda data_root: calls.append(data_root) or {"name": "Chieh"},
    )

    assert context_builder._personal_facts_for_context({"managed": True}, tmp_path) == {}
    assert calls == []
    assert context_builder._personal_facts_for_context({}, tmp_path) == {"name": "Chieh"}
    assert calls == [tmp_path]


def test_memory_summary_helpers_preserve_section_join_and_daemon_url_shape():
    assert context_builder._memory_sections_summary(["one", "two"]) == "one\n\ntwo"
    assert context_builder._memory_sections_summary([]) == "No relevant context found."

    assert context_builder._memory_daemon_query_url("hello world?", None) == (
        "http://127.0.0.1:8083/query?q=hello%20world%3F"
    )
    assert context_builder._memory_daemon_query_url("hello", "/tmp/essence db") == (
        "http://127.0.0.1:8083/query?q=hello&essence_path=/tmp/essence%20db"
    )
