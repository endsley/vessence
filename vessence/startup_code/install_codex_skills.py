#!/usr/bin/env python3
"""Install repo-backed Codex skills into the local Codex runtime directory.

Vessence keeps durable Codex skills in ``$VESSENCE_HOME/codex_skills``. Codex
loads runnable skills from ``$CODEX_HOME/skills`` (usually ``~/.codex/skills``).
This installer copies each repo-backed skill into that runtime directory.

The repo copy is canonical. If a destination skill has the same name, it is
replaced when its contents differ.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


VESSENCE_HOME = Path(
    os.environ.get("VESSENCE_HOME", Path(__file__).resolve().parents[1])
).resolve()
CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).resolve()
SOURCE_SKILLS_DIR = VESSENCE_HOME / "codex_skills"
TARGET_SKILLS_DIR = CODEX_HOME / "skills"

IGNORED_DIRS = {"__pycache__"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def _is_ignored(path: Path) -> bool:
    return any(part in IGNORED_DIRS for part in path.parts) or path.suffix in IGNORED_SUFFIXES


def discover_skills() -> list[Path]:
    if not SOURCE_SKILLS_DIR.exists():
        return []
    return sorted(
        path
        for path in SOURCE_SKILLS_DIR.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    )


def iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if _is_ignored(rel):
            continue
        if path.is_file():
            files.append(rel)
    return sorted(files)


def trees_equal(source: Path, target: Path) -> bool:
    if not target.exists() or not target.is_dir() or target.is_symlink():
        return False

    source_files = iter_files(source)
    target_files = iter_files(target)
    if source_files != target_files:
        return False

    for rel in source_files:
        if (source / rel).read_bytes() != (target / rel).read_bytes():
            return False
    return True


def copy_skill(source: Path, target: Path, dry_run: bool) -> bool:
    if trees_equal(source, target):
        return False
    if dry_run:
        return True

    if target.exists() or target.is_symlink():
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    return True


def install(dry_run: bool = False) -> tuple[list[Path], list[Path]]:
    changed: list[Path] = []
    unchanged: list[Path] = []

    for source in discover_skills():
        target = TARGET_SKILLS_DIR / source.name
        if copy_skill(source, target, dry_run=dry_run):
            changed.append(target)
        else:
            unchanged.append(target)
    return changed, unchanged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Show skills that would be copied")
    args = parser.parse_args()

    skills = discover_skills()
    if not skills:
        print(f"No repo-backed Codex skills found in {SOURCE_SKILLS_DIR}.")
        return 0

    changed, unchanged = install(dry_run=args.dry_run)
    action = "Would install/update" if args.dry_run else "Installed/updated"
    if changed:
        print(f"{action} Codex skills:")
        for path in changed:
            print(f"  - {path}")
    else:
        print("Codex skills already up to date.")

    if unchanged and args.dry_run:
        print("Already up to date:")
        for path in unchanged:
            print(f"  - {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
