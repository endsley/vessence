"""Canonical markdown document helpers for web/API routes."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


CANONICAL_DOCS_WHITELIST: dict[str, dict[str, str]] = {
    "architecture": {"file": "Jane_architecture.md", "title": "Jane Architecture"},
    "memory": {"file": "memory_manage_architecture.md", "title": "Memory System"},
    "skills": {"file": "SKILLS_REGISTRY.md", "title": "Skills Registry"},
    "todos": {"file": "TODO_PROJECTS.md", "title": "TODO / Projects"},
    "accomplishments": {"file": "PROJECT_ACCOMPLISHMENTS.md", "title": "Accomplishments"},
    "cron": {"file": "CRON_JOBS.md", "title": "Cron Jobs"},
}


def configs_dir() -> Path:
    base = os.environ.get("VESSENCE_HOME", os.path.expanduser("~/ambient/vessence"))
    return Path(base) / "configs"


def _doc_path(meta: dict[str, str], config_dir: Path | None) -> Path:
    return (config_dir or configs_dir()) / meta["file"]


def read_doc_meta(
    slug: str,
    *,
    whitelist: dict[str, dict[str, str]] = CANONICAL_DOCS_WHITELIST,
    config_dir: Path | None = None,
    logger: Any = None,
) -> dict[str, Any] | None:
    """Summary-only: stat the file, do not read the body."""
    meta = whitelist.get(slug)
    if not meta:
        return None
    path = _doc_path(meta, config_dir)
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    except Exception as exc:
        if logger:
            logger.warning("docs: failed to stat %s: %s", path, exc)
        return None
    return {
        "slug": slug,
        "title": meta["title"],
        "file": meta["file"],
        "bytes": int(stat.st_size),
        "last_modified": int(stat.st_mtime),
    }


def read_doc_body(
    slug: str,
    *,
    whitelist: dict[str, dict[str, str]] = CANONICAL_DOCS_WHITELIST,
    config_dir: Path | None = None,
    logger: Any = None,
) -> dict[str, Any] | None:
    meta = whitelist.get(slug)
    if not meta:
        return None
    path = _doc_path(meta, config_dir)
    try:
        stat = path.stat()
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except Exception as exc:
        if logger:
            logger.warning("docs: failed to read %s: %s", path, exc)
        return None
    return {
        "slug": slug,
        "title": meta["title"],
        "file": meta["file"],
        "content": content,
        "bytes": int(stat.st_size),
        "last_modified": int(stat.st_mtime),
    }
