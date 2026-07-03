"""Helper functions for Jane web vault file search."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any


def file_matches_type(filename: str, type_exts: set[str] | frozenset[str] | None) -> bool:
    if not type_exts:
        return True
    return os.path.splitext(filename)[1].lower() in type_exts


def normalize_index_path(path_value: str, vault_root: str) -> str | None:
    fpath = path_value or ""
    if not fpath:
        return None
    if os.path.isabs(fpath):
        try:
            fpath = os.path.relpath(fpath, vault_root)
        except ValueError:
            return None
    if fpath.startswith(".."):
        return None
    return fpath


def row_scope_allowed(meta: dict[str, Any], allowed_scope: str | None) -> bool:
    row_scope = (meta.get("user_id") or "").strip()
    return not (allowed_scope and row_scope and row_scope != allowed_scope)


def description_excerpt(doc: Any, limit: int = 200) -> str:
    return (doc or "")[:limit]


def file_search_result(
    *,
    name: str,
    path: str,
    description: str = "",
    detect_file_type: Callable[[str], str],
) -> dict[str, str]:
    return {
        "name": name,
        "path": path,
        "type": detect_file_type(name),
        "description": description,
        "serve_url": f"/api/files/serve/{path}",
    }


def filename_search_results(
    *,
    vault_root: str,
    query: str,
    type_exts: set[str] | frozenset[str] | None,
    detect_file_type: Callable[[str], str],
) -> dict[str, dict[str, str]]:
    results: dict[str, dict[str, str]] = {}
    for root, _dirs, files in os.walk(vault_root):
        for filename in files:
            if filename.startswith("."):
                continue
            if query not in filename.lower():
                continue
            if not file_matches_type(filename, type_exts):
                continue
            rel_path = os.path.relpath(os.path.join(root, filename), vault_root)
            results[rel_path] = file_search_result(
                name=filename,
                path=rel_path,
                detect_file_type=detect_file_type,
            )
    return results


def merge_index_search_results(
    results_map: dict[str, dict[str, str]],
    docs: list[Any],
    metas: list[dict[str, Any] | None],
    *,
    vault_root: str,
    type_exts: set[str] | frozenset[str] | None,
    allowed_scope: str | None,
    detect_file_type: Callable[[str], str],
    path_exists: Callable[[str], bool] = os.path.isfile,
) -> None:
    for doc, meta in zip(docs, metas):
        meta = meta or {}
        if not row_scope_allowed(meta, allowed_scope):
            continue
        indexed_path = normalize_index_path(meta.get("path", "") or meta.get("file", "") or "", vault_root)
        if not indexed_path:
            continue
        filename = os.path.basename(indexed_path)
        if not file_matches_type(filename, type_exts):
            continue
        if indexed_path not in results_map:
            full_path = os.path.join(vault_root, indexed_path)
            if not path_exists(full_path):
                continue
            results_map[indexed_path] = file_search_result(
                name=filename,
                path=indexed_path,
                description=description_excerpt(doc),
                detect_file_type=detect_file_type,
            )
        elif doc and not results_map[indexed_path]["description"]:
            results_map[indexed_path]["description"] = description_excerpt(doc)
