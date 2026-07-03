"""Cache I/O helpers for the TODO-list Stage 2 handler."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path


logger = logging.getLogger(__name__)


_VESSENCE_DATA_HOME = Path(os.environ.get(
    "VESSENCE_DATA_HOME",
    str(Path.home() / "ambient" / "vessence-data"),
))
TODO_CACHE_PATH = Path(os.environ.get(
    "TODO_CACHE_PATH",
    str(_VESSENCE_DATA_HOME / "todo_list_cache.json"),
))


def load_todo_cache(path: str | Path = TODO_CACHE_PATH) -> dict | None:
    """Load the cached TODO list payload, returning None on miss or failure."""
    cache_path = Path(path)
    try:
        if not cache_path.exists():
            return None
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("todo_list: cache read failed: %s", exc)
        return None
