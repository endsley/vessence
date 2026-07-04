"""Pure spec and cache rules for ambient_heartbeat.py."""
from __future__ import annotations

import datetime
import re


_OPEN_QUESTIONS_RE = re.compile(
    r"^##\s+(?:\d+\.\s*)?Open Questions\b.*$",
    re.MULTILINE | re.IGNORECASE,
)


def is_cache_stale(
    cache: dict,
    topic_id: str,
    *,
    days: int = 7,
    now: datetime.datetime | None = None,
) -> bool:
    if topic_id not in cache:
        return True
    last = datetime.datetime.fromisoformat(cache[topic_id]["last_researched"])
    current = now or datetime.datetime.now()
    return (current - last).days >= days


def heartbeat_sleep_window(
    now: datetime.datetime,
    *,
    start_hour: int = 1,
    end_hour: int = 7,
) -> bool:
    return start_hour <= now.hour < end_hour


def heartbeat_should_run(user_active: bool, now: datetime.datetime) -> bool:
    return not user_active or heartbeat_sleep_window(now)


def research_note_block(note: str, date_str: str) -> str:
    return (
        f"\n\n> **🔬 Research Note ({date_str} — auto):**\n"
        + "\n".join(f"> {line}" for line in note.splitlines())
    )


def apply_research_note_to_spec(
    content: str,
    *,
    heading: str,
    topic_id: str,
    note: str,
    date_str: str,
) -> tuple[str, str]:
    """
    Return (updated_content, action), where action is inserted, duplicate, or appended.
    """
    if heading in content:
        insert_pos = content.index(heading) + len(heading)
        marker = f"Research Note ({date_str} — auto)"
        if marker in content[insert_pos : insert_pos + 2000]:
            return content, "duplicate"
        updated = content[:insert_pos] + research_note_block(note, date_str) + content[insert_pos:]
        return updated, "inserted"

    updated = content + f"\n\n---\n\n### Research: {topic_id} ({date_str})\n{note}"
    return updated, "appended"


def unanswered_open_questions(content: str) -> list[str]:
    match = _OPEN_QUESTIONS_RE.search(content)
    if match is None:
        return []

    section_start = match.end()
    next_h2 = re.search(r"^##\s+", content[section_start:], re.MULTILINE)
    section_end = section_start + next_h2.start() if next_h2 else len(content)
    questions_section = content[section_start:section_end]

    return [
        line
        for line in questions_section.splitlines()
        if re.match(r"^\s*\d+\.", line)
        and "?" in line
        and "~~" not in line
    ]


def phase1_unchecked_tasks(content: str) -> list[str]:
    ready = []
    in_phase1 = False
    for line in content.splitlines():
        stripped = line.strip()
        if "### Phase 1" in line:
            in_phase1 = True
        elif stripped.startswith("### Phase"):
            in_phase1 = False
        if in_phase1 and stripped.startswith("- [ ]"):
            ready.append(stripped[6:].strip())
    return ready


def implementation_ready_tasks_from_text(content: str) -> list[str]:
    if unanswered_open_questions(content):
        return []
    return phase1_unchecked_tasks(content)


def heartbeat_discord_summary(
    *,
    research_done: list[str],
    implementations_done: list[str],
    generated_label: str,
) -> str:
    lines = [f"🔁 **Ambient Heartbeat** ({generated_label})"]
    if research_done:
        lines.append(f"\n📚 **Researched {len(research_done)} topics:**")
        for topic in research_done:
            lines.append(f"  • {topic.replace('_', ' ')}")
    if implementations_done:
        lines.append("\n🔨 **Implemented:**")
        for task in implementations_done:
            lines.append(f"  {task}")
    lines.append("\n_Spec updated. Check `ambient_app.md` for new research notes._")
    return "\n".join(lines)


def automation_synthesis_prompt(topic_prompt: str, web_data: str) -> str:
    system = (
        "You are a Senior Technical Researcher helping refine the spec for 'Project Ambient', "
        "a cross-platform Flutter app (Linux, Windows, Android, macOS) that connects to a local "
        "Google ADK AI server (Amber). Your job is to produce a concise, actionable technical note "
        "with concrete recommendations, package names, version numbers, and code patterns where relevant. "
        "Format your response in clean Markdown."
    )
    web_section = f"\n\nWeb Search Data:\n{web_data[:8000]}" if web_data else ""
    return f"{system}\n\n{topic_prompt}{web_section}"


def implementation_prompt(task: str, spec_excerpt: str) -> str:
    return (
        f"You are implementing a task for 'Project Ambient', a cross-platform Flutter app "
        f"(Linux, Windows, Android, macOS) that provides a ChatGPT-like UI for talking to the "
        f"Amber AI agent (Google ADK server at localhost:8000).\n\n"
        f"Task to implement: {task}\n\n"
        f"Project spec context:\n{spec_excerpt}\n\n"
        f"Implement this task now. Create or modify the necessary files. "
        f"After completing, report what was done in 2-3 sentences."
    )
