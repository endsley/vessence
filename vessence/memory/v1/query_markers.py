"""Static and dynamic query marker loading for memory retrieval."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

from jane.config import DYNAMIC_QUERY_MARKERS_PATH

LOGGER = logging.getLogger("memory.v1.memory_retrieval")

STATIC_PERSONAL_MARKERS = (
    "my ", "do you know", "favorite", "office", "instrument", "sport", "restaurant",
    "wife", "daughter", "play", "piano", "name", "prefer",
)
STATIC_PROJECT_MARKERS = (
    "task", "project", "status", "transition", "migration", "bug", "fix", "implement",
    "patch", "code", "repo", "architecture", "website", "deploy", "service", "cron",
    "backup", "memory", "optimiz", "todo", "slow", "performance",
)


class QueryMarkerRegistry:
    def __init__(self, path: str | os.PathLike[str], *, logger: logging.Logger | None = None):
        self.path = Path(path)
        self.logger = logger or LOGGER
        self.lock = threading.Lock()
        self.mtime: float = 0.0
        self.dynamic_personal: tuple[str, ...] = ()
        self.dynamic_project: tuple[str, ...] = ()
        self.dynamic_file: tuple[str, ...] = ()

    def reload_if_changed(self) -> None:
        """Check mtime of the dynamic markers JSON; reload if it changed."""
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            return  # file doesn't exist yet - janitor hasn't run
        if mtime == self.mtime:
            return
        with self.lock:
            if mtime == self.mtime:
                return  # double-check after acquiring lock
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                self.dynamic_personal = tuple(data.get("personal_markers", []))
                self.dynamic_project = tuple(data.get("project_markers", []))
                self.dynamic_file = tuple(data.get("file_markers", []))
                self.mtime = mtime
                self.logger.info(
                    "Reloaded dynamic query markers: %d personal, %d project, %d file.",
                    len(self.dynamic_personal), len(self.dynamic_project), len(self.dynamic_file),
                )
            except Exception as e:
                self.logger.warning("Failed to reload dynamic query markers: %s", e)

    def personal_markers(self) -> tuple[str, ...]:
        self.reload_if_changed()
        return STATIC_PERSONAL_MARKERS + self.dynamic_personal

    def project_markers(self) -> tuple[str, ...]:
        self.reload_if_changed()
        return STATIC_PROJECT_MARKERS + self.dynamic_project

    def file_markers(self) -> tuple[str, ...]:
        self.reload_if_changed()
        return self.dynamic_file  # static file markers are in memory_retrieval._is_file_query.


_default_registry = QueryMarkerRegistry(DYNAMIC_QUERY_MARKERS_PATH)


def reload_dynamic_markers_if_changed() -> None:
    _default_registry.reload_if_changed()


def get_personal_markers() -> tuple[str, ...]:
    return _default_registry.personal_markers()


def get_project_markers() -> tuple[str, ...]:
    return _default_registry.project_markers()


def get_file_markers() -> tuple[str, ...]:
    return _default_registry.file_markers()
