import os

from memory.v1.query_markers import QueryMarkerRegistry, STATIC_PERSONAL_MARKERS, STATIC_PROJECT_MARKERS


def test_missing_dynamic_marker_file_returns_static_markers(tmp_path):
    registry = QueryMarkerRegistry(tmp_path / "missing.json")

    assert registry.personal_markers() == STATIC_PERSONAL_MARKERS
    assert registry.project_markers() == STATIC_PROJECT_MARKERS
    assert registry.file_markers() == ()
    assert registry.mtime == 0.0


def test_dynamic_marker_reload_adds_personal_project_and_file_markers(tmp_path):
    path = tmp_path / "markers.json"
    path.write_text(
        '{"personal_markers": ["piano"], "project_markers": ["refactor"], "file_markers": ["vault note"]}',
        encoding="utf-8",
    )
    registry = QueryMarkerRegistry(path)

    assert registry.personal_markers() == STATIC_PERSONAL_MARKERS + ("piano",)
    assert registry.project_markers() == STATIC_PROJECT_MARKERS + ("refactor",)
    assert registry.file_markers() == ("vault note",)
    assert registry.mtime == path.stat().st_mtime


def test_unchanged_mtime_skips_reparsing_bad_file(tmp_path):
    path = tmp_path / "markers.json"
    path.write_text('{"file_markers": ["first"]}', encoding="utf-8")
    registry = QueryMarkerRegistry(path)
    assert registry.file_markers() == ("first",)
    loaded_mtime = registry.mtime

    path.write_text("{bad json", encoding="utf-8")
    os.utime(path, (loaded_mtime, loaded_mtime))

    assert registry.file_markers() == ("first",)


def test_failed_reload_keeps_previous_markers_and_mtime(tmp_path):
    path = tmp_path / "markers.json"
    path.write_text('{"file_markers": ["first"]}', encoding="utf-8")
    registry = QueryMarkerRegistry(path)
    assert registry.file_markers() == ("first",)
    loaded_mtime = registry.mtime

    path.write_text("{bad json", encoding="utf-8")
    os.utime(path, (loaded_mtime + 10, loaded_mtime + 10))

    assert registry.file_markers() == ("first",)
    assert registry.mtime == loaded_mtime


def test_json_values_use_existing_tuple_conversion_behavior(tmp_path):
    path = tmp_path / "markers.json"
    path.write_text('{"file_markers": "abc"}', encoding="utf-8")
    registry = QueryMarkerRegistry(path)

    assert registry.file_markers() == ("a", "b", "c")
