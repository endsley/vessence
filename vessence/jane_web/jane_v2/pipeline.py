"""Pipeline orchestrator for v2 Jane.

Entry points used by main.py:
  - handle_chat(body, request)         → non-streaming /api/jane/chat
  - handle_chat_stream(body, request)  → streaming /api/jane/chat/stream

3-stage flow:
  Stage 1: classify the prompt via ChromaDB embeddings (~200 ms)
  Stage 2: dispatch to the class pack's handler in
           jane_web/jane_v2/classes/<name>/. Handler lookup is
           dynamic — no hardcoded class names in this file.
  Stage 3: everything else → v1's brain (stream_message / _handle_jane_chat).

Stage 2 returning None signals "I can't answer this" — the pipeline
treats that as a request to escalate to Stage 3.

v1 is never modified.

Stage 1 + Stage 2 logic is shared between streaming and non-streaming
entry points via `_classify_and_try_stage2()`. Only Stage 3 differs
per entry point because streaming delegates to v1's `stream_message`
(async generator) while non-streaming calls `_handle_jane_chat`.

Adding a new class = adding a new folder under classes/. This file
never needs to change.
"""

from __future__ import annotations

import json
import logging
import time
import asyncio
from typing import Any, AsyncIterator

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from . import (
    pending_action_resolver,
    recent_context,
    stage1_classifier,
    stage2_dispatcher,
    stage3_escalate,
)
from jane_web.session_context import set_current_session_id

logger = logging.getLogger(__name__)


_DEFAULT_ESCALATE_ACK = "Let me think about that…"


# ─── shared helpers ──────────────────────────────────────────────────────────


_AWAITING_RE = __import__("re").compile(
    r"\[\[AWAITING:\s*([A-Za-z0-9_\-\s]{1,200})\s*\]\]\s*\Z"
)


def _inject_self_improvement_context(body):
    """Inject recent self-improve vocal summaries so Opus can answer
    conversationally without reciting code or exit codes."""
    try:
        import sys as _sys
        _sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
        from agent_skills.self_improve_log import read_recent_summaries
        entries = read_recent_summaries(days=14, limit=20)
    except Exception as exc:
        logger.warning("self_improvement injection: could not load summaries: %s", exc)
        return body

    log_path = "$VESSENCE_DATA_HOME/self_improve_vocal_log.jsonl"
    tech_logs = "$VESSENCE_DATA_HOME/logs/self_improve_*.log"
    if not entries:
        block = (
            "\n\n[SELF IMPROVEMENT CONTEXT]\n"
            f"Vocal summary log file: {log_path}\n"
            f"Technical job logs: {tech_logs}\n"
            "No recent self-improvement entries found (empty log or "
            "older than 14 days). Tell the user nothing's been logged "
            "yet and the nightly job may not have run recently.\n"
            "[END SELF IMPROVEMENT CONTEXT]"
        )
    else:
        # Group for the headline by job category
        from collections import Counter
        by_job = Counter(e.get("job", "?") for e in entries)

        lines = ["\n\n[SELF IMPROVEMENT CONTEXT]"]
        lines.append(f"Vocal summary log file: {log_path}")
        lines.append(f"Technical job logs: {tech_logs}")
        lines.append(
            "RESPONSE STYLE — CRITICAL. The user is on voice and doesn't "
            "want a long recital. Your reply should be CONVERSATIONAL:\n"
            "  1) Open with a one-sentence headline: how many changes in "
            "total and roughly what categories (e.g. 'I logged 7 changes "
            "overnight — mostly transcript review fixes plus a couple doc "
            "tweaks').\n"
            "  2) Ask which one the user wants to hear about, offering by "
            "NUMBER: 'want me to walk through number 3, the timer bug?'\n"
            "  3) Do NOT enumerate every entry. Do NOT read timestamps, "
            "job names, severity labels, or file paths aloud. Do NOT use "
            "bullet points or lists — speak it like a friend giving a "
            "quick update.\n"
            "  4) If the user asks for 'number N', jump to entry N below "
            "and speak its summary conversationally (one to three "
            "sentences).\n"
            "  5) If the user asks about a specific topic (timers, "
            "transcripts, etc.), filter to matching entries and apply "
            "the same short-headline-plus-offer pattern.\n\n"
            f"Total entries in context window: {len(entries)} "
            f"(most recent first). Job categories: "
            + ", ".join(f"{job} ({n})" for job, n in by_job.most_common())
            + "."
        )
        lines.append("")
        lines.append("Entries (numbered for drill-down reference):")
        for i, e in enumerate(entries, 1):
            ts = e.get("timestamp", "?")
            job = e.get("job", "?")
            sev = e.get("severity", "info")
            summ = e.get("summary", "").strip()
            lines.append(f"{i}. [{ts} | {job} | {sev}] {summ}")
        lines.append("[END SELF IMPROVEMENT CONTEXT]")
        block = "\n".join(lines)

    try:
        return body.model_copy(
            update={"message": (body.message or "") + block}
        )
    except AttributeError:
        return body.copy(
            update={"message": (body.message or "") + block}
        )


def _copy_body_with_appended_message(body, extra: str):
    if not extra:
        return body
    new_message = (getattr(body, "message", "") or "") + extra
    try:
        return body.model_copy(update={"message": new_message})
    except AttributeError:
        if hasattr(body, "copy"):
            return body.copy(update={"message": new_message})
        setattr(body, "message", new_message)
        return body


def _copy_body_with_prepended_message(body, extra: str):
    """Prepend `extra` ABOVE the existing message content.

    Used by the verify-first policy so the `<verify_first>` / `<memory_verify>`
    XML blocks are the first thing Opus reads in the user turn, not something
    tacked onto the end where they compete with later context injections for
    attention.
    """
    if not extra:
        return body
    existing = getattr(body, "message", "") or ""
    sep = "\n\n" if existing and not extra.endswith("\n\n") else ""
    new_message = extra + sep + existing
    try:
        return body.model_copy(update={"message": new_message})
    except AttributeError:
        if hasattr(body, "copy"):
            return body.copy(update={"message": new_message})
        setattr(body, "message", new_message)
        return body


async def _fetch_required_memory_evidence(prompt: str) -> tuple[str, bool]:
    """Query Chroma when the shared evidence policy requires memory."""
    try:
        from memory.v1.memory_retrieval import build_memory_sections
        from jane_web.verify_first_policy import has_meaningful_memory
        sections = await asyncio.to_thread(
            build_memory_sections,
            prompt,
            assistant_name="Jane",
        )
        memory_text = "\n\n".join(sections or [])
        return memory_text, has_meaningful_memory(memory_text)
    except Exception as exc:
        logger.warning("pipeline: required memory evidence lookup failed: %s", exc)
        return "", False


# Path to the condensed Jane architecture context. Generated nightly by
# startup_code/regenerate_jane_context.py from configs/*.md — single source
# of truth, two sinks (CLI hook + this web/android consumer). Read fresh on
# each Stage 3 code/system turn so a recent regen is picked up without a
# server restart. Missing file → silent skip (the Read tool is still there).
import os as _os
_JANE_CTX_WEB_PATH = _os.environ.get(
    "JANE_CONTEXT_WEB_OUTPUT",
    "/home/chieh/ambient/vessence-data/cache/jane_context_web.txt",
)
_JANE_CTX_MAX_CHARS = 6000  # safety cap — file is ~5KB today


