"""Code-memory verification policy and prompt builders."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any


CODE_INDICATOR_RE = re.compile(
    r"(\.py\b|handler|classifier|cron|Stage [123]|Ollama|pipeline|"
    r"ChromaDB|model|endpoint|/api/|jane_web|agent_skills|intent_classifier|"
    r"configs/|\.env|keep_alive|VRAM|qwen|gemma|server|restart|service)",
    re.IGNORECASE,
)
JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")


def is_code_memory(doc: str) -> bool:
    """Return True if a memory references Vessence internals."""
    return bool(doc and CODE_INDICATOR_RE.search(doc))


def code_memory_records_from_collection(
    collection_data: dict[str, list[Any]],
    *,
    is_code_memory_fn: Callable[[str], bool] = is_code_memory,
    max_text_chars: int = 500,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for doc_id, doc, meta in zip(
        collection_data.get("ids", []),
        collection_data.get("documents", []),
        collection_data.get("metadatas", []),
    ):
        if doc and is_code_memory_fn(doc):
            records.append({
                "id": doc_id,
                "text": doc[:max_text_chars],
                "topic": (meta or {}).get("topic", ""),
                "metadata": dict(meta or {}),
            })
    return records


def split_reverification_candidates(
    memories: list[dict[str, Any]],
    *,
    needs_reverification_fn: Callable[[dict[str, Any] | None], bool],
) -> tuple[list[dict[str, Any]], int]:
    eligible = []
    skipped_recent = 0
    for memory in memories:
        if needs_reverification_fn(memory.get("metadata")):
            eligible.append(memory)
        else:
            skipped_recent += 1
    return eligible, skipped_recent


def code_memory_verification_sort_key(memory: dict[str, Any]) -> str:
    value = (memory.get("metadata") or {}).get("code_verified_at")
    return value if value is not None else ""


def json_object_from_text(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    json_match = JSON_OBJECT_RE.search(raw)
    if not json_match:
        return None, "parse_fail"
    try:
        return json.loads(json_match.group()), None
    except json.JSONDecodeError:
        return None, "json_decode"


def code_verification_prompt(mem: dict) -> str:
    return f"""\
You are auditing ONE ChromaDB memory about the Vessence codebase.
CHECK whether it is still accurate by reading the actual code.

Verify:
- File paths mentioned → do they still exist?
- Function/class names → are they still present?
- Model names (qwen, gemma, etc.) → are they still used?
- Cron schedules → do they match the crontab?
- Architecture claims → do they match current code?

MEMORY (id={mem['id'][:12]}, topic={mem['topic']}):
{mem['text']}

Output EXACTLY one JSON object, no markdown fences:
{{"verdict": "ACCURATE|STALE|PARTIAL",
  "explanation": "what you found",
  "corrected_text": null or "the corrected memory text"}}
"""


def frontier_fix_prompt(mem: dict, codex_finding: dict) -> str:
    return f"""\
Codex flagged this ChromaDB memory as stale or partially wrong.

MEMORY (id={mem['id'][:12]}, topic={mem['topic']}):
{mem['text']}

CODEX VERDICT: {codex_finding.get('verdict', '?')}
CODEX EXPLANATION: {codex_finding.get('explanation', '?')}
CODEX SUGGESTED CORRECTION: {codex_finding.get('corrected_text') or '(none)'}

Your job:
1. READ THE ACTUAL CODE to confirm Codex is right. Do NOT trust blindly.
2. If stale, write a CORRECTED version. Keep the same topic and style.
3. If Codex was wrong, say so.

Output EXACTLY one JSON object, no markdown fences:
{{"action": "update|delete|keep",
  "corrected_text": "the fixed memory text" or null,
  "reason": "brief explanation"}}
"""


def code_verification_result(
    *,
    checked: int,
    stale: int,
    fixed: int,
    deleted: int,
    errors: int,
    skipped_recent: int,
    details: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "checked": checked,
        "stale": stale,
        "fixed": fixed,
        "deleted": deleted,
        "errors": errors,
        "skipped_recent": skipped_recent,
        "details": details,
    }


def code_verification_metadata(
    metadata: dict[str, Any] | None,
    *,
    status: str,
    verified_at: str,
    explanation: str = "",
) -> dict[str, Any]:
    meta = dict(metadata or {})
    meta["code_verified_at"] = verified_at
    meta["code_verification_status"] = status
    if explanation:
        meta["code_verification_note"] = explanation[:240]
    else:
        meta.pop("code_verification_note", None)
    return meta


def code_verification_summary_line(result: dict[str, Any]) -> str:
    return (
        f"Checked: {result['checked']} | Stale: {result['stale']} "
        f"| Fixed: {result['fixed']} | Deleted: {result['deleted']} "
        f"| Errors: {result['errors']} | Skipped recent: {result['skipped_recent']}"
    )


def code_verification_detail_line(detail: dict[str, Any]) -> str:
    return f"- **{detail['action'].upper()}** `{detail['id'][:12]}` — {detail['reason']}"


def code_verification_detail_lines(details: list[dict[str, Any]]) -> list[str]:
    return [
        code_verification_detail_line(detail)
        for detail in details
        if detail["action"] != "accurate"
    ]


def code_verification_report_markdown(
    *,
    timestamp: str,
    result: dict[str, Any],
) -> str:
    lines = [f"# Memory Verification Report — {timestamp}\n"]
    lines.append(f"{code_verification_summary_line(result)}\n")
    lines.extend(code_verification_detail_lines(result.get("details", [])))
    return "\n".join(lines) + "\n"
