"""Code-memory verification policy and prompt builders."""

from __future__ import annotations

import re


CODE_INDICATOR_RE = re.compile(
    r"(\.py\b|handler|classifier|cron|Stage [123]|Ollama|pipeline|"
    r"ChromaDB|model|endpoint|/api/|jane_web|agent_skills|intent_classifier|"
    r"configs/|\.env|keep_alive|VRAM|qwen|gemma|server|restart|service)",
    re.IGNORECASE,
)


def is_code_memory(doc: str) -> bool:
    """Return True if a memory references Vessence internals."""
    return bool(doc and CODE_INDICATOR_RE.search(doc))


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
