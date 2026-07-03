"""Pure helpers for doc_drift_auditor.py."""

from __future__ import annotations

import ast
import re
from pathlib import Path


SCRIPT_PATH_RE = re.compile(
    r"\*\*Script Path:\*\*\s*`[^`]*?/([^/`]+\.(?:py|sh))`"
)

CRON_COMMAND_PREFIXES = ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "@")


def extract_class_map_keys(source: str) -> set[str]:
    """Return canonical class keys from stage1_classifier.py's _CLASS_MAP."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "_CLASS_MAP" for t in node.targets):
            continue
        try:
            class_map = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            return set()
        if not isinstance(class_map, dict):
            return set()
        return {
            str(key).upper().replace(" ", "_")
            for key in class_map
            if isinstance(key, str)
        }
    return set()


def extract_doc_table_classes(doc_text: str) -> set[str]:
    """Return uppercase class keys from the documented class table."""
    classes: set[str] = set()
    in_class_table = False
    for line in doc_text.splitlines():
        stripped = line.strip()
        if in_class_table and not stripped:
            break
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip().strip("`") for cell in stripped.strip("|").split("|")]
        if not cells:
            continue
        first_cell = cells[0].lower()
        if first_cell in {"class", "chromadb name"}:
            in_class_table = True
            continue
        if not in_class_table:
            continue
        candidate = cells[0]
        if re.fullmatch(r"[A-Z][A-Z0-9_]{3,}", candidate):
            classes.add(candidate)
    return classes


def extract_active_cron_script_names(cron_lines: list[str]) -> set[str]:
    actual_scripts = set()
    for line in cron_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped and not stripped.startswith(CRON_COMMAND_PREFIXES):
            continue
        for token in stripped.split():
            if token.endswith(".py") or token.endswith(".sh"):
                actual_scripts.add(Path(token).name)
    return actual_scripts


def extract_documented_cron_script_names(doc_text: str) -> set[str]:
    return set(SCRIPT_PATH_RE.findall(doc_text))


def extract_inactive_documented_cron_script_names(doc_text: str) -> set[str]:
    inactive_scripts: set[str] = set()
    sections = re.split(r"^##\s+", doc_text, flags=re.MULTILINE)
    for section in sections:
        if not section.strip():
            continue
        header = section.splitlines()[0]
        inactive_section = any(
            key in header
            for key in ("Removed Jobs", "Non-Cron Scheduled Scripts")
        )
        disabled_entry = any(
            key in header for key in ("DISABLED", "COMMENTED OUT", "Paused:")
        )
        if inactive_section or disabled_entry:
            inactive_scripts |= extract_documented_cron_script_names(section)
    return inactive_scripts


def build_drift_report(changes: list[str], warnings: list[str], timestamp: str) -> str:
    body = [f"# Doc Drift Report — {timestamp}\n"]
    if changes:
        body.append("## Auto-fixed\n")
        body.extend(changes)
        body.append("")
    if warnings:
        body.append("## Needs human review\n")
        body.extend(f"- {warning}" for warning in warnings)
        body.append("")
    if not changes and not warnings:
        body.append("All docs in sync. ✅\n")
    return "\n".join(body) + "\n"


def drift_vocal_summary_kwargs(changes: list[str], warnings: list[str]) -> dict:
    if not changes and not warnings:
        return {
            "job": "Doc Drift Audit",
            "summary": (
                "I checked that docs like the cron registry, skill "
                "registry, and pipeline class map still match the code. "
                "Everything lined up — no drift."
            ),
            "severity": "info",
        }

    n_fix = len(changes)
    n_warn = len(warnings)
    return {
        "job": "Doc Drift Audit",
        "what_was_wrong": (
            f"I found {n_warn} spot{'s' if n_warn != 1 else ''} where "
            f"docs drifted from the code"
        ) if n_warn else (
            f"I found {n_fix} doc{'s' if n_fix != 1 else ''} that needed "
            "small fixes"
        ),
        "why_it_mattered": (
            "Stale docs make it easy to ship changes that break "
            "undocumented behavior"
        ),
        "what_was_done": (
            f"I auto-fixed {n_fix} and flagged the rest in the doc "
            f"drift report for you to review"
        ) if n_fix else (
            "I flagged them in the doc drift report for your review — "
            "the ambiguous ones need a human call"
        ),
        "severity": "medium" if warnings else "info",
    }
