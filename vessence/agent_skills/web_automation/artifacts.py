"""Run-directory layout + trace writing + retention.

Per spec section 6. A run produces a directory under
``$VESSENCE_DATA_HOME/data/browser_runs/<run_id>/`` containing:

  run.json       — top-level run record (schema in ``new_run()``)
  trace.json     — chronological step trace (one entry per action)
  trace.zip      — Playwright trace (when record_trace=True)
  screenshot_*.png — on failure or explicit request

Phase 1 keeps the policy plumbing simple:
  - Every run writes ``run.json`` and ``trace.json``.
  - Screenshots are opt-in (action call) or on failure.
  - No size budget enforcement yet (Phase 1 has too few runs to matter).
    Spec 9.6 outcome-tiered TTLs are stubbed as constants so the sweeper
    in Phase 2+ can read them.
"""

from __future__ import annotations

import json
import logging
import os
import secrets as _secrets
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Retention windows from spec 9.6 — read by a future sweeper. NOT enforced
# in Phase 1 (single user, low run volume).
TTL_SECONDS_RUN_RECORD = 90 * 86_400
TTL_SECONDS_SCREENSHOT_SUCCESS = 14 * 86_400
TTL_SECONDS_SCREENSHOT_FAILURE = 90 * 86_400
TTL_SECONDS_TRACE_SUCCESS = 7 * 86_400
TTL_SECONDS_TRACE_FAILURE = 90 * 86_400


def _runs_dir() -> Path:
    base = Path(
        os.environ.get(
            "VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data")
        )
    )
    d = base / "data" / "browser_runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_run_id(*, label: str = "adhoc") -> str:
    """Stable run id: ``run_<epoch>_<label>_<rand>``. Unique per-second."""
    ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    rand = _secrets.token_hex(4)
    safe = "".join(c for c in label.lower() if c.isalnum() or c in "-_")[:20] or "adhoc"
    return f"run_{ts}_{safe}_{rand}"


@dataclass
class StepEntry:
    step_id: int
    action: str
    args: dict[str, Any]
    ok: bool
    message: str
    duration_ms: int
    url: str = ""
    title: str = ""


@dataclass
class RunRecord:
    run_id: str
    started_at: str
    mode: str = "adhoc"           # "adhoc" | "replay" (Phase 3+)
    workflow_id: str | None = None
    status: str = "running"       # "running" | "completed" | "failed" | "cancelled"
    ended_at: str | None = None
    steps: list[StepEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    pinned: bool = False


class RunDir:
    """One run on disk. Cheap — writes incrementally; callers can crash
    without leaving a half-written trace.
    """

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.dir = _runs_dir() / run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.record = RunRecord(
            run_id=run_id,
            started_at=_utc_now_iso(),
        )
        self._step_counter = 0
        self._flush_run()

    @property
    def trace_path(self) -> Path:
        return self.dir / "trace.json"

    @property
    def trace_zip_path(self) -> Path:
        return self.dir / "trace.zip"

    @property
    def run_path(self) -> Path:
        return self.dir / "run.json"

    def screenshot_path(self, tag: str) -> Path:
        safe = "".join(c for c in tag if c.isalnum() or c in "-_") or "shot"
        return self.dir / f"screenshot_{safe}.png"

    def append_step(
        self,
        *,
        action: str,
        args: dict[str, Any],
        ok: bool,
        message: str,
        duration_ms: int,
        url: str = "",
        title: str = "",
    ) -> None:
        self._step_counter += 1
        entry = StepEntry(
            step_id=self._step_counter,
            action=action,
            args=_redact(args),
            ok=ok,
            message=message[:1000],
            duration_ms=duration_ms,
            url=url,
            title=title,
        )
        self.record.steps.append(entry)
        self._flush_run()

    def note_error(self, message: str) -> None:
        self.record.errors.append(message[:500])
        self._flush_run()

    def finish(self, *, status: str) -> None:
        self.record.status = status
        self.record.ended_at = _utc_now_iso()
        self._flush_run()

    def _flush_run(self) -> None:
        try:
            with open(self.run_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self.record), f, indent=2, default=str)
            with open(self.trace_path, "w", encoding="utf-8") as f:
                json.dump([asdict(s) for s in self.record.steps], f, indent=2, default=str)
        except Exception as e:
            logger.warning("artifacts: failed to flush run %s: %s", self.run_id, e)


# ── Redaction ────────────────────────────────────────────────────────────────

_SECRET_FIELDS = {"password", "secret", "token", "api_key", "apikey", "auth"}


def _redact(args: dict[str, Any]) -> dict[str, Any]:
    """Redact obvious secret fields before writing them to disk.

    Operates on the kwargs dict passed to an action. This is the last-line
    defense; the primary path for real credentials in Phase 2+ is the
    secret-ref API in ``secrets.py`` which never materializes plaintext
    in the kwargs.
    """
    out: dict[str, Any] = {}
    for k, v in args.items():
        lk = (k or "").lower()
        if lk in _SECRET_FIELDS or "password" in lk:
            out[k] = "[REDACTED]"
        elif isinstance(v, str) and len(v) > 400:
            out[k] = v[:400] + f"...(+{len(v) - 400} chars)"
        else:
            out[k] = v
    return out


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


__all__ = [
    "RunDir",
    "RunRecord",
    "StepEntry",
    "new_run_id",
]