def _load_jane_architecture_context() -> str:
    """Read the condensed architecture context, or '' if missing/empty."""
    try:
        from pathlib import Path as _P
        p = _P(_JANE_CTX_WEB_PATH)
        if not p.exists():
            return ""
        text = p.read_text(encoding="utf-8").strip()
        if not text:
            return ""
        if len(text) > _JANE_CTX_MAX_CHARS:
            text = text[:_JANE_CTX_MAX_CHARS] + "\n[… truncated]"
        return text
    except Exception as exc:
        logger.warning("pipeline: jane context load failed: %s", exc)
        return ""


def _dedup_memory_for_session(memory_text: str, session_id: str) -> str:
    """Filter chunks already injected for this session (cross-turn dedup).

    Reuses the CLI's per-entry hash/cache at /tmp/jane_mem_seen_<sid>.txt so
    chat, CLI, and web all share a single dedup store when they happen to
    use the same session_id. The CLI cache file format is stable (one MD5
    hash per line), so concurrent use is safe.
    """
    if not memory_text or not session_id:
        return memory_text
    try:
        import sys as _sys
        _path = "/home/chieh/ambient/vessence/startup_code"
        if _path not in _sys.path:
            _sys.path.insert(0, _path)
        from session_memory_dedup import dedup as _dedup  # type: ignore
        return _dedup(memory_text, session_id)
    except Exception as exc:
        logger.warning("pipeline: memory dedup failed (sid=%s): %s", session_id[:12], exc)
        return memory_text


async def _apply_evidence_policy(body, prompt: str, session_id: str = "") -> tuple[Any, dict]:
    """Apply shared code/memory evidence requirements to a Stage 3 body."""
    metadata = {
        "required": False,
        "requires_code": False,
        "requires_memory": False,
        "memory_evidence": False,
        "memory_chars": 0,
        "memory_chars_after_dedup": 0,
        "architecture_context_chars": 0,
    }
    try:
        from jane_web.verify_first_policy import (
            classify_evidence_requirements,
            instruction_for_requirements,
        )
        req = classify_evidence_requirements(prompt)
        metadata.update({
            "required": req.any,
            "requires_code": req.code,
            "requires_memory": req.memory,
        })
        if not req.any:
            return body, metadata
        # Build the verify-first block as a single prepended payload so it
        # sits at the TOP of the user turn, before any other injected context
        # (self-improvement, stage3_followup hints, sms drafts). Opus weighs
        # top-of-turn XML directives more reliably than trailing appends.
        verify_block = instruction_for_requirements(req)
        # For code/architecture turns, also inject the condensed Jane system
        # context (generated nightly from configs/*.md by
        # startup_code/regenerate_jane_context.py). Single source of truth,
        # shared with the CLI hook. Scoped to req.code so memory-only or
        # chitchat escalations don't pay the ~5KB token tax.
        if req.code:
            arch_ctx = _load_jane_architecture_context()
            if arch_ctx:
                verify_block = (
                    "<jane_architecture>\n"
                    "Authoritative snapshot of Jane's system. Use this before "
                    "guessing about architecture, cron jobs, or which file "
                    "owns what. If you need detail beyond this summary, Read "
                    "the specific configs/*.md file.\n\n"
                    + arch_ctx +
                    "\n</jane_architecture>\n\n"
                    + verify_block
                )
                metadata["architecture_context_chars"] = len(arch_ctx)
        if req.memory:
            memory_text, memory_ok = await _fetch_required_memory_evidence(prompt)
            metadata["memory_evidence"] = memory_ok
            metadata["memory_chars"] = len(memory_text or "")
            if memory_text:
                deduped = _dedup_memory_for_session(memory_text, session_id)
                metadata["memory_chars_after_dedup"] = len(deduped or "")
                if deduped and deduped.strip():
                    verify_block = (
                        verify_block
                        + "\n\n[REQUIRED CHROMA MEMORY EVIDENCE]\n"
                        + deduped
                        + "\n[END REQUIRED CHROMA MEMORY EVIDENCE]"
                    )
        body = _copy_body_with_prepended_message(body, verify_block)
        logger.info(
            "pipeline: evidence policy applied code=%s memory=%s memory_ok=%s "
            "chars=%d after_dedup=%d arch_ctx=%d prompt=%r",
            req.code, req.memory, metadata["memory_evidence"],
            metadata["memory_chars"], metadata["memory_chars_after_dedup"],
            metadata["architecture_context_chars"], prompt[:80],
        )
    except Exception as exc:
        logger.warning("pipeline: evidence policy failed: %s", exc)
    return body, metadata


class _AwaitingDeltaStripper:
    """Strip trailing `[[AWAITING:<topic>]]` markers from streaming Stage 3
    deltas before they reach the client.

    Markers are always at the END of the response, but may arrive split
    across chunks (e.g. "answer  [[AWAIT", "ING:pasta]]"). Two-state
    machine:

      STREAMING  : normal flow. Keep a tiny trailing buffer that might
                   be the beginning of a marker; emit only what's
                   definitely not part of one.
      SUPPRESS   : saw `[[AWAITING:`, everything from here to end of
                   stream is dropped.

    Usage:
        stripper = _AwaitingDeltaStripper()
        for chunk in stream:
            out = stripper.feed(chunk)
            if out:
                yield_delta(out)
        tail = stripper.flush()
        if tail:
            yield_delta(tail)
    """

    _MARKER_START = "[[AWAITING:"
    # The length of _MARKER_START minus one — the longest trailing
    # prefix we might have seen that's still ambiguous.
    _AMBIGUOUS = len(_MARKER_START) - 1

    def __init__(self) -> None:
        self._buffer = ""
        self._suppress = False

    def feed(self, chunk: str) -> str:
        if self._suppress or not chunk:
            return ""

        combined = self._buffer + chunk

        # Fast path: marker opener anywhere in combined → emit before it,
        # enter suppress mode, drop the rest.
        start = combined.find(self._MARKER_START)
        if start >= 0:
            self._buffer = ""
            self._suppress = True
            return combined[:start]

        # No complete marker opener yet. Safe to emit all but the last
        # `_AMBIGUOUS` chars — those might be a partial `[[AWAITING:`
        # prefix that completes in the next chunk.
        if len(combined) <= self._AMBIGUOUS:
            self._buffer = combined
            return ""

        safe_len = len(combined) - self._AMBIGUOUS
        out = combined[:safe_len]
        self._buffer = combined[safe_len:]
        return out

    def flush(self) -> str:
        """End of stream — emit anything left in buffer (it wasn't a marker).

        If we entered suppress mode, return nothing. Otherwise whatever's
        in the buffer is just regular text shorter than marker length.
        """
        if self._suppress:
            self._buffer = ""
            return ""
        out = self._buffer
        self._buffer = ""
        return out


def _extract_awaiting_marker(text: str) -> tuple[str, str | None]:
    """Scan a Stage 3 response for a TRAILING [[AWAITING:<topic>]] marker.

    The marker must be the last non-whitespace thing in the response —
    Opus echoing the instruction mid-reply is ignored. This prevents
    accidental (or injected) mid-text markers from activating a
    follow-up.

    Returns (cleaned_text, topic). If no trailing marker is present,
    topic is None and cleaned_text == text.
    """
    if not text or "[[AWAITING:" not in text:
        return text, None
    m = _AWAITING_RE.search(text)
    if not m:
        return text, None
    topic = m.group(1).strip().replace(" ", "_")[:60] or None
    cleaned = text[:m.start()].rstrip()
    return cleaned, topic


