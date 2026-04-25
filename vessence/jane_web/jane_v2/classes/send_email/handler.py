"""Send Email Stage 2 handler.

Extracts recipient + subject + body from the user prompt using the local LLM,
reads the draft back, and waits for explicit confirmation before calling
Gmail API server-side.

Flow:
  Turn N:
    - If a pending EMAIL_DRAFT_OPEN exists and user confirms/cancels → act.
    - Otherwise extract {to, subject, body, coherent}. If all present +
      coherent → save draft, read back, set pending_action.
    - If any field missing, recipient name unresolved, or body unclear
      → escalate to Stage 3 (Opus).

  Turn N+1 (answering the draft read-back):
    - "yes send" → call email_tools.send_email, clear pending, respond "Sent."
    - "cancel"   → clear pending, respond "Cancelled."
    - edit       → escalate to Opus (it redrafts).

Unlike send_message, email is server-side: there's no CLIENT_TOOL marker
and no phone relay. We call email_tools.send_email() directly in-process.
"""
from __future__ import annotations

import json
import logging
import re
import sys
import uuid
from pathlib import Path
from typing import Optional

import httpx

# Ensure agent_skills is importable for email_tools
_SKILLS_DIR = Path(__file__).resolve().parents[4] / "agent_skills"
if str(_SKILLS_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILLS_DIR))
_VAULT_WEB_DIR = Path(__file__).resolve().parents[4] / "vault_web"
if str(_VAULT_WEB_DIR) not in sys.path:
    sys.path.insert(0, str(_VAULT_WEB_DIR))

logger = logging.getLogger(__name__)

from jane_web.jane_v2.models import (  # noqa: E402
    LOCAL_LLM as MODEL, LOCAL_LLM_NUM_CTX, LOCAL_LLM_TIMEOUT, OLLAMA_URL,
)

_PENDING_TYPE = "EMAIL_DRAFT_OPEN"
_WRONG_CLASS_SENTINEL = {"wrong_class": True}

_EXTRACT_PROMPT = """\
The classifier thinks the user wants to SEND AN EMAIL.
First, confirm: is the user actually asking to send/email/draft an email to \
someone? If NOT (meta question, architecture discussion, just mentioning email \
in passing), output ONLY: WRONG_CLASS

If YES, extract the recipient, subject, and body AS THEY SHOULD APPEAR IN THE EMAIL.

Perspective rewrite: the user is speaking TO YOU about a third person. Convert:
  - "email Bob saying I'll be late" → TO: Bob / BODY: I'll be late
  - "email Alice about the meeting tomorrow at 10" → TO: Alice / SUBJECT: Meeting tomorrow / BODY: <brief body matching the request>
  - "email sarah@example.com: hey thanks for dinner" → TO: sarah@example.com / BODY: Hey, thanks for dinner
  - "draft an email to my accountant about Q3 taxes" → TO: accountant / SUBJECT: Q3 taxes / BODY: <brief body>

Output EXACTLY these 4 lines — nothing else:

TO: <recipient — email address if given, else the name>
SUBJECT: <short subject line, or (none)>
BODY: <the email body written from user to recipient>
COHERENT: yes or no (no = garbled / cut off / too vague to compose a sensible body)

If the body is missing (e.g., "email bob"), output:
BODY: (none)
COHERENT: yes

Use the recent conversation below to resolve pronouns ("him", "her", "that") \
and to fill in an unspecified recipient from prior context.

{context_block}User: {prompt}"""

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _email_body_coherent(body: str) -> bool:
    """Lightweight rule-based coherence check for email bodies.

    Reuses the SMS coherence helper so an email body dictated through STT
    that picked up an Alexa/Siri/Google command is also escalated rather
    than sent verbatim. Imported lazily to avoid circular import risk.
    """
    if not body:
        return False
    try:
        from jane_web.jane_v2.classes.send_message.handler import _is_coherent
        return _is_coherent(body)
    except Exception:
        return True  # fail-open: never block a send because of import error


def _parse_extraction(raw: str) -> Optional[dict]:
    """Parse the LLM's TO/SUBJECT/BODY/COHERENT block. Returns None on failure,
    or the wrong-class sentinel if the model rejected the classification."""
    if not raw:
        return None
    if "WRONG_CLASS" in raw.upper():
        return _WRONG_CLASS_SENTINEL
    to_val: str = ""
    subject_val: str = ""
    body_val: str = ""
    coherent_val: str = "yes"
    # Simple line-by-line parser; tolerates case variations and extra whitespace.
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if lower.startswith("to:"):
            to_val = stripped.split(":", 1)[1].strip()
        elif lower.startswith("subject:"):
            subject_val = stripped.split(":", 1)[1].strip()
        elif lower.startswith("body:"):
            body_val = stripped.split(":", 1)[1].strip()
        elif lower.startswith("coherent:"):
            coherent_val = stripped.split(":", 1)[1].strip().lower()
    if not to_val:
        return None
    return {
        "to": to_val,
        "subject": subject_val or "(none)",
        "body": body_val or "(none)",
        "coherent": coherent_val != "no",
    }


