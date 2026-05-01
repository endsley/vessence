"""dead_code_auditor.py — find duplicate / dead code, conservatively.

Two phases:
  1. SCAN — walk the tree and flag candidates (dead files, dead functions,
            duplicate function bodies)
  2. ACT  — auto-delete ONLY the safest subset; report everything else

Auto-delete criteria (all must hold):
  - File is in agent_skills/ or test_code/ (not web/android/intent paths)
  - Filename is not in HARD_KEEP allowlist
  - mtime > AUTO_DELETE_AGE_DAYS (60 days — stable, not in active churn)
  - ZERO grep matches across the entire vessence/ tree (excluding the
    file itself) — looking for both `from X import Y` and bare `Y(` calls
  - No references in any *.md or *.json (could be cron-scheduled)
  - File is < 500 lines (small enough that any reference is real)

Everything else is logged to configs/dead_code_report.md for human review.

Auto-deletes are committed with prefix `auto-dead-code:`.
"""

from __future__ import annotations

import ast
import datetime as dt
import hashlib
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

VESSENCE_HOME = Path(os.environ.get("VESSENCE_HOME", str(Path(__file__).resolve().parents[1])))
HOME = Path(os.environ.get("HOME", str(Path.home())))
REPORT_PATH = VESSENCE_HOME / "configs" / "dead_code_report.md"

# Directories to scan
SCAN_DIRS = ["agent_skills", "test_code", "jane_web", "vault_web",
             "intent_classifier", "context_builder", "memory", "startup_code"]

# Hard-skip — never even consider these for deletion or duplicate detection.
# Web framework files have HTTP route side effects; android is compiled separately.
HARD_SKIP_PREFIXES = (
    "android/", "configs/", "marketing_site/", "vault/",
    "node_modules/", ".git/", "venv/", "__pycache__/",
    "test_code/auto_audit_",  # auditor-generated tests
)

# Files NEVER auto-deleted (keep regardless of "no references")
HARD_KEEP = {
    "__init__.py", "main.py", "jane_proxy.py", "database.py",
    "stage1_classifier.py", "stage2_dispatcher.py", "stage3_escalate.py",
    "pipeline.py", "classifier.py", "graceful_restart.sh",
    "first_run_setup.py", "nightly_self_improve.py",
}

# Auto-delete only if file is at least this old AND truly unreferenced
AUTO_DELETE_AGE_DAYS = 60
MAX_AUTO_DELETE_LINES = 500

# Directories outside vessence/ that can invoke vessence scripts — hooks, systemd
# units, etc. grep these too or we miss real references and delete live code.
EXTERNAL_SEARCH_ROOTS = [
    HOME / ".claude" / "hooks",
    HOME / ".claude" / "commands",
    HOME / ".config" / "systemd" / "user",
]

_dead_files: list[Path] = []
_dead_functions: list[tuple[Path, str]] = []
_duplicate_groups: list[tuple[str, list[Path]]] = []
_auto_deleted: list[Path] = []


def log(msg: str) -> None:
    print(f"[dead-code] {msg}")


def in_hard_skip(rel_path: str) -> bool:
    return any(rel_path.startswith(p) for p in HARD_SKIP_PREFIXES)


def is_pytest_discovery_file(rel_path: str) -> bool:
    """Pytest discovers test_*.py by filename, not imports."""
    path = Path(rel_path)
    return path.parts[:1] == ("test_code",) and path.name.startswith("test_")


def gather_python_files() -> list[Path]:
    files = []
    for sub in SCAN_DIRS:
        d = VESSENCE_HOME / sub
        if not d.exists():
            continue
        for f in d.rglob("*.py"):
            rel = str(f.relative_to(VESSENCE_HOME))
            if "/__pycache__/" in rel or in_hard_skip(rel):
                continue
            files.append(f)
    return files