def _persist_turn_to_fifo(
    session_id: str | None,
    user_prompt: str,
    jane_response: str,
    *,
    stage: str = "stage2",
    intent: str = "",
    confidence: str = "",
    handler_structured: dict | None = None,
    extras: dict | None = None,
) -> None:
    """Persist a completed turn to the FIFO as a structured record.

    Stage 2 and Stage 3 both call this so the next turn's resolver + Stage
    1 packet + Stage 3 context see the full conversation history.

    Handlers can opt into richer context by returning a ``structured``
    field alongside ``text``; it's merged in here (entities / pending_action
    / safety etc.).
    """
    if not session_id or not jane_response:
        return
    try:
        from vault_web.recent_turns import add_structured, _format_turn_compact
        record: dict = {
            "user_text": user_prompt or "",
            "assistant_text": jane_response,
            "summary": _format_turn_compact(user_prompt or "", jane_response),
            "stage": stage,
            "intent": intent or "",
        }
        if confidence:
            record["confidence"] = confidence
        if handler_structured:
            # Shallow merge: handler-provided fields win.
            for k, v in handler_structured.items():
                if v is not None:
                    record[k] = v
        if extras:
            if extras.get("client_tools"):
                record.setdefault("tool_results", []).extend(
                    [{"name": t.get("name") or t.get("tool"), "args": t.get("args", {})}
                     for t in extras["client_tools"]]
                )
            if extras.get("conversation_end"):
                record.setdefault("metadata", {})["conversation_end"] = True
            if extras.get("evidence"):
                record.setdefault("metadata", {})["evidence"] = extras["evidence"]
        add_structured(session_id, record)
    except Exception as e:
        logger.warning("pipeline: failed to persist turn to FIFO: %s", e)


# Backward-compatible alias for older callers/tests that imported the
# previous name. New code should use _persist_turn_to_fifo directly.
def _persist_stage2_to_fifo(session_id: str | None, user_prompt: str, jane_response: str) -> None:
    _persist_turn_to_fifo(session_id, user_prompt, jane_response, stage="stage2")


def _ack_for(class_name: str, *, escalate: bool) -> str | None:
    """Return the static ack text for a class from metadata, or None
    if the class explicitly suppresses the ack (ack=None in metadata)."""
    meta = stage2_dispatcher.metadata_for(class_name) or {}
    key = "escalate_ack" if escalate else "ack"
    # Distinguish between "ack not set" (use default) and "ack = None" (suppress)
    if key in meta and meta[key] is None:
        return None  # explicitly suppressed
    return meta.get(key) or _DEFAULT_ESCALATE_ACK


def _fifo_as_fake_history(session_id: str | None) -> list[dict]:
    """Pull recent Haiku summaries from the FIFO and shape them as a
    `[{role, content}]` list so v1's classify_prompt can consume them.

    FIFO entries are per-turn narrative summaries (user + jane combined),
    not clean role-separated turns. We fake each as an "assistant" turn
    so the classifier sees them as background context. v1 already caps
    the history at 600 chars before calling gemma, so even a full FIFO
    is auto-trimmed to fit the ack budget.
    """
    if not session_id:
        return []
    try:
        from vault_web.recent_turns import get_recent
        summaries = get_recent(session_id, n=10)
    except Exception as e:
        logger.warning("_fifo_as_fake_history: FIFO read failed: %s", e)
        return []
    return [{"role": "assistant", "content": s} for s in summaries if s]


import random as _random

# Heuristics for estimating Opus duration without running it.
def _estimate_duration(prompt: str) -> str:
    """Return 'a few seconds' | 'a minute or two' | 'a while' based on prompt."""
    p = prompt.lower()
    word_count = len(prompt.split())
    long_signals = ("build", "implement", "refactor", "write code",
                    "debug", "analyze the codebase", "trace through",
                    "compare and contrast", "summarize the entire")
    medium_signals = ("research", "look online", "compare", "analyze",
                      "explain how", "explain why", "walk me through",
                      "what are the differences", "pros and cons",
                      "investigate", "trace")
    if any(s in p for s in long_signals) or word_count > 60:
        return "a while"
    if any(s in p for s in medium_signals) or word_count > 25:
        return "a minute or two"
    return "a few seconds"


_ACK_FALLBACK = "Got it, give me a moment to look into that."


async def _generate_delegate_ack(prompt: str, session_id: str | None,
                                  cls: str = "others") -> str:
    """Produce an ack for a Stage 3 escalation using the local LLM.

    Two-part structured response:
      Part 1: acknowledge understanding + intent ("Got it", "I'll work on it",
              "Let me think about that")
      Part 2: time estimate ("give me a sec", "this might take a few minutes",
              "could take a while")

    Uses qwen2.5:7b at higher temp for variety. Falls back to a static
    sentence on failure. ~700ms cost, runs in parallel with Stage 3 brain
    so net latency is unchanged.
    """
    import os
    import httpx
    from jane_web.jane_v2.models import LOCAL_LLM, LOCAL_LLM_NUM_CTX, OLLAMA_KEEP_ALIVE
    duration = _estimate_duration(prompt)
    model = os.environ.get("JANE_ACK_MODEL", LOCAL_LLM)
    # If the ack model IS the pinned local LLM, inherit the pin's keep_alive
    # (-1 = forever) so this call doesn't shorten the runner's retention timer
    # and evict the model. Per Ollama scheduler, every request's keep_alive
    # REPLACES the existing runner.sessionDuration — a "1h" here would defeat
    # the startup warmup's -1 pin and cause cold loads after 1h idle.
    ack_keep_alive = OLLAMA_KEEP_ALIVE if model == LOCAL_LLM else "1h"
    # Force variety by REQUIRING a random opener per call. qwen otherwise
    # anchors on "Sure thing" no matter the temperature.
    openers = [
        "Got it", "Yeah", "Alright", "Okay", "Hmm",
        "Interesting one", "Good question", "Let me think about it",
        "I can do that", "On it", "Right", "Hmm let me see",
        "Mmkay", "Cool", "Oh nice", "Yep", "Sure", "Sure thing",
        "Fair", "Solid one", "Heh, yeah", "Ah",
    ]
    chosen_opener = _random.choice(openers)
    gen_prompt = (
        f"Write ONE casual sentence with two parts:\n"
        f"  PART 1 — START with: \"{chosen_opener}\". You may extend it with a few "
        f"more words but keep that as your opening.\n"
        f"  PART 2 — say it'll take about {duration}, in your own natural words.\n\n"
        f"Be casual like a friend. Never use the user's name. No questions. "
        f"No filler. One sentence only.\n\n"
        f"User said: {prompt.strip()[:300]}\n\n"
        f"Your acknowledgment (must start with \"{chosen_opener}\"):"
    )
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model, "prompt": gen_prompt, "stream": False,
                    "think": False,
                    "options": {"temperature": 1.0, "top_p": 0.95, "num_predict": 60, "num_ctx": LOCAL_LLM_NUM_CTX},
                    "keep_alive": ack_keep_alive,
                },
            )
            r.raise_for_status()
            text = (r.json().get("response") or "").strip()
            # Strip stray quotes the model sometimes adds
            text = text.strip('"').strip("'").strip()
            return text or _ACK_FALLBACK
    except Exception as e:
        logger.warning("ack generation failed (%s) — using fallback", e)
        return _ACK_FALLBACK


def _ndjson(event_type: str, data=None, **extra) -> str:
    payload = {"type": event_type}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=True) + "\n"


def _load_v1_chat():
    """Import v1's non-streaming handler lazily."""
    try:
        from jane_web.main import _handle_jane_chat
        return _handle_jane_chat
    except Exception as e:
        logger.exception("jane_v2: failed to import v1 _handle_jane_chat: %s", e)
        return None