def _is_confirm(prompt: str) -> bool:
    try:
        from jane_web.jane_v2.pending_action_resolver import _is_confirm as _c
        return bool(_c(prompt))
    except Exception:
        return bool(re.match(r"^\s*(yes|send|send it|ok send|go ahead|confirm)\s*\.?\s*$", prompt.strip().lower()))


def _is_cancel(prompt: str) -> bool:
    try:
        from jane_web.jane_v2.pending_action_resolver import _is_cancel as _c
        return bool(_c(prompt))
    except Exception:
        return bool(re.match(r"^\s*(no|cancel|nevermind|never mind|stop|scrap it)\s*\.?\s*$", prompt.strip().lower()))


def _is_edit_intent(prompt: str) -> bool:
    try:
        from jane_web.jane_v2.pending_action_resolver import _is_edit_intent as _e
        return bool(_e(prompt))
    except Exception:
        keywords = ("change", "make it", "shorter", "longer", "different", "instead", "edit", "rewrite")
        return any(k in prompt.lower() for k in keywords)


def _check_open_draft(prompt: str) -> Optional[dict]:
    """If an EMAIL_DRAFT_OPEN pending_action exists, resolve confirm / cancel
    here in Stage 2 rather than re-extracting or bouncing to Stage 3.
    """
    try:
        from vault_web.recent_turns import get_active_state
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
        state = get_active_state(session_id) or {}
    except Exception:
        return None
    pending = state.get("pending_action")
    if not pending or pending.get("type") != _PENDING_TYPE:
        return None
    data = pending.get("data") or {}
    to = data.get("to") or ""
    subject = data.get("subject") or ""
    body = data.get("body") or ""

    if _is_confirm(prompt):
        try:
            import email_tools  # agent_skills/email_tools.py via sys.path insert above
        except Exception as exc:
            logger.exception("send_email handler: email_tools import failed: %s", exc)
            return {
                "text": "I couldn't reach the email tool. Try again in a moment.",
                "structured": {
                    "intent": "send email",
                    "pending_action": {
                        "type": _PENDING_TYPE,
                        "status": "resolved",
                        "resolution": "error",
                    },
                },
            }
        try:
            result = email_tools.send_email(
                to=to,
                subject=(subject if subject and subject != "(none)" else "(no subject)"),
                body=body,
            )
            logger.info("send_email handler: sent to=%s subject=%r result=%s", to, subject, bool(result))
            who = data.get("display") or to
            return {
                "text": f"Sent to {who}.",
                "structured": {
                    "intent": "send email",
                    "entities": {"to": to, "subject": subject, "body": body},
                    "pending_action": {
                        "type": _PENDING_TYPE,
                        "status": "resolved",
                        "resolution": "sent",
                    },
                    "safety": {"side_effectful": True, "requires_confirmation": False},
                },
            }
        except Exception as exc:
            logger.exception("send_email handler: send failed: %s", exc)
            return {
                "text": f"I couldn't send the email: {exc}",
                "structured": {
                    "intent": "send email",
                    "pending_action": {
                        "type": _PENDING_TYPE,
                        "status": "resolved",
                        "resolution": "error",
                    },
                },
            }

    if _is_cancel(prompt):
        logger.info("send_email handler: draft cancelled to=%s", to)
        return {
            "text": f"Okay, cancelled the email to {data.get('display') or to}.",
            "structured": {
                "intent": "send email",
                "pending_action": {
                    "type": _PENDING_TYPE,
                    "status": "resolved",
                    "resolution": "cancelled",
                },
            },
        }

    if _is_edit_intent(prompt):
        # Let Opus redraft with full reasoning.
        logger.info("send_email handler: edit detected — escalating to Stage 3")
        return None

    # User asked something unrelated — abandon the pending draft and escalate.
    return None


