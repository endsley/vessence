#!/usr/bin/env python3
"""Project-scoped code edit locks.

Prevents two agents from editing the same codebase simultaneously without
blocking unrelated projects such as Vessence, the education app, and Waterlily.

Usage:
    from agent_skills.code_lock import acquire_lock, release_lock

    lock = acquire_lock("jane-claude")  # uses the current project's lock
    try:
        # ... edit code ...
    finally:
        release_lock(lock)

Or as a context manager:
    with code_edit_lock("jane-claude", project="education"):
        # ... edit code ...

Lock files: $VESSENCE_DATA_HOME/locks/code_edit_<project>.lock
Contains: agent name, PID, timestamp, and project scope.
"""

from dataclasses import dataclass
import fcntl
import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

VESSENCE_DATA_HOME = Path(os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data")))
LOCK_DIR = VESSENCE_DATA_HOME / "locks"
LEGACY_LOCK_FILE = LOCK_DIR / "code_edit.lock"
# Backward-compatible public name for callers that imported LOCK_FILE directly.
LOCK_FILE = LEGACY_LOCK_FILE
LOCK_TIMEOUT = 300  # 5 minutes max wait
PROJECT_ENV_VARS = ("JANE_CODE_LOCK_PROJECT", "CODE_EDIT_LOCK_PROJECT")
_SLUG_RE = re.compile(r"[^a-zA-Z0-9_.-]+")


@dataclass(frozen=True)
class LockScope:
    """Resolved project lock scope."""

    name: str
    root: str | None
    lock_file: Path


def _expand(path: str | os.PathLike[str]) -> Path:
    return Path(path).expanduser().resolve()


def _slug(value: str) -> str:
    slug = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return slug or "default"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _known_project_roots() -> dict[str, Path]:
    """Known local project aliases.

    The aliases make CLI usage readable (`--project education`) while cwd-based
    inference still works when agents run from inside a project checkout.
    """
    home = Path.home()
    roots: dict[str, Path] = {
        "education": home / "code" / "chieh_class_v2",
        "chieh_class_v2": home / "code" / "chieh_class_v2",
        "waterlily": home / "code" / "waterlily",
    }
    vessence_home = os.environ.get("VESSENCE_HOME") or str(home / "ambient" / "vessence")
    roots["vessence"] = Path(vessence_home).expanduser()
    return {name: root.resolve() for name, root in roots.items()}


def _nearest_git_root(path: Path) -> Path | None:
    current = path if path.is_dir() else path.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _canonical_project_root(path: Path) -> Path:
    for alias_root in _known_project_roots().values():
        if _is_relative_to(path, alias_root):
            return alias_root
    return _nearest_git_root(path) or path


def _name_for_root(root: Path) -> str | None:
    for name, alias_root in _known_project_roots().items():
        if root == alias_root:
            return "education" if name == "chieh_class_v2" else name
    return None


def _looks_like_path(value: str) -> bool:
    return value.startswith(("/", "~", ".")) or os.sep in value


def resolve_lock_scope(project: str | os.PathLike[str] | None = None) -> LockScope:
    """Resolve a project argument or current working directory to a lock file."""
    raw_project = project
    if raw_project is None:
        for var in PROJECT_ENV_VARS:
            if os.environ.get(var):
                raw_project = os.environ[var]
                break

    aliases = _known_project_roots()
    root: Path | None
    if raw_project is not None:
        raw = os.fspath(raw_project).strip()
        alias = raw.lower()
        if alias in aliases:
            root = aliases[alias]
            name = "education" if alias == "chieh_class_v2" else alias
        elif _looks_like_path(raw):
            root = _canonical_project_root(_expand(raw))
            name = _name_for_root(root) or _slug(root.name)
        else:
            root = None
            name = _slug(raw)
    else:
        root = _canonical_project_root(Path.cwd().resolve())
        name = _name_for_root(root) or _slug(root.name)

    lock_file = LOCK_DIR / f"code_edit_{_slug(name)}.lock"
    return LockScope(name=_slug(name), root=str(root) if root else None, lock_file=lock_file)


def acquire_lock(
    agent_name: str,
    timeout: float = LOCK_TIMEOUT,
    project: str | os.PathLike[str] | None = None,
) -> int:
    """Acquire a project code edit lock. Blocks until available or timeout.

    Returns the file descriptor (needed for release).
    Raises TimeoutError if lock not acquired within timeout.
    """
    scope = resolve_lock_scope(project)
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(scope.lock_file), os.O_CREAT | os.O_RDWR)

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
                "project": scope.name,
                "root": scope.root,
                "lock_file": str(scope.lock_file),
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
                    holder = scope.lock_file.read_text().strip()
                except Exception:
                    holder = "unknown"
                raise TimeoutError(
                    f"Code edit lock for project '{scope.name}' held for "
                    f"{elapsed:.0f}s by {holder}. Agent '{agent_name}' timed out waiting."
                )
            time.sleep(1)


