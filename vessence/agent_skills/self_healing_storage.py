"""Small durable JSON primitives for self-healing incident state.

Incident files can control unattended retries, so a process crash must never
turn a valid incident into a partially written JSON document that the watchdog
silently skips.  These helpers keep the JSON private, atomically replace it,
and serialize read/merge/write updates per path.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterator


class PrivateJsonLockUnavailable(RuntimeError):
    """A private JSON update could not acquire its per-file lease promptly.

    Callers that run in a request path or a durable repair worker must treat
    this as a transient control-plane failure, rather than waiting forever
    behind a wedged process.  The existing JSON file remains untouched.
    """


def _fsync_parent(path: Path) -> None:
    try:
        fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def atomic_write_private_json(path: Path, payload: Any) -> None:
    """Write JSON as mode 0600 with fsync + atomic replacement."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = -1
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
        _fsync_parent(path)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


@contextlib.contextmanager
def private_json_lock(path: Path) -> Iterator[None]:
    """Take a narrow, nonblocking lock shared by one JSON file.

    A held lock is not a reason to stall a failure capture or a repair worker.
    Raise :class:`PrivateJsonLockUnavailable` immediately so the caller can
    defer capture or retain its existing repair state for the watchdog.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    lock_path = path.with_suffix(path.suffix + ".lock")
    with lock_path.open("a+") as handle:
        try:
            lock_path.chmod(0o600)
        except OSError:
            pass
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PrivateJsonLockUnavailable("private JSON lock unavailable") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def update_private_json(path: Path, updates: dict[str, Any]) -> dict[str, Any]:
    """Atomically merge trusted structural updates into a JSON object."""
    path = Path(path)
    with private_json_lock(path):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("private JSON update requires an object")
        payload.update(updates)
        atomic_write_private_json(path, payload)
        return payload


def compare_and_update_private_json(
    path: Path,
    predicate: Callable[[dict[str, Any]], bool],
    updates: dict[str, Any] | Callable[[dict[str, Any]], dict[str, Any]],
) -> tuple[bool, dict[str, Any]]:
    """Atomically apply trusted updates only when the current state matches.

    The critical-repair watchdog can run concurrently from overlapping cron
    invocations.  A normal merge is not enough for a one-time side effect
    such as a graceful termination request: two readers could otherwise both
    observe the same stale child and signal it.  This narrow compare-and-set
    holds the existing per-file private lock across read, predicate, and
    replacement.  A failed predicate leaves the JSON untouched.
    """
    path = Path(path)
    with private_json_lock(path):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("private JSON update requires an object")
        if not predicate(dict(payload)):
            return False, payload
        resolved_updates = updates(dict(payload)) if callable(updates) else updates
        if not isinstance(resolved_updates, dict):
            raise ValueError("private JSON compare-and-update requires object updates")
        payload.update(resolved_updates)
        atomic_write_private_json(path, payload)
        return True, payload
