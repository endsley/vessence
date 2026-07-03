"""JSONL announcement log reader for Jane web."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class AnnouncementsLog:
    def __init__(self, path: Path, *, max_bytes: int = 1 * 1024 * 1024, keep_lines: int = 200):
        self.path = path
        self.max_bytes = max_bytes
        self.keep_lines = keep_lines

    def read(self, since: Optional[str]) -> list[dict]:
        if not self.path.exists():
            return []
        self._truncate_if_large()
        since_dt = self._parse_datetime(since)
        rows: list[dict] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                created_at = payload.get("created_at") or payload.get("timestamp")
                if since_dt and created_at:
                    created_dt = self._parse_datetime(created_at)
                    if created_dt and created_dt <= since_dt:
                        continue
                rows.append(payload)
        return rows

    def _truncate_if_large(self) -> None:
        try:
            if self.path.stat().st_size > self.max_bytes:
                lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
                self.path.write_text("\n".join(lines[-self.keep_lines:]) + "\n", encoding="utf-8")
        except Exception:
            pass

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        try:
            return datetime.fromisoformat(value) if value else None
        except ValueError:
            return None