def _assemble_music_text(result: dict) -> str:
    """Append `[MUSIC_PLAY:<id>]` to text when the handler returned a
    playlist_id. Idempotent — skips if already present."""
    text = result.get("text", "")
    pid = result.get("playlist_id")
    if pid and "[MUSIC_PLAY:" not in text:
        text = text.rstrip() + f" [MUSIC_PLAY:{pid}]"
    return text


def _stage2_response_parts(result: dict) -> tuple[str, dict[str, Any]]:
    """Normalize a Stage 2 handler result into (user-visible text, extras)."""
    text = _assemble_music_text(result)
    extras: dict[str, Any] = {}
    if result.get("playlist_id"):
        extras["playlist_id"] = result["playlist_id"]
        extras["playlist_name"] = result.get("playlist_name")
    if result.get("client_tools"):
        extras["client_tools"] = result["client_tools"]
    if result.get("conversation_end"):
        extras["conversation_end"] = True
    return text, extras


def _resolve_pending_sms_confirmation(pending: dict) -> dict:
    """Build a Stage 2-shaped result dict that sends the pending SMS.

    Marks the pending action as `resolved` in a structured record so the
    next resolver call won't re-confirm the same pending twice.
    """
    import json as _json
    data = pending.get("data") or {}
    phone = data.get("phone_number") or ""
    body = data.get("body") or data.get("message_body") or ""
    display = data.get("display_name") or data.get("recipient") or "them"
    tool_args = _json.dumps({"phone_number": phone, "body": body})
    marker = f"[[CLIENT_TOOL:contacts.sms_send_direct:{tool_args}]]"
    return {
        "text": f"Sending to {display}. {marker}",
        "structured": {
            "intent": "send message",
            "entities": {"recipient": display, "message_body": body,
                         "phone_number": phone},
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "status": "resolved",
                "resolution": "confirmed",
            },
            "safety": {"side_effectful": True, "requires_confirmation": False},
        },
    }


def _cancel_pending_sms_confirmation(pending: dict) -> dict:
    """Build a Stage 2-shaped result dict that drops the pending SMS."""
    data = pending.get("data") or {}
    display = data.get("display_name") or data.get("recipient") or "them"
    return {
        "text": f"Okay, not sending that to {display}.",
        "structured": {
            "intent": "send message",
            "pending_action": {
                "type": "SEND_MESSAGE_CONFIRMATION",
                "status": "resolved",
                "resolution": "cancelled",
            },
        },
    }


# ─── sms_draft short-circuit helpers ─────────────────────────────────────────
#
# Stage 3 (Opus) sometimes emits the full draft protocol (sms_draft →
# sms_send) rather than the single-shot sms_send_direct. When that
# happens we track the open draft in FIFO as SEND_MESSAGE_DRAFT_OPEN so
# the next turn's user confirm/cancel/edit can short-circuit past Stage 1
# and Stage 2 and directly emit the paired sms_send / sms_cancel /
# sms_draft_update marker with the EXISTING draft_id.

_SMS_DRAFT_MARKER_RE = __import__("re").compile(
    r"\[\[CLIENT_TOOL:contacts\.(sms_draft|sms_draft_update|sms_send|sms_cancel):"
    r"(\{[^\n]*?\})\]\]"
)


def _extract_sms_draft_state(text: str) -> dict | None:
    """Scan Stage 3 output for SMS draft markers. Return the latest
    open draft as {draft_id, query, body}, or None if no draft is open
    (e.g. sms_send or sms_cancel closed it, or no markers at all).

    Multiple markers may appear in one turn (e.g. draft then an update).
    We walk them in order and track whether a draft is open at the end.
    """
    if not text or "[[CLIENT_TOOL:contacts.sms_" not in text:
        return None
    import json as _json
    state: dict | None = None
    for m in _SMS_DRAFT_MARKER_RE.finditer(text):
        tool = m.group(1)
        try:
            args = _json.loads(m.group(2))
        except Exception:
            continue
        if tool == "sms_draft":
            state = {
                "draft_id": args.get("draft_id") or "",
                "query": args.get("query") or "",
                "body": args.get("body") or "",
            }
        elif tool == "sms_draft_update":
            if state is not None:
                state["body"] = args.get("body", state.get("body", ""))
                # draft_id may be echoed — keep existing if args is missing
                if args.get("draft_id"):
                    state["draft_id"] = args["draft_id"]
            else:
                # update without prior draft in this turn — start from scratch
                state = {
                    "draft_id": args.get("draft_id") or "",
                    "query": "",
                    "body": args.get("body") or "",
                }
        elif tool in ("sms_send", "sms_cancel"):
            # Draft is closed — nothing pending after this.
            state = None
    if state and state.get("draft_id") and state.get("body"):
        return state
    return None


def _resolve_pending_sms_draft_send(pending: dict) -> dict:
    """User confirmed an open sms_draft. Emit sms_send with the draft_id."""
    import json as _json
    data = pending.get("data") or {}
    draft_id = data.get("draft_id") or ""
    query = data.get("query") or data.get("display_name") or data.get("recipient") or "them"
    body = data.get("body") or ""
    tool_args = _json.dumps({"draft_id": draft_id})
    marker = f"[[CLIENT_TOOL:contacts.sms_send:{tool_args}]]"
    return {
        "text": f"Sending to {query}. {marker}",
        "structured": {
            "intent": "send message",
            "entities": {"recipient": query, "message_body": body,
                         "draft_id": draft_id},
            "pending_action": {
                "type": "SEND_MESSAGE_DRAFT_OPEN",
                "status": "resolved",
                "resolution": "sent",
            },
            "safety": {"side_effectful": True, "requires_confirmation": False},
        },
    }


def _cancel_pending_sms_draft(pending: dict) -> dict:
    """User cancelled an open sms_draft. Emit sms_cancel with the draft_id."""
    import json as _json
    data = pending.get("data") or {}
    draft_id = data.get("draft_id") or ""
    query = data.get("query") or data.get("display_name") or data.get("recipient") or "them"
    tool_args = _json.dumps({"draft_id": draft_id})
    marker = f"[[CLIENT_TOOL:contacts.sms_cancel:{tool_args}]]"
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


