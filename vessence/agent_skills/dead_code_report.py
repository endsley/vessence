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

    if auto_deleted:
        body.append(f"## Auto-deleted ({len(auto_deleted)} files)\n")
        for path in auto_deleted:
            body.append(_relative_path_item(root, path))
        body.append("")

    if dead_files:
        body.append(f"## Dead files — review needed ({len(dead_files)})\n")
        body.append("(Candidates for deletion, but failed an auto-delete safety check —")
        body.append(" usually means the file is too new, too large, or outside agent_skills/test_code.)\n")
        for path in dead_files:
            body.append(_relative_path_item(root, path))
        body.append("")

    if dead_functions:
        body.append(f"## Possibly-dead functions ({len(dead_functions)})\n")
        body.append("(No references found via grep. May be false positives if called via")
        body.append(" getattr, dynamic dispatch, or HTTP route registration.)\n")
        for path, name in dead_functions[:50]:
            body.append(_dead_function_item(root, path, name))
        if len(dead_functions) > 50:
            body.append(f"- … and {len(dead_functions) - 50} more")
        body.append("")

    if duplicate_groups:
        body.append(f"## Duplicate function bodies ({len(duplicate_groups)} groups)\n")
        body.append("(Identical bodies — candidates for extraction into a shared helper.)\n")
        body.extend(_duplicate_group_lines(root, duplicate_groups))
        body.append("")

    if not (auto_deleted or dead_files or dead_functions or duplicate_groups):
        body.append("Codebase clean — no dead code candidates found. ✅\n")

    return "\n".join(body) + "\n"
