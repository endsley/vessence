"""Pure helpers for qwen_orchestrator.py."""
from __future__ import annotations


def package_name_from_requirement(line: str) -> str | None:
    cleaned = line.split("#")[0].strip()
    if not cleaned:
        return None
    return cleaned.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0].strip()


def search_name_for_package(package_name: str) -> str:
    return package_name.replace("-", "_")


def harvested_context_section(pattern: str, stdout: str, *, max_lines: int = 5) -> str:
    if not stdout:
        return ""
    lines = stdout.splitlines()[:max_lines]
    return f"--- Matches for '{pattern}' ---\n" + "\n".join(lines) + "\n\n"


def finalized_harvested_context(harvested_context: str) -> str:
    return harvested_context or "No idiomatic context harvested."
