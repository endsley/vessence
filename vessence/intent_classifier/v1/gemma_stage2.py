"""gemma_stage2.py — Stage 2 of the two-pass Gemma4 architecture.

Responsibility: dispatch based on Stage 1's classification.

Fast-path intents (pure Python, no LLM):
  SEND_MESSAGE     — resolve recipient → emit CLIENT_TOOL or delegate
  END_CONVERSATION — return fixed ack, set conversation_end flag
  SYNC_MESSAGES    — emit CLIENT_TOOL, no LLM

Data-summarization intents (Gemma call with task-specific context):
  READ_MESSAGES    — summarize SMS data block
  READ_EMAIL       — summarize email data block
  MUSIC_PLAY       — announce playlist

Conversational intents (Gemma call with FIFO context):
  SHOPPING_LIST    — short confirmation of list action
  SELF_HANDLE      — direct conversational response
  DELEGATE_OPUS    — generate delegation ack, set delegate=True

Public entry point:
  async def stage2_execute(classification, metadata, task_context,
                           session_id, message) -> dict

Return dict always contains:
  response          str   — user-facing text (may be empty on delegate)
  delegate          bool  — True → caller should invoke Opus
  client_tools      list  — [{name, args}] for client-side actions
  conversation_end  bool  — True → client should stop auto-reopening STT
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

_VAULT_WEB_DIR = Path(__file__).resolve().parents[2] / "vault_web"
if str(_VAULT_WEB_DIR) not in sys.path:
    sys.path.insert(0, str(_VAULT_WEB_DIR))

_AGENT_SKILLS_DIR = Path(__file__).resolve().parents[2] / "agent_skills"
if str(_AGENT_SKILLS_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_SKILLS_DIR))

logger = logging.getLogger(__name__)

STAGE2_TIMEOUT_S = float(os.environ.get("JANE_STAGE2_TIMEOUT", "5.0"))

# Context budget for FIFO (same cap as Stage 1)
FIFO_CHAR_CAP = 2400
FIFO_TURN_COUNT = 4

# Recipient unresolved — context block for Opus fallback
_UNRESOLVED_RECIPIENT_TMPL = """\
[SMS SEND REQUEST — RECIPIENT UNRESOLVED]
The user wants to TEXT (SMS) "{recipient}" with message "{body}".
THIS IS AN SMS REQUEST — do NOT use contacts.call. Use sms_send_direct only.
This name is not in contacts or aliases. Use your memory to figure out who this person is,
search contacts for their real name, then POST to /api/contacts/alias with
{{"alias": "{recipient}", "phone_number": "<resolved number>", "display_name": "<real name>"}}
so next time this name resolves automatically.
IMPORTANT: Confirm the message with the user FIRST, then send via:
[[CLIENT_TOOL:contacts.sms_send_direct:{{"phone_number":"<resolved>","body":"<confirmed body>"}}]]
Never send without the user's explicit confirmation. Never use contacts.call for this.
[END SMS SEND REQUEST]"""

# Incoherent body — context block for Opus fallback (draft-confirm flow)
_INCOHERENT_SMS_TMPL = """\
[SMS SEND REQUEST — COHERENCE GATE FAILED]
The user tried to text "{recipient}" but the body looks garbled or cut-off: "{body}".
Compose a clean draft based on their intent, read it back, and ask for confirmation
before sending. If they confirm, send via
[[CLIENT_TOOL:contacts.sms_send:{{"phone_number":"{phone}","body":"<final body>"}}]].
[END SMS SEND REQUEST]"""


# ── Shared Gemma CLI / ollama runner ─────────────────────────────────────────

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


def _get_cli() -> Optional[str]:
    try:
        from jane.config import PROVIDER_CLI  # type: ignore
    except Exception:
        PROVIDER_CLI = "gemini"
    cli = os.environ.get("PROVIDER_CLI", PROVIDER_CLI)
    # claude CLI can't run local ollama models
    if cli == "claude":
        return None
    return cli if shutil.which(cli) else None


def _get_model() -> str:
    return (
        os.environ.get("JANE_STAGE2_MODEL")
        or os.environ.get("JANE_ACK_MODEL")
        or "gemma4:e2b"
    )


async def _gemma_call(prompt: str, timeout: float = STAGE2_TIMEOUT_S) -> Optional[str]:
    """Run Gemma via ollama HTTP (preferred) or CLI fallback. Returns text or None."""
    model = _get_model()
    loop = asyncio.get_event_loop()

    # Ollama HTTP path — preferred for local gemma models
    is_ollama_model = not any(x in model for x in ("gemini", "gpt", "claude", "anthropic"))
    if is_ollama_model:
        import json as _json
        import urllib.request
        url = f"{OLLAMA_URL}/api/generate"
        payload = _json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            raw = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=int(timeout)).read()),
                timeout=timeout + 0.5,
            )
            data = _json.loads(raw)
            text = (data.get("response") or "").strip()
            return text or None
        except asyncio.TimeoutError:
            logger.info("stage2: ollama timeout (%.1fs)", timeout)
            return None
        except Exception as e:
            logger.debug("stage2: ollama HTTP error: %s — trying CLI", e)
            # fall through to CLI

    cli = _get_cli()
    if not cli:
        logger.debug("stage2: no usable CLI for model %r", model)
        return None

    if "gemini" in cli:
        cmd = [cli, "-p", prompt]
    else:
        cmd = [cli, "-p", prompt, "--output-format", "text", "--model", model]

    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=int(timeout), env=os.environ.copy(),
            )),
            timeout=timeout + 0.5,
        )
    except asyncio.TimeoutError:
        logger.info("stage2: CLI timeout (%.1fs)", timeout)
        return None
    except Exception as e:
        logger.warning("stage2: subprocess error: %s", e)
        return None

    if result.returncode != 0:
        logger.info("stage2: CLI exit %d stderr=%r", result.returncode, (result.stderr or "")[:200])
        return None

    return (result.stdout or "").strip() or None


# ── FIFO context (for SELF_HANDLE / DELEGATE_OPUS) ───────────────────────────

def _build_fifo_context(session_id: str) -> str:
    if not session_id:
        return ""
    try:
        from vault_web.recent_turns import get_recent  # type: ignore
        raw = get_recent(session_id, n=FIFO_TURN_COUNT)
    except Exception as e:
        logger.warning("stage2 FIFO fetch failed: %s", e)
        return ""
    if not raw:
        return ""
    summaries = list(raw)  # copy so we don't mutate the caller's list
    total = sum(len(s) + 1 for s in summaries)
    while summaries and total > FIFO_CHAR_CAP:
        dropped = summaries.pop(0)
        total -= len(dropped) + 1
    return "\n".join(summaries)


# ── Result helpers ────────────────────────────────────────────────────────────

def _result(
    response: str = "",
    delegate: bool = False,
    client_tools: Optional[list] = None,
    conversation_end: bool = False,
    delegate_context: str = "",
) -> dict:
    return {
        "response": response,
        "delegate": delegate,
        "client_tools": client_tools or [],
        "conversation_end": conversation_end,
        "delegate_context": delegate_context,  # injected into Opus context when delegate=True
    }


# ── Dispatch handlers ─────────────────────────────────────────────────────────

async def _handle_send_message(metadata: dict, session_id: str) -> dict:
    """Fast path: resolve recipient, check coherence, emit CLIENT_TOOL or delegate."""
    try:
        from agent_skills.sms_helpers import resolve_recipient  # type: ignore
    except Exception as e:
        logger.warning("stage2 SEND_MESSAGE: sms_helpers import failed: %s", e)
        return _result(delegate=True)

    recipient_raw = metadata.get("recipient", "")
    body = metadata.get("body", "")
    # Normalize coherent to bool regardless of how Stage 1 returned it
    raw_coherent = metadata.get("coherent", False)
    coherent = raw_coherent is True or str(raw_coherent).lower() == "yes"

    resolved = resolve_recipient(recipient_raw)

    if resolved is None:
        # Recipient unresolved — delegate to Opus with alias-learning context
        ctx = _UNRESOLVED_RECIPIENT_TMPL.format(recipient=recipient_raw, body=body)
        logger.info("stage2 SEND_MESSAGE: recipient '%s' unresolved — delegating", recipient_raw)
        return _result(delegate=True, delegate_context=ctx)

    phone = resolved["phone_number"]
    display = resolved["display_name"]

    if not coherent:
        # Body is garbled — delegate to Opus for draft-confirm flow
        ctx = _INCOHERENT_SMS_TMPL.format(recipient=display, body=body, phone=phone)
        logger.info("stage2 SEND_MESSAGE: coherence=no for '%s' — delegating", display)
        return _result(delegate=True, delegate_context=ctx)

    # Fast path: send immediately using sms_send_direct (no draft slot required)
    logger.info("stage2 SEND_MESSAGE: fast-path → %s (%s)", display, phone)
    return _result(
        response="msg sent",
        client_tools=[{
            "name": "contacts.sms_send_direct",
            "args": {"phone_number": phone, "body": body},
        }],
    )


def _handle_end_conversation() -> dict:
    return _result(response="Ok.", conversation_end=True)


def _handle_get_time() -> dict:
    # The phone is authoritative for the user's timezone — delegate to client.
    # Server has no reliable way to know the user's local time (it may run in
    # a different TZ or on a remote host). Emit an empty response so the
    # Android handler's TTS is the only spoken output.
    return _result(
        response="",
        client_tools=[{"name": "device.speak_time", "args": {}}],
    )


def _handle_sync_messages() -> dict:
    return _result(
        response="Syncing your messages...",
        client_tools=[{"name": "sync.force_sms", "args": {}}],
    )


async def _handle_read_messages(task_context: str) -> dict:
    if not task_context:
        return _result(delegate=True)
    prompt = (
        "You are Jane, a friendly AI assistant. Summarize the following SMS inbox data "
        "for the user. Triage: personal messages from contacts first (important), then reminders, "
        "then skip spam/promos. Group by sender. Be concise.\n\n"
        + task_context
    )
    resp = await _gemma_call(prompt)
    if resp:
        return _result(response=resp)
    return _result(delegate=True)


async def _handle_read_email(task_context: str) -> dict:
    if not task_context:
        return _result(delegate=True)
    prompt = (
        "You are Jane, a friendly AI assistant. Summarize the following email inbox data "
        "for the user. Triage: personal/work emails first, skip promos/spam. "
        "Mention sender and subject. Be concise.\n\n"
        + task_context
    )
    resp = await _gemma_call(prompt)
    if resp:
        return _result(response=resp)
    return _result(delegate=True)


async def _handle_music_play(metadata: dict, task_context: str) -> dict:
    if not task_context:
        return _result(delegate=True)
    query = metadata.get("query", "music")
    prompt = (
        f"You are Jane. The user asked to play {query!r}. "
        "Announce this playlist enthusiastically in one short sentence. "
        "The playlist data is below:\n\n"
        + task_context
    )
    resp = await _gemma_call(prompt)

    # Extract playlist_id from task_context if present
    import re
    pid_match = re.search(r"Playlist ID:\s*(\S+)", task_context)
    playlist_id = pid_match.group(1) if pid_match else ""

    tools = []
    if playlist_id:
        tools = [{"name": "music.play", "args": {"playlist_id": playlist_id}}]

    return _result(response=resp or f"Playing {query}...", client_tools=tools)


async def _handle_shopping_list(metadata: dict, task_context: str, message: str) -> dict:
    if task_context:
        # Pre-processed result from _build_task_context
        prompt = (
            "You are Jane. Confirm this shopping list action in one short friendly sentence:\n\n"
            + task_context
        )
        resp = await _gemma_call(prompt)
        if resp:
            return _result(response=resp)
    return _result(delegate=True)


async def _handle_greeting(session_id: str, message: str) -> dict:
    """Respond to a greeting using recent FIFO context — no Opus delegation."""
    fifo = _build_fifo_context(session_id)
    parts = [
        "You are Jane, a warm and concise AI assistant. "
        "The user said a greeting. Reply naturally in 1 short sentence. "
        "Use the recent conversation history if it helps make the response feel connected.",
    ]
    if fifo:
        parts.append(f"\nRecent history:\n{fifo}")
    parts.append(f"\nUser: {message.strip()}")
    prompt = "\n".join(parts)
    resp = await _gemma_call(prompt)
    if resp:
        return _result(response=resp)
    # Fallback if model times out
    return _result(response="Hey!")


async def _handle_self_handle(session_id: str, message: str) -> dict:
    fifo = _build_fifo_context(session_id)
    parts = [
        "You are Jane, a warm and concise AI assistant. "
        "Respond directly to the user's message in 1-2 short sentences.",
    ]
    if fifo:
        parts.append(f"\nRecent history:\n{fifo}")
    parts.append(f"\nUser: {message.strip()}")
    prompt = "\n".join(parts)
    resp = await _gemma_call(prompt)
    if resp:
        return _result(response=resp)
    return _result(delegate=True)


async def _handle_delegate_opus(session_id: str, message: str) -> dict:
    fifo = _build_fifo_context(session_id)
    parts = [
        "You are Jane. The user's request needs deeper thought. "
        "Generate a very short acknowledgment (5-10 words max) that you're looking into it. "
        "Examples: 'Looking into that...', 'On it.', 'Let me check that for you.'",
    ]
    if fifo:
        parts.append(f"\nRecent history:\n{fifo}")
    parts.append(f"\nUser: {message.strip()}")
    prompt = "\n".join(parts)
    ack = await _gemma_call(prompt)
    return _result(response=ack or "On it...", delegate=True)


# ── Public entry point ────────────────────────────────────────────────────────

async def stage2_execute(
    classification: str,
    metadata: dict,
    task_context: str,
    session_id: str,
    message: str,
) -> dict:
    """Dispatch classification to the appropriate handler.

    Args:
        classification: Stage 1 result (e.g. "SEND_MESSAGE")
        metadata:       Stage 1 metadata dict (recipient, body, coherent, query, etc.)
        task_context:   Pre-fetched data block (SMS inbox, email, playlist) — empty string
                        for intents that don't need it
        session_id:     Session ID for FIFO context lookup
        message:        Original user message (for conversational intents)

    Returns:
        dict with keys: response, delegate, client_tools, conversation_end, delegate_context
    """
    cls = (classification or "DELEGATE_OPUS").upper()
    logger.info("stage2: dispatching %s (session=%s)", cls, session_id[:12] if session_id else "?")

    if cls == "SEND_MESSAGE":
        return await _handle_send_message(metadata, session_id)
    elif cls == "END_CONVERSATION":
        return _handle_end_conversation()
    elif cls == "SYNC_MESSAGES":
        return _handle_sync_messages()
    elif cls == "GET_TIME":
        return _handle_get_time()
    elif cls == "READ_MESSAGES":
        return await _handle_read_messages(task_context)
    elif cls == "READ_EMAIL":
        return await _handle_read_email(task_context)
    elif cls == "MUSIC_PLAY":
        return await _handle_music_play(metadata, task_context)
    elif cls == "SHOPPING_LIST":
        return await _handle_shopping_list(metadata, task_context, message)
    elif cls == "SELF_HANDLE":
        return await _handle_self_handle(session_id, message)
    elif cls == "GREETING":
        # qwen2.5:7b handles it directly with FIFO context — no Opus needed
        return await _handle_greeting(session_id, message)
    elif cls == "DELEGATE_OPUS":
        return await _handle_delegate_opus(session_id, message)
    else:
        logger.warning("stage2: unknown classification '%s' — delegating", cls)
        return _result(delegate=True)
