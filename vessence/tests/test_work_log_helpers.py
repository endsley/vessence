from agent_skills import work_log_tools
from agent_skills.work_log_helpers import (
    activity_entry,
    append_bounded,
    coerce_entry_list,
    recent_entries,
    resolve_activity_log_path,
)


def test_work_log_tools_exposes_helpers():
    assert work_log_tools._activity_entry is activity_entry
    assert work_log_tools._append_bounded is append_bounded
    assert work_log_tools._coerce_entry_list is coerce_entry_list
    assert work_log_tools._recent_entries is recent_entries
    assert work_log_tools._resolve_activity_log_path is resolve_activity_log_path


def test_resolve_activity_log_path_matches_env_precedence():
    assert resolve_activity_log_path({}, home="/home/chieh") == (
        "/home/chieh/ambient/skills/work_log/user_data/activity_log.json"
    )
    assert resolve_activity_log_path({"ESSENCES_DIR": "/essences"}, home="/home/chieh") == (
        "/essences/work_log/user_data/activity_log.json"
    )
    assert resolve_activity_log_path(
        {"TOOLS_DIR": "/tools", "ESSENCES_DIR": "/essences"},
        home="/home/chieh",
    ) == "/tools/work_log/user_data/activity_log.json"
    assert resolve_activity_log_path({"AMBIENT_BASE": "/ambient"}, home="/home/chieh") == (
        "/ambient/skills/work_log/user_data/activity_log.json"
    )


def test_activity_entry_preserves_written_shape():
    assert activity_entry(
        description="Wrote tests",
        category="engineering",
        timestamp="2026-07-02T12:00:00Z",
        timestamp_epoch=123.4,
    ) == {
        "timestamp": "2026-07-02T12:00:00Z",
        "timestamp_epoch": 123.4,
        "description": "Wrote tests",
        "category": "engineering",
    }


def test_entry_list_coercion_bounded_append_and_recent_order():
    entries = [{"id": idx} for idx in range(5)]
    assert coerce_entry_list(entries) is entries
    assert coerce_entry_list({"id": 1}) == []
    assert append_bounded(entries, {"id": 5}, max_entries=3) == [{"id": 3}, {"id": 4}, {"id": 5}]
    assert recent_entries(entries, 3) == [{"id": 4}, {"id": 3}, {"id": 2}]
