#!/usr/bin/env python3
"""Code edit lock — prevents two agents from editing the same codebase simultaneously.

Usage:
    from agent_skills.code_lock import acquire_lock, release_lock

    lock = acquire_lock("jane-claude")  # blocks until lock is available
    try:
        # ... edit code ...
    finally:
        release_lock(lock)

Or as a context manager:
    with code_edit_lock("jane-claude"):
        # ... edit code ...

Lock file: $VESSENCE_DATA_HOME/locks/code_edit.lock
Contains: agent name, PID, timestamp
"""

import fcntl
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

VESSENCE_DATA_HOME = Path(os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data")))
LOCK_DIR = VESSENCE_DATA_HOME / "locks"
LOCK_FILE = LOCK_DIR / "code_edit.lock"
LOCK_TIMEOUT = 300  # 5 minutes max wait


def acquire_lock(agent_name: str, timeout: float = LOCK_TIMEOUT) -> int:
    """Acquire the code edit lock. Blocks until available or timeout.

    Returns the file descriptor (needed for release).
    Raises TimeoutError if lock not acquired within timeout.
    """
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR)

    start = time.time()
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Got the lock — write our info
            os.ftruncate(fd, 0)
            os.lseek(fd, 0, os.SEEK_SET)
            info = json.dumps({
                "agent": agent_name,
                "pid": os.getpid(),
                "acquired": time.strftime("%Y-%m-%dT%H:%M:%S"),
            })
            os.write(fd, info.encode())
            return fd
        except (IOError, OSError):
            # Lock held by another agent
            elapsed = time.time() - start
            if elapsed > timeout:
                os.close(fd)
                # Read who holds it
                try:
                    holder = LOCK_FILE.read_text().strip()
                except Exception:
                    holder = "unknown"
                raise TimeoutError(
                    f"Code edit lock held for {elapsed:.0f}s by {holder}. "
                    f"Agent '{agent_name}' timed out waiting."
                )
            time.sleep(1)


def release_lock(fd: int) -> None:
    """Release the code edit lock."""
    try:
        os.ftruncate(fd, 0)
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def who_holds_lock() -> dict | None:
    """Check who currently holds the lock (non-blocking)."""
    if not LOCK_FILE.exists():
        return None
    try:
        fd = os.open(str(LOCK_FILE), os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # We got it — nobody holds it
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
            return None
        except (IOError, OSError):
            os.close(fd)
            # Someone holds it — read who
            info = LOCK_FILE.read_text().strip()
            return json.loads(info) if info else {"agent": "unknown"}
    except Exception:
        return None


@contextmanager
def code_edit_lock(agent_name: str, timeout: float = LOCK_TIMEOUT):
    """Context manager for code edit locking."""
    fd = acquire_lock(agent_name, timeout)
    try:
        yield
    finally:
        release_lock(fd)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        holder = who_holds_lock()
        if holder:
            print(f"Lock held by: {json.dumps(holder)}")
        else:
            print("Lock is free")
    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        name = sys.argv[2] if len(sys.argv) > 2 else "test-agent"
        print(f"Acquiring lock as '{name}'...")
        with code_edit_lock(name):
            print(f"Lock acquired. Holding for 10s...")
            time.sleep(10)
        print("Lock released.")
    else:
        print("Usage: code_lock.py status|test [agent_name]")
