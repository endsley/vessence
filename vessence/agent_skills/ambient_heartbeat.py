#!/usr/bin/env python3
"""
ambient_heartbeat.py — Autonomous research & spec refinement loop for Project Ambient.

Runs every 3 hours via cron. Per run:
  1. Checks if user is in an active Claude session (skips if so)
  2. Reads the Project Ambient spec and identifies sections needing research
  3. Uses DuckDuckGo + qwen2.5-coder:14b to research each topic
  4. Refines/appends findings directly into the spec under each section
  5. Checks the progress tracker for implementation-ready tasks
  6. Implements ready tasks via the shared automation runner (only when open questions are resolved)
  7. Sends a Discord summary of everything done
"""

import os
import sys
import json
import time
import logging
import subprocess
import datetime
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_skills.web_search_utils import web_search as _web_search
from jane.config import (
    AMBIENT_HEARTBEAT_LOG,
    CONFIGS_DIR,
    JANE_BRIDGE_ENV,
    VESSENCE_HOME,
    OPENAI_API_URL,
)
from jane.automation_runner import AutomationError, run_automation_prompt

# ─── Config ────────────────────────────────────────────────────────────────────
SPEC_PATH        = os.path.join(CONFIGS_DIR, 'project_specs', 'ambient_app.md')
CLAUDE_SESSIONS  = os.path.join(os.path.expanduser('~'), '.claude', 'projects', f'-home-{os.environ.get("USER", "user")}')
ENV_FILE         = JANE_BRIDGE_ENV
LOG_FILE         = AMBIENT_HEARTBEAT_LOG
RESEARCH_CACHE   = os.path.join(CONFIGS_DIR, 'project_specs', 'ambient_research_cache.json')
IDLE_MINUTES     = 20   # Skip if Claude was active within this many minutes
MODEL            = os.environ.get("HEARTBEAT_MODEL", "gpt-4o-mini")

