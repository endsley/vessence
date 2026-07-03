"""Pure and file-backed helpers for essence management routes."""
from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from typing import Any


def read_active_essences(path: str) -> list[str]:
    try:
        with open(path) as handle:
            data = json.load(handle)
        return data.get("active", [])
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def write_active_essences(path: str, active: list[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        json.dump({"active": active}, handle, indent=2)


def read_essence_manifest_summary(manifest_path: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        with open(manifest_path) as handle:
            manifest = json.load(handle)
        return (manifest.get("capabilities", {}), manifest.get("preferred_model", {}))
    except (json.JSONDecodeError, OSError):
        return ({}, {})


def read_essence_detail_manifest(manifest_path: str, essence_name: str, loaded_names: Iterable[str]) -> dict[str, Any]:
    with open(manifest_path) as handle:
        manifest = json.load(handle)
    manifest["loaded"] = essence_name in set(loaded_names)
    return manifest


def essence_list_item(
    essence: Mapping[str, Any],
    *,
    capabilities: dict[str, Any],
    preferred_model: dict[str, Any],
    loaded_names: Iterable[str],
) -> dict[str, Any]:
    loaded = set(loaded_names)
    return {
        "name": essence["name"],
        "role_title": essence.get("role_title", ""),
        "description": essence.get("description", ""),
        "type": essence.get("type", "tool"),
        "has_brain": essence.get("has_brain", False),
        "loaded": essence["name"] in loaded,
        "capabilities": capabilities,
        "preferred_model": preferred_model,
    }


def find_essence_by_name(available: Iterable[Mapping[str, Any]], essence_name: str) -> Mapping[str, Any] | None:
    return next((essence for essence in available if essence["name"] == essence_name), None)


def find_essence_match(available: Iterable[Mapping[str, Any]], essence_name: str) -> Mapping[str, Any] | None:
    items = list(available)
    match = find_essence_by_name(items, essence_name)
    if match:
        return match
    return next((essence for essence in items if os.path.basename(essence["path"]) == essence_name), None)


def remove_active_essence(active: list[str], essence_name: str) -> tuple[list[str], bool]:
    if essence_name not in active:
        return (active, False)
    next_active = list(active)
    next_active.remove(essence_name)
    return (next_active, True)


def essence_search_dirs(ambient_base: str, tools_dir: str | None = None) -> list[str]:
    return [
        os.path.join(ambient_base, "skills") if tools_dir is None else tools_dir,
        os.path.join(ambient_base, "essences"),
    ]


def essence_folder_slug(essence_name: str) -> str:
    return essence_name.lower().replace(" ", "_")


def read_manifest(path: str) -> dict[str, Any] | None:
    try:
        with open(path) as handle:
            manifest = json.load(handle)
        return manifest if isinstance(manifest, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def find_essence_manifest_match(essence_name: str, search_dirs: Iterable[str]) -> dict[str, Any] | None:
    target = essence_name.lower()
    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for entry in os.listdir(search_dir):
            manifest_path = os.path.join(search_dir, entry, "manifest.json")
            if not os.path.isfile(manifest_path):
                continue
            manifest = read_manifest(manifest_path)
            if not manifest:
                continue
            if manifest.get("essence_name", "").lower() == target:
                return {
                    "search_dir": search_dir,
                    "folder_name": entry,
                    "manifest": manifest,
                    "manifest_path": manifest_path,
                    "essence_type": manifest.get("type", "tool"),
                    "tools_path": os.path.join(search_dir, entry, "functions", "custom_tools.py"),
                    "template_path": os.path.join(search_dir, entry, "ui", "template.html"),
                }
    return None


def find_essence_tools_path(essence_name: str, search_dirs: list[str]) -> str | None:
    if search_dirs:
        direct = os.path.join(search_dirs[0], essence_folder_slug(essence_name), "functions", "custom_tools.py")
        if os.path.isfile(direct):
            return direct
    match = find_essence_manifest_match(essence_name, search_dirs)
    if not match:
        return None
    tools_path = str(match["tools_path"])
    return tools_path if os.path.isfile(tools_path) else None


def find_essence_page_target(essence_name: str, search_dirs: Iterable[str]) -> dict[str, Any]:
    match = find_essence_manifest_match(essence_name, search_dirs)
    if not match:
        return {"essence_type": "tool", "folder_name": None, "template_path": None}
    template_path = str(match["template_path"])
    return {
        "essence_type": match["essence_type"],
        "folder_name": match["folder_name"],
        "template_path": template_path if os.path.isfile(template_path) else None,
    }


def essence_tool_command(python_bin: str, tools_path: str, tool_name: str, body: Mapping[str, Any]) -> list[str]:
    command = [python_bin, tools_path, tool_name]
    if body:
        command.append(json.dumps(body))
    return command


def essence_tool_success_payload(stdout: str) -> Any:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"status": "ok", "output": stdout.strip()}


def essence_tool_error_payload(stderr: str) -> dict[str, str]:
    return {"status": "error", "message": (stderr or "")[:300]}


def loaded_essence_payload(state: Any) -> dict[str, Any]:
    return {
        "status": "loaded",
        "role_title": state.role_title,
        "permissions": state.manifest.get("permissions", []),
    }
