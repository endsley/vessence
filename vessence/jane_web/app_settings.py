"""JSON-backed Android app settings storage."""

from __future__ import annotations

import json
from pathlib import Path


class JsonSettingsStore:
    """Tiny JSON object store used by the Android app settings routes."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict:
        try:
            with self.path.open() as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save(self, settings: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w") as f:
            json.dump(settings, f, indent=2)
