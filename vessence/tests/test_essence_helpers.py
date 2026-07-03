import json

from jane_web.essence_helpers import (
    essence_list_item,
    essence_search_dirs,
    essence_tool_command,
    essence_tool_error_payload,
    essence_tool_success_payload,
    find_essence_by_name,
    find_essence_manifest_match,
    find_essence_match,
    find_essence_page_target,
    find_essence_tools_path,
    read_manifest,
    read_active_essences,
    read_essence_detail_manifest,
    read_essence_manifest_summary,
    loaded_essence_payload,
    remove_active_essence,
    write_active_essences,
)


def test_active_essences_read_write_and_missing_or_bad_files(tmp_path):
    path = tmp_path / "data" / "active_essence.json"

    assert read_active_essences(str(path)) == []
    write_active_essences(str(path), ["Tax"])
    assert json.loads(path.read_text()) == {"active": ["Tax"]}
    assert read_active_essences(str(path)) == ["Tax"]
    path.write_text("{bad json")
    assert read_active_essences(str(path)) == []


def test_read_essence_manifest_summary_returns_empty_on_missing_or_bad_manifest(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "capabilities": {"provides": ["tax"]},
                "preferred_model": {"provider": "openai"},
            }
        )
    )

    assert read_essence_manifest_summary(str(manifest)) == (
        {"provides": ["tax"]},
        {"provider": "openai"},
    )
    assert read_essence_manifest_summary(str(tmp_path / "missing.json")) == ({}, {})
    manifest.write_text("{bad")
    assert read_essence_manifest_summary(str(manifest)) == ({}, {})


def test_read_essence_detail_manifest_adds_loaded_flag(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"role_title": "Tax"}), encoding="utf-8")

    assert read_essence_detail_manifest(str(manifest), "Tax", ["Tax"]) == {
        "role_title": "Tax",
        "loaded": True,
    }
    assert read_essence_detail_manifest(str(manifest), "Tax", []) == {
        "role_title": "Tax",
        "loaded": False,
    }


def test_essence_list_item_shape_defaults_and_loaded_state():
    assert essence_list_item(
        {"name": "Tax", "path": "/essences/tax", "has_brain": True},
        capabilities={"provides": ["tax"]},
        preferred_model={},
        loaded_names=["Tax"],
    ) == {
        "name": "Tax",
        "role_title": "",
        "description": "",
        "type": "tool",
        "has_brain": True,
        "loaded": True,
        "capabilities": {"provides": ["tax"]},
        "preferred_model": {},
    }


def test_essence_lookup_preserves_exact_and_activation_fallback_rules():
    available = [
        {"name": "Tax Accountant", "path": "/essences/tax_accountant_2025"},
        {"name": "Work Log", "path": "/essences/work_log"},
    ]

    assert find_essence_by_name(available, "Tax Accountant") == available[0]
    assert find_essence_by_name(available, "tax_accountant_2025") is None
    assert find_essence_match(available, "Tax Accountant") == available[0]
    assert find_essence_match(available, "tax_accountant_2025") == available[0]
    assert find_essence_match(available, "missing") is None


def test_remove_active_essence_returns_new_list_only_when_changed():
    active = ["Tax", "Work"]

    assert remove_active_essence(active, "Tax") == (["Work"], True)
    assert active == ["Tax", "Work"]
    assert remove_active_essence(active, "Missing") == (active, False)


def test_essence_runtime_lookup_helpers_find_tools_and_page_targets(tmp_path):
    ambient = tmp_path / "ambient"
    skills = ambient / "skills"
    essences = ambient / "essences"
    direct = skills / "tax_helper" / "functions"
    direct.mkdir(parents=True)
    direct_tool = direct / "custom_tools.py"
    direct_tool.write_text("print('direct')", encoding="utf-8")

    themed = essences / "doctor_helper"
    (themed / "functions").mkdir(parents=True)
    (themed / "ui").mkdir()
    (themed / "manifest.json").write_text(
        json.dumps({"essence_name": "Doctor Helper", "type": "essence"}),
        encoding="utf-8",
    )
    tool_path = themed / "functions" / "custom_tools.py"
    template_path = themed / "ui" / "template.html"
    tool_path.write_text("print('doctor')", encoding="utf-8")
    template_path.write_text("<main></main>", encoding="utf-8")

    search_dirs = essence_search_dirs(str(ambient))

    assert search_dirs == [str(skills), str(essences)]
    assert find_essence_tools_path("Tax Helper", search_dirs) == str(direct_tool)
    assert find_essence_tools_path("Doctor Helper", search_dirs) == str(tool_path)
    match = find_essence_manifest_match("doctor helper", search_dirs)
    assert match["folder_name"] == "doctor_helper"
    assert match["essence_type"] == "essence"
    assert find_essence_page_target("Doctor Helper", search_dirs) == {
        "essence_type": "essence",
        "folder_name": "doctor_helper",
        "template_path": str(template_path),
    }


def test_essence_runtime_lookup_helpers_tolerate_bad_or_missing_manifests(tmp_path):
    search_dir = tmp_path / "skills"
    bad = search_dir / "bad"
    bad.mkdir(parents=True)
    manifest = bad / "manifest.json"
    manifest.write_text("{bad", encoding="utf-8")

    assert read_manifest(str(manifest)) is None
    assert find_essence_manifest_match("Bad", [str(search_dir)]) is None
    assert find_essence_tools_path("Missing", [str(search_dir)]) is None
    assert find_essence_page_target("Missing", [str(search_dir)]) == {
        "essence_type": "tool",
        "folder_name": None,
        "template_path": None,
    }


def test_essence_tool_command_preserves_body_argument_rules():
    assert essence_tool_command("python", "/tools/custom_tools.py", "run", {}) == [
        "python",
        "/tools/custom_tools.py",
        "run",
    ]
    assert essence_tool_command("python", "/tools/custom_tools.py", "run", {"a": 1}) == [
        "python",
        "/tools/custom_tools.py",
        "run",
        '{"a": 1}',
    ]


def test_essence_tool_payload_helpers_parse_json_or_fallback_output():
    assert essence_tool_success_payload('{"status": "ok", "value": 3}') == {
        "status": "ok",
        "value": 3,
    }
    assert essence_tool_success_payload("plain output\n") == {
        "status": "ok",
        "output": "plain output",
    }
    assert essence_tool_error_payload("x" * 350) == {
        "status": "error",
        "message": "x" * 300,
    }


def test_loaded_essence_payload_preserves_response_shape_and_permission_default():
    class State:
        role_title = "Helper"
        manifest = {"permissions": ["read"]}

    class StateWithoutPermissions:
        role_title = "Minimal"
        manifest = {}

    assert loaded_essence_payload(State()) == {
        "status": "loaded",
        "role_title": "Helper",
        "permissions": ["read"],
    }
    assert loaded_essence_payload(StateWithoutPermissions()) == {
        "status": "loaded",
        "role_title": "Minimal",
        "permissions": [],
    }
