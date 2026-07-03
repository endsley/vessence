"""Dynamic import detection helpers for the dead-code auditor."""

from __future__ import annotations

import re
from collections.abc import Iterable


DYNAMIC_IMPORT_PREFIX_PATTERNS = (
    re.compile(r"""import_module\(\s*f?['"]([a-zA-Z_][\w.]*?)\.\{"""),
    re.compile(r"""import_module\(\s*['"]([a-zA-Z_][\w.]*?)\.['"]\s*\+"""),
    re.compile(r"""__import__\(\s*f?['"]([a-zA-Z_][\w.]*?)\.\{"""),
)


def dynamic_import_prefixes_from_text(text: str) -> set[str]:
    prefixes: set[str] = set()
    for pattern in DYNAMIC_IMPORT_PREFIX_PATTERNS:
        for match in pattern.finditer(text):
            prefixes.add(match.group(1))
    return prefixes


def dotted_dir_for_python_relpath(rel_path: str) -> str:
    return rel_path.replace("/", ".").rsplit(".", 1)[0].rsplit(".", 1)[0]


def path_matches_dynamic_import_prefix(rel_path: str, prefixes: Iterable[str]) -> bool:
    dotted_dir = dotted_dir_for_python_relpath(rel_path)
    return any(dotted_dir == prefix or dotted_dir.startswith(prefix + ".") for prefix in prefixes)