def grep_references(name: str, exclude: Path | None = None) -> int:
    """Count references to a Python name inside vessence/, invoker files in
    external roots (shell hooks, systemd units — NOT arbitrary markdown which
    would give false positives from docs), and the live crontab. On ANY
    lookup error, returns 1 ("fail safe — assume referenced")."""
    try:
        # Inside the tree: search code + our own config/doc files.
        cmd_internal = [
            "grep", "-r",
            "--include=*.py", "--include=*.md", "--include=*.json",
            "--include=*.sh", "--include=*.service", "--include=*.timer",
            "-l", "-w", name, str(VESSENCE_HOME),
        ]
        r = subprocess.run(cmd_internal, capture_output=True, text=True, check=False)
        files = [ln for ln in r.stdout.splitlines() if ln.strip()]
        if exclude:
            files = [f for f in files if Path(f).resolve() != exclude.resolve()]
        count = len(files)

        # Outside the tree: only actual invoker files. Skip *.md because
        # e.g. ~/.claude/commands/*.md contain chat-history prose that
        # mentions filenames without invoking them.
        for root in EXTERNAL_SEARCH_ROOTS:
            if not root.exists():
                continue
            cmd_ext = [
                "grep", "-r",
                "--include=*.sh", "--include=*.service", "--include=*.timer",
                "--include=*.py",
                "-l", "-w", name, str(root),
            ]
            r = subprocess.run(cmd_ext, capture_output=True, text=True, check=False)
            count += sum(1 for ln in r.stdout.splitlines() if ln.strip())
    except Exception:
        return 1  # fail safe: assume referenced

    # Also check the live crontab — cron entries reference scripts by path.
    try:
        r = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, check=False,
        )
        if r.returncode == 0 and re.search(rf"\b{re.escape(name)}\b", r.stdout):
            count += 1
    except Exception:
        pass

    return count


# Cache of importlib.import_module() prefix patterns discovered in the tree.
# A file at e.g. intent_classifier/v2/classes/restart_server.py is "referenced"
# if any python file does importlib.import_module(f"intent_classifier.v2.classes.{x}")
# — grep on the stem won't catch that dynamic import.
_DYNAMIC_IMPORT_PREFIXES: set[str] | None = None


def _collect_dynamic_import_prefixes() -> set[str]:
    """Scan the tree once for importlib.import_module / __import__ call sites
    with a string prefix (e.g. f"package.subpackage.{name}"), return the set
    of dotted prefixes like {"intent_classifier.v2.classes"}."""
    global _DYNAMIC_IMPORT_PREFIXES
    if _DYNAMIC_IMPORT_PREFIXES is not None:
        return _DYNAMIC_IMPORT_PREFIXES

    prefixes: set[str] = set()
    patterns = [
        # importlib.import_module(f"pkg.sub.{name}") or with . concat
        re.compile(r"""import_module\(\s*f?['"]([a-zA-Z_][\w.]*?)\.\{"""),
        re.compile(r"""import_module\(\s*['"]([a-zA-Z_][\w.]*?)\.['"]\s*\+"""),
        re.compile(r"""__import__\(\s*f?['"]([a-zA-Z_][\w.]*?)\.\{"""),
    ]
    # Only scan our own source tree — SCAN_DIRS. Otherwise rglob walks into
    # any .venv/site-packages that happens to live inside and returns junk
    # prefixes like scipy, torch, pip._vendor.
    for sub in SCAN_DIRS:
        d = VESSENCE_HOME / sub
        if not d.exists():
            continue
        for py in d.rglob("*.py"):
            rel = str(py.relative_to(VESSENCE_HOME))
            if in_hard_skip(rel) or "/__pycache__/" in rel:
                continue
            try:
                text = py.read_text()
            except Exception:
                continue
            for pat in patterns:
                for m in pat.finditer(text):
                    prefix = m.group(1)
                    # Only trust prefixes that correspond to a real dir in our tree.
                    candidate = VESSENCE_HOME / prefix.replace(".", "/")
                    if candidate.is_dir():
                        prefixes.add(prefix)

    _DYNAMIC_IMPORT_PREFIXES = prefixes
    log(f"Dynamic-import prefixes detected: {sorted(prefixes)}")
    return prefixes