async def _extract_via_llm(prompt: str, context: str) -> Optional[dict]:
    """Legacy fallback extractor: ask qwen for {to, subject, body, coherent}."""
    context_block = ""
    if context and context.strip():
        context_block = f"Recent conversation:\n{context.strip()}\n\n"
    extract_prompt = _EXTRACT_PROMPT.format(prompt=prompt.strip(), context_block=context_block)
    ollama_body = {
        "model": MODEL,
        "prompt": extract_prompt,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 160, "num_ctx": LOCAL_LLM_NUM_CTX},
        "keep_alive": -1,
    }
    try:
        async with httpx.AsyncClient(timeout=LOCAL_LLM_TIMEOUT) as client:
            r = await client.post(OLLAMA_URL, json=ollama_body)
            r.raise_for_status()
            try:
                from jane_web.jane_v2.models import record_ollama_activity
                record_ollama_activity()
            except Exception:
                pass
            raw = (r.json().get("response") or "").strip()
    except Exception as exc:
        logger.warning("send_email handler: LLM extract failed: %s", exc)
        return None
    return _parse_extraction(raw)


async def handle(prompt: str, context: str = "", params: dict | None = None) -> Optional[dict]:
    """Entry point called by stage2_dispatcher.

    When `params` is provided (v3 path), the classifier has already extracted
    {to, subject, body, confirm_signal} — use them directly and skip the
    Stage 2 LLM extract. When `params` is None, fall back to the legacy LLM
    extraction (v2 path).
    """
    # Step 0: pending-draft resolution (reads session state, not params)
    result = _check_open_draft(prompt)
    if result is not None:
        return result

    # Step 1: Build metadata from params, or fall back to LLM extraction.
    metadata: Optional[dict] = None
    if params:
        to_val = (params.get("to") or "").strip()
        subject_val = (params.get("subject") or "").strip()
        body_val = (params.get("body") or "").strip()
        confirm = (params.get("confirm_signal") or "").strip().lower()
        # confirm_signal is only meaningful with an open draft; if we got
        # here, _check_open_draft returned None, so a stray confirm/cancel/
        # edit signal means we have no draft to act on. Escalate so Opus
        # can phrase a sensible reply.
        if confirm in ("send", "cancel", "edit"):
            logger.info("send_email handler: confirm_signal=%s with no open draft — escalating", confirm)
            return None
        if not to_val:
            logger.info("send_email handler: params has no recipient — escalating")
            return None
        if not body_val:
            logger.info("send_email handler: params has no body — escalating to ask user")
            return None
        coherent = _email_body_coherent(body_val)
        if not coherent:
            logger.info("send_email handler: params body looks incoherent — escalating")
            return None
        metadata = {
            "to": to_val,
            "subject": subject_val or "(none)",
            "body": body_val,
            "coherent": True,
        }
    else:
        metadata = await _extract_via_llm(prompt, context)
        if metadata is _WRONG_CLASS_SENTINEL:
            logger.info("send_email handler: LLM says WRONG_CLASS — escalating with self-correct")
            return _WRONG_CLASS_SENTINEL
        if not metadata:
            logger.warning("send_email handler: extract failed — escalating")
            return None

    logger.info(
        "send_email handler: to=%r subject=%r body=%r coherent=%s",
        metadata["to"], metadata["subject"], metadata["body"][:60], metadata["coherent"],
    )

    # Step 2: Coherence guard
    if not metadata["coherent"]:
        return None

    # Step 3: If body is missing, ask the user for content. Escalate so Opus
    # can ask the question naturally using conversation context.
    if metadata["body"] == "(none)" or not metadata["body"].strip():
        return None

    # Step 4: Recipient must be a real email address for the fast path. If the
    # user only gave a name ("Bob"), Opus must resolve it (address book lookup,
    # search recent emails, ask the user). Escalate.
    to_field = metadata["to"].strip()
    match = _EMAIL_RE.search(to_field)
    if not match:
        logger.info("send_email handler: no email address in recipient %r — escalating", to_field)
        return None
    to_addr = match.group(0)
    display = to_field if to_field == to_addr else to_field

    # Step 5: Build draft + read-back. DO NOT send yet — the user must confirm
    # on the next turn via _check_open_draft.
    draft_id = uuid.uuid4().hex[:12]
    subject = metadata["subject"]
    subject_line = "" if subject == "(none)" else f"Subject: {subject}. "
    text = (
        f"{subject_line}To {display}: \"{metadata['body']}\". "
        f"Ready to send?"
    )
    logger.info("send_email handler: draft ready (id=%s) to=%s", draft_id, to_addr)
    return {
        "text": text,
        "structured": {
            "intent": "send email",
            "entities": {"to": to_addr, "subject": subject, "body": metadata["body"]},
            "pending_action": {
                "type": _PENDING_TYPE,
                "status": "awaiting_user",
                "handler_class": "send_email",
                "data": {
                    "draft_id": draft_id,
                    "to": to_addr,
                    "display": display,
                    "subject": subject,
                    "body": metadata["body"],
                },
            },
            "safety": {"side_effectful": True, "requires_confirmation": True},
        },
    }
