"""Send Message Stage 2 handler.

Extracts recipient + body from the user prompt using a local LLM,
resolves the recipient against contacts/aliases, then either:
  - Fast-path: emit CLIENT_TOOL to send immediately ("msg sent")
  - Escalate: delegate to Stage 3 (Opus) for disambiguation or draft-confirm

Two-path flow per CLAUDE.md SMS Protocols:
  Fast path: COHERENT=yes + recipient resolves → send immediately, no confirmation
  Fallback:  COHERENT=no, recipient ambiguous, or unresolved → Opus handles it
"""

from __future__ import annotations

import logging
import os
import re
import sys
from pathlib import Path

import httpx

# Ensure sms_helpers is importable
_SKILLS_DIR = Path(__file__).resolve().parents[4] / "agent_skills"
if str(_SKILLS_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILLS_DIR))
_VAULT_WEB_DIR = Path(__file__).resolve().parents[4] / "vault_web"
if str(_VAULT_WEB_DIR) not in sys.path:
    sys.path.insert(0, str(_VAULT_WEB_DIR))

logger = logging.getLogger(__name__)

from jane_web.jane_v2.models import LOCAL_LLM as MODEL, LOCAL_LLM_NUM_CTX, LOCAL_LLM_TIMEOUT, OLLAMA_URL  # noqa: E402

_EXTRACT_PROMPT = """\
The classifier thinks the user wants to SEND A TEXT MESSAGE to someone.
First, confirm: is the user actually asking to send/text/tell someone a message?
If NOT (e.g., they're discussing architecture, asking a question, or just mentioning \
a person's name without a send intent), output ONLY: WRONG_CLASS

If YES, extract the recipient and compose the message body AS IT SHOULD APPEAR IN THE TEXT.

CRITICAL: The user is speaking TO YOU about a third person. You must rewrite the \
body so it reads correctly FROM THE USER TO THE RECIPIENT. Convert perspective:
- "tell my wife I love her" → RECIPIENT: wife / BODY: I love you
- "tell my wife she is beautiful" → RECIPIENT: wife / BODY: You are beautiful
- "let mom know I'm on my way" → RECIPIENT: mom / BODY: I'm on my way
- "tell kathia I miss her today" → RECIPIENT: kathia / BODY: I miss you today
- "text my wife I'll be home soon" → RECIPIENT: wife / BODY: I'll be home soon
- "tell my dad happy birthday" → RECIPIENT: dad / BODY: Happy birthday!
- "text romeo hey sorry for using you as a test subject" → RECIPIENT: romeo / BODY: Hey, sorry for using you as a test subject
- "text john hey what's up" → RECIPIENT: john / BODY: Hey, what's up?
- "text sarah thanks for dinner last night" → RECIPIENT: sarah / BODY: Thanks for dinner last night

IMPORTANT: In "text [name] [message]", everything after the name IS the message body. \
Do NOT output (none) if there are words after the recipient name.

Output EXACTLY these 3 lines — nothing else:

RECIPIENT: <who to text — keep relational names like "wife", "mom", "dad" as-is>
BODY: <the actual text message to send, written from user to recipient>
COHERENT: yes or no (no = garbled, cut off mid-sentence, or contains background noise like Alexa/Siri commands)

If the user didn't include a message body (e.g., "text my wife"), output:
BODY: (none)
COHERENT: yes

Use the recent conversation below to resolve pronouns ("him", "her", "that") \
and to pick up an unspecified recipient from prior context.

{context_block}User: {prompt}"""

# ── Rule-based coherence check (faster and more reliable than LLM) ─────────

# Words that signal a sentence was cut off mid-thought
_DANGLING_ENDINGS = {
    "the", "a", "an", "was", "is", "are", "were", "at", "on", "in",
    "about", "with", "for", "to", "of", "from", "and", "but", "or",
    "that", "which", "who", "when", "where", "how", "if", "so",
    "because", "like", "just", "really", "yeah", "no",
}

# Filler / hesitation words
_FILLER_WORDS = {"uh", "um", "uhh", "umm", "hmm", "hm"}

# Background device commands
_DEVICE_COMMANDS = ["alexa", "hey siri", "ok google", "hey google"]


def _is_coherent(body: str) -> bool:
    """Rule-based coherence check for voice-to-text SMS bodies."""
    if not body or body == "(none)":
        return True  # no body = user just said "text my wife" — coherent intent

    words = body.lower().split()
    if not words:
        return False

    # Check: ends with a dangling function word (cut off mid-sentence)
    if words[-1].rstrip(".,!?") in _DANGLING_ENDINGS:
        return False

    # Check: contains filler/hesitation words
    if _FILLER_WORDS & set(w.rstrip(".,!?") for w in words):
        return False

    # Check: contains background device commands
    body_lower = body.lower()
    if any(cmd in body_lower for cmd in _DEVICE_COMMANDS):
        return False

    return True


