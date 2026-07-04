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
ENTRY_START_RE = re.compile(r"^(\d+)\.\s*")


def prompt_entry_chunks(content: str) -> list[str]:
    return [chunk.strip() for chunk in re.split(r"\n(?=\d+\.\s)", content) if chunk.strip()]


def parse_status_prefix(text: str) -> tuple[str, str]:
    status = "pending"
    inline_text = text
    for tag, parsed_status in STATUS_TAGS.items():
        if text.startswith(tag):
            status = parsed_status
            inline_text = text[len(tag):].strip()
            break
    return status, inline_text


def prompt_body_lines(inline_text: str, following_lines: list[str]) -> list[str]:
    body_lines = []
    if inline_text:
        body_lines.append(inline_text)
    for line in following_lines:
        if line.startswith("   -") or line.startswith("\t-"):
            break
        if line.strip() == "---":
            break
        body_lines.append(line)
    return body_lines


def parse_prompt_chunk(chunk: str) -> dict | None:
    lines = chunk.splitlines()
    if not lines:
        return None
    first = lines[0].strip()
    match = ENTRY_START_RE.match(first)
    if not match:
        return None

    idx = int(match.group(1))
    status, inline_text = parse_status_prefix(first[match.end():])
    text = "\n".join(prompt_body_lines(inline_text, lines[1:])).strip()
    return {"index": idx, "text": text, "status": status}


def parse_prompt_list(content: str) -> list[dict]:
    """
    Parse prompt_list.md into a list of {index, text, status} dicts.

    Format per entry:
        N. [status]
        Verbatim prompt text (possibly multiline)

           - sub-bullet outcome/note
    """
    prompts = []
    for chunk in prompt_entry_chunks(content):
        parsed = parse_prompt_chunk(chunk)
        if parsed is not None:
            prompts.append(parsed)
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


def queue_prompt_run_text(prompt_text: str, is_retry: bool) -> str:
    if not is_retry:
        return prompt_text
    return (
        "This prompt previously ran but was marked INCOMPLETE (empty or failed result). "
        "Please investigate why it may have failed, then complete it properly.\n\n"
        f"Original prompt:\n{prompt_text}"
    )


def prompt_result_status(success: bool) -> str:
    return "complete" if success else "incomplete"


def prompt_result_note(result: str, max_chars: int = 200) -> str:
    return result[:max_chars].replace("\n", " ").strip()


def prompt_failure_detail(result: str) -> str:
    return (
        result.strip()
        if result.strip()
        else "_(No output returned — possible timeout, permission error, or execution failure.)_"
    )


def prompt_result_discord_message(
    index: int,
    prompt_text: str,
    result: str,
    success: bool,
) -> str:
    if success:
        return (
            f"✅ **Prompt #{index} COMPLETE**\n\n"
            f"**Result:**\n{result}"
        )
    return (
        f"⚠️ **Prompt #{index} INCOMPLETE**\n\n"
        f"**Prompt was:**\n{prompt_summary(prompt_text)}\n\n"
        f"**What went wrong:**\n{prompt_failure_detail(result)}\n\n"
        f"_Review the above and edit the prompt or fix the underlying issue before the next retry._"
    )
