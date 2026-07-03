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

import os
import sys
from datetime import datetime, timezone

from agent_skills.code_map_indexers import (
    MAX_ENTRIES_PRIORITY,
    MAX_ENTRIES_SECONDARY,
    SKIP_DIRS,
    cap_entries as _cap_entries,
    count_lines,
    index_file as _index_file,
    index_html_file,
    index_kotlin_file,
    index_python_file,
    should_skip as _should_skip,
)
from agent_skills.code_map_output import (
    combined_code_map_index as _combined_code_map_index,
    generated_header as _generated_header,
    merge_preserved_header as _merge_preserved_header,
    rendered_line_count as _rendered_line_count,
    short_android_path as _short_android_path,
)

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

MARKER = "<!-- AUTO-GENERATED BELOW — do not edit below this line -->"


# ═══════════════════════════════════════════════════════════════════════════════
# Parsers
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# Map generators
# ═══════════════════════════════════════════════════════════════════════════════

def generate_core_map() -> str:
    """Generate CODE_MAP_CORE.md — Python backend files."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sections = _generated_header("# Code Map — Core (Python Backend)", now)

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
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sections = _generated_header("# Code Map — Web Frontend", now)

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
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sections = _generated_header("# Code Map — Android (Kotlin)", now)

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
        short_path = _short_android_path(rel_path)
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
    existing = ""
    if os.path.isfile(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            existing = f.read()
    output = _merge_preserved_header(existing, content, MARKER)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output)

    line_count = _rendered_line_count(output)
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
    _write_map(combined_path, _combined_code_map_index())

    print("Done.")


if __name__ == "__main__":
    main()
