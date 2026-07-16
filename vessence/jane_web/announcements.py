"""JSONL announcement log reader for Jane web."""

from __future__ import annotations

import json
from datetime import datetime, timezone
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
                if not self._is_after_since(payload, since_dt):
                    continue
                rows.append(payload)
        return self._collapse_ra_report_history(rows)

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

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _created_at_value(payload: dict) -> str | None:
        return payload.get("created_at") or payload.get("timestamp")

    @classmethod
    def _is_after_since(cls, payload: dict, since_dt: datetime | None) -> bool:
        if not since_dt:
            return True
        created_at = cls._created_at_value(payload)
        if not created_at:
            return True
        created_dt = cls._parse_datetime(created_at)
        return not (created_dt and cls._as_utc(created_dt) <= cls._as_utc(since_dt))

    @classmethod
    def _collapse_ra_report_history(cls, rows: list[dict]) -> list[dict]:
        """Return at most the newest RA research report announcement.

        Older Android builds do not persist the `since` cursor across process
        restarts, so a cold start can ask for the full announcement log and
        replay every historical RA report as a separate notification. Queue
        progress announcements stay untouched, but RA report-ready history is
        a replaceable "latest report" signal.
        """
        latest_idx: int | None = None
        latest_key: tuple[int, float, int] | None = None
        for idx, payload in enumerate(rows):
            if not cls._is_ra_report_ready(payload):
                continue
            key = cls._ra_report_sort_key(payload, idx)
            if latest_key is None or key > latest_key:
                latest_key = key
                latest_idx = idx

        if latest_idx is None:
            return rows
        return [
            payload
            for idx, payload in enumerate(rows)
            if idx == latest_idx or not cls._is_ra_report_ready(payload)
        ]

    @classmethod
    def _is_ra_report_ready(cls, payload: dict) -> bool:
        return (
            payload.get("type") == "report_ready"
            and (
                payload.get("report_kind") == "ra_research"
                or str(payload.get("id", "")).startswith("ra_report")
            )
        )

    @classmethod
    def _ra_report_sort_key(cls, payload: dict, idx: int) -> tuple[int, float, int]:
        created_at = cls._created_at_value(payload)
        created_dt = cls._parse_datetime(created_at)
        if created_dt is None:
            return (0, 0.0, idx)
        return (1, cls._as_utc(created_dt).timestamp(), idx)