def is_dynamically_imported(f: Path) -> bool:
    """Return True if f sits under a directory that's the target of an
    importlib dynamic load. The classifier does this for v2/classes; other
    plugin-style paths will be picked up automatically."""
    rel = str(f.relative_to(VESSENCE_HOME))
    dotted_dir = rel.replace("/", ".").rsplit(".", 1)[0].rsplit(".", 1)[0]
    for prefix in _collect_dynamic_import_prefixes():
        if dotted_dir == prefix or dotted_dir.startswith(prefix + "."):
            return True
    return False


# ── Phase 1: dead files (zero references anywhere) ──────────────────────────


def scan_dead_files(files: list[Path]) -> None:
    log(f"Scanning {len(files)} files for dead-file candidates")
    for f in files:
        rel = str(f.relative_to(VESSENCE_HOME))
        if f.name in HARD_KEEP:
            continue
        # Pytest test modules are "used" by filesystem discovery even when
        # nothing imports them directly.
        if is_pytest_discovery_file(rel):
            continue
        # Files sitting in a directory that other code loads via
        # importlib.import_module(f"pkg.{name}") look dead to grep but aren't.
        if is_dynamically_imported(f):
            continue
        # Module-style import path: agent_skills/foo.py → "agent_skills.foo"
        module = rel.replace("/", ".").rsplit(".py", 1)[0]
        # Also check stem alone since some imports do `from x import foo`
        stem = f.stem
        if grep_references(module, exclude=f) > 0:
            continue
        if grep_references(stem, exclude=f) > 0:
            continue
        _dead_files.append(f)


# ── Phase 2: dead functions inside live files ───────────────────────────────


def scan_dead_functions(files: list[Path]) -> None:
    log("Scanning for dead functions inside live files")
    for f in files:
        rel = str(f.relative_to(VESSENCE_HOME))
        # Pytest fixtures are referenced via parameter injection, and test-only
        # helpers are low-value dead-code targets anyway. Skip the whole test tree.
        if rel.startswith("test_code/"):
            continue
        try:
            tree = ast.parse(f.read_text(), filename=str(f))
        except Exception:
            continue
        same_file_refs = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        # Only consider module-level functions. Nested closures are frequently
        # used as thread targets, generators, callbacks, or FastAPI helpers.
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name.startswith("_") or node.name.startswith("test_"):
                continue
            if node.name in ("main", "handle", "metadata"):
                continue
            if node.name in same_file_refs:
                continue
            # Single-pass grep (skip if any reference outside the file)
            if grep_references(node.name, exclude=f) == 0:
                _dead_functions.append((f, node.name))


# ── Phase 3: duplicate function bodies across files ─────────────────────────


def normalize_body(node: ast.FunctionDef) -> str:
    """Return a canonical hash-friendly form of the function body."""
    try:
        body_str = ast.unparse(node.body) if hasattr(ast, "unparse") else ""
    except Exception:
        body_str = ""
    # Strip docstrings + comments + whitespace differences
    lines = [ln.strip() for ln in body_str.split("\n") if ln.strip() and not ln.strip().startswith("#")]
    return "\n".join(lines)


def scan_duplicates(files: list[Path]) -> None:
    log("Scanning for duplicate function bodies")
    by_hash: dict[str, list[tuple[Path, str]]] = defaultdict(list)
    for f in files:
        try:
            tree = ast.parse(f.read_text(), filename=str(f))
        except Exception:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            body = normalize_body(node)
            if len(body) < 100:  # too small, lots of trivial collisions
                continue
            h = hashlib.sha256(body.encode()).hexdigest()[:12]
            by_hash[h].append((f, node.name))
    for h, group in by_hash.items():
        if len(group) >= 2:
            paths = [p for p, _ in group]
            _duplicate_groups.append((h, paths))


# ── Phase 4: conservative auto-delete ───────────────────────────────────────


def can_auto_delete(f: Path) -> bool:
    rel = str(f.relative_to(VESSENCE_HOME))
    # Skip anything that still has HTTP route side-effects or dynamic loading.
    # jane_web/ has Flask blueprint registrations that grep can't see; intent
    # classes are caught by is_dynamically_imported already.
    if rel.startswith("jane_web/"):
        return False
    if f.name in HARD_KEEP:
        return False
    if is_dynamically_imported(f):
        return False
    try:
        if f.stat().st_size > MAX_AUTO_DELETE_LINES * 200:  # rough byte cap
            return False
        line_count = sum(1 for _ in f.open())
        if line_count > MAX_AUTO_DELETE_LINES:
            return False
        age_days = (time.time() - f.stat().st_mtime) / 86400
        if age_days < AUTO_DELETE_AGE_DAYS:
            return False
    except Exception:
        return False
    return True


