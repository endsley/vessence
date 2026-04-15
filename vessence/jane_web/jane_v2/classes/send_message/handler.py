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

from jane_web.jane_v2.models import LOCAL_LLM as MODEL, OLLAMA_URL  # noqa: E402

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


async def handle(prompt: str, context: str = "") -> dict | None:
    """Extract recipient + body, resolve contact, fast-path or escalate.

    Returns:
      {"text": "msg sent", "client_tools": [...]}  → fast-path send
      None                                          → escalate to Stage 3
    """
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
        "options": {"temperature": 0.0, "num_predict": 100},
        "keep_alive": -1,
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(OLLAMA_URL, json=body)
            r.raise_for_status()
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
        from agent_skills.sms_helpers import resolve_recipient
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