def release_lock(fd: int) -> None:
    """Release the code edit lock."""
    try:
        os.ftruncate(fd, 0)
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _read_holder(lock_file: Path) -> dict:
    info = lock_file.read_text().strip()
    return json.loads(info) if info else {"agent": "unknown"}


def _lock_holder(lock_file: Path) -> dict | None:
    if not lock_file.exists():
        return None
    try:
        fd = os.open(str(lock_file), os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # We got it — nobody holds it
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
            return None
        except (IOError, OSError):
            os.close(fd)
            # Someone holds it — read who
            return _read_holder(lock_file)
    except Exception:
        return None


def who_holds_lock(project: str | os.PathLike[str] | None = None) -> dict | None:
    """Check who currently holds the current/project lock (non-blocking)."""
    return _lock_holder(resolve_lock_scope(project).lock_file)


def _candidate_lock_files() -> Iterable[Path]:
    if LOCK_DIR.exists():
        yield from sorted(LOCK_DIR.glob("code_edit_*.lock"))
    # Include the old global lock in status output during the transition.
    if LEGACY_LOCK_FILE.exists():
        yield LEGACY_LOCK_FILE


def held_locks() -> list[dict]:
    """Return all currently held code edit locks."""
    holders: list[dict] = []
    seen: set[Path] = set()
    for lock_file in _candidate_lock_files():
        if lock_file in seen:
            continue
        seen.add(lock_file)
        holder = _lock_holder(lock_file)
        if holder:
            holder.setdefault("lock_file", str(lock_file))
            if lock_file == LEGACY_LOCK_FILE:
                holder.setdefault("project", "legacy-global")
            holders.append(holder)
    return holders


@contextmanager
def code_edit_lock(
    agent_name: str,
    timeout: float = LOCK_TIMEOUT,
    project: str | os.PathLike[str] | None = None,
):
    """Context manager for project-scoped code edit locking."""
    fd = acquire_lock(agent_name, timeout, project)
    try:
        yield
    finally:
        release_lock(fd)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        project_arg = None
        if "--project" in sys.argv:
            idx = sys.argv.index("--project")
            if idx + 1 < len(sys.argv):
                project_arg = sys.argv[idx + 1]
        elif len(sys.argv) > 2:
            project_arg = sys.argv[2]

        if project_arg:
            holder = who_holds_lock(project_arg)
            scope = resolve_lock_scope(project_arg)
            if holder:
                print(f"Lock held for {scope.name}: {json.dumps(holder)}")
            else:
                print(f"Lock is free for {scope.name}")
        else:
            holders = held_locks()
            if holders:
                for holder in holders:
                    print(f"Lock held for {holder.get('project', 'unknown')}: {json.dumps(holder)}")
            else:
                print("Lock is free")
    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        args = [arg for arg in sys.argv[2:] if arg != "--project"]
        project = None
        if "--project" in sys.argv:
            idx = sys.argv.index("--project")
            if idx + 1 < len(sys.argv):
                project = sys.argv[idx + 1]
        name = args[0] if args else "test-agent"
        scope = resolve_lock_scope(project)
        print(f"Acquiring lock for project '{scope.name}' as '{name}'...")
        with code_edit_lock(name, project=project):
            print("Lock acquired. Holding for 10s...")
            time.sleep(10)
        print("Lock released.")
    else:
        print("Usage: code_lock.py status [--project PROJECT] | test [agent_name] [--project PROJECT]")
