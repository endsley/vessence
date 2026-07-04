import os

from agent_skills import essence_loader
from agent_skills.essence_loader_helpers import (
    available_essence_record,
    available_essence_sort_rank,
    available_essence_sort_key,
    essence_search_dirs,
    manifest_item_type,
    resolve_essences_dir,
    resolve_tools_dir,
    should_include_essence_type,
)


def test_essence_loader_uses_extracted_helpers():
    assert essence_loader._available_essence_record is available_essence_record
    assert essence_loader._available_essence_sort_key is available_essence_sort_key
    assert essence_loader._resolve_tools_dir is resolve_tools_dir
    assert essence_loader._resolve_essences_dir is resolve_essences_dir


def test_resolve_tools_dir_preserves_environment_precedence():
    home = "/home/chieh"

    assert resolve_tools_dir({}, home) == os.path.join(home, "ambient", "skills")
    assert resolve_tools_dir({"AMBIENT_BASE": "/ambient"}, home) == "/ambient/skills"
    assert resolve_tools_dir({"ESSENCES_DIR": "/legacy"}, home) == "/legacy"
    assert resolve_tools_dir({"TOOLS_DIR": "/tools", "ESSENCES_DIR": "/legacy"}, home) == "/tools"


def test_resolve_essences_dir_and_search_dirs():
    assert resolve_essences_dir({}, "/home/chieh") == "/home/chieh/ambient/essences"
    assert resolve_essences_dir({"AMBIENT_BASE": "/ambient"}, "/home/chieh") == "/ambient/essences"
    assert essence_search_dirs("/tools", "/essences") == ["/tools", "/essences"]


def test_manifest_type_filter_and_available_record_defaults():
    manifest = {
        "essence_name": "Jane",
        "role_title": "assistant",
        "version": "1.0",
        "description": "core",
    }

    assert manifest_item_type(manifest) == "tool"
    assert should_include_essence_type("tool", "all")
    assert should_include_essence_type("tool", "tool")
    assert not should_include_essence_type("tool", "essence")
    assert available_essence_record("jane", manifest, "/path") == {
        "name": "Jane",
        "role_title": "assistant",
        "version": "1.0",
        "description": "core",
        "type": "tool",
        "has_brain": False,
        "path": "/path",
    }


def test_available_essence_sort_key_keeps_jane_first_work_log_last():
    assert available_essence_sort_rank("jane") == 0
    assert available_essence_sort_rank("alpha") == 1
    assert available_essence_sort_rank("work log") == 2

    essences = [
        {"name": "Zeta"},
        {"name": "Work Log"},
        {"name": "Jane"},
        {"name": "alpha"},
    ]

    assert sorted(essences, key=available_essence_sort_key) == [
        {"name": "Jane"},
        {"name": "alpha"},
        {"name": "Zeta"},
        {"name": "Work Log"},
    ]
