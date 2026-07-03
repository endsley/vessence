"""Prompt helpers for audit_auto_fixer.py."""
from __future__ import annotations

from pathlib import Path


AUDIT_FIX_ANALYSIS_PROMPT_TEMPLATE = """\
You are a code maintenance assistant. Analyze this audit report and produce a JSON array of issues that can be SAFELY auto-fixed.

RULES:
- Only include issues where you can specify an EXACT file path, search text, and replacement text
- The file path must be absolute (starting with {vessence_home}/)
- NEVER include crontab modifications
- NEVER include file deletions
- Focus on: wrong paths in docs, stale descriptions, missing imports, wrong variable names
- Category must be one of: "doc_update", "code_fix", "skip"
- Use "skip" for anything risky, ambiguous, or requiring human judgment
- For "skip" items, omit search_text and replacement_text
- Keep it conservative — better to skip than to break something

Output ONLY a JSON array. No markdown fences, no explanation.

Example format:
[
  {{
    "issue": "CRON_JOBS.md uses wrong path prefix",
    "category": "doc_update",
    "file": "{vessence_home}/configs/CRON_JOBS.md",
    "fix_description": "Replace old path prefix with correct one",
    "search_text": "old/wrong/path/",
    "replacement_text": "correct/path/"
  }},
  {{
    "issue": "Architecture change requires human review",
    "category": "skip",
    "file": "{vessence_home}/jane/config.py",
    "fix_description": "Needs human review — changes user-facing behavior"
  }}
]

AUDIT REPORT:
{report_text}
"""


def build_audit_fix_analysis_prompt(report_text: str, vessence_home: str | Path) -> str:
    return AUDIT_FIX_ANALYSIS_PROMPT_TEMPLATE.format(
        report_text=report_text,
        vessence_home=vessence_home,
    )
