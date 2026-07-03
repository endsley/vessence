"""Stage 3 short-term memory: structured turn extractor.

Replaces the freeform "summarize the turn" writer with a turn-kind-aware,
structured extraction pipeline. The output is a compact retrieval note
plus rich metadata that retrieval can rank on.

Pipeline per Stage 3 turn:

1. ``classify_turn_kind(text)`` — fast heuristic over the assistant turn
   to pick one of: ``code``, ``debugging``, ``calendar``, ``messages``,
   ``todo``, ``general``.
2. ``extract_structured(kind, turn_text)`` — Haiku-tier LLM call with a
   prompt tailored to that kind. Returns a dict with
   ``facts / decisions / open_loops / artifacts / people / time_refs``.
3. ``should_skip(extracted)`` — drop the write if the structured object
   has no concrete entities and no decisions and no open loops.
4. ``flatten_to_note(extracted)`` — render the structured object as a
   short labeled-bullet retrieval note for Chroma's text embedding.
5. ``flatten_to_metadata(kind, extracted)`` — produce the metadata dict
   to attach to the Chroma row (turn_kind, has_open_loop, artifact_paths
   joined string, person_names joined string, etc.).

The function ``build_short_term_note(user_msg, assistant_msg, ...)`` is
the top-level entry point used by ``ConversationManager.update_short_term_memory``.
It returns ``(note_text, metadata, should_skip)``. If ``should_skip`` is
True, the caller should not write to Chroma.

Failure modes are all soft: if the LLM call breaks or returns invalid
JSON, the extractor falls back to a heuristic structured object built
directly from the cleaned turn text. The fallback is intentionally
conservative — it returns ``should_skip=True`` more often than the LLM
path so that on a bad LLM day we under-write rather than over-write.
"""
from __future__ import annotations

