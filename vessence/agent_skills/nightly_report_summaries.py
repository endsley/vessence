"""Text summarizers for nightly self-improvement reports."""
from __future__ import annotations

import re


def bullet(line: str) -> str:
    clean = re.sub(r"\s+", " ", line.strip())
    return f"- {clean}"


def first_matching_lines(text: str, patterns: tuple[str, ...], limit: int = 5) -> list[str]:
    matches: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if any(re.search(pattern, line, re.IGNORECASE) for pattern in patterns):
            matches.append(bullet(line))
        if len(matches) >= limit:
            break
    return matches


def extract_markdown_bullets(text: str, after_heading: str, limit: int = 5) -> list[str]:
    match = re.search(rf"^{re.escape(after_heading)}.*$", text, flags=re.MULTILINE)
    if not match:
        return []
    out: list[str] = []
    for raw in text[match.end():].splitlines():
        line = raw.strip()
        if line.startswith("## "):
            break
        if line.startswith("- "):
            out.append(bullet(line[2:]))
        if len(out) >= limit:
            break
    return out


def extract_field(text: str, field_name: str, limit: int = 4) -> list[str]:
    pattern = re.compile(rf"^\*\*{re.escape(field_name)}:\*\*\s*(.+)$", re.MULTILINE)
    return [bullet(m.group(1)) for m in pattern.finditer(text)][:limit]


def condense_tldr_items(
    items: list[str],
    skip_prefixes: tuple[str, ...] = (),
    *,
    limit: int = 3,
    max_chars: int = 160,
) -> list[str]:
    """Normalize bullets for the compact TL;DR report block."""
    out: list[str] = []
    for item in items:
        text = item.lstrip("- ").strip()
        if not text:
            continue
        if skip_prefixes and text.startswith(skip_prefixes):
            continue
        text = " ".join(text.split())
        if len(text) > max_chars:
            text = text[:max_chars - 3].rstrip() + "..."
        out.append(text)
        if len(out) >= limit:
            break
    return out


def summarize_dead_code(report: str, log_tail: str) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    improvements: list[str] = []
    for heading in (
        "Dead files — review needed",
        "Possibly-dead functions",
        "Duplicate function bodies",
    ):
        m = re.search(rf"## {re.escape(heading)} \(([^)]+)\)", report)
        if m:
            problems.append(bullet(f"{heading}: {m.group(1)}."))
    improvements.extend(first_matching_lines(
        log_tail,
        (r"auto-deleted", r"Done —"),
        limit=2,
    ))
    return problems, improvements


def summarize_pipeline(report: str, log_tail: str) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    improvements: list[str] = []
    for label in (
        "Prompts audited",
        "Classification failures",
        "Response failures",
        "Auto-fixes applied",
    ):
        m = re.search(rf"- {re.escape(label)}:\s*\*\*([^*]+)\*\*", report)
        if m:
            target = improvements if label == "Auto-fixes applied" else problems
            target.append(bullet(f"{label}: {m.group(1)}."))
    problems.extend(extract_markdown_bullets(report, "## Response failures", limit=4))
    improvements.extend(first_matching_lines(log_tail, (r"AUTO-FIX:", r"Added exemplar:"), limit=5))
    return problems, improvements


def summarize_doc_drift(report: str, log_tail: str) -> tuple[list[str], list[str]]:
    problems = extract_markdown_bullets(report, "## Needs human review", limit=8)
    improvements = first_matching_lines(
        log_tail,
        (r"auto-fix", r"updated", r"wrote", r"fixed"),
        limit=5,
    )
    return problems, improvements


def summarize_transcript_review(report: str, log_tail: str) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    improvements: list[str] = []
    severities = [
        sev.upper()
        for sev in re.findall(r"^## Issue \d+ \[([A-Z]+)\]", report, flags=re.MULTILINE | re.IGNORECASE)
    ]
    if severities:
        counts = {sev: severities.count(sev) for sev in sorted(set(severities))}
        summary = ", ".join(f"{count} {sev.lower()}" for sev, count in counts.items())
        problems.append(bullet(f"Transcript review found {len(severities)} issues: {summary}."))
    problems.extend(extract_field(report, "Problem", limit=4))
    improvements.extend(first_matching_lines(
        log_tail,
        (r"Report written", r"self_improve_log: recorded"),
        limit=3,
    ))
    return problems, improvements


def summarize_generic_log(log_tail: str) -> tuple[list[str], list[str]]:
    problems = first_matching_lines(
        log_tail,
        (r"\bERROR\b", r"\bWARNING\b", r"failed", r"timeout", r"crash"),
        limit=5,
    )
    improvements = first_matching_lines(
        log_tail,
        (r"\bDone\b", r"\bCommitted\b", r"\bPushed\b", r"\bWrote\b", r"\brecorded\b", r"\bcleaned\b"),
        limit=5,
    )
    return problems, improvements
