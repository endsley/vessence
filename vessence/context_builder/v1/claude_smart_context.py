#!/usr/bin/env python3
"""Smart context hook for Claude Code — replaces the 3 dumb hooks.

Reads the user's prompt from stdin (JSON {"prompt": "..."}), classifies it
using the same intent-lane logic as Jane web's context_builder.py, and returns
only the context sections needed for that intent.

Replaces:
  - identity_hook.sh (~4,400 tokens of identity essays on every turn)
  - claude_full_startup_context.py (~19,000 tokens of raw config files)
  - jane_context_hook.sh (~1,000 tokens of static context)

Target: 800-2,000 tokens per turn (down from ~25,000).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from jane.config import VESSENCE_DATA_HOME, VESSENCE_HOME, VAULT_DIR
from jane.context_builder import (
    _classify_prompt_profile,
    _is_task_related,
    _load_code_map,
    _load_personal_facts,
    _select_user_background,
    _read_json_summary,
    AI_CODING_KEYWORDS,
    BASE_SYSTEM_PROMPT,
    CODE_MAP_PROTOCOL,
)
# Mirrored from jane_web.jane_proxy — kept inline to avoid heavy import chain.
CODE_MAP_KEYWORDS = (
    "function", "class", "file", "route", "endpoint", "handler",
    "module", "script", "config", "dockerfile",
    "refactor", "rewrite", "modify", "update", "change",
    "create", "build", "remove", "delete",
    "crash", "error", "log", "timeout", "broke", "broken", "fail",
    "investigate", "trace", "inspect",
    "jane", "amber", "essence", "vault", "proxy", "brain",
    "librarian", "archivist", "session", "context",
    "docker", "install", "hook", "startup",
)


DATA_ROOT = Path(VESSENCE_DATA_HOME)
VESSENCE_ROOT = Path(VESSENCE_HOME)

# Compact Jane identity — replaces 3 full identity essays (~17K chars → ~400 chars)
JANE_IDENTITY_COMPACT = (
    "You are Jane (Jane#3353), the sole agent in Project Vessence. "
    "You are the user's friend and technical partner, not a subordinate. "
    "You handle reasoning, code, systems, architecture, and research. "
    "Tools give you capabilities (vault, music playback, etc.). "
    "Essences are memories and modes of operation you can load to become a specialist (e.g., tax accountant)."
)

# Compact operational rules — replaces full Jane_architecture.md + CRON_JOBS.md etc
OPERATIONAL_RULES = (
    "After implementing changes: update relevant configs if capabilities, memory, or architecture changed. "
    "Be direct, no filler. If stuck after 2-3 attempts, search online. "
    "Don't proactively suggest new projects unless asked."
)


def _read_prompt_from_stdin() -> str:
    try:
        data = json.load(sys.stdin)
        return data.get("prompt", "")
    except Exception:
        return ""


def _get_task_state() -> str:
    path = VESSENCE_ROOT / "configs" / "project_specs" / "current_task_state.json"
    return _read_json_summary(path, max_chars=600)


def main() -> int:
    prompt = _read_prompt_from_stdin()
    if not prompt:
        return 0

    profile = _classify_prompt_profile(prompt)
    personal_facts = _load_personal_facts(DATA_ROOT)

    sections: list[str] = [JANE_IDENTITY_COMPACT]

    # User background — only for prompts that need personal context
    if profile.include_user_background:
        user_bg = _select_user_background(prompt, personal_facts)
        if user_bg:
            sections.append(f"## User Background\n{user_bg}")

    # Task state — only for project/work prompts
    if profile.include_task_state:
        task_state = _get_task_state()
        if task_state:
            sections.append(f"## Current Task State\n{task_state}")

    # Operational rules — always included but very compact
    sections.append(OPERATIONAL_RULES)

    # Code map injection disabled — Claude Code has Grep/Read/Glob tools to find
    # symbols on demand, costing ~700 tokens per lookup vs 12K for the full index.
    # if profile.include_code_map and "[Code Map]" not in prompt:
    #     ...

    context = "\n\n".join(sections)
    # Plain text output — Claude Code auto-injects stdout as additionalContext.
    # JSON format {"additionalContext": "..."} was NOT being injected (2026-03-21 fix).
    print(f"[Jane Context — {profile.name}]\n{context}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