async def _resolve_pending_sms_draft_edit(pending: dict, edit_text: str) -> dict:
    """User asked to revise an open sms_draft. Compose a new body via a
    tiny LLM call (same local model the send_message handler uses) and
    emit sms_draft_update with the EXISTING draft_id — no round-trip
    through Opus.

    On LLM failure we fall back to a minimal "<old_body>. <edit_text>"
    concatenation so the draft still progresses rather than silently
    losing the user's edit.
    """
    import json as _json
    data = pending.get("data") or {}
    draft_id = data.get("draft_id") or ""
    query = data.get("query") or data.get("display_name") or data.get("recipient") or "them"
    old_body = data.get("body") or ""
    new_body = old_body

    compose_prompt = (
        "You are revising an SMS draft based on the user's edit instruction.\n"
        "CRITICAL: output ONLY the new message body — no preamble, no quotes, "
        "no 'Sure, here is' prefix. Just the revised SMS body text itself.\n\n"
        f"CURRENT DRAFT BODY: {old_body}\n"
        f"USER EDIT INSTRUCTION: {edit_text}\n\n"
        "NEW BODY:"
    )
    try:
        import httpx
        from jane_web.jane_v2.models import (
            LOCAL_LLM as _model,
            LOCAL_LLM_NUM_CTX as _num_ctx,
            OLLAMA_URL as _url,
        )
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(_url, json={
                "model": _model,
                "prompt": compose_prompt,
                "stream": False,
                "think": False,
                "options": {"temperature": 0.2, "num_predict": 80, "num_ctx": _num_ctx},
                "keep_alive": -1,
            })
            r.raise_for_status()
            composed = (r.json().get("response") or "").strip()
            # Strip any stray quotes / "NEW BODY:" echo
            composed = composed.strip('"').strip("'").strip()
            if composed.lower().startswith("new body:"):
                composed = composed[len("new body:"):].strip()
            if composed:
                new_body = composed
    except Exception as e:
        logger.warning("draft-edit compose failed (%s) — using fallback concat", e)
        new_body = f"{old_body}. {edit_text}".strip()

    tool_args = _json.dumps({"draft_id": draft_id, "body": new_body})
    marker = f"[[CLIENT_TOOL:contacts.sms_draft_update:{tool_args}]]"
    return {
        "text": f"Updated. To {query}: {new_body}. {marker}",
        "structured": {
            "intent": "send message",
            "entities": {"recipient": query, "message_body": new_body,
                         "draft_id": draft_id},
            "pending_action": {
                "type": "SEND_MESSAGE_DRAFT_OPEN",
                "status": "awaiting_user",
                "awaiting": "confirm_draft",
                "handler_class": "send message",
                "data": {
                    "draft_id": draft_id,
                    "query": query,
                    "body": new_body,
                },
            },
        },
    }


def _cookie_session_id(request) -> str | None:
    """Best-effort lookup of the cookie-derived session_id so the v2
    pipeline and v1's conversation_manager write FIFO rows under the
    SAME key. If the cookie isn't present or auth failed, returns None
    and the caller falls back to body.session_id.
    """
    try:
        from jane_web.main import get_or_bootstrap_session
    except Exception:
        return None
    try:
        sid, _ = get_or_bootstrap_session(request)
        return sid or None
    except Exception:
        return None


def _canonical_session_id(body, request) -> str | None:
    """Resolve the canonical session_id for a chat request.

    Preference order:
      1. body.session_id  — stable client-side id (jane_android_XXX, etc.)
      2. cookie session   — server-side fallback when client didn't send one

    This ONE id is then used for every FIFO read/write and threaded into
    Stage 3 so v1's conversation_manager writes under the same key. The
    old bug: pipeline wrote under body.session_id, escalate_stream wrote
    under the cookie session, pending actions disappeared between turns.
    """
    sid = (getattr(body, "session_id", None) or "").strip()
    if sid:
        return sid
    return _cookie_session_id(request)


async def _classify_and_try_stage2(
    prompt: str, session_id: str | None = None
) -> dict[str, Any]:
    """Run Stage 1 and (when applicable) Stage 2.

    This is the shared core used by both entry points. Returns a dict
    with everything the caller needs to build either a JSONResponse or
    a stream:

      cls, conf, classification
      stage1_ms, stage2_ms
      result        — Stage 2 handler output, or None if skipped/declined
      stage2_ack    — ack text to show while Stage 2 runs
      fallback_ack  — ack text to show when escalating to Stage 3
    """
    # ── Pre-Stage-1: deterministic pending-action resolver ────────────
    # If the last turn left an unresolved SMS confirmation in FIFO and
    # the user replied "yes"/"cancel", short-circuit Stage 1 so a raw
    # "yes" can't be mis-embedded as GREETING or OTHERS. Also handles
    # the generic STAGE2_FOLLOWUP loop — see pending_action_resolver.
    try:
        resolved = pending_action_resolver.resolve(session_id, prompt)
    except Exception as e:
        logger.warning("pipeline: resolver failed: %s", e)
        resolved = None
    if resolved:
        pending = resolved.get("pending") or {}
        action = resolved["action"]
        if action == "confirm":
            result = _resolve_pending_sms_confirmation(pending)
            cls = "send message"
        elif action == "sms_draft_send":
            # Short-circuit: open sms_draft + user confirmed → emit sms_send
            # with the existing draft_id. No Opus round-trip.
            result = _resolve_pending_sms_draft_send(pending)
            cls = "send message"
        elif action == "sms_draft_edit":
            # Short-circuit: open sms_draft + user asked to revise → compose
            # new body via local LLM and emit sms_draft_update.
            result = await _resolve_pending_sms_draft_edit(pending, prompt)
            cls = "send message"
        elif action == "cancel":
            # Cancel applies to STAGE2_FOLLOWUP, SEND_MESSAGE_CONFIRMATION,
            # and SEND_MESSAGE_DRAFT_OPEN.
            ptype = pending.get("type", "")
            if ptype == "STAGE2_FOLLOWUP":
                handler_class = pending.get("handler_class", "")
                result = {
                    "text": "Okay, never mind.",
                    "structured": {
                        "intent": handler_class,
                        "pending_action": {
                            "type": "STAGE2_FOLLOWUP",
                            "handler_class": handler_class,
                            "status": "cancelled",
                        },
                    },
                }
                cls = handler_class or "others"
            elif ptype == "SEND_MESSAGE_DRAFT_OPEN":
                result = _cancel_pending_sms_draft(pending)
                cls = "send message"
            else:
                result = _cancel_pending_sms_confirmation(pending)
                cls = "send message"
        elif action == "stage3_followup":
            # Opus asked a question last turn (emitted [[AWAITING:...]]).
            # Skip Stage 1 + Stage 2 — route straight to Stage 3 with a
            # contextual hint so Opus knows this reply is answering its
            # pending question.
            awaiting = pending.get("awaiting") or "previous_question"
            logger.info("jane_v2 pipeline: resolver → stage3_followup (awaiting=%s)",
                        awaiting)
            return {
                "cls": "stage3_followup", "conf": "High",
                "classification": "stage3_followup:High",
                "stage1_ms": 0, "stage2_ms": 0, "result": None,
                "stage2_ack": None, "fallback_ack": None,
                "force_stage3": True,
                "stage3_followup_topic": awaiting,
            }
        elif action == "followup":
            # Re-dispatch to the Stage 2 handler that's mid-conversation.
            handler_class = resolved["handler_class"]
            pending_data = resolved.get("pending_data", {})
            fifo_ctx = ""
            try:
                fifo_ctx = recent_context.render_stage2_context(session_id, max_turns=3)
            except Exception:
                pass
            try:
                result = await stage2_dispatcher.dispatch(
                    handler_class, prompt, context=fifo_ctx, pending=pending_data,
                )
            except Exception as e:
                logger.exception("pipeline: followup dispatch crashed: %s", e)
                result = None
            # If the handler explicitly asks to abandon, either re-run
            # Stage 1 or jump straight to Stage 3. Some follow-up prompts
            # are real questions rather than answers to the pending slot
            # (e.g. TODO awaiting category, user asks a question).
            if isinstance(result, dict) and result.get("abandon_pending"):
                structured = result.get("structured") or {}
                if result.get("force_stage3"):
                    logger.info("pipeline: handler abandoned pending → Stage 3")
                    return {
                        "cls": handler_class, "conf": "High",
                        "classification": f"{handler_class}:High",
                        "stage1_ms": 0, "stage2_ms": 0, "result": None,
                        "stage2_ack": None,
                        "fallback_ack": _ack_for(handler_class, escalate=True),
                        "force_stage3": True,
                        "resolve_pending_action": structured.get("pending_action"),
                    }
                logger.info("pipeline: handler abandoned pending → falling through to Stage 1")
                # Fall out of the `if resolved` block.
                resolved = None
            else:
                cls = handler_class
                logger.info("pipeline: followup handler %s → result=%s",
                            handler_class,
                            "ok" if result else "none")
        else:
            result = None
            cls = "others"
        if resolved:  # still live after possible abandon
            conf = "High"
            logger.info("jane_v2 pipeline: resolver → %s", action)
            return {
                "cls": cls, "conf": conf, "classification": f"{cls}:{conf}",
                "stage1_ms": 0, "stage2_ms": 0, "result": result,
                "stage2_ack": _ack_for(cls, escalate=False),
                "fallback_ack": _ack_for(cls, escalate=True),
            }

    # Stage 1
    _t1 = time.perf_counter()
    try:
        cls, conf = await stage1_classifier.classify(prompt, session_id=session_id)
    except Exception as e:
        logger.exception("jane_v2 pipeline: stage1 crashed: %s", e)
        cls, conf = "others", "Low"
    stage1_ms = int((time.perf_counter() - _t1) * 1000)
    classification = f"{cls}:{conf}"
    logger.info("jane_v2 pipeline: stage1 %s (%dms)", classification, stage1_ms)

    # Stage 2 (dispatcher)
    # Pass recent conversation context to handlers that declare a
    # `context=` parameter (e.g. greeting). Handlers that don't accept
    # it (weather, music) simply ignore it — the dispatcher checks
    # the handler's signature before passing kwargs.
    stage2_ms = 0
    result: dict | None = None

    # END_CONVERSATION short-circuit: gate-check first since this is destructive
    # (no Stage 3 recovery). Only fires if BOTH classifier confidence is high
    # AND the LLM gate confirms the user is really saying goodbye.
    if conf in ("High", "Medium") and cls == "end conversation":
        fifo_ctx = ""
        try:
            fifo_ctx = recent_context.render_stage2_context(session_id, max_turns=3)
        except Exception:
            pass
        if await stage2_dispatcher._gate_check("end conversation", prompt, fifo_ctx):
            result = {"text": "Ok.", "conversation_end": True}
        else:
            logger.info("pipeline: END_CONVERSATION gate rejected — escalating instead")

    if result is None and conf in ("High", "Medium") and cls != "others":
        fifo_ctx = ""
        try:
            fifo_ctx = recent_context.render_stage2_context(session_id, max_turns=3)
        except Exception:
            pass
        _t2 = time.perf_counter()
        try:
            result = await stage2_dispatcher.dispatch(cls, prompt, context=fifo_ctx, stage1_conf=conf)
        except Exception as e:
            logger.exception("jane_v2 pipeline: dispatcher crashed: %s", e)
            result = None
        stage2_ms = int((time.perf_counter() - _t2) * 1000)
        if result is not None:
            logger.info("jane_v2 pipeline: stage2 %s handler (%dms)", cls, stage2_ms)
        else:
            logger.info("jane_v2 pipeline: stage2 %s declined (%dms)", cls, stage2_ms)

    return {
        "cls": cls,
        "conf": conf,
        "classification": classification,
        "stage1_ms": stage1_ms,
        "stage2_ms": stage2_ms,
        "result": result,
        "stage2_ack": _ack_for(cls, escalate=False),
        "fallback_ack": _ack_for(cls, escalate=True),
    }


