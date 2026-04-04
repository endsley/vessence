#!/usr/bin/env python3
"""
ambient_task_research.py — Autonomous per-task research loop for Project Ambient.

Runs every 30 minutes via cron. Per run:
  1. Checks if user has been idle for more than 10 minutes (skips if active)
  2. Reads the Project Ambient spec and extracts all unchecked tasks (- [ ]) from ALL phases
  3. For each un-researched task, searches DuckDuckGo for how others have implemented it
  4. Synthesizes findings with qwen2.5-coder:14b into actionable implementation notes
  5. Saves research notes to ambient_task_research_cache.json (7-day TTL per task)
  6. Sends a Discord summary of what was researched
"""

import os
import sys
import json
import time
import logging
import datetime
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_skills.web_search_utils import web_search as _web_search
from jane.config import CONFIGS_DIR, JANE_BRIDGE_ENV, LOGS_DIR, OPENAI_API_URL

# ─── Config ─────────────────────────────────────────────────────────────────────
SPEC_PATH        = os.path.join(CONFIGS_DIR, 'project_specs', 'ambient_app.md')
CLAUDE_SESSIONS  = os.path.join(os.path.expanduser('~'), '.claude', 'projects', f'-home-{os.environ.get("USER", "user")}')
ENV_FILE         = JANE_BRIDGE_ENV
LOG_FILE         = os.path.join(LOGS_DIR, 'ambient_task_research.log')
RESEARCH_CACHE   = os.path.join(CONFIGS_DIR, 'project_specs', 'ambient_task_research_cache.json')
IDLE_MINUTES     = 10    # Skip if Claude was active within this many minutes
MAX_TASKS_PER_RUN = 5    # Max tasks to research per run (30-min cadence, keep it fast)
CACHE_TTL_DAYS   = 7     # Re-research each task after this many days
MODEL            = os.environ.get("HEARTBEAT_MODEL", "gpt-4o-mini")

# ─── Logging ────────────────────────────────────────────────────────────────────
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("AmbientTaskResearch")


# ─── Idle Detection ──────────────────────────────────────────────────────────────
def is_user_active() -> bool:
    """Return True if the user has been active in Claude Code within IDLE_MINUTES."""
    try:
        sessions_dir = Path(CLAUDE_SESSIONS)
        jsonl_files = list(sessions_dir.glob("*.jsonl"))
        if not jsonl_files:
            return False
        most_recent_mtime = max(f.stat().st_mtime for f in jsonl_files)
        age_minutes = (time.time() - most_recent_mtime) / 60
        if age_minutes < IDLE_MINUTES:
            logger.info(f"User active {age_minutes:.1f}min ago — skipping this run.")
            return True
        return False
    except Exception as e:
        logger.warning(f"Idle check failed: {e} — assuming idle.")
        return False


# ─── Task Extraction ─────────────────────────────────────────────────────────────
def extract_unchecked_tasks() -> list[dict]:
    """
    Parse the Progress Tracker in the spec and return all unchecked tasks as:
    [{"phase": "Phase 1 — Core Chat (MVP)", "task": "Flutter project scaffold ..."}]
    """
    try:
        with open(SPEC_PATH, "r") as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Could not read spec: {e}")
        return []

    # Find the Progress Tracker section
    tracker_start = content.find("## 9. Progress Tracker")
    if tracker_start == -1:
        logger.warning("Could not find '## 9. Progress Tracker' in spec.")
        return []

    tracker_content = content[tracker_start:]

    tasks = []
    current_phase = "Unknown Phase"

    for line in tracker_content.splitlines():
        # Detect phase headings like "### Phase 1 — Core Chat (MVP)"
        stripped = line.strip()
        if stripped.startswith("###"):
            current_phase = stripped.lstrip("#").strip()
        # Collect unchecked tasks
        elif stripped.startswith("- [ ]"):
            task_text = stripped[6:].strip()
            if task_text:
                tasks.append({"phase": current_phase, "task": task_text})

    logger.info(f"Found {len(tasks)} unchecked tasks across all phases.")
    return tasks


# ─── Research Cache ──────────────────────────────────────────────────────────────
def load_cache() -> dict:
    if os.path.exists(RESEARCH_CACHE):
        try:
            with open(RESEARCH_CACHE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache: dict):
    with open(RESEARCH_CACHE, "w") as f:
        json.dump(cache, f, indent=2)


def task_cache_key(task: str) -> str:
    """Stable cache key from task text (lowercased, spaces→underscores, truncated)."""
    return task.lower().replace(" ", "_").replace("/", "_")[:80]


def is_stale(cache: dict, key: str) -> bool:
    """Return True if the task hasn't been researched in CACHE_TTL_DAYS days."""
    if key not in cache:
        return True
    try:
        last = datetime.datetime.fromisoformat(cache[key]["last_researched"])
        return (datetime.datetime.now() - last).days >= CACHE_TTL_DAYS
    except Exception:
        return True