_WRONG_CLASS_SENTINEL = {"wrong_class": True}


def _parse_extraction(raw: str) -> dict | None:
    """Parse the LLM's structured output into a dict.
    Returns _WRONG_CLASS_SENTINEL if LLM says WRONG_CLASS."""
    if "WRONG_CLASS" in raw.upper():
        return _WRONG_CLASS_SENTINEL
    recipient = body = llm_coherent = None
    for line in raw.strip().splitlines():
        line = line.strip()
        m = re.match(r"RECIPIENT:\s*(.+)", line, re.IGNORECASE)
        if m:
            recipient = m.group(1).strip()
            continue
        m = re.match(r"BODY:\s*(.+)", line, re.IGNORECASE)
        if m:
            body = m.group(1).strip()
            continue
        m = re.match(r"COHERENT:\s*(.+)", line, re.IGNORECASE)
        if m:
            llm_coherent = m.group(1).strip().lower()
            continue

    if not recipient:
        return None
    body = body or "(none)"
    # LLM coherence with rule-based backup
    llm_says_coherent = llm_coherent != "no"
    rules_say_coherent = _is_coherent(body)
    return {
        "recipient": recipient,
        "body": body,
        "coherent": llm_says_coherent and rules_say_coherent,
    }


def _check_open_draft(prompt: str) -> dict | None:
    """If there's an open SMS draft in the FIFO, handle confirm/cancel/edit
    here in Stage 2 instead of falling through to Stage 3 or re-extracting."""
    try:
        from vault_web.recent_turns import get_active_state
        from jane_web.jane_v2.pending_action_resolver import (
            _is_confirm, _is_cancel, _is_edit_intent,
            _STAGE3_CANCEL_STRONG, _normalize,
        )
    except Exception:
        return None

    try:
        from jane_web.session_context import get_current_session_id
        session_id = get_current_session_id()
    except Exception:
        return None
    if not session_id:
        return None

    try:
        state = get_active_state(session_id)
    except Exception:
        return None

    pending = state.get("pending_action")
    if not pending or pending.get("type") != "SEND_MESSAGE_DRAFT_OPEN":
        return None

    import json as _json
    data = pending.get("data") or {}
    draft_id = data.get("draft_id") or ""
    query = data.get("query") or data.get("display_name") or data.get("recipient") or "them"
    body = data.get("body") or ""

    if _is_confirm(prompt):
        tool_args = _json.dumps({"draft_id": draft_id})
        marker = f"[[CLIENT_TOOL:contacts.sms_send:{tool_args}]]"
        logger.info("send_message handler: draft confirm (stage2 safety net) draft_id=%s", draft_id[:12])
        return {
            "text": f"Sending to {query}. {marker}",
            "structured": {
                "intent": "send message",
                "entities": {"recipient": query, "message_body": body, "draft_id": draft_id},
                "pending_action": {
                    "type": "SEND_MESSAGE_DRAFT_OPEN",
                    "status": "resolved",
                    "resolution": "sent",
                },
                "safety": {"side_effectful": True, "requires_confirmation": False},
            },
        }

    if _is_cancel(prompt) and _normalize(prompt) in _STAGE3_CANCEL_STRONG:
        tool_args = _json.dumps({"draft_id": draft_id})
        marker = f"[[CLIENT_TOOL:contacts.sms_cancel:{tool_args}]]"
        logger.info("send_message handler: draft cancel (stage2 safety net) draft_id=%s", draft_id[:12])
        return {
            "text": f"Okay, cancelled the message to {query}. {marker}",
            "structured": {
                "intent": "send message",
                "pending_action": {
                    "type": "SEND_MESSAGE_DRAFT_OPEN",
                    "status": "resolved",
                    "resolution": "cancelled",
                },
            },
        }

    if _is_edit_intent(prompt):
        logger.info("send_message handler: draft edit detected (stage2 safety net) — escalating to Stage 3")
        return None

    return None


