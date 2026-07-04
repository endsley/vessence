"""Interview text helpers for the Vessence essence builder."""

from __future__ import annotations

from collections.abc import Iterable


SECTION_DISPLAY_NAMES = (
    "Identity & Personality",
    "Knowledge Base",
    "Custom Functions",
    "Shared Skills",
    "UI Paradigm",
    "Interaction Patterns",
    "Triggers & Automations",
    "Capabilities Declaration",
    "Preferred Model",
    "Permissions & Credentials",
    "User Data Layer",
    "Review & Approve",
)


def section_display_name(index: int) -> str:
    return SECTION_DISPLAY_NAMES[index] if 0 <= index < len(SECTION_DISPLAY_NAMES) else f"Section {index}"


def numbered_questions(questions: Iterable[str], start: int = 1) -> list[str]:
    return [f"{i}. {question}" for i, question in enumerate(questions, start)]


def format_questions(interview_questions: dict[int, dict], section_index: int, include_optional: bool = False) -> str:
    q = interview_questions[section_index]
    lines = numbered_questions(q["required_questions"])
    if include_optional and q["optional_questions"]:
        lines.append("\nOptional — answer these if relevant:")
        lines.extend(numbered_questions(q["optional_questions"], len(q["required_questions"]) + 1))
    return "\n".join(lines)


def section_intro(section_names: list[str], interview_questions: dict[int, dict], section_index: int) -> str:
    name = section_display_name(section_index)
    total = len(section_names)
    return (
        f"--- **Section {section_index + 1}/{total}: {name}** ---\n\n"
        f"{format_questions(interview_questions, section_index, include_optional=True)}"
    )


def extract_essence_name(answer: str) -> str:
    for line in answer.split("\n"):
        lower = line.lower()
        if "name" in lower or "called" in lower or "essence" in lower:
            for quote in ('"', "'"):
                if quote in line:
                    parts = line.split(quote)
                    if len(parts) >= 3:
                        return parts[1].strip()
            if ":" in line:
                return line.split(":", 1)[1].strip()
    return answer[:60].strip()


def progress_summary(
    section_names: list[str],
    completed_sections: Iterable[int],
    current_section: int,
) -> str:
    total = len(section_names)
    completed = set(completed_sections)
    done = len(completed)
    parts = []
    for i in range(total):
        name = section_display_name(i)
        if i in completed:
            parts.append(f"{name} done")
    next_name = section_display_name(current_section) if current_section < total else "None"
    done_str = ", ".join(parts) if parts else "None yet"
    return f"Sections completed: {done}/{total} — {done_str}, next: {next_name}"


def spec_document(section_names: list[str], answers: dict[str, str], essence_name: str) -> str:
    lines = [
        f"# Essence Spec: {essence_name}",
        "",
    ]
    for i, section_name in enumerate(section_names):
        if section_name == "review_approve":
            continue
        display = section_display_name(i)
        answer = answers.get(section_name, "_Not yet answered._")
        lines.append(f"## {i + 1}. {display}")
        lines.append("")
        lines.append(answer)
        lines.append("")
    return "\n".join(lines)