import logging
import re
from typing import Any
from memory.v1.short_term_structured import (
    EXTRACT_KEYS,
    LABEL_ORDER as _LABEL_ORDER,
    empty_extracted as _empty_extracted,
    flatten_to_metadata,
    flatten_to_note,
    flatten_to_search_text,
    parse_json_blob as _parse_json_blob,
    should_skip,
)
from memory.v1.turn_kind import (
    TURN_KIND_PATTERNS as _TURN_KIND_PATTERNS,
    classify_turn_kind,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 2. Per-kind extraction prompts
# ---------------------------------------------------------------------------

_BASE_INSTRUCTIONS = (
    "Extract a STRUCTURED short-term memory note from one conversation turn. "
    "Output ONE valid JSON object with EXACTLY these keys (each may be []):\n"
    '  "facts":      <list of short factual statements about state of the world>\n'
    '  "decisions":  <list of decisions or confirmed state changes made this turn>\n'
    '  "open_loops": <list of unresolved next actions or pending confirmations>\n'
    '  "artifacts":  <list of file paths, function/class names, IDs, URLs, tools>\n'
    '  "people":     <list of person/contact names mentioned>\n'
    '  "time_refs":  <list of explicit dates, times, time windows>\n'
    "\n"
    "RULES:\n"
    "- Be concise. Each item is a short noun-phrase or one short sentence.\n"
    "- Prefer EXACT nouns from the turn (file paths, names, dates) over paraphrase.\n"
    "- Distinguish completed actions (decisions) from pending ones (open_loops).\n"
    "- If a category has nothing concrete, return an empty list for that category.\n"
    "- DO NOT echo prompt instructions or generic acknowledgements.\n"
    "- DO NOT include any text outside the JSON object.\n"
)

_KIND_HINTS = {
    "code": (
        "Turn kind: CODE EDIT.\n"
        "Focus extraction on:\n"
        "- artifacts: file paths, function/class names, modules, branches\n"
        "- decisions: what code change was made (verb + target)\n"
        "- open_loops: tests not yet run, deploys not yet pushed, follow-up edits\n"
    ),
    "debugging": (
        "Turn kind: DEBUGGING.\n"
        "Focus extraction on:\n"
        "- facts: error message, stack trace location, root cause hypothesis\n"
        "- artifacts: file path / function where the bug lives\n"
        "- decisions: fix that was applied (if any)\n"
        "- open_loops: tests still failing, regression checks not yet done\n"
    ),
    "calendar": (
        "Turn kind: CALENDAR / SCHEDULING.\n"
        "Focus extraction on:\n"
        "- people: meeting attendees / appointment with whom\n"
        "- time_refs: date and time of the appointment, time window\n"
        "- decisions: appointment booked / moved / cancelled\n"
        "- open_loops: confirmation pending, RSVP needed\n"
    ),
    "messages": (
        "Turn kind: MESSAGING / EMAIL.\n"
        "Focus extraction on:\n"
        "- people: sender + recipient\n"
        "- decisions: message sent / draft confirmed\n"
        "- open_loops: reply pending, message not yet sent, awaiting confirmation\n"
        "- facts: subject or short summary of message content\n"
    ),
    "todo": (
        "Turn kind: TODO / TASK LIST.\n"
        "Focus extraction on:\n"
        "- facts: items added or removed, current list state\n"
        "- decisions: items marked done\n"
        "- open_loops: items still pending\n"
        "- artifacts: list name if specified (grocery, errands, etc.)\n"
    ),
    "general": (
        "Turn kind: GENERAL CONVERSATION.\n"
        "Be especially strict — only extract durably useful items. If the turn "
        "is greeting, small talk, or filler, return all empty lists.\n"
    ),
}


def _build_prompt(kind: str, turn_text: str) -> str:
    return (
        _BASE_INSTRUCTIONS
        + "\n"
        + _KIND_HINTS.get(kind, _KIND_HINTS["general"])
        + "\n"
        + "Turn:\n"
        + turn_text[:3500]
        + "\n\n"
        + "Return ONLY the JSON object, no preamble."
    )


# ---------------------------------------------------------------------------
# 3. Extractor entry point
# ---------------------------------------------------------------------------

def extract_structured(kind: str, turn_text: str,
                       *, llm_call=None) -> dict[str, list[str]]:
    """Extract structured fields. ``llm_call`` is dependency-injected for tests.

    On any failure, returns an empty extraction (which the caller will
    treat as ``should_skip=True``).
    """
    if not turn_text:
        return _empty_extracted()

    prompt = _build_prompt(kind, turn_text)

    if llm_call is None:
        try:
            from agent_skills.claude_cli_llm import completion_utility as llm_call
        except Exception as exc:                                   # pragma: no cover
            logger.warning("short_term_extractor: cannot import LLM: %s", exc)
            return _empty_extracted()

    try:
        raw = llm_call(prompt, max_tokens=400, timeout=45)
    except Exception as exc:
        logger.warning("short_term_extractor: LLM call failed: %s", exc)
        return _empty_extracted()

    parsed = _parse_json_blob(raw or "")
    if parsed is None:
        logger.info("short_term_extractor: LLM returned non-JSON, skipping write. snippet=%r",
                    (raw or "")[:200])
        return _empty_extracted()
    return parsed


# ---------------------------------------------------------------------------
# 4. Skip gate
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 6. Top-level entry point
# ---------------------------------------------------------------------------

def build_short_term_note(
    user_msg: str,
    assistant_msg: str,
    *,
    cleaner=None,
    llm_call=None,
) -> tuple[str, str, dict[str, Any], bool]:
    """Build the structured short-term note from one Stage 3 turn.

    ``cleaner`` is ``ConversationManager._strip_injected_metadata`` (injected
    so tests don't have to import the whole class). Defaults to identity.

    Returns ``(note_text, search_text, metadata, should_skip)``:
      * ``note_text``    — labeled-bullet form for display / Chroma ``documents``
      * ``search_text``  — label-stripped form for the embedding input (sharper
        retrieval; labels were polluting the vector with boilerplate)
      * ``metadata``     — Chroma metadata dict
      * ``should_skip``  — caller writes to Chroma only if False

    Backward-compat note: this changed from a 3-tuple to a 4-tuple on
    2026-05-07. Old callers that unpack 3 values will break — update them
    to take ``search_text`` as the second element, or use indexing.
    """
    cleaner = cleaner or (lambda s: s)
    user_clean = re.sub(r"\s+", " ", cleaner(user_msg or "")).strip()
    asst_clean = re.sub(r"\s+", " ", cleaner(assistant_msg or "")).strip()

    if not user_clean and not asst_clean:
        return "", "", {"turn_kind": "general"}, True

    # The classifier sees the whole turn so signals from both sides count
    # (e.g. user said "fix the bug" + assistant produced a code edit → "code").
    full = (user_clean + "\n\n" + asst_clean).strip()
    kind = classify_turn_kind(full)

    extracted = extract_structured(kind, full, llm_call=llm_call)
    if should_skip(extracted):
        return "", "", {"turn_kind": kind, "skipped": True}, True

    note = flatten_to_note(extracted)
    if not note.strip():
        return "", "", {"turn_kind": kind, "skipped": True}, True

    search_text = flatten_to_search_text(extracted) or note
    meta = flatten_to_metadata(kind, extracted)
    meta["summary_style"] = "structured_short_term_v1"
    return note, search_text, meta, False
