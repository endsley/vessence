"""Pure helpers for essence_loader.py."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any


def ambient_base(environ: Mapping[str, str], home: str) -> str:
    return environ.get("AMBIENT_BASE", os.path.join(home, "ambient"))


def resolve_tools_dir(environ: Mapping[str, str], home: str) -> str:
    base = ambient_base(environ, home)
    return environ.get(
        "TOOLS_DIR",
        environ.get("ESSENCES_DIR", os.path.join(base, "skills")),
    )


def resolve_essences_dir(environ: Mapping[str, str], home: str) -> str:
    return os.path.join(ambient_base(environ, home), "essences")


def essence_search_dirs(tools_dir: str, essences_dir: str) -> list[str]:
    return [tools_dir, essences_dir]


def manifest_item_type(manifest: dict[str, Any]) -> str:
    return manifest.get("type", "tool")


def should_include_essence_type(item_type: str, type_filter: str) -> bool:
    return type_filter == "all" or item_type == type_filter


def available_essence_record(
    entry: str,
    manifest: dict[str, Any],
    path: str,
) -> dict[str, Any]:
    item_type = manifest_item_type(manifest)
    return {
        "name": manifest.get("essence_name", entry),
        "role_title": manifest.get("role_title", ""),
        "version": manifest.get("version", ""),
        "description": manifest.get("description", ""),
        "type": item_type,
        "has_brain": manifest.get("has_brain", False),
        "path": path,
    }


def available_essence_sort_rank(name: str) -> int:
    if name == "jane":
        return 0
    if name == "work log":
        return 2
    return 1


def available_essence_sort_key(essence: dict[str, Any]) -> tuple[int, str]:
    name = essence.get("name", "").lower()
    rank = available_essence_sort_rank(name)
    return (rank, "" if rank != 1 else name)