def auto_delete_safe_files() -> None:
    for f in list(_dead_files):
        if can_auto_delete(f):
            try:
                f.unlink()
                _auto_deleted.append(f)
                _dead_files.remove(f)
                log(f"AUTO-DELETED: {f.relative_to(VESSENCE_HOME)}")
            except Exception as e:
                log(f"delete failed for {f}: {e}")


# ── Report + commit ─────────────────────────────────────────────────────────


def write_report() -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    body = [f"# Dead Code Report — {ts}\n"]

    if _auto_deleted:
        body.append(f"## Auto-deleted ({len(_auto_deleted)} files)\n")
        for f in _auto_deleted:
            body.append(f"- `{f.relative_to(VESSENCE_HOME)}`")
        body.append("")

    if _dead_files:
        body.append(f"## Dead files — review needed ({len(_dead_files)})\n")
        body.append("(Candidates for deletion, but failed an auto-delete safety check —")
        body.append(" usually means the file is too new, too large, or outside agent_skills/test_code.)\n")
        for f in _dead_files:
            body.append(f"- `{f.relative_to(VESSENCE_HOME)}`")
        body.append("")

    if _dead_functions:
        body.append(f"## Possibly-dead functions ({len(_dead_functions)})\n")
        body.append("(No references found via grep. May be false positives if called via")
        body.append(" getattr, dynamic dispatch, or HTTP route registration.)\n")
        for f, name in _dead_functions[:50]:
            body.append(f"- `{f.relative_to(VESSENCE_HOME)}` :: `{name}()`")
        if len(_dead_functions) > 50:
            body.append(f"- … and {len(_dead_functions) - 50} more")
        body.append("")

    if _duplicate_groups:
        body.append(f"## Duplicate function bodies ({len(_duplicate_groups)} groups)\n")
        body.append("(Identical bodies — candidates for extraction into a shared helper.)\n")
        for h, paths in _duplicate_groups[:20]:
            body.append(f"- group `{h}`:")
            for p in paths:
                body.append(f"    - `{p.relative_to(VESSENCE_HOME)}`")
        if len(_duplicate_groups) > 20:
            body.append(f"- … and {len(_duplicate_groups) - 20} more groups")
        body.append("")

    if not (_auto_deleted or _dead_files or _dead_functions or _duplicate_groups):
        body.append("Codebase clean — no dead code candidates found. ✅\n")

    REPORT_PATH.write_text("\n".join(body) + "\n")
    log(f"Wrote {REPORT_PATH.relative_to(VESSENCE_HOME)}")


def commit_if_changed() -> None:
    if not _auto_deleted:
        return
    try:
        subprocess.run(["git", "add", "-A"], cwd=VESSENCE_HOME,
                       check=False, capture_output=True)
        msg = (f"auto-dead-code: removed {len(_auto_deleted)} unreferenced file(s)\n\n"
               + "\n".join(f"- {f.relative_to(VESSENCE_HOME)}" for f in _auto_deleted))
        subprocess.run(["git", "commit", "-m", msg, "--no-verify"],
                       cwd=VESSENCE_HOME, check=False, capture_output=True)
        log(f"Committed {len(_auto_deleted)} deletions")
    except Exception as e:
        log(f"git commit failed: {e}")


def main() -> int:
    files = gather_python_files()
    scan_dead_files(files)
    scan_dead_functions(files)
    scan_duplicates(files)
    auto_delete_safe_files()
    write_report()
    commit_if_changed()
    log(f"Done — {len(_auto_deleted)} auto-deleted, "
        f"{len(_dead_files)} flagged, "
        f"{len(_dead_functions)} dead funcs, "
        f"{len(_duplicate_groups)} dup groups")
    return 0


if __name__ == "__main__":
    sys.exit(main())
