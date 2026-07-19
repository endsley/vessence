"""JSONL announcement log reader for Jane web."""

from __future__ import annotations

import json
import fcntl
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_CRITICAL_SELF_HEALING_PROVIDER_FAILURE_ID_PREFIX = "self-healing-provider-failure-"


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
        """Trim under the same lock used by durable announcement appends.

        Repair-provider exhaustion notices are appended with an exclusive
        ``.lock`` file.  Rewriting JSONL without that lock could race a writer
        and erase a just-persisted alert.  Re-check size only after taking the
        shared lock, then atomically replace the complete retained file.
        """
        try:
            if self.path.stat().st_size <= self.max_bytes:
                return
            lock_path = self.path.with_suffix(self.path.suffix + ".lock")
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            with lock_path.open("a+") as lock_handle:
                try:
                    lock_path.chmod(0o600)
                except OSError:
                    pass
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
                try:
                    # An appender may have completed while this reader waited.
                    if not self.path.exists() or self.path.stat().st_size <= self.max_bytes:
                        return
                    lines = self.path.read_text(encoding="utf-8", errors="replace").splitlines()
                    recent_start = len(lines) - len(lines[-self.keep_lines:])
                    retained_lines = [
                        raw
                        for index, raw in enumerate(lines)
                        if index >= recent_start or self._is_critical_self_healing_provider_failure(raw)
                    ]
                    descriptor, temporary_name = tempfile.mkstemp(
                        prefix=f".{self.path.name}.",
                        suffix=".tmp",
                        dir=self.path.parent,
                    )
                    temporary = Path(temporary_name)
                    try:
                        os.fchmod(descriptor, 0o600)
                        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                            handle.write("\n".join(retained_lines) + "\n")
                            handle.flush()
                            os.fsync(handle.fileno())
                        os.replace(temporary, self.path)
                    finally:
                        temporary.unlink(missing_ok=True)
                finally:
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass

    @staticmethod
    def _is_critical_self_healing_provider_failure(raw: str) -> bool:
        """Keep provider-exhaustion alerts during JSONL size trimming.

        The regular tail remains bounded by ``keep_lines``.  These alerts are
        deliberately retained even when older because they are the durable
        signal that both repair providers were exhausted and Chieh must be
        notified.
        """
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return False
        return isinstance(payload, dict) and str(payload.get("id", "")).startswith(
            _CRITICAL_SELF_HEALING_PROVIDER_FAILURE_ID_PREFIX
        )

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
