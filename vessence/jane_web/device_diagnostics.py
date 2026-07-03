"""JSONL storage helpers for Android device diagnostics."""

from __future__ import annotations

import json
from pathlib import Path


class DeviceDiagnosticsLog:
    """Append and read Android diagnostic events from a JSONL file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, entry: dict) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    def read_recent(self, lines: int = 50) -> list[dict]:
        if not self.path.exists():
            return []
        all_lines = self.path.read_text().strip().split("\n")
        recent = all_lines[-lines:]
        recent.reverse()
        entries = []
        for line in recent:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return entries
