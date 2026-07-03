"""Pure Markdown document helpers for the prompt queue."""
from __future__ import annotations

import re


STATUS_TAGS = {
    "[completed]": "complete",
    "[COMPLETE]": "complete",
    "[incomplete]": "incomplete",
    "[INCOMPLETE]": "incomplete",
    "[new]": "pending",
}


def parse_prompt_list(content: str) -> list[dict]:
    """
    Parse prompt_list.md into a list of {index, text, status} dicts.

    Format per entry:
        N. [status]
        Verbatim prompt text (possibly multiline)

           - sub-bullet outcome/note
    """
    prompts = []
    chunks = re.split(r"\n(?=\d+\.\s)", content)
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        lines = chunk.splitlines()
        first = lines[0].strip()
        m = re.match(r"^(\d+)\.\s*", first)
        if not m:
            continue
        idx = int(m.group(1))
        after_num = first[m.end():]

        status = "pending"
        inline_text = after_num
        for tag, parsed_status in STATUS_TAGS.items():
            if after_num.startswith(tag):
                status = parsed_status
                inline_text = after_num[len(tag):].strip()
                break

        body_lines = []
        if inline_text:
            body_lines.append(inline_text)
        for line in lines[1:]:
            if line.startswith("   -") or line.startswith("\t-"):
                break
            if line.strip() == "---":
                break
            body_lines.append(line)

        text = "\n".join(body_lines).strip()
        prompts.append({"index": idx, "text": text, "status": status})

    return prompts


def status_tag(status: str) -> str:
    return {"complete": "[completed]", "incomplete": "[incomplete]"}.get(status, "[new]")


def render_prompt_status_update(content: str, index: int, status: str, note: str = "") -> str:
    tag = status_tag(status)
    entry_re = re.compile(rf"^{index}\.\s")

    lines = content.split("\n")
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if entry_re.match(line):
            new_lines.append(f"{index}. {tag}")
            i += 1
            body_lines = []
            while i < len(lines):
                candidate = lines[i]
                if re.match(r"^\d+\.\s", candidate):
                    break
                if candidate.startswith("   -") or candidate.startswith("\t-"):
                    i += 1
                    continue
                body_lines.append(candidate)
                i += 1
            while body_lines and not body_lines[-1].strip():
                body_lines.pop()
            new_lines.extend(body_lines)
            if note:
                new_lines.append("")
                prefix = "" if status == "complete" else "Attempted: "
                new_lines.append(f"   - {prefix}{note}")
            new_lines.append("")
        else:
            new_lines.append(line)
            i += 1

    return "\n".join(new_lines)


def delete_prompt_entry(content: str, index: int) -> str:
    entry_re = re.compile(rf"^{index}\.\s")
    lines = content.split("\n")
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if entry_re.match(line):
            i += 1
            while i < len(lines) and not re.match(r"^\d+\.\s", lines[i]):
                i += 1
        else:
            new_lines.append(line)
            i += 1

    while new_lines and not new_lines[-1].strip():
        new_lines.pop()
    new_lines.append("")
    return "\n".join(new_lines)


def renumber_prompt_entries(content: str) -> str:
    lines = content.split("\n")
    new_lines = []
    counter = 1
    for line in lines:
        if re.match(r"^(\d+)\.\s", line):
            line = re.sub(r"^\d+\.", f"{counter}.", line, count=1)
            counter += 1
        new_lines.append(line)
    return "\n".join(new_lines)


def render_completed_archive_section(completed_prompts: list[dict], archived_date: str) -> str:
    out = f"\n\n## Archived {archived_date}\n\n"
    for prompt in completed_prompts:
        out += f"### Prompt #{prompt['index']}\n\n{prompt['text']}\n\n---\n"
    return out


def remove_completed_prompt_entries(content: str, completed_indices: set[int]) -> str:
    chunks = re.split(r"\n(?=\d+\.\s)", content)
    kept = []
    for chunk in chunks:
        match = re.match(r"^(\d+)\.\s", chunk.strip())
        if match and int(match.group(1)) in completed_indices:
            continue
        kept.append(chunk)

    header_chunks = [chunk for chunk in kept if not re.match(r"^\d+\.\s", chunk.strip())]
    item_chunks = [chunk for chunk in kept if re.match(r"^\d+\.\s", chunk.strip())]
    renumbered = []
    for new_idx, chunk in enumerate(item_chunks, start=1):
        chunk = re.sub(r"^\d+\.", f"{new_idx}.", chunk.strip())
        renumbered.append(chunk)

    return "\n\n".join(header_chunks + renumbered).strip() + "\n"


def prompt_summary(text: str, max_chars: int = 400) -> str:
    """
    Return a readable summary of the prompt for notifications.
    Shows the full prompt up to max_chars so the user can recognize what's running.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    for sep in ("\n", ". ", "! ", "? "):
        idx = cut.rfind(sep)
        if idx > max_chars // 2:
            return cut[:idx + len(sep)].strip() + "\n_(prompt continues…)_"
    return cut.rstrip() + "…"