async def handle(prompt: str, context: str = "") -> dict | None:
    """Extract recipient + body, resolve contact, fast-path or escalate.

    Returns:
      {"text": "msg sent", "client_tools": [...]}  → fast-path send
      None                                          → escalate to Stage 3
    """
    # Step 0: If there's an open SMS draft, handle confirm/cancel here
    # instead of re-extracting. This is the Stage 2 safety net — even if
    # the pre-Stage-1 resolver missed (race, FIFO timing), Stage 2 catches it.
    draft_result = _check_open_draft(prompt)
    if draft_result is not None:
        return draft_result

    # Step 1: Extract metadata via local LLM (with FIFO context for pronoun resolution)
    context_block = ""
    if context and context.strip():
        context_block = f"Recent conversation:\n{context.strip()}\n\n"
    extract_prompt = _EXTRACT_PROMPT.format(prompt=prompt.strip(), context_block=context_block)
    body = {
        "model": MODEL,
        "prompt": extract_prompt,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 100, "num_ctx": LOCAL_LLM_NUM_CTX},
        "keep_alive": -1,
    }

    try:
        async with httpx.AsyncClient(timeout=LOCAL_LLM_TIMEOUT) as client:
            r = await client.post(OLLAMA_URL, json=body)
            r.raise_for_status()
            try:
                from jane_web.jane_v2.models import record_ollama_activity
                record_ollama_activity()
            except Exception:
                pass
            raw = (r.json().get("response") or "").strip()
    except Exception as e:
        logger.warning("send_message handler: LLM extract failed: %s", e)
        return None  # escalate

    metadata = _parse_extraction(raw)
    if metadata is _WRONG_CLASS_SENTINEL:
        logger.info("send_message handler: LLM says WRONG_CLASS — escalating with self-correct")
        return _WRONG_CLASS_SENTINEL  # dispatcher will self-correct Stage 1
    if not metadata:
        logger.warning("send_message handler: parse failed: %r", raw[:200])
        return None  # escalate

    logger.info(
        "send_message handler: extracted recipient=%r body=%r coherent=%s",
        metadata["recipient"], metadata["body"][:60], metadata["coherent"],
    )

    # Step 2: Resolve recipient
    try:
        from agent_skills.sms_helpers import resolve_recipient, add_alias, _normalize_name
    except Exception as e:
        logger.warning("send_message handler: sms_helpers import failed: %s", e)
        return None  # escalate

    resolved = resolve_recipient(metadata["recipient"])

    if resolved is None:
        # Unresolved — let Stage 3 (Opus) figure out who this person is
        logger.info(
            "send_message handler: recipient '%s' unresolved — escalating",
            metadata["recipient"],
        )
        return None

    phone = resolved["phone_number"]
    display = resolved["display_name"]

    # Step 2b: Auto-write alias on first successful disambiguation.
    # When the user's spoken recipient ("Lee") resolves via the contacts
    # table (not via an existing alias) and the spoken form differs from
    # the display name, learn the shortcut so the next request hits the
    # alias fast-path without touching contacts LIKE-matching again.
    # We do NOT overwrite an existing alias — add_alias uses INSERT OR
    # REPLACE which would clobber Chieh's curated entries. Guard by
    # checking the alias table first.
    try:
        if resolved.get("source") == "contacts":
            spoken = _normalize_name(metadata["recipient"])
            display_norm = _normalize_name(display)
            if spoken and spoken != display_norm:
                from vault_web.database import get_db as _get_db
                with _get_db() as _conn:
                    _existing = _conn.execute(
                        "SELECT 1 FROM contact_aliases WHERE LOWER(alias) = ? LIMIT 1",
                        (spoken,),
                    ).fetchone()
                if not _existing:
                    if add_alias(spoken, phone, display_name=display):
                        logger.info(
                            "send_message handler: auto-aliased '%s' → %s (%s)",
                            spoken, phone, display,
                        )
    except Exception as _alias_exc:
        # Never let alias-write fail the send.
        logger.warning("auto-alias attempt failed (non-fatal): %s", _alias_exc)

    # Step 3: Check coherence
    if not metadata["coherent"]:
        logger.info("send_message handler: coherence=no for '%s' — escalating", display)
        return None

    # Step 4: Check if body is missing (user just said "text my wife")
    if metadata["body"] == "(none)" or not metadata["body"].strip():
        logger.info("send_message handler: no body for '%s' — escalating", display)
        return None

    # Step 5: Fast-path send — embed CLIENT_TOOL marker in text
    # Android parses [[CLIENT_TOOL:<name>:<json>]] markers from response text
    import json
    tool_args = json.dumps({"phone_number": phone, "body": metadata["body"]})
    marker = f"[[CLIENT_TOOL:contacts.sms_send_direct:{tool_args}]]"
    logger.info("send_message handler: fast-path → %s (%s)", display, phone)
    return {"text": f"Done, message sent. {marker}"}