# Topics tied to spec sections — keyed by a stable ID.
# Each topic has a search query and the spec heading it belongs to.
RESEARCH_TOPICS = {
    "flutter_vs_alternatives": {
        "heading": "## 2. Framework Recommendation: Flutter",
        "query": "Flutter vs React Native vs Tauri 2024 cross-platform desktop Android performance comparison",
        "prompt": "Summarize the current (2025) state of cross-platform app frameworks for Linux, Windows, macOS, and Android. Compare Flutter, React Native, and Tauri v2 on: performance, single codebase support, desktop Linux maturity, developer experience, and community. Give a concrete recommendation.",
    },
    "flutter_chat_ui": {
        "heading": "### 3.2 Required UI Components",
        "query": "Flutter chat UI library markdown code highlighting streaming text 2024",
        "prompt": "What are the best Flutter packages for building a ChatGPT-like chat UI? Cover: markdown rendering (flutter_markdown vs others), code syntax highlighting, streaming/typewriter text animation, and scrollable chat list performance. Give specific package names and versions.",
    },
    "adk_sse_streaming": {
        "heading": "### 4.3 Streaming Responses",
        "query": "Google ADK agent development kit SSE streaming endpoint FastAPI response streaming 2024",
        "prompt": "How do you add Server-Sent Events (SSE) streaming to a Google ADK (Agent Development Kit) web server? What's the correct way to wrap the ADK /run endpoint to stream tokens to a Flutter client? Include relevant FastAPI/Starlette patterns.",
    },
    "xtts_v2_setup": {
        "heading": "#### Option A: XTTS v2 (Coqui — Local)",
        "query": "XTTS v2 Coqui TTS FastAPI server setup voice cloning GPU latency 2024",
        "prompt": "Provide a practical guide for running XTTS v2 as a persistent FastAPI service for low-latency TTS. Include: installation steps, how to run as a server, voice cloning from a sample, expected GPU latency per sentence, and Python client code to call it. Focus on production-ready setup.",
    },
    "f5_tts_comparison": {
        "heading": "#### Option B: F5-TTS (Local)",
        "query": "F5-TTS vs XTTS v2 quality latency benchmark local TTS 2025",
        "prompt": "Compare F5-TTS and XTTS v2 on: voice naturalness, GPU latency, ease of setup, voice cloning quality, and active maintenance. Which is better for a personal voice assistant in 2025?",
    },
    "faster_whisper_vad": {
        "heading": "### 6.2 Components",
        "query": "faster-whisper silero-vad real-time speech recognition Python pipeline 2024",
        "prompt": "Describe a production-ready real-time STT pipeline using faster-whisper + silero-vad in Python. Include: VAD setup for detecting speech start/end, streaming audio from microphone, whisper model selection for low latency, and handling the STT result. Give concrete code patterns.",
    },
    "flutter_audio_recording": {
        "heading": "### Phase 3 — Conversational Voice Mode",
        "query": "Flutter microphone audio recording real-time stream Android Linux 2024",
        "prompt": "What Flutter packages handle real-time microphone audio capture on Android and Linux desktop simultaneously? Compare: record, flutter_sound, and microphone_stream packages. How do you stream raw PCM audio from Flutter to a Python VAD/STT server?",
    },
    "tailscale_self_hosted": {
        "heading": "**Mode 3 — Remote (away from home):**",
        "query": "Tailscale self-hosted headscale mobile app remote access home server 2024",
        "prompt": "Explain how to set up Tailscale (or Headscale for fully self-hosted) to securely access a home Linux server from an Android app and Windows laptop. What configuration is needed? Does the Flutter app need any special handling for Tailscale IPs?",
    },
    "flutter_sqflite": {
        "heading": "### Phase 1 — Core Chat (MVP)",
        "query": "Flutter sqflite sqlite chat history local storage Android Linux desktop 2024",
        "prompt": "Best practice for persisting chat conversation history in Flutter using sqflite on both Android and Linux desktop. Include: schema for messages + conversations tables, how to handle migrations, and efficient pagination for loading old messages.",
    },
    "flutter_beautiful_ui_design": {
        "heading": "### 4.2 Visual Theme",
        "query": "Flutter beautiful dark UI design chat app animations micro-interactions 2025",
        "prompt": "How do top Flutter apps achieve a premium, polished look and feel? Focus on: smooth page/message transitions, micro-interactions (button press feedback, send animation, typing indicator), message bubble design details, and overall dark theme polish comparable to Claude.ai or Linear. List specific Flutter packages and techniques with code examples.",
    },
    "flutter_animations_motion": {
        "heading": "### 4.2 Visual Theme",
        "query": "Flutter implicit explicit animations motion design best practices beautiful UI 2025",
        "prompt": "What are the best patterns for adding delightful motion to a Flutter chat app without hurting performance? Cover: AnimatedList for message insertion, Hero transitions, shimmer loading states, staggered animations for sidebar items, and the flutter_animate package. Give concrete code patterns and explain when to use implicit vs explicit animations.",
    },
    "ai_chat_ui_inspiration": {
        "heading": "### 4.1 Layout",
        "query": "AI chat app beautiful UI design inspiration Claude ChatGPT Perplexity dark theme 2025",
        "prompt": "Analyze the UI design of the best AI chat apps in 2025 (Claude.ai, ChatGPT, Perplexity, Linear). What specific design decisions make them feel premium and beautiful? List: typography choices, spacing/padding rhythm, color palette construction, subtle effects (blur, gradient, glow), hover/focus states, and any standout interaction patterns that could be replicated in Flutter.",
    },
}

# ─── Logging ───────────────────────────────────────────────────────────────────
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("AmbientHeartbeat")


# ─── Idle Detection ─────────────────────────────────────────────────────────────
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


# ─── Research Cache ────────────────────────────────────────────────────────────
def load_cache() -> dict:
    if os.path.exists(RESEARCH_CACHE):
        with open(RESEARCH_CACHE, "r") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    with open(RESEARCH_CACHE, "w") as f:
        json.dump(cache, f, indent=2)


def is_stale(cache: dict, topic_id: str, days: int = 7) -> bool:
    """Return True if the topic hasn't been researched in `days` days."""
    if topic_id not in cache:
        return True
    last = datetime.datetime.fromisoformat(cache[topic_id]["last_researched"])
    return (datetime.datetime.now() - last).days >= days


# ─── Web Search ───────────────────────────────────────────────────────────────
def web_search(query: str, max_results: int = 6) -> str:
    """Search the web via Tavily (with DuckDuckGo fallback)."""
    return _web_search(query, max_results)


