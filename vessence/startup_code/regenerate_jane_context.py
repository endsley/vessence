#!/usr/bin/env python3
"""
Nightly cron script: regenerates Jane's condensed boot context file
from the authoritative source config files. Runs at 3:15 AM.

This ensures Jane's architecture boot context stays current as projects
and capabilities evolve, without requiring manual updates to the hook file.
"""

import os
import sys
import re
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jane.config import VAULT_DIR, VESSENCE_DATA_HOME, VESSENCE_HOME

# Load gate: wait until CPU/memory is acceptable
try:
    from agent_skills.system_load import wait_until_safe
    if not wait_until_safe(max_wait_minutes=10):
        print("System busy — skipping context regeneration this cycle.")
        sys.exit(0)
except Exception:
    pass

BASE = VESSENCE_HOME
DATA_ROOT = VESSENCE_DATA_HOME
VAULT_ROOT = VAULT_DIR
OUTPUT = os.environ.get('JANE_CONTEXT_OUTPUT', str(Path.home() / '.claude' / 'hooks' / 'jane_context.txt'))

def read_file(path):
    try:
        with open(path) as f:
            return f.read()
    except Exception as e:
        return f"[ERROR reading {path}: {e}]"

def extract_section(text, header_pattern, max_lines=30):
    """Extract lines after a matching header, up to max_lines or next header."""
    lines = text.splitlines()
    result = []
    capturing = False
    for line in lines:
        if re.search(header_pattern, line, re.IGNORECASE):
            capturing = True
            continue
        if capturing:
            if line.startswith("## ") and result:
                break
            result.append(line)
            if len(result) >= max_lines:
                break
    return "\n".join(result).strip()

def extract_cron_jobs(cron_text):
    jobs = []
    current = {}
    for line in cron_text.splitlines():
        if line.startswith("## "):
            if current:
                jobs.append(current)
            current = {"name": line.lstrip("# ").strip()}
        elif "**Schedule:**" in line:
            m = re.search(r'`([^`]+)`', line)
            current["schedule"] = m.group(1) if m else "?"
        elif "**Script Path:**" in line:
            m = re.search(r'`([^`]+)`', line)
            if m:
                current["script"] = m.group(1).replace(f"{BASE}/", "")
        elif "**Description:**" in line:
            current["desc"] = line.split("**Description:**")[-1].strip()[:120]
    if current:
        jobs.append(current)

    lines = []
    for j in jobs:
        sched = j.get("schedule", "?")
        script = j.get("script", j.get("name", "?"))
        desc = j.get("desc", j.get("name", ""))[:80]
        lines.append(f"- {sched}: {script} — {desc}")
    return "\n".join(lines)

def extract_projects(todo_text):
    projects = []
    for line in todo_text.splitlines():
        m = re.match(r'\s*\d+\.\s+\*\*(.+?)\*\*', line)
        if m:
            projects.append(m.group(1))
    numbered = [f"{i+1}. {p}" for i, p in enumerate(projects)]
    return "\n".join(numbered) if numbered else "[not found]"

def build_context():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    todo = read_file(f"{BASE}/configs/TODO_PROJECTS.md")
    cron = read_file(f"{BASE}/configs/CRON_JOBS.md")
    skills = read_file(f"{BASE}/configs/SKILLS_REGISTRY.md")

    projects = extract_projects(todo)
    cron_jobs = extract_cron_jobs(cron)

    context = f"""[Jane Architecture Context — Always Active]
Generated: {now} | Auto-updated nightly by startup_code/regenerate_jane_context.py

=== SYSTEM IDENTITY ===
- Jane (Jane#3353): Claude Code (claude-opus-4-6). Sole agent — reasoning, code, systems, research. Direct executor, not a delegator.
- Tools: Capabilities Jane can invoke (vault/file access, music playback, daily briefing, etc.)
- Essences: Memories + modes of operation Jane can load to become a specialist (e.g., tax accountant)
- User profile: see $VESSENCE_DATA_HOME/user_profile.md
- Relationship rule: Friends, not user/assistant. No filler flattery.

=== ENVIRONMENT ===
- ChromaDB: $VESSENCE_DATA_HOME/vector_db (collection: user_memories)
- Vault: $VAULT_HOME/
- Identity essays: $VAULT_HOME/documents/{{user,jane}}_identity_essay.txt

=== MEMORY SYSTEM ===
- Memory injection: automatic via UserPromptSubmit hooks (claude_smart_context.py + memory_hook.sh)
- Long-term DB: ChromaDB persistent collection (user_memories)
- Short-term DB: Persistent shared ChromaDB at $VESSENCE_DATA_HOME/vector_db/short_term_memory/ (14-day TTL, purged nightly)
- Nightly janitor: agent_skills/janitor_memory.py (3:00 AM) — LLM-powered dedup/merge
- End-of-session archival: agent_skills/conversation_manager.py → ConversationManager._run_archival()

=== ACTIVE PROJECTS (priority order) ===
{projects}

=== CRON JOBS ===
{cron_jobs}

=== MANDATORY UPDATE RULES ===
After any change: update the relevant config in $VESSENCE_HOME/configs/:
Jane capability → Jane_architecture.md
Memory system → memory_manage_architecture.md | Skills → SKILLS_REGISTRY.md
Projects/TODOs → TODO_PROJECTS.md | Accomplishments → PROJECT_ACCOMPLISHMENTS.md
Cron jobs → CRON_JOBS.md
"""
    return context.strip()

if __name__ == "__main__":
    context = build_context()
    with open(OUTPUT, "w") as f:
        f.write(context + "\n")
    print(f"[regenerate_jane_context] Written {len(context)} chars to {OUTPUT}")
