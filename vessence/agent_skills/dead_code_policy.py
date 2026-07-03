"""Pure safety policy helpers for dead_code_auditor.py."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable


AUTO_DELETE_ROOTS = ("agent_skills/", "test_code/")


def in_hard_skip(rel_path: str, hard_skip_prefixes: Iterable[str]) -> bool:
    return any(rel_path.startswith(prefix) for prefix in hard_skip_prefixes)


def is_pytest_discovery_file(rel_path: str) -> bool:
    path = Path(rel_path)
    return path.parts[:1] == ("test_code",) and path.name.startswith("test_")


def auto_delete_eligibility(
    *,
    rel_path: str,
    filename: str,
    size_bytes: int,
    line_count: int,
    age_days: float,
    hard_keep: set[str],
    max_auto_delete_lines: int,
    auto_delete_age_days: int,
    dynamically_imported: bool,
) -> tuple[bool, str]:
    if not rel_path.startswith(AUTO_DELETE_ROOTS):
        return False, "outside_auto_delete_roots"
    if rel_path.startswith("jane_web/"):
        return False, "web_route_side_effects"
    if filename in hard_keep:
        return False, "hard_keep"
    if dynamically_imported:
        return False, "dynamically_imported"
    if size_bytes > max_auto_delete_lines * 200:
        return False, "too_large_bytes"
    if line_count > max_auto_delete_lines:
        return False, "too_many_lines"
    if age_days < auto_delete_age_days:
        return False, "too_new"
    return True, "eligible"
