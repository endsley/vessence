"""Deterministic helpers for Stage 3 verify-first context blocks."""

from __future__ import annotations

from typing import Any


def initial_evidence_metadata() -> dict[str, Any]:
    return {
        "required": False,
        "requires_code": False,
        "requires_memory": False,
        "memory_evidence": False,
        "memory_chars": 0,
        "memory_chars_after_dedup": 0,
        "architecture_context_chars": 0,
    }


def prepend_architecture_context(verify_block: str, architecture_context: str) -> str:
    if not architecture_context:
        return verify_block
    return (
        "<jane_architecture>\n"
        "Authoritative snapshot of Jane's system. Use this before "
        "guessing about architecture, cron jobs, or which file "
        "owns what. If you need detail beyond this summary, Read "
        "the specific configs/*.md file.\n\n"
        + architecture_context
        + "\n</jane_architecture>\n\n"
        + verify_block
    )


def append_required_memory_evidence(verify_block: str, memory_text: str) -> str:
    if not memory_text or not memory_text.strip():
        return verify_block
    return (
        verify_block
        + "\n\n[REQUIRED CHROMA MEMORY EVIDENCE]\n"
        + memory_text
        + "\n[END REQUIRED CHROMA MEMORY EVIDENCE]"
    )
