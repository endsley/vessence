#!/usr/bin/env python3
"""generate_code_map.py — Build lightweight code indexes for the Vessence codebase.

Pure static analysis using ast.parse() for Python, regex for HTML/JS and Kotlin.
No LLM required. Outputs three maps to configs/:
  CODE_MAP_CORE.md   — Python backend (jane/, agent_skills/, startup_code/)
  CODE_MAP_WEB.md    — Web frontend (vault_web/templates/*.html, jane_web/*.html)
  CODE_MAP_ANDROID.md — Android app (android/ Kotlin files)

Usage:
    python agent_skills/generate_code_map.py          # generate all three
    python agent_skills/generate_code_map.py core      # generate only core
    python agent_skills/generate_code_map.py web       # generate only web
    python agent_skills/generate_code_map.py android   # generate only android
"""

import ast
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

VESSENCE_HOME = os.environ.get("VESSENCE_HOME", os.path.expanduser("~/ambient/vessence"))
CONFIGS_DIR = os.path.join(VESSENCE_HOME, "configs")

# ── Core map config ──────────────────────────────────────────────────────────

CORE_PRIORITY_FILES = [
    # ── Jane Web (HTTP layer) ──
    "jane_web/jane_proxy.py",
    "jane_web/main.py",
    "jane_web/broadcast.py",
    "jane_web/reverse_proxy.py",
    "jane_web/task_classifier.py",
    "jane_web/task_offloader.py",
    # ── Jane Brain (adapters, sessions, context) ──
    "jane/brain_adapters.py",
    "jane/standing_brain.py",
    "jane/persistent_claude.py",
    "jane/persistent_gemini.py",
    "jane/context_builder.py",
    "jane/config.py",
    "jane/session_summary.py",
    "jane/automation_runner.py",
    "jane/jane_session_wrapper.py",
    "jane/task_spine.py",
    "jane/tts.py",
    "jane/audit_wrapper.py",
    "jane/research_router.py",
    # ── Agent Skills (core) ──
    "agent_skills/memory/v1/conversation_manager.py",
    "agent_skills/memory/v1/memory_retrieval.py",
    "agent_skills/memory/v1/local_vector_memory.py",
    "agent_skills/prompt_queue_runner.py",
    "agent_skills/essence_builder.py",
    "agent_skills/essence_loader.py",
    "agent_skills/essence_runtime.py",
    "agent_skills/essence_scheduler.py",
    "agent_skills/memory/v1/index_vault.py",
    "agent_skills/memory/v1/janitor_memory.py",
    "agent_skills/janitor_system.py",
    "agent_skills/nightly_audit.py",
    "agent_skills/audit_auto_fixer.py",
    "agent_skills/system_load.py",
    "agent_skills/fallback_query.py",
    "agent_skills/generate_code_map.py",
    "agent_skills/ambient_heartbeat.py",
    "agent_skills/ambient_task_research.py",
    "agent_skills/llm_summarize.py",
    "agent_skills/qwen_orchestrator.py",
    "agent_skills/validate_essence.py",
    "agent_skills/show_job_queue.py",
    # ── Vault Web (shared libraries used by jane_web) ──
    "vault_web/files.py",
    "vault_web/auth.py",
    "vault_web/oauth.py",
    "vault_web/database.py",
    "vault_web/playlists.py",
    # ── Onboarding ──
    "onboarding/main.py",
    # ── Startup / Infrastructure ──
    "startup_code/jane_bootstrap.py",
    "startup_code/memory_daemon.py",
    "startup_code/regenerate_jane_context.py",
    "startup_code/seed_chromadb.py",
    "startup_code/usb_sync.py",
    "startup_code/usb_rotation.py",
    "startup_code/build_docker_bundle.py",
    "startup_code/query_live_memory.py",
    "startup_code/claude_smart_context.py",
]

CORE_SECONDARY_DIRS = [
    "jane_web",
    "jane",
    "agent_skills",
    "startup_code",
    "vault_web",
    "onboarding",
]

# ── Web map config ───────────────────────────────────────────────────────────

WEB_PRIORITY_FILES = [
    "vault_web/templates/jane.html",
    "vault_web/templates/app.html",
]

WEB_SECONDARY_DIRS = [
    "vault_web/templates",
]

# ── Android map config ───────────────────────────────────────────────────────

