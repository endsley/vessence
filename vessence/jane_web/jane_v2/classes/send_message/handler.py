"""Send Message Stage 2 handler.

Extracts recipient + body from the user prompt using a local LLM,
resolves the recipient against contacts/aliases, then branches to:

  Fast path (qwen COHERENT=yes + recipient + body all present):
      Emit `sms_send_direct` marker immediately, reply "Done, message sent.",
      and signal conversation_end=True so the voice loop closes.

  Confirm-or-revise (qwen COHERENT=no with resolved recipient + non-empty body):
      Build a draft and ask "Message to X: Y. Should I send it?" with a
      STAGE2_FOLLOWUP pending. Next turn resumes here to interpret yes/no/end.
          yes  → send + end_conversation
          no   → ask "please give me the updated message." + pending(revised_body)
          end  → end_conversation("Ok.")
          else → abandon_pending + force_stage3 (pivot to Opus)

  Escalate (None):
      intent_kind=ask, missing recipient, unresolved recipient, missing body.
      Stage 3 (Opus) handles those — it can ask for body, disambiguate
      aliases, or phrase the draft+ack for `ask` messages.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from jane_web.jane_v2.ollama_client import post_local_llm_response as _post_local_llm_response

from .extraction_prompt import (
    EXTRACT_PROMPT as _EXTRACT_PROMPT,
    build_extraction_prompt as _build_extraction_prompt,
    extraction_request_payload as _extraction_request_payload,
)
from .parsing import (
    WRONG_CLASS_SENTINEL as _WRONG_CLASS_SENTINEL,
    has_direct_send_confidence as _has_direct_send_confidence,
    is_coherent as _is_coherent,
    parse_extraction as _parse_extraction,
    parse_params_metadata as _parse_params_metadata,
)
from .responses import (
    build_confirmation_response as _build_confirmation_response,
    build_open_draft_cancel_response as _build_open_draft_cancel_response,
    build_open_draft_send_response as _build_open_draft_send_response,
    build_revision_request_response as _build_revision_request_response,
    build_send_marker as _build_send_marker,
    build_sent_response as _build_sent_response,
)

# Ensure sms_helpers is importable
_SKILLS_DIR = Path(__file__).resolve().parents[4] / "agent_skills"
if str(_SKILLS_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILLS_DIR))
_VAULT_WEB_DIR = Path(__file__).resolve().parents[4] / "vault_web"
if str(_VAULT_WEB_DIR) not in sys.path:
    sys.path.insert(0, str(_VAULT_WEB_DIR))

logger = logging.getLogger(__name__)

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

    data = pending.get("data") or {}
    draft_id = data.get("draft_id") or ""
    query = data.get("query") or data.get("display_name") or data.get("recipient") or "them"
    body = data.get("body") or ""

    if _is_confirm(prompt):
        logger.info("send_message handler: draft confirm (stage2 safety net) draft_id=%s", draft_id[:12])
        return _build_open_draft_send_response(draft_id, query, body)

    if _is_cancel(prompt) and _normalize(prompt) in _STAGE3_CANCEL_STRONG:
        logger.info("send_message handler: draft cancel (stage2 safety net) draft_id=%s", draft_id[:12])
        return _build_open_draft_cancel_response(draft_id, query)

    if _is_edit_intent(prompt):
        logger.info("send_message handler: draft edit detected (stage2 safety net) — escalating to Stage 3")
        return None

    return None


async def _extract_via_llm(prompt: str, context: str) -> dict | None:
    """Legacy fallback: ask qwen for {recipient, body, coherent}."""
    def payload_builder(prompt_text: str, *, model: str, num_ctx: int, keep_alive: str | int) -> dict:
        return _extraction_request_payload(
            model=model,
            prompt=prompt_text,
            context=context,
            num_ctx=num_ctx,
            keep_alive=keep_alive,
        )

    try:
        raw = await _post_local_llm_response(prompt, payload_builder)
    except Exception as e:
        logger.warning("send_message handler: LLM extract failed: %s", e)
        return None
    return _parse_extraction(raw)


async def _handle_resume(prompt: str, pending: dict) -> dict | None:
    """Resume a STAGE2_FOLLOWUP for send_message (confirm-or-revise loop)."""
    from agent_skills import end_phrase, confirmation
    from agent_skills.private_handler_utils import end_conversation

    data = pending.get("data") if isinstance(pending.get("data"), dict) else pending
    awaiting = (data or {}).get("awaiting") or pending.get("awaiting") or ""
    draft = (data or {}).get("draft") or {}
    phone = draft.get("phone") or ""
    display = draft.get("display") or "them"
    body = draft.get("body") or ""

    if awaiting == "send_confirmation":
        # Order matters: check is_yes/is_no BEFORE end_phrase. Bare "no"
        # answers "Should I send it?" with "no, change it" — treating it
        # as a cancel here would surprise the user (see confirmation.py
        # docstring for full rationale). Cancel is reserved for stronger
        # phrases like "cancel"/"nevermind"/"stop", which are in
        # end_phrase but not is_no.
        if confirmation.is_yes(prompt):
            if not phone or not body:
                logger.warning("send_message handler: resume yes but draft incomplete → abandon")
                return {"abandon_pending": True, "force_stage3": True}
            logger.info("send_message handler: confirmed → send to %s", display)
            return _build_sent_response(phone, display, body, prefix="Done.")
        if confirmation.is_no(prompt):
            return _build_revision_request_response(phone, display)
        if end_phrase.is_end(prompt):
            logger.info("send_message handler: resume — end phrase, cancelling draft to %s", display)
            return end_conversation("Ok.", structured={"intent": "send message"})
        logger.info("send_message handler: resume — unrecognized confirm reply → escalate")
        return {"abandon_pending": True, "force_stage3": True}

    if awaiting == "revised_body":
        # In the revised_body slot, the user is supplying a new message body.
        # Don't apply is_yes/is_no here — those would clobber valid 1-word
        # bodies. Only end_phrase aborts.
        if end_phrase.is_end(prompt):
            return end_conversation("Ok.", structured={"intent": "send message"})
        new_body = (prompt or "").strip()
        if not new_body:
            return {"abandon_pending": True, "force_stage3": True}
        return _build_confirmation_response(phone, display, new_body)

    logger.warning("send_message handler: unknown awaiting %r → abandon", awaiting)
    return {"abandon_pending": True, "force_stage3": True}


async def handle(prompt: str, context: str = "", pending: dict | None = None,
                 params: dict | None = None) -> dict | None:
    """Extract recipient + body, resolve contact, fast-path or escalate.

    Returns:
      {"text": "Done, ...", conversation_end=True}  → fast-path send
      {"text": "Message to X: Y. Should I send it?", pending_action: ...}
                                                     → confirm-or-revise
      None                                          → escalate to Stage 3
    """
    if not isinstance(prompt, str):
        return None

    # Resume path: STAGE2_FOLLOWUP from a previous send_message turn.
    if pending and (pending.get("handler_class") == "send message"
                    or (pending.get("data") or {}).get("awaiting") in
                       {"send_confirmation", "revised_body"}):
        return await _handle_resume(prompt, pending)

    # Step 0: If there's an open SMS draft, handle confirm/cancel here
    # instead of re-extracting. This is the Stage 2 safety net — even if
    # the pre-Stage-1 resolver missed (race, FIFO timing), Stage 2 catches it.
    draft_result = _check_open_draft(prompt)
    if draft_result is not None:
        return draft_result

    # Step 1: Build metadata from params, or fall back to LLM extraction.
    metadata: dict | None = None
    if params:
        param_status, metadata = _parse_params_metadata(params)
        if param_status == "ask":
            logger.info("send_message handler: intent_kind=ask — escalating to Opus draft path")
            return None
        if param_status == "missing_recipient":
            logger.info("send_message handler: params has no recipient — escalating")
            return None
    else:
        metadata = await _extract_via_llm(prompt, context)
        if metadata is _WRONG_CLASS_SENTINEL:
            logger.info("send_message handler: LLM says WRONG_CLASS — escalating with self-correct")
            return _WRONG_CLASS_SENTINEL
        if not metadata:
            logger.warning("send_message handler: extract failed — escalating")
            return None

    logger.info(
        "send_message handler: recipient=%r body=%r coherent=%s",
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

    # Step 4: If the body is missing (user just said "text my wife"), let
    # Stage 3 ask for it — there's no draft to confirm yet.
    if metadata["body"] == "(none)" or not metadata["body"].strip():
        logger.info("send_message handler: no body for '%s' — escalating", display)
        return None

    # Step 3: Coherence check. If qwen flagged the body as garbled / cut off,
    # don't blast it. Build a draft and ask the user to confirm or revise.
    if not metadata["coherent"]:
        logger.info("send_message handler: coherence=no → confirm-or-revise for '%s'", display)
        return _build_confirmation_response(phone, display, metadata["body"])

    if "confidence" in metadata and not _has_direct_send_confidence(metadata["confidence"]):
        logger.info(
            "send_message handler: confidence %r below direct-send floor — escalating",
            metadata["confidence"],
        )
        return None

    # Step 5: Fast-path send — embed CLIENT_TOOL marker in text and end the
    # conversation so the voice loop returns to wake-word mode.
    logger.info("send_message handler: fast-path → %s (%s)", display, phone)
    return _build_sent_response(phone, display, metadata["body"])
