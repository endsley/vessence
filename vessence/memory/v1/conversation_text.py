"""Pure text helpers for conversation memory management."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


BAD_THEMATIC_META_PREFIX_PATTERNS = (
    r"^i need clarification\b",
    r"^there(?:'|’)s no conversation turn to summarize\b",
    r"^no action needed\b",
    r"^i notice there(?:'|’)s a mismatch here\b",
)
BAD_THEMATIC_PROTOCOL_PATTERNS = (
    r"^\*{0,2}\s*class protocol:",
    r"<class_protocol\b",
    r"\[extracted params\]",
    r"\[current conversation state\]",
    r"\[standing brain mode\]",
    r"\bclass protocol metadata\b",
    r"\bdocumentation \(belongs in code/config\)\b",
    r"\bprovided (?:class )?protocol\b",
    r"\bclass protocol you provided\b",
    r"\bnew turn.*class protocol metadata\b",
)


def strip_injected_metadata(content: str) -> str:
    content = re.sub(
        r'<class_protocol[^>]*>.*?</class_protocol>',
        '',
        content,
        flags=re.DOTALL,
    )
    content = re.sub(
        r'\[EXTRACTED PARAMS\].*?(?=\n\n|\Z)',
        '',
        content,
        flags=re.DOTALL,
    )
    content = re.sub(
        r'\[[A-Z][A-Z_ ]*DATA\].*?(?=\n\n|\Z)',
        '',
        content,
        flags=re.DOTALL,
    )
    content = re.sub(
        r'\[CURRENT CONVERSATION STATE\].*?\[END CURRENT CONVERSATION STATE\]\s*',
        '',
        content,
        flags=re.DOTALL,
    )
    content = re.sub(
        r'\(voice request — .*?\)\n*',
        '',
        content,
        flags=re.DOTALL,
    )
    content = re.sub(
        r'\[STANDING BRAIN MODE\].*?(?=\n|\Z)',
        '',
        content,
    )
    return content.strip()


def looks_like_bad_thematic_output(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalized:
        return False
    protocol_hit = any(
        re.search(pattern, normalized, re.IGNORECASE)
        for pattern in BAD_THEMATIC_PROTOCOL_PATTERNS
    )
    if not protocol_hit:
        return False
    if re.search(r"^\*{0,2}\s*class protocol:", normalized, re.IGNORECASE):
        return True
    return any(
        re.search(pattern, normalized, re.IGNORECASE)
        for pattern in BAD_THEMATIC_META_PREFIX_PATTERNS
    ) or any(
        marker in normalized.lower()
        for marker in (
            "<class_protocol",
            "[extracted params]",
            "[current conversation state]",
            "[standing brain mode]",
        )
    )


def prepare_thematic_turn(user_msg: str, assistant_msg: str) -> str:
    cleaned_user = re.sub(r"\s+", " ", strip_injected_metadata(user_msg or "")).strip()
    cleaned_assistant = re.sub(r"\s+", " ", strip_injected_metadata(assistant_msg or "")).strip()

    if looks_like_bad_thematic_output(cleaned_user):
        cleaned_user = ""
    if looks_like_bad_thematic_output(cleaned_assistant):
        cleaned_assistant = ""

    if not cleaned_user and not cleaned_assistant:
        return ""

    lines = []
    if cleaned_user:
        lines.append(f"User: {cleaned_user}")
    if cleaned_assistant:
        lines.append(f"Jane: {cleaned_assistant}")
    return "\n".join(lines).strip()


def should_store_short_term_turn(role: str, content: str) -> bool:
    text = re.sub(r"\s+", " ", str(content or "")).strip().lower()
    if not text:
        return False
    low_value_exact = {
        "ok", "okay", "yes", "yeah", "yep", "no", "nope", "thanks", "thank you",
        "got it", "sounds good", "cool", "nice", "done", "send", "sent",
        "/new", "none",
    }
    if text in low_value_exact:
        return False
    if role == "user" and len(text) <= 12 and text.endswith("?") and text in {"why?", "how?", "which?", "where?", "when?"}:
        return False
    upper_text = text.upper()
    if upper_text == text and len(text) < 40 and re.match(r"^[A-Z_]+$", text.replace(" ", "")):
        return False
    if role == "user":
        greeting_patterns = [
            r"^hey\s*(jane)?\s*[,!.]?\s*(how.s it going|are you|you there|testing|can you say)?\s*[?!.]?\s*$",
            r"^(hi|hello|yo)\s*(jane)?\s*[!.]?\s*$",
            r"^you (working|there) now\??$",
            r"^(hey )?jane did you crash\??$",
            r"^let.s (run this test|see how long|test this)",
            r"^can you respond to this message so i can test",
            r"^what is \d+\+\d+\??\s*$",
        ]
        for pattern in greeting_patterns:
            if re.search(pattern, text):
                return False
    if role == "assistant":
        filler_patterns = [
            r"^hey \w+[!.,]?\s*(i.m here|going well|what.s up|what do you)",
            r"^(i.m here|here)\.\s*what do you",
            r"^jane here\.\s*(what|i.ll)",
            r"^doing well\.?\s*(in the workspace|ready)",
            r"^fresh start\.?\s*what.s up",
            r"^yeah\.?\s*what do you need",
            r"^when you what\?",
        ]
        for pattern in filler_patterns:
            if re.search(pattern, text):
                return False
    return True


def looks_like_code_edit(content: str) -> bool:
    text = str(content or "")
    markers = [
        "```",
        "*** Begin Patch",
        "*** Update File:",
        "*** Add File:",
        "*** Delete File:",
        "diff --git",
        "@@",
        "+def ",
        "-def ",
        "+import ",
        "-import ",
        "Syntax check passed",
        "File changed:",
        os.path.expanduser("~/"),
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".md",
    ]
    return any(marker in text for marker in markers)


@dataclass(frozen=True)
class ShortTermSummaryPlan:
    immediate_summary: str | None
    summary_style: str
    prompt: str | None
    preserve_bullets: bool


def build_short_term_summary_plan(role: str, content: str) -> ShortTermSummaryPlan:
    clean = re.sub(r"\s+", " ", str(content or "")).strip()
    summary_style = "concise_turn_memory_v1"
    if not clean:
        return ShortTermSummaryPlan(
            immediate_summary="",
            summary_style=summary_style,
            prompt=None,
            preserve_bullets=False,
        )

    if role == "assistant" and looks_like_code_edit(content):
        summary_style = "code_change_turn_memory_v1"
        prompt = (
            "Summarize this assistant turn as a compact code-change memory note for later retrieval.\n"
            "Rules:\n"
            "- Do NOT restate the full diff or prose explanation.\n"
            "- Extract only: files changed, core behavior change, key functions/classes, and any open risk or next step.\n"
            "- Prefer 2 to 4 very short bullets in plain text.\n"
            "- Start each bullet with '- '.\n"
            "- Keep file paths when they matter.\n"
            "- Omit filler, acknowledgements, and formatting chatter.\n"
            "- If no durable code-change context exists, return exactly: No durable context.\n\n"
            f"Role: {role}\n"
            f"Turn: {clean}"
        )
        return ShortTermSummaryPlan(
            immediate_summary=None,
            summary_style=summary_style,
            prompt=prompt,
            preserve_bullets=True,
        )

    if len(clean) <= 150:
        return ShortTermSummaryPlan(
            immediate_summary=clean[:150],
            summary_style="rule_based_turn_memory_v1",
            prompt=None,
            preserve_bullets=False,
        )

    prompt = (
        "Compress this single conversation turn into the shortest and most concise memory note "
        "that will maximally help later context retrieval.\n"
        "Rules:\n"
        "- Keep only concrete facts, decisions, requests, constraints, file paths, errors, or open loops.\n"
        "- Remove filler, politeness, repetition, style words, and nonessential explanation.\n"
        "- Prefer one compact sentence or two very short bullets in plain text.\n"
        "- Do not add analysis or speculation.\n"
        "- If the turn contains no durable or useful context, return exactly: No durable context.\n\n"
        f"Role: {role}\n"
        f"Turn: {clean}"
    )
    return ShortTermSummaryPlan(
        immediate_summary=None,
        summary_style=summary_style,
        prompt=prompt,
        preserve_bullets=False,
    )


def normalize_short_term_summary(text: str, preserve_bullets: bool) -> str:
    text = str(text or "").strip()
    if not text:
        return ""
    if not preserve_bullets:
        return re.sub(r"\s+", " ", text).strip()

    lines = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        if re.match(r"^[-*]\s+", line):
            line = "- " + line[2:].strip()
        elif re.match(r"^\d+\.\s+", line):
            line = "- " + re.sub(r"^\d+\.\s+", "", line).strip()
        lines.append(line)

    if not lines:
        return ""
    if len(lines) > 1:
        lines = [line for line in lines if line != "No durable context." and line != "- No durable context."]
    if not lines:
        return "No durable context."
    if len(lines) == 1 and lines[0] != "No durable context.":
        return f"- {re.sub(r'^[-*]\s+', '', lines[0]).strip()}"
    return "\n".join(lines)