ANDROID_ROOT = "android"

# ── Shared config ────────────────────────────────────────────────────────────

SKIP_DIRS = {"__pycache__", "node_modules", "omniparser", ".git", "test_code", "venv", "build", ".gradle"}
SKIP_FILES = {"__init__.py"}

MARKER = "<!-- AUTO-GENERATED BELOW — do not edit below this line -->"

MAX_ENTRIES_PRIORITY = 50
MAX_ENTRIES_SECONDARY = 20


# ═══════════════════════════════════════════════════════════════════════════════
# Parsers
# ═══════════════════════════════════════════════════════════════════════════════

def count_lines(filepath: str) -> int:
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def index_python_file(filepath: str) -> list[str]:
    """Extract functions, classes, decorators, and constants from a Python file."""
    entries = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            source = f.read()
        tree = ast.parse(source, filename=filepath)
    except (SyntaxError, Exception):
        return entries

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            end = getattr(node, "end_lineno", node.lineno)
            entries.append(f"  class {node.name} → L{node.lineno}-{end}")
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    item_end = getattr(item, "end_lineno", item.lineno)
                    entries.append(f"    {item.name}() → L{item.lineno}-{item_end}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            route = ""
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                    attr = dec.func.attr
                    if attr in ("get", "post", "put", "delete", "patch"):
                        if dec.args and isinstance(dec.args[0], ast.Constant):
                            route = f"  {attr.upper()} {dec.args[0].value} → L{node.lineno}"
                            break
            if route:
                entries.append(route)
            else:
                entries.append(f"  {node.name}() → L{node.lineno}-{end}")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper() and len(target.id) > 2:
                    entries.append(f"  {target.id} = ... → L{node.lineno}")

    return entries


def index_html_file(filepath: str) -> list[str]:
    """Extract Alpine.js methods and event handlers from HTML."""
    entries = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return entries

    for i, line in enumerate(lines, 1):
        m = re.match(r'\s{8,}(async\s+)?(\w+)\s*\(.*\)\s*\{', line)
        if m and m.group(2) not in ("if", "for", "while", "switch", "catch", "else", "function", "return"):
            name = m.group(2)
            prefix = "async " if m.group(1) else ""
            entries.append(f"  {prefix}{name}() → L{i}")

        m = re.search(r"event\.type\s*===?\s*['\"](\w+)['\"]", line)
        if m:
            entries.append(f"  event.type === '{m.group(1)}' → L{i}")

    seen = set()
    unique = []
    for e in entries:
        if e not in seen:
            seen.add(e)
            unique.append(e)
    return unique


def index_kotlin_file(filepath: str) -> list[str]:
    """Extract classes, objects, functions, and @Composable functions from a Kotlin file."""
    entries = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return entries

    # Track class/object nesting for indentation
    current_class = None

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Skip comments and blank lines
        if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*") or not stripped:
            continue

        # Class / object / interface declarations
        m = re.match(r'^\s*((?:data|sealed|abstract|open|private|internal)\s+)*(class|object|interface)\s+(\w+)', line)
        if m:
            kind = m.group(2)
            name = m.group(3)
            current_class = name
            entries.append(f"  {kind} {name} → L{i}")
            continue

        # @Composable function (always top-level in Compose)
        if stripped == "@Composable":
            # Look ahead for the function name
            if i < len(lines):
                next_line = lines[i].strip()  # i is 1-indexed, lines[i] is the next line
                m = re.match(r'(?:(?:private|internal)\s+)?fun\s+(\w+)', next_line)
                if m:
                    entries.append(f"  @Composable {m.group(1)}() → L{i + 1}")
                    # Mark next line as consumed so the fun matcher skips it
                    lines[i] = "\n"
            continue

        # Top-level and class-level fun declarations
        m = re.match(r'^(\s*)((?:override|suspend|private|internal|protected|open)\s+)*fun\s+(\w+)', line)
        if m:
            indent = len(m.group(1))
            name = m.group(3)
            modifiers = (m.group(2) or "").strip()
            prefix = ""
            if "suspend" in modifiers:
                prefix = "suspend "
            if "override" in modifiers:
                prefix = "override "
            if indent >= 4:
                entries.append(f"    {prefix}{name}() → L{i}")
            else:
                entries.append(f"  {prefix}{name}() → L{i}")
            continue

        # Companion object constants (val NAME = ...)
        m = re.match(r'^\s+(?:const\s+)?val\s+([A-Z_]{3,})\s*[=:]', line)
        if m:
            entries.append(f"    {m.group(1)} → L{i}")

    return entries


def _index_file(fpath: str, functions_only: bool = False) -> list[str]:
    """Index a single file."""
    if fpath.endswith(".py"):
        entries = index_python_file(fpath)
        if functions_only:
            entries = [e for e in entries if "()" in e or e.strip().startswith(("GET ", "POST ", "PUT ", "DELETE ", "PATCH "))]
        return entries
    elif fpath.endswith(".html"):
        return index_html_file(fpath)
    elif fpath.endswith(".kt"):
        entries = index_kotlin_file(fpath)
        if functions_only:
            entries = [e for e in entries if "()" in e or "class " in e or "object " in e or "interface " in e]
        return entries
    return []


def _should_skip(fpath: str, fname: str) -> bool:
    if fname in SKIP_FILES:
        return True
    if any(skip in fpath for skip in SKIP_DIRS):
        return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# Map generators
# ═══════════════════════════════════════════════════════════════════════════════

def _cap_entries(entries: list[str]) -> list[str]:
    """Apply priority-file entry cap."""
    if len(entries) <= MAX_ENTRIES_PRIORITY:
        return entries
    routes = [e for e in entries if any(m in e for m in ("GET ", "POST ", "PUT ", "DELETE ", "PATCH "))]
    funcs = [e for e in entries if "()" in e]
    classes = [e for e in entries if "class " in e]
    consts = [e for e in entries if "= ..." in e]
    result = classes + routes + funcs
    remaining = MAX_ENTRIES_PRIORITY - len(result)
    if remaining > 0:
        result.extend(consts[:remaining])
    return result[:MAX_ENTRIES_PRIORITY]


def generate_core_map() -> str:
    """Generate CODE_MAP_CORE.md — Python backend files."""
    sections = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sections.append("# Code Map — Core (Python Backend)")
    sections.append(f"_Auto-generated on {now} by `generate_code_map.py`_\n")

    indexed_paths = set()
    sections.append("## Priority Files\n")

    for rel in CORE_PRIORITY_FILES:
        fpath = os.path.join(VESSENCE_HOME, rel)
        if not os.path.isfile(fpath):
            continue
        indexed_paths.add(os.path.abspath(fpath))
        line_count = count_lines(fpath)
        entries = _index_file(fpath, functions_only=False)
        if not entries:
            continue
        entries = _cap_entries(entries)
        sections.append(f"### {rel} ({line_count} lines)")
        sections.extend(entries)
        sections.append("")

    sections.append("## Other Files\n")

    for scan_dir in CORE_SECONDARY_DIRS:
        full_dir = os.path.join(VESSENCE_HOME, scan_dir)
        if not os.path.isdir(full_dir):
            continue
        for root, dirs, files in os.walk(full_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fname in sorted(files):
                fpath = os.path.join(root, fname)
                if not fname.endswith(".py"):
                    continue
                if os.path.abspath(fpath) in indexed_paths:
                    continue
                if _should_skip(fpath, fname):
                    continue
                line_count = count_lines(fpath)
                if line_count < 50:
                    continue
                rel_path = os.path.relpath(fpath, VESSENCE_HOME)
                entries = _index_file(fpath, functions_only=False)
                if not entries:
                    continue
                entries = entries[:MAX_ENTRIES_SECONDARY]
                sections.append(f"### {rel_path} ({line_count} lines)")
                sections.extend(entries)
                sections.append("")

    return "\n".join(sections)


def generate_web_map() -> str:
    """Generate CODE_MAP_WEB.md — HTML/JS frontend files."""
    sections = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sections.append("# Code Map — Web Frontend")
    sections.append(f"_Auto-generated on {now} by `generate_code_map.py`_\n")

    indexed_paths = set()

    # Priority HTML files (full index)
    for rel in WEB_PRIORITY_FILES:
        fpath = os.path.join(VESSENCE_HOME, rel)
        if not os.path.isfile(fpath):
            continue
        indexed_paths.add(os.path.abspath(fpath))
        line_count = count_lines(fpath)
        entries = _index_file(fpath, functions_only=False)
        if not entries:
            continue
        sections.append(f"## {rel} ({line_count} lines)")
        sections.extend(entries)
        sections.append("")

    # Secondary HTML files
    for scan_dir in WEB_SECONDARY_DIRS:
        full_dir = os.path.join(VESSENCE_HOME, scan_dir)
        if not os.path.isdir(full_dir):
            continue
        for fname in sorted(os.listdir(full_dir)):
            fpath = os.path.join(full_dir, fname)
            if not os.path.isfile(fpath) or os.path.abspath(fpath) in indexed_paths:
                continue
            if _should_skip(fpath, fname) or not fname.endswith(".html"):
                continue
            line_count = count_lines(fpath)
            if line_count < 50:
                continue
            rel_path = os.path.relpath(fpath, VESSENCE_HOME)
            entries = _index_file(fpath, functions_only=False)
            if not entries:
                continue
            sections.append(f"## {rel_path} ({line_count} lines)")
            sections.extend(entries)
            sections.append("")

    return "\n".join(sections)


def generate_android_map() -> str:
    """Generate CODE_MAP_ANDROID.md — Kotlin Android files."""
    sections = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sections.append("# Code Map — Android (Kotlin)")
    sections.append(f"_Auto-generated on {now} by `generate_code_map.py`_\n")

    android_dir = os.path.join(VESSENCE_HOME, ANDROID_ROOT)
    if not os.path.isdir(android_dir):
        sections.append("_No android/ directory found._")
        return "\n".join(sections)

    kt_files = []
    for root, dirs, files in os.walk(android_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in sorted(files):
            if fname.endswith(".kt"):
                kt_files.append(os.path.join(root, fname))

    # Sort by relative path for readability
    kt_files.sort(key=lambda p: os.path.relpath(p, VESSENCE_HOME))

    for fpath in kt_files:
        line_count = count_lines(fpath)
        if line_count < 20:
            continue
        rel_path = os.path.relpath(fpath, VESSENCE_HOME)
        # Shorten android path for readability
        short_path = rel_path.replace("android/app/src/main/java/com/vessences/android/", "android:.../")
        entries = _index_file(fpath, functions_only=False)
        if not entries:
            continue
        if len(entries) > MAX_ENTRIES_PRIORITY:
            entries = _cap_entries(entries)
        sections.append(f"## {short_path} ({line_count} lines)")
        sections.extend(entries)
        sections.append("")

    return "\n".join(sections)


# ═══════════════════════════════════════════════════════════════════════════════
# Output
# ═══════════════════════════════════════════════════════════════════════════════

def _write_map(output_path: str, content: str):
    """Write a code map, preserving any hand-written header above the marker."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    header = ""
    if os.path.isfile(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            existing = f.read()
        if MARKER in existing:
            header = existing[:existing.index(MARKER) + len(MARKER)] + "\n\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header + content)

    line_count = (header + content).count("\n") + 1
    print(f"  {output_path} ({line_count} lines)")


def main():
    targets = set(sys.argv[1:]) if len(sys.argv) > 1 else {"core", "web", "android"}

    print("Generating code maps...")

    if "core" in targets:
        _write_map(os.path.join(CONFIGS_DIR, "CODE_MAP_CORE.md"), generate_core_map())

    if "web" in targets:
        _write_map(os.path.join(CONFIGS_DIR, "CODE_MAP_WEB.md"), generate_web_map())

    if "android" in targets:
        _write_map(os.path.join(CONFIGS_DIR, "CODE_MAP_ANDROID.md"), generate_android_map())

    # Also write combined CODE_MAP.md for backwards compat (just a pointer)
    combined_path = os.path.join(CONFIGS_DIR, "CODE_MAP.md")
    _write_map(combined_path,
        "# Code Map Index\n\n"
        "Split into three targeted maps:\n"
        "- `CODE_MAP_CORE.md` — Python backend (jane/, agent_skills/, startup_code/)\n"
        "- `CODE_MAP_WEB.md` — Web frontend (vault_web/templates/)\n"
        "- `CODE_MAP_ANDROID.md` — Android app (Kotlin)\n\n"
        "Run `python agent_skills/generate_code_map.py` to regenerate all, "
        "or pass `core`, `web`, or `android` to regenerate one.\n"
    )

    print("Done.")


if __name__ == "__main__":
    main()
