"""Pipeline orchestrator for v2 Jane.

Entry points used by main.py:
  - handle_chat(body, request)         → non-streaming /api/jane/chat
  - handle_chat_stream(body, request)  → streaming /api/jane/chat/stream

3-stage flow:
  Stage 1: classify the prompt with gemma4:e2b (~700 ms)
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
from typing import Any, AsyncIterator

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from . import recent_context, stage1_classifier, stage2_dispatcher, stage3_escalate

logger = logging.getLogger(__name__)


_DEFAULT_ESCALATE_ACK = "Let me think about that…"


# ─── shared helpers ──────────────────────────────────────────────────────────


def _persist_stage2_to_fifo(session_id: str | None, user_prompt: str, jane_response: str) -> None:
    """After a successful Stage 2 turn, write a compact summary to the
    recent_turns FIFO so future Stage 3 calls (and Stage 2 handlers that
    use FIFO context) can see what happened in this turn.

    Without this, Stage 2 turns are invisible to subsequent context lookups
    and Opus loses the conversation thread when it eventually runs.
    """
    if not session_id or not jane_response:
        return
    try:
        from vault_web.recent_turns import add as _recent_add, _format_turn_compact
        summary = _format_turn_compact(user_prompt or "", jane_response)
        _recent_add(session_id, summary)
    except Exception as e:
        logger.warning("pipeline: failed to persist stage2 turn to FIFO: %s", e)


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

# Topic phrase per class — used to fill a "what I'll do" slot in the
# ack templates. Just a short verb phrase, not a full sentence.
_ACK_TOPIC = {
    "send message":  "draft that text",
    "read messages": "look through your messages",
    "sync messages": "sync your messages",
    "read email":    "check your email",
    "shopping list": "update your list",
    "weather":       "check the weather",
    "music play":    "find that music",
    "others":        "look into that",
}

# Templates split by expected duration. The pipeline picks a bucket based on
# the prompt's complexity, then a random template within the bucket.
# Each template has a {topic} slot filled from _ACK_TOPIC.
_ACK_TEMPLATES_FAST = [  # seconds — simple lookups
    "Sure thing, give me a sec to {topic}.",
    "Yeah, let me {topic} real quick.",
    "Hold on a moment while I {topic}.",
    "Okay, give me just a sec to {topic}.",
    "Alright, I'll {topic} — back in a moment.",
    "Sure, hang tight while I {topic}.",
]
_ACK_TEMPLATES_MEDIUM = [  # ~1-3 minutes — research, multi-step
    "Sure, give me a minute or two to {topic} properly.",
    "Yeah, this might take a couple minutes — let me {topic}.",
    "Okay, hold on a bit while I {topic} carefully.",
    "Alright, let me {topic} — I'll need a minute or two.",
    "Sure, give me a few minutes to {topic} thoroughly.",
    "Yeah, let me take a couple minutes to {topic}.",
]
_ACK_TEMPLATES_LONG = [  # 5+ minutes — research, code, complex
    "Sure, this is going to take a while — let me {topic} and I'll come back when I'm done.",
    "Yeah, give me a good chunk of time to {topic} properly.",
    "Okay, this might take several minutes — let me {topic}.",
    "Alright, hang on for a bit — I need real time to {topic}.",
    "Sure, this won't be quick — let me {topic} and circle back.",
]


# Heuristics for estimating Opus duration without running it.
def _estimate_duration(prompt: str) -> str:
    """Return 'fast' | 'medium' | 'long' based on prompt content."""
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
        return "long"
    if any(s in p for s in medium_signals) or word_count > 25:
        return "medium"
    return "fast"




async def _generate_delegate_ack(prompt: str, session_id: str | None,
                                  cls: str = "others") -> str:
    """Produce an ack for a Stage 3 escalation.

    Estimates how long Opus will take (fast/medium/long), picks a template
    from the matching pool, and fills in the topic from the Stage 1 class.
    No LLM call, zero tokens, no name-dropping, conveys time expectation.
    """
    duration = _estimate_duration(prompt)
    if duration == "long":
        templates = _ACK_TEMPLATES_LONG
    elif duration == "medium":
        templates = _ACK_TEMPLATES_MEDIUM
    else:
        templates = _ACK_TEMPLATES_FAST
    topic = _ACK_TOPIC.get(cls, _ACK_TOPIC["others"])
    return _random.choice(templates).format(topic=topic)


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
    # Stage 1
    _t1 = time.perf_counter()
    try:
        cls, conf = await stage1_classifier.classify(prompt)
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
            fifo_ctx = recent_context.get_recent_context(session_id, max_turns=2)
        except Exception:
            pass
        if await stage2_dispatcher._gate_check("end conversation", prompt, fifo_ctx):
            result = {"text": "Ok.", "conversation_end": True}
        else:
            logger.info("pipeline: END_CONVERSATION gate rejected — escalating instead")

    if result is None and conf in ("High", "Medium") and cls != "others":
        fifo_ctx = ""
        try:
            fifo_ctx = recent_context.get_recent_context(session_id, max_turns=2)
        except Exception:
            pass
        _t2 = time.perf_counter()
        try:
            result = await stage2_dispatcher.dispatch(cls, prompt, context=fifo_ctx)
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

    state = await _classify_and_try_stage2(prompt, body.session_id)

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
        _persist_stage2_to_fifo(body.session_id, prompt, visible_text or text)
        return JSONResponse(resp)

    # ── Stage 3: delegate to v1's non-streaming brain ───────────────────
    # Generate a contextual ack first (uses v1's classify_prompt — topic
    # echo + time hint). Falls back to the static class ack on failure.
    dynamic_ack = await _generate_delegate_ack(
        body.message or "", body.session_id, cls=state["cls"]
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

    effective_body = stage3_escalate._maybe_voice_wrap(body)
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
    new_body_bytes = json.dumps(v1_body, ensure_ascii=True).encode("utf-8")
    v1_response.body = new_body_bytes
    v1_response.headers["content-length"] = str(len(new_body_bytes))
    return v1_response


# ─── streaming entry point (/api/jane/chat/stream) ───────────────────────────


async def handle_chat_stream(body, request: Request):
    """Streaming entry point. Yields NDJSON events compatible with
    existing Alpine/Android chat UI handlers."""
    prompt = (body.message or "").strip()

    async def _stream() -> AsyncIterator[str]:
        if not prompt:
            yield _ndjson("done", "")
            return

        yield _ndjson("status", "Classifying…")
        state = await _classify_and_try_stage2(prompt, body.session_id)

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
            _persist_stage2_to_fifo(body.session_id, prompt, visible_text or text)
            return

        # ── Stage 3: delegate to v1's streaming brain ──────────────────
        # Generate a contextual ack via v1's classify_prompt (topic
        # echo + time hint). Static class ack is the safe fallback.
        dynamic_ack = await _generate_delegate_ack(
            body.message or "", body.session_id, cls=state["cls"]
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

        reason = f"{state['cls']}:{state['conf']}"
        async for ev in stage3_escalate.escalate_stream(
            effective_body, request, dynamic_ack, reason=reason
        ):
            yield ev

    return StreamingResponse(_stream(), media_type="application/x-ndjson")
