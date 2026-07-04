"""Pure helpers for pipeline_audit_100.py."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any


SYSTEM_XML_RE = re.compile(
    r"<(?:jane_architecture|class_protocol|memory_verify|verify_first|standing_brain_context)"
    r"[^>]*>[\s\S]*?</(?:jane_architecture|class_protocol|memory_verify|verify_first|standing_brain_context)>\s*",
)
CONV_STATE_RE = re.compile(
    r"\[CURRENT CONVERSATION STATE\][\s\S]*?\[END CURRENT CONVERSATION STATE\]\s*",
)


def strip_system_context(message: str) -> str:
    cleaned = SYSTEM_XML_RE.sub("", message)
    cleaned = CONV_STATE_RE.sub("", cleaned)
    return cleaned.strip()


def recent_prompt_rows_from_jsonl(lines: Iterable[str], n: int) -> list[dict[str, str]]:
    rows = []
    for line in lines:
        try:
            data = json.loads(line)
            message = (data.get("message") or "").strip()
            if not message:
                continue
            message = strip_system_context(message)
            if len(message) < 3:
                continue
            if message.startswith("[") or message.startswith("("):
                continue
            rows.append({"prompt": message, "ts": data.get("timestamp", "")})
        except Exception:
            continue

    seen = set()
    unique = []
    for row in rows:
        if row["prompt"] in seen:
            continue
        seen.add(row["prompt"])
        unique.append(row)
    return unique[-n:]


def summarize_pipeline_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    classification = None
    stage = None
    response_text = ""
    ack_text = None
    tool_calls = []

    for event in events:
        event_type = event.get("type")
        data = event.get("data")
        if event_type == "ack":
            ack_text = data
        elif event_type == "client_tool_call":
            try:
                tool_call = json.loads(data) if isinstance(data, str) else data
                tool_calls.append(tool_call.get("tool", "?"))
            except Exception:
                pass
        elif event_type == "delta":
            response_text = data if isinstance(data, str) else response_text
        elif event_type == "done":
            response_text = data if isinstance(data, str) else response_text

        if "classification" in event:
            classification = event["classification"]
        if "stage" in event:
            stage = event["stage"]

    if not stage:
        if any(event.get("type") == "start" for event in events):
            stage = "stage3"
        elif tool_calls or response_text:
            stage = "stage2"

    return {
        "classification": classification,
        "stage": stage,
        "response": response_text[:500],
        "ack": ack_text,
        "tool_calls": tool_calls,
        "events": events,
    }


def parse_judge_response(raw: str) -> dict[str, Any]:
    out: dict[str, Any] = {"raw": raw}
    for line in raw.splitlines():
        match = re.match(r"CORRECT_CLASS:\s*(.+)", line, re.IGNORECASE)
        if match:
            out["correct_class"] = match.group(1).strip().lower()
        match = re.match(r"CLASSIFICATION_OK:\s*(yes|no)", line, re.IGNORECASE)
        if match:
            out["classification_ok"] = match.group(1).lower() == "yes"
        match = re.match(r"RESPONSE_OK:\s*(yes|no)", line, re.IGNORECASE)
        if match:
            out["response_ok"] = match.group(1).lower() == "yes"
    return out


def build_judge_prompt(
    prompt: str,
    result: dict[str, Any],
    known_classes: list[str],
) -> str:
    return f"""You are auditing Jane's 3-stage pipeline. Decide if the pipeline handled this prompt correctly.

USER PROMPT: {prompt}

PIPELINE OUTPUT:
- Classification: {result.get("classification", "?")}
- Stage: {result.get("stage", "?")}
- Ack to user: {result.get("ack") or "(none)"}
- Tool calls: {result.get("tool_calls") or "(none)"}
- Response text: {result.get("response", "")[:300]}

Evaluate:
1. Was the Stage 1 classification correct? Pick the ideal class from:
   {", ".join(known_classes)}
2. Did Stage 2/3 produce a useful response that actually answers the prompt?

Output EXACTLY this format (3 lines, nothing else):
CORRECT_CLASS: <one of the classes above>
CLASSIFICATION_OK: yes | no
RESPONSE_OK: yes | no
"""


def _most_common_items(counts: Any) -> list[tuple[str, int]]:
    if hasattr(counts, "most_common"):
        return list(counts.most_common())
    return sorted(counts.items(), key=lambda item: item[1], reverse=True)


def count_section_lines(title: str, counts: Any, *, line_formatter=None) -> list[str]:
    formatter = line_formatter or (lambda key, count: f"- {key}: {count}")
    lines = [f"## {title}"]
    for key, count in _most_common_items(counts):
        lines.append(formatter(key, count))
    lines.append("")
    return lines


def classification_failure_table_lines(
    classification_failures: list[dict[str, Any]],
    *,
    limit: int = 30,
) -> list[str]:
    if not classification_failures:
        return []
    lines = [
        "## Classification failures (top 30)",
        "| Prompt | Got | Should be |",
        "|---|---|---|",
    ]
    for failure in classification_failures[:limit]:
        prompt = failure["prompt"][:80].replace("|", "\\|")
        lines.append(f"| {prompt} | {failure['got']} | {failure['should_be']} |")
    lines.append("")
    return lines


def response_failure_lines(
    response_failures: list[dict[str, Any]],
    *,
    limit: int = 20,
) -> list[str]:
    if not response_failures:
        return []
    lines = ["## Response failures (top 20) — usually need code changes"]
    for failure in response_failures[:limit]:
        prompt = failure["prompt"][:80].replace("|", "\\|")
        lines.append(
            f"- **{prompt}** ({failure['classification']}/{failure['stage']}): {failure['response'][:150]}"
        )
    lines.append("")
    return lines


def build_pipeline_audit_report_markdown(
    *,
    started: Any,
    prompt_count: int,
    elapsed_seconds: float,
    stage_counts: Any,
    class_counts: Any,
    classification_failures: list[dict[str, Any]],
    response_failures: list[dict[str, Any]],
    fixes_applied: int,
    fixes_by_class: Any,
) -> str:
    report_lines = [
        f"# Pipeline Audit Report — {started.strftime('%Y-%m-%d %H:%M')}",
        "",
        f"- Prompts audited: **{prompt_count}**",
        f"- Elapsed: {elapsed_seconds:.0f}s",
        f"- Classification failures: **{len(classification_failures)}**",
        f"- Response failures: **{len(response_failures)}**",
        f"- Auto-fixes applied (exemplars added): **{fixes_applied}**",
        "",
    ]
    report_lines.extend(count_section_lines("Stage breakdown", stage_counts))
    report_lines.extend(count_section_lines("Classification breakdown", class_counts))
    if fixes_by_class:
        report_lines.extend(
            count_section_lines(
                "Self-correct fixes by class",
                fixes_by_class,
                line_formatter=lambda cls, count: f"- {cls}: +{count} exemplars",
            )
        )
    report_lines.extend(classification_failure_table_lines(classification_failures))
    report_lines.extend(response_failure_lines(response_failures))

    return "\n".join(report_lines)
