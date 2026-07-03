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