# ─── Search Query Generation ─────────────────────────────────────────────────────
def build_search_query(phase: str, task: str) -> str:
    """
    Generate a targeted search query for how others have implemented this task.
    Adds Flutter / cross-platform context where relevant.
    """
    task_lower = task.lower()

    # Context hints based on the task content
    context = "Flutter cross-platform"
    if any(k in task_lower for k in ["sqlite", "sqflite", "database", "persistence", "history"]):
        context = "Flutter SQLite"
    elif any(k in task_lower for k in ["stream", "sse", "server-sent"]):
        context = "Flutter SSE streaming ADK"
    elif any(k in task_lower for k in ["markdown", "code block", "syntax highlight"]):
        context = "Flutter markdown rendering"
    elif any(k in task_lower for k in ["tts", "speech", "voice", "audio", "whisper", "vad"]):
        context = "Python TTS voice assistant"
    elif any(k in task_lower for k in ["tailscale", "remote", "vpn", "tunnel"]):
        context = "Tailscale self-hosted remote access"
    elif any(k in task_lower for k in ["wake word", "porcupine", "standby"]):
        context = "Picovoice Porcupine wake word Python"
    elif any(k in task_lower for k in ["android", "apk"]):
        context = "Flutter Android"
    elif any(k in task_lower for k in ["linux", "desktop"]):
        context = "Flutter Linux desktop"
    elif any(k in task_lower for k in ["notification", "push"]):
        context = "Flutter push notifications"
    elif any(k in task_lower for k in ["auth", "invite", "user", "register"]):
        context = "FastAPI user authentication"
    elif any(k in task_lower for k in ["theme", "dark", "color"]):
        context = "Flutter dark theme ChatGPT UI"

    return f"{context} {task} implementation tutorial 2024 2025"


# ─── Web Search ──────────────────────────────────────────────────────────────────
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web via Tavily (with DuckDuckGo fallback)."""
    return _web_search(query, max_results)


# ─── OpenAI Synthesis ────────────────────────────────────────────────────────────
def synthesize_with_openai(phase: str, task: str, web_data: str) -> str:
    """
    Use OpenAI (gpt-4o-mini) to synthesize web data into a concrete implementation note.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.error("OPENAI_API_KEY not set — cannot synthesize.")
        return ""

    system = (
        "You are a Senior Software Engineer advising on 'Project Ambient' — "
        "a cross-platform Flutter app (Linux, Windows, Android, macOS) that provides "
        "a ChatGPT-like interface to a local Google ADK AI server (Amber, running at localhost:8000). "
        "Your job: given a specific development task, explain how others have implemented this "
        "and give a concrete, actionable approach for this project. "
        "Be specific: include package names, versions, code patterns, and pitfalls to avoid. "
        "Format in clean Markdown. Keep it under 400 words."
    )

    web_section = f"\n\nWeb search results:\n{web_data[:6000]}" if web_data else ""
    user_msg = (
        f"Phase: {phase}\n"
        f"Task: {task}\n\n"
        f"How have others implemented this? What's the best approach for our project?{web_section}"
    )

    try:
        resp = requests.post(
            OPENAI_API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                "max_tokens": 800,
                "temperature": 0.3,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"OpenAI synthesis failed for '{task}': {e}")
        return ""


# ─── Discord Notification ─────────────────────────────────────────────────────────
from agent_skills.cron_utils import send_discord


# ─── Main ─────────────────────────────────────────────────────────────────────────
def main():
    logger.info("═══ Ambient Task Research starting ═══")

    # 0. Load gate: wait until CPU/memory is acceptable
    try:
        from agent_skills.system_load import wait_until_safe
        if not wait_until_safe(max_wait_minutes=10):
            logger.info("System busy — skipping task research this cycle.")
            return
    except Exception:
        pass

    # 1. Idle check — only run when user has been away for 10+ minutes
    if is_user_active():
        logger.info("User is active — exiting without running.")
        return

    # 2. Extract all unchecked tasks from the spec
    all_tasks = extract_unchecked_tasks()
    if not all_tasks:
        logger.info("No unchecked tasks found in spec.")
        return

    cache = load_cache()

    # 4. Filter to tasks that need research (stale or never researched), pick first N
    tasks_to_research = [
        t for t in all_tasks
        if is_stale(cache, task_cache_key(t["task"]))
    ][:MAX_TASKS_PER_RUN]

    if not tasks_to_research:
        logger.info(f"All {len(all_tasks)} tasks have fresh research — nothing to do.")
        return

    logger.info(f"Researching {len(tasks_to_research)} tasks this run.")

    researched = []

    for item in tasks_to_research:
        phase = item["phase"]
        task = item["task"]
        key = task_cache_key(task)

        logger.info(f"  → [{phase}] {task}")

        query = build_search_query(phase, task)
        logger.info(f"     Search: {query}")

        web_data = web_search(query)
        logger.info(f"     Got {len(web_data)} chars of web data")

        note = synthesize_with_openai(phase, task, web_data)
        if not note:
            logger.warning(f"     No synthesis output — skipping.")
            continue

        # Save to cache
        cache[key] = {
            "task": task,
            "phase": phase,
            "last_researched": datetime.datetime.now().isoformat(),
            "query": query,
            "note": note,
        }
        save_cache(cache)
        researched.append({"phase": phase, "task": task, "note": note})
        logger.info(f"     Saved research note ({len(note)} chars)")

        # Brief pause between Qwen calls
        time.sleep(2)

    # 5. Discord summary
    if researched:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [f"🔬 **Ambient Task Research** ({date_str})"]
        lines.append(f"Researched **{len(researched)}/{len(all_tasks)} tasks** remaining in the spec.\n")

        for item in researched:
            # Show phase + task + first 2 lines of the note as a teaser
            note_preview = "\n".join(item["note"].splitlines()[:3])
            lines.append(f"**[{item['phase']}]** `{item['task']}`")
            lines.append(f"> {note_preview[:200]}")
            lines.append("")

        lines.append(f"_Full notes in `{RESEARCH_CACHE}`_")
        send_discord("\n".join(lines))
    else:
        logger.info("No research completed this run.")

    logger.info("═══ Ambient Task Research complete ═══")


if __name__ == "__main__":
    main()
