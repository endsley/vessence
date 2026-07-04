"""Markdown report helpers for dead_code_auditor.py."""
from __future__ import annotations

import datetime as dt
from pathlib import Path


def _relative_path_item(root: Path, path: Path, *, indent: str = "") -> str:
    return f"{indent}- `{path.relative_to(root)}`"


def _dead_function_item(root: Path, path: Path, name: str) -> str:
    return f"- `{path.relative_to(root)}` :: `{name}()`"


def _duplicate_group_lines(
    root: Path,
    duplicate_groups: list[tuple[str, list[Path]]],
    *,
    limit: int = 20,
) -> list[str]:
    lines: list[str] = []
    for hash_value, paths in duplicate_groups[:limit]:
        lines.append(f"- group `{hash_value}`:")
        for path in paths:
            lines.append(_relative_path_item(root, path, indent="    "))
    if len(duplicate_groups) > limit:
        lines.append(f"- … and {len(duplicate_groups) - limit} more groups")
    return lines


def _auto_deleted_section_lines(root: Path, auto_deleted: list[Path]) -> list[str]:
    if not auto_deleted:
        return []
    lines = [f"## Auto-deleted ({len(auto_deleted)} files)\n"]
    lines.extend(_relative_path_item(root, path) for path in auto_deleted)
    lines.append("")
    return lines


def _dead_files_section_lines(root: Path, dead_files: list[Path]) -> list[str]:
    if not dead_files:
        return []
    lines = [
        f"## Dead files — review needed ({len(dead_files)})\n",
        "(Candidates for deletion, but failed an auto-delete safety check —",
        " usually means the file is too new, too large, or outside agent_skills/test_code.)\n",
    ]
    lines.extend(_relative_path_item(root, path) for path in dead_files)
    lines.append("")
    return lines


def _dead_functions_section_lines(
    root: Path,
    dead_functions: list[tuple[Path, str]],
    *,
    limit: int = 50,
) -> list[str]:
    if not dead_functions:
        return []
    lines = [
        f"## Possibly-dead functions ({len(dead_functions)})\n",
        "(No references found via grep. May be false positives if called via",
        " getattr, dynamic dispatch, or HTTP route registration.)\n",
    ]
    for path, name in dead_functions[:limit]:
        lines.append(_dead_function_item(root, path, name))
    if len(dead_functions) > limit:
        lines.append(f"- … and {len(dead_functions) - limit} more")
    lines.append("")
    return lines


def _duplicate_functions_section_lines(
    root: Path,
    duplicate_groups: list[tuple[str, list[Path]]],
) -> list[str]:
    if not duplicate_groups:
        return []
    lines = [
        f"## Duplicate function bodies ({len(duplicate_groups)} groups)\n",
        "(Identical bodies — candidates for extraction into a shared helper.)\n",
    ]
    lines.extend(_duplicate_group_lines(root, duplicate_groups))
    lines.append("")
    return lines


def build_dead_code_report_markdown(
    *,
    root: Path,
    auto_deleted: list[Path],
    dead_files: list[Path],
    dead_functions: list[tuple[Path, str]],
    duplicate_groups: list[tuple[str, list[Path]]],
    generated_at: dt.datetime,
) -> str:
    ts = generated_at.strftime("%Y-%m-%d %H:%M")
    body = [f"# Dead Code Report — {ts}\n"]

    body.extend(_auto_deleted_section_lines(root, auto_deleted))
    body.extend(_dead_files_section_lines(root, dead_files))
    body.extend(_dead_functions_section_lines(root, dead_functions))
    body.extend(_duplicate_functions_section_lines(root, duplicate_groups))

    if not (auto_deleted or dead_files or dead_functions or duplicate_groups):
        body.append("Codebase clean — no dead code candidates found. ✅\n")

    return "\n".join(body) + "\n"