# ─── Automation Synthesis ─────────────────────────────────────────────────────
def synthesize_with_automation(topic_prompt: str, web_data: str) -> str:
    """Use the shared automation runner to synthesize web search data into a research note."""
    system = (
        "You are a Senior Technical Researcher helping refine the spec for 'Project Ambient', "
        "a cross-platform Flutter app (Linux, Windows, Android, macOS) that connects to a local "
        "Google ADK AI server (Amber). Your job is to produce a concise, actionable technical note "
        "with concrete recommendations, package names, version numbers, and code patterns where relevant. "
        "Format your response in clean Markdown."
    )

    web_section = f"\n\nWeb Search Data:\n{web_data[:8000]}" if web_data else ""
    full_prompt = f"{system}\n\n{topic_prompt}{web_section}"

    try:
        return run_automation_prompt(full_prompt, timeout_seconds=120)
    except AutomationError as e:
        logger.error(f"Automation synthesis failed: {e}")
        return ""


# ─── Spec Updater ─────────────────────────────────────────────────────────────
def append_research_to_spec(heading: str, topic_id: str, note: str):
    """Inject a research note block under the matching heading in the spec."""
    with open(SPEC_PATH, "r") as f:
        content = f.read()

    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    block = (
        f"\n\n> **🔬 Research Note ({date_str} — auto):**\n"
        + "\n".join(f"> {line}" for line in note.splitlines())
    )

    # Find the heading and inject after it (before the next same-level heading)
    if heading in content:
        insert_pos = content.index(heading) + len(heading)
        # Avoid inserting duplicate notes for the same topic on the same day
        marker = f"Research Note ({date_str} — auto)"
        if marker not in content[insert_pos : insert_pos + 2000]:
            content = content[:insert_pos] + block + content[insert_pos:]
            with open(SPEC_PATH, "w") as f:
                f.write(content)
            logger.info(f"Injected research note for '{topic_id}' under '{heading[:60]}'")
        else:
            logger.info(f"Research note for '{topic_id}' already present today — skipping.")
    else:
        logger.warning(f"Heading not found in spec: '{heading[:60]}' — appending to end.")
        with open(SPEC_PATH, "a") as f:
            f.write(f"\n\n---\n\n### Research: {topic_id} ({date_str})\n{note}")


# ─── Implementation Readiness Check ──────────────────────────────────────────
def check_implementation_readiness() -> list[str]:
    """
    Parse the progress tracker in the spec. Return a list of unchecked Phase 1
    tasks that appear implementable (i.e., no open questions blocking them).
    Only considers tasks as ready if ALL open questions (Section 8) are answered.
    """
    with open(SPEC_PATH, "r") as f:
        content = f.read()

    # Check if any open questions remain unanswered (contain "?" and not struck through)
    questions_section = ""
    if "## 8. Open Questions" in content:
        questions_section = content.split("## 8. Open Questions")[1].split("\n## ")[0]

    unanswered = [
        line for line in questions_section.splitlines()
        if line.strip().startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "10.",
                                    "11.", "12.", "13.", "14.", "15.", "16.", "17.", "18."))
        and "?" in line
        and "~~" not in line  # not struck through
    ]

    if unanswered:
        logger.info(f"{len(unanswered)} open questions remain — implementation deferred.")
        return []

    # Find unchecked Phase 1 tasks
    ready = []
    in_phase1 = False
    for line in content.splitlines():
        if "### Phase 1" in line:
            in_phase1 = True
        elif line.startswith("### Phase"):
            in_phase1 = False
        if in_phase1 and line.strip().startswith("- [ ]"):
            task = line.strip()[6:].strip()
            ready.append(task)

    logger.info(f"Implementation-ready Phase 1 tasks: {len(ready)}")
    return ready