# ─── non-streaming entry point (/api/jane/chat) ──────────────────────────────


async def handle_chat(body, request: Request):
    """Non-streaming entry point. See module docstring for the response
    JSON shape (superset of v1's).
    """
    prompt = (body.message or "").strip()
    if not prompt:
        return JSONResponse({
            "response": "",
            "ack": "",
            "classification": "",
            "stage": "",
            "stage1_ms": 0,
            "stage2_ms": 0,
            "stage3_ms": 0,
            "files": [],
        })

    # Canonical session_id: prefer body (stable client id), fall back to
    # cookie. Used for every FIFO read/write in this request so a multi-
    # turn conversation never splits across two session_ids.
    canonical_sid = _canonical_session_id(body, request) or body.session_id
    set_current_session_id(canonical_sid)
    state = await _classify_and_try_stage2(prompt, canonical_sid)

    # ── Stage 2 success → return directly ──────────────────────────────
    if state["result"] is not None:
        text, extras = _stage2_response_parts(state["result"])
        # Strip [[CLIENT_TOOL:...]] markers from user-visible text
        # and surface them as structured client_tools in the JSON response
        from jane_web.jane_proxy import ToolMarkerExtractor
        _extractor = ToolMarkerExtractor()
        visible, tool_calls = _extractor.feed(text)
        tail, tail_calls = _extractor.flush()
        visible_text = (visible or "") + (tail or "")
        all_tool_calls = tool_calls + tail_calls
        resp: dict[str, Any] = {
            "response": visible_text or text,
            "ack": None,  # acks only emitted when Stage 3 runs
            "classification": state["classification"],
            "stage": "stage2",
            "stage1_ms": state["stage1_ms"],
            "stage2_ms": state["stage2_ms"],
            "stage3_ms": 0,
            "files": [],
        }
        if all_tool_calls:
            resp["client_tool_calls"] = all_tool_calls
        resp.update(extras)
        _persist_turn_to_fifo(
            canonical_sid, prompt, visible_text or text,
            stage="stage2",
            intent=state["cls"],
            confidence=state["conf"],
            handler_structured=state["result"].get("structured") if isinstance(state["result"], dict) else None,
            extras=extras,
        )
        return JSONResponse(resp)

    # ── Stage 3: delegate to v1's non-streaming brain ───────────────────
    # Generate a contextual ack first (uses v1's classify_prompt — topic
    # echo + time hint). Falls back to the static class ack on failure.
    dynamic_ack = await _generate_delegate_ack(
        body.message or "", canonical_sid, cls=state["cls"]
    )

    v1_chat = _load_v1_chat()
    if v1_chat is None:
        return JSONResponse(
            {
                "response": "Jane v2 pipeline is unavailable.",
                "ack": dynamic_ack,
                "classification": state["classification"],
                "stage": "stage3",
                "stage1_ms": state["stage1_ms"],
                "stage2_ms": state["stage2_ms"],
                "stage3_ms": 0,
                "files": [],
            },
            status_code=500,
        )

    effective_body = stage3_escalate._inject_structured_state(body)
    effective_body = stage3_escalate._maybe_voice_wrap(effective_body)
    # Inject SMS context for unresolved send-message requests
    if state["cls"] == "send message":
        sms_ctx = (
            "\n\n[SMS SEND REQUEST — Stage 2 could not resolve recipient]\n"
            "Use sms_send_direct: [[CLIENT_TOOL:contacts.sms_send_direct:"
            "{\"phone_number\":\"<number>\",\"body\":\"<message>\"}]]\n"
            "Resolve the recipient, confirm with user, send via sms_send_direct.\n"
            "[END SMS SEND REQUEST]"
        )
        try:
            effective_body = effective_body.model_copy(
                update={"message": (effective_body.message or "") + sms_ctx}
            )
        except AttributeError:
            effective_body = effective_body.copy(
                update={"message": (effective_body.message or "") + sms_ctx}
            )
    if state.get("stage3_followup_topic"):
        topic = state["stage3_followup_topic"]
        hint = (
            f"\n\n[STAGE3 FOLLOWUP] Your previous reply ended with "
            f"[[AWAITING:{topic}]] — the user's message above is their "
            f"answer to that pending question. Continue the task.\n"
        )
        try:
            effective_body = effective_body.model_copy(
                update={"message": (effective_body.message or "") + hint}
            )
        except AttributeError:
            effective_body = effective_body.copy(
                update={"message": (effective_body.message or "") + hint}
            )
    if state["cls"] == "self improvement":
        effective_body = _inject_self_improvement_context(effective_body)
    effective_body, evidence_meta = await _apply_evidence_policy(
        effective_body, prompt, session_id=canonical_sid
    )
    _t3 = time.perf_counter()
    v1_response = await v1_chat(effective_body, request)
    stage3_ms = int((time.perf_counter() - _t3) * 1000)
    logger.info("jane_v2 handle_chat: stage3 brain (%dms)", stage3_ms)

    # Inject v2 fields into v1's response body. Mutating in place
    # preserves cookies v1 already set on the Response object.
    try:
        v1_body = json.loads(v1_response.body.decode("utf-8"))
    except Exception:
        v1_body = {"response": "", "files": []}
    v1_body.setdefault("files", [])
    v1_body["ack"] = dynamic_ack
    v1_body["classification"] = state["classification"]
    v1_body["stage"] = "stage3"
    v1_body["stage1_ms"] = state["stage1_ms"]
    v1_body["stage2_ms"] = state["stage2_ms"]
    v1_body["stage3_ms"] = stage3_ms
    if evidence_meta.get("required"):
        v1_body["evidence"] = evidence_meta
    new_body_bytes = json.dumps(v1_body, ensure_ascii=True).encode("utf-8")
    v1_response.body = new_body_bytes
    v1_response.headers["content-length"] = str(len(new_body_bytes))
    # FIFO record for Stage 3 turn so the next pending-action resolver /
    # Stage 3 state block sees continuity. v1 has its own long-term memory,
    # so we only record a minimal handoff summary here.
    raw_response = v1_body.get("response", "") or ""
    cleaned_text, awaiting_topic = _extract_awaiting_marker(raw_response)
    structured_extras: dict | None = None
    # SMS draft tracking takes precedence over AWAITING. If Stage 3 opened
    # a draft (sms_draft / sms_draft_update without a closing sms_send or
    # sms_cancel), stash it so the next user reply short-circuits to send.
    draft_state = _extract_sms_draft_state(raw_response)
    if draft_state:
        import datetime as _dt
        structured_extras = {
            "intent": "send message",
            "pending_action": {
                "type": "SEND_MESSAGE_DRAFT_OPEN",
                "handler_class": "send message",
                "status": "awaiting_user",
                "awaiting": "confirm_draft",
                "data": draft_state,
                "expires_at": (
                    _dt.datetime.utcnow() + _dt.timedelta(minutes=5)
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        }
        logger.info("pipeline: stage3 (non-stream) SMS_DRAFT_OPEN draft_id=%s",
                    draft_state.get("draft_id", "")[:12])
    elif awaiting_topic:
        import datetime as _dt
        structured_extras = {
            "pending_action": {
                "type": "STAGE3_FOLLOWUP",
                "handler_class": "stage3",
                "status": "awaiting_user",
                "awaiting": awaiting_topic,
                "expires_at": (
                    _dt.datetime.utcnow() + _dt.timedelta(minutes=2)
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        }
        logger.info("pipeline: stage3 (non-stream) AWAITING → topic=%s",
                    awaiting_topic)
        # Strip marker from client-facing response too.
        v1_body["response"] = cleaned_text
        new_body_bytes = json.dumps(v1_body, ensure_ascii=True).encode("utf-8")
        v1_response.body = new_body_bytes
        v1_response.headers["content-length"] = str(len(new_body_bytes))
    resolved_pa = state.get("resolve_pending_action")
    if resolved_pa and not (structured_extras and structured_extras.get("pending_action")):
        structured_extras = {**(structured_extras or {}), "pending_action": resolved_pa}
    _persist_turn_to_fifo(
        canonical_sid, prompt, cleaned_text or raw_response,
        stage="stage3",
        intent=state["cls"],
        confidence=state["conf"],
        handler_structured=structured_extras,
        extras={"evidence": evidence_meta} if evidence_meta.get("required") else None,
    )
    return v1_response


def _persist_fifo_for_stream(
    stage3_text_parts: list[str],
    evidence_meta: dict,
    evidence_tool_counter,
    prompt: str,
    state: dict,
    canonical_sid: str | None,
) -> None:
    """Extract AWAITING / SMS-draft state from accumulated Stage 3 deltas
    and persist the FIFO record.

    Factored out so it can be called from INSIDE the async generator
    BEFORE yielding the ``done`` event.  This eliminates the race where
    the client receives ``done``, fires the next request, and the
    pending-action resolver sees stale FIFO state because the persist
    hadn't happened yet.
    """
    full_stage3_text = "".join(stage3_text_parts)
    if evidence_meta.get("required") and evidence_tool_counter is not None:
        try:
            from jane_web.verify_first_policy import summarize_verification_status
            evidence_meta.update(
                summarize_verification_status(
                    prompt,
                    evidence_tool_counter,
                    memory_evidence=bool(evidence_meta.get("memory_evidence")),
                )
            )
            if evidence_meta.get("flagged"):
                logger.warning("pipeline: evidence policy flagged stream turn: %s", evidence_meta)
        except Exception as exc:
            logger.warning("pipeline: evidence summary failed: %s", exc)
    cleaned_text, awaiting_topic = _extract_awaiting_marker(full_stage3_text)
    structured_extras: dict | None = None
    # SMS draft tracking wins over AWAITING when both appear.
    draft_state = _extract_sms_draft_state(full_stage3_text)
    if draft_state:
        import datetime as _dt
        structured_extras = {
            "intent": "send message",
            "pending_action": {
                "type": "SEND_MESSAGE_DRAFT_OPEN",
                "handler_class": "send message",
                "status": "awaiting_user",
                "awaiting": "confirm_draft",
                "data": draft_state,
                "expires_at": (
                    _dt.datetime.utcnow() + _dt.timedelta(minutes=5)
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        }
        logger.info("pipeline: stage3 (stream) SMS_DRAFT_OPEN draft_id=%s",
                    draft_state.get("draft_id", "")[:12])
    elif awaiting_topic:
        import datetime as _dt
        structured_extras = {
            "pending_action": {
                "type": "STAGE3_FOLLOWUP",
                "handler_class": "stage3",
                "status": "awaiting_user",
                "awaiting": awaiting_topic,
                "expires_at": (
                    _dt.datetime.utcnow() + _dt.timedelta(minutes=5)
                ).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        }
        logger.info("pipeline: stage3 emitted AWAITING marker → topic=%s",
                    awaiting_topic)
    resolved_pa = state.get("resolve_pending_action")
    if resolved_pa and not (structured_extras and structured_extras.get("pending_action")):
        structured_extras = {**(structured_extras or {}), "pending_action": resolved_pa}
    _persist_turn_to_fifo(
        canonical_sid, prompt, cleaned_text or full_stage3_text,
        stage="stage3",
        intent=state["cls"],
        confidence=state["conf"],
        handler_structured=structured_extras,
        extras={"evidence": evidence_meta} if evidence_meta.get("required") else None,
    )


# ─── streaming entry point (/api/jane/chat/stream) ───────────────────────────


async def handle_chat_stream(body, request: Request):
    """Streaming entry point. Yields NDJSON events compatible with
    existing Alpine/Android chat UI handlers."""
    prompt = (body.message or "").strip()

    # Canonical session_id: prefer body (stable client id), fall back to
    # cookie. Captured here so the inner _stream() generator and all FIFO
    # reads/writes share one id.
    canonical_sid = _canonical_session_id(body, request) or body.session_id
    set_current_session_id(canonical_sid)

    async def _stream() -> AsyncIterator[str]:
        if not prompt:
            yield _ndjson("done", "")
            return

        yield _ndjson("status", "Classifying…")
        state = await _classify_and_try_stage2(prompt, canonical_sid)

        # ── Stage 2 success → emit ack + delta + done ─────────────────
        if state["result"] is not None:
            # No ack when Stage 2 handles directly — acks only fire on Stage 3 escalation
            text, extras = _stage2_response_parts(state["result"])
            if extras.get("playlist_id"):
                yield _ndjson(
                    "tool_result",
                    f"playlist_id={extras['playlist_id']} "
                    f"name={extras.get('playlist_name')}",
                )
            # Extract [[CLIENT_TOOL:...]] markers from text and emit as
            # structured client_tool_call events (Android expects these)
            from jane_web.jane_proxy import ToolMarkerExtractor
            _extractor = ToolMarkerExtractor()
            visible, tool_calls = _extractor.feed(text)
            tail, tail_calls = _extractor.flush()
            visible_text = (visible or "") + (tail or "")
            for tc in tool_calls + tail_calls:
                # Android NdjsonParser uses asString on "data", so the
                # tool call payload must be a JSON *string*, not a nested object.
                yield _ndjson("client_tool_call", json.dumps(tc, ensure_ascii=True))
            # ALSO emit any structured client_tools from the handler result.
            # Some handlers (get_time, sync_messages) return tool calls in a
            # structured "client_tools" field rather than embedding markers
            # in text. Without this, those tools never reach Android.
            for ct in extras.pop("client_tools", []):
                tc_payload = {
                    "tool": ct.get("name", ct.get("tool", "unknown")),
                    "args": ct.get("args", {}),
                    "call_id": __import__("uuid").uuid4().hex[:16],
                }
                yield _ndjson("client_tool_call", json.dumps(tc_payload, ensure_ascii=True))
            yield _ndjson("delta", visible_text or text)
            yield _ndjson("done", visible_text or text, **extras)
            _persist_turn_to_fifo(
                canonical_sid, prompt, visible_text or text,
                stage="stage2",
                intent=state["cls"],
                confidence=state["conf"],
                handler_structured=state["result"].get("structured") if isinstance(state["result"], dict) else None,
                extras=extras,
            )
            return

        # ── Stage 3: delegate to v1's streaming brain ──────────────────
        # Generate a contextual ack via v1's classify_prompt (topic
        # echo + time hint). Static class ack is the safe fallback.
        dynamic_ack = await _generate_delegate_ack(
            body.message or "", canonical_sid, cls=state["cls"]
        )

        # Inject class-specific context into the message so Opus
        # knows how to handle the request (e.g., SMS protocol).
        effective_body = body
        if state["cls"] == "send message":
            sms_ctx = (
                "\n\n[SMS SEND REQUEST — Stage 2 could not resolve recipient]\n"
                "The user wants to send a TEXT MESSAGE (SMS). Use sms_send_direct:\n"
                "[[CLIENT_TOOL:contacts.sms_send_direct:{\"phone_number\":\"<number>\",\"body\":\"<message>\"}]]\n"
                "Steps: 1) Figure out who the recipient is from memory/contacts. "
                "2) Compose the message body (rewrite perspective: 'tell X I love her' → 'I love you'). "
                "3) Confirm with the user, then send via sms_send_direct. "
                "NEVER use contacts.call. NEVER use sms_draft for simple sends.\n"
                "[END SMS SEND REQUEST]"
            )
            try:
                effective_body = body.model_copy(
                    update={"message": (body.message or "") + sms_ctx}
                )
            except AttributeError:
                effective_body = body.copy(
                    update={"message": (body.message or "") + sms_ctx}
                )

        if state.get("stage3_followup_topic"):
            topic = state["stage3_followup_topic"]
            hint = (
                f"\n\n[STAGE3 FOLLOWUP] Your previous reply ended with "
                f"[[AWAITING:{topic}]] — the user's message above is "
                f"their answer to that pending question. Continue the "
                f"task.\n"
            )
            try:
                effective_body = effective_body.model_copy(
                    update={"message": (effective_body.message or "") + hint}
                )
            except AttributeError:
                effective_body = effective_body.copy(
                    update={"message": (effective_body.message or "") + hint}
                )

        if state["cls"] == "self improvement":
            effective_body = _inject_self_improvement_context(effective_body)

        effective_body, evidence_meta = await _apply_evidence_policy(
            effective_body, prompt, session_id=canonical_sid
        )

        reason = f"{state['cls']}:{state['conf']}"
        # Accumulate streamed deltas so we can persist a FIFO record at the end.
        # Also run deltas through a stripper so `[[AWAITING:...]]` markers
        # never reach the client's chat bubble / TTS.
        _stage3_text_parts: list[str] = []
        _fifo_persisted = False
        try:
            from jane_web.verify_first_policy import ToolUseCounter
            _evidence_tool_counter = ToolUseCounter()
        except Exception:
            _evidence_tool_counter = None
        stripper = _AwaitingDeltaStripper()
        async for ev in stage3_escalate.escalate_stream(
            effective_body, request, dynamic_ack, reason=reason,
            session_id_override=canonical_sid,
        ):
            # Try to parse the event; if it's a `delta`, filter the text
            # through the stripper and rewrite the event before yielding.
            try:
                payload = json.loads(ev)
            except Exception:
                payload = None
            if (
                isinstance(payload, dict)
                and payload.get("type") == "delta"
                and isinstance(payload.get("data"), str)
            ):
                raw = payload["data"]
                _stage3_text_parts.append(raw)  # for FIFO / marker extraction
                cleaned = stripper.feed(raw)
                if not cleaned:
                    continue  # buffered — don't send anything this tick
                payload["data"] = cleaned
                yield json.dumps(payload, ensure_ascii=True) + "\n"
                continue
            if (
                isinstance(payload, dict)
                and payload.get("type") == "tool_use"
                and _evidence_tool_counter is not None
            ):
                _evidence_tool_counter(str(payload.get("data") or "tool_use"))
            # Non-delta event — if we have buffered visible text, flush it
            # BEFORE passing through any `done`/terminal event.
            if (
                isinstance(payload, dict)
                and payload.get("type") in ("done", "error")
            ):
                tail = stripper.flush()
                if tail:
                    yield _ndjson("delta", tail)
                if payload.get("type") == "done" and isinstance(payload.get("data"), str):
                    cleaned_done, _ = _extract_awaiting_marker(payload["data"])
                    payload["data"] = cleaned_done
                    # ── Persist FIFO BEFORE yielding done ─────────────
                    # The client sees "done" and may immediately fire
                    # the next request. If we persist after yielding,
                    # the next turn's pending_action_resolver races
                    # against the FIFO write and often sees stale state
                    # (no AWAITING pending action → Stage 1 re-classifies).
                    _persist_fifo_for_stream(
                        _stage3_text_parts, evidence_meta,
                        _evidence_tool_counter, prompt, state,
                        canonical_sid,
                    )
                    _fifo_persisted = True
                    yield json.dumps(payload, ensure_ascii=True) + "\n"
                    continue
            yield ev
        # Safety: if the loop exited without a terminal event, flush now
        # and persist if we haven't already.
        tail = stripper.flush()
        if tail:
            yield _ndjson("delta", tail)
        if not _fifo_persisted:
            _persist_fifo_for_stream(
                _stage3_text_parts, evidence_meta,
                _evidence_tool_counter, prompt, state,
                canonical_sid,
            )

    return StreamingResponse(_stream(), media_type="application/x-ndjson")
