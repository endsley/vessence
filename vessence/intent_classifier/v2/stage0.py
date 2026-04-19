"""Stage 0: exact-match lookup before any LLM call.

Loads a JSON file mapping normalized phrases to class names.
classify(msg) returns the class string on a hit, or None to fall through.
"""

import json
from pathlib import Path


class Stage0ExactMatch:
    def __init__(self, lookup_path: str | Path):
        self._path = Path(lookup_path)
        self._table: dict[str, str] = {}
        self._load()

    def _load(self):
        with open(self._path) as f:
            raw = json.load(f)
        self._table = {self._normalize(k): v for k, v in raw.items()}

    def reload(self):
        """Reload lookup file from disk (call after edits)."""
        self._load()

    @staticmethod
    def _normalize(text: str) -> str:
        return text.strip().lower()

    def classify(self, msg: str) -> str | None:
        return self._table.get(self._normalize(msg))
