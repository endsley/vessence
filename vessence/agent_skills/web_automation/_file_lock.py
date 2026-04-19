"""Tiny fcntl file-lock context manager.

Used by ``secrets.py`` and ``workflow.py`` to serialize read-modify-write
cycles on their shared ``index.json`` files. Without this, two concurrent
``save()`` calls can silently clobber each other's entries.

Linux-only (fcntl). On macOS fcntl is available too. Not a distributed
lock — serves one process + its threads.
"""

from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def exclusive(lock_path: Path) -> Iterator[int]:
    """Acquire an exclusive advisory lock on ``lock_path``.

    Creates the lockfile with 0600 perms. Blocks until the lock is
    available (no timeout — the protected sections are small).
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except Exception:
            pass
        os.close(fd)