def implement_task(task: str) -> str:
    """
    Call the shared automation runner to implement a specific task from the spec.
    Returns the output (summary of what was done).
    """
    spec_excerpt = ""
    try:
        with open(SPEC_PATH, "r") as f:
            spec_excerpt = f.read()[:6000]  # Give the automation runner context from the spec
    except Exception:
        pass

    prompt = (
        f"You are implementing a task for 'Project Ambient', a cross-platform Flutter app "
        f"(Linux, Windows, Android, macOS) that provides a ChatGPT-like UI for talking to the "
        f"Amber AI agent (Google ADK server at localhost:8000).\n\n"
        f"Task to implement: {task}\n\n"
        f"Project spec context:\n{spec_excerpt}\n\n"
        f"Implement this task now. Create or modify the necessary files. "
        f"After completing, report what was done in 2-3 sentences."
    )

    try:
        output = run_automation_prompt(prompt, timeout_seconds=300)
        logger.info(f"Implemented: '{task}'")
        return output
    except AutomationError as e:
        logger.error(f"Implementation call failed: {e}")
        return ""


def mark_task_complete(task: str):
    """Flip `- [ ] task` to `- [x] task` in the spec."""
    with open(SPEC_PATH, "r") as f:
        content = f.read()
    updated = content.replace(f"- [ ] {task}", f"- [x] {task}")
    if updated != content:
        with open(SPEC_PATH, "w") as f:
            f.write(updated)
        logger.info(f"Marked complete in spec: '{task}'")


# ─── Discord Notification ─────────────────────────────────────────────────────
from agent_skills.cron_utils import send_discord


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    logger.info("═══ Ambient Heartbeat starting ═══")

    # 0. Load gate: wait until CPU/memory is acceptable
    try:
        from agent_skills.system_load import wait_until_safe
        if not wait_until_safe(max_wait_minutes=10):
            logger.info("System busy — skipping heartbeat this cycle.")
            return
    except Exception:
        pass

    # 1. Idle check (bypassed during sleep hours 2-6 AM local time)
    import datetime as _dt
    _now_hour = _dt.datetime.now().hour
    _is_sleep_window = 2 <= _now_hour < 6
    if is_user_active() and not _is_sleep_window:
        logger.info("User is active — exiting without running.")
        return
    if _is_sleep_window:
        logger.info(f"Sleep-window override active (hour={_now_hour}) — running regardless of activity.")

    cache = load_cache()
    research_done = []
    implementations_done = []

    # 3. Research loop
    for topic_id, topic in RESEARCH_TOPICS.items():
        if not is_stale(cache, topic_id, days=7):
            logger.info(f"Topic '{topic_id}' researched recently — skipping.")
            continue

        logger.info(f"Researching: {topic_id}")

        # Web search
        web_data = web_search(topic["query"])
        logger.info(f"  → Got {len(web_data)} chars of web data")

        # Synthesize
        note = synthesize_with_automation(topic["prompt"], web_data)
        if not note:
            logger.warning(f"  → No synthesis output for '{topic_id}'")
            continue

        # Inject into spec
        append_research_to_spec(topic["heading"], topic_id, note)

        # Update cache
        cache[topic_id] = {
            "last_researched": datetime.datetime.now().isoformat(),
            "note_length": len(note),
        }
        save_cache(cache)
        research_done.append(topic_id)

        # Brief pause between Qwen calls to avoid overloading
        time.sleep(3)

    # 4. Implementation readiness check
    ready_tasks = check_implementation_readiness()
    for task in ready_tasks[:3]:  # Max 3 tasks per run to avoid runaway execution
        logger.info(f"Implementing: {task}")
        result = implement_task(task)
        if result:
            mark_task_complete(task)
            implementations_done.append(f"✅ {task}")
        else:
            logger.warning(f"Implementation returned empty for: {task}")

    # 5. Discord summary
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if research_done or implementations_done:
        lines = [f"🔁 **Ambient Heartbeat** ({date_str})"]
        if research_done:
            lines.append(f"\n📚 **Researched {len(research_done)} topics:**")
            for t in research_done:
                lines.append(f"  • {t.replace('_', ' ')}")
        if implementations_done:
            lines.append(f"\n🔨 **Implemented:**")
            for t in implementations_done:
                lines.append(f"  {t}")
        lines.append("\n_Spec updated. Check `ambient_app.md` for new research notes._")
        send_discord("\n".join(lines))
    else:
        logger.info("Nothing new to research or implement this run.")

    logger.info("═══ Ambient Heartbeat complete ═══")


if __name__ == "__main__":
    main()
