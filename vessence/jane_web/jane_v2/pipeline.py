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

from . import (
    pending_action_resolver,
    recent_context,
    stage1_classifier,
    stage2_dispatcher,
    stage3_escalate,
)

logger = logging.getLogger(__name__)


_DEFAULT_ESCALATE_ACK = "Let me think about that…"


# ─── shared helpers ──────────────────────────────────────────────────────────


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
    """Produce an ack for a Stage 3 escalation using gemma4:e2b.

    Two-part structured response:
      Part 1: acknowledge understanding + intent ("Got it", "I'll work on it",
              "Let me think about that")
      Part 2: time estimate ("give me a sec", "this might take a few minutes",
              "could take a while")

    Uses gemma4:e2b at higher temp for variety. Falls back to a static
    sentence on failure. ~700ms cost, runs in parallel with Stage 3 brain
    so net latency is unchanged.
    """
    import os
    import httpx
    duration = _estimate_duration(prompt)
    model = os.environ.get("JANE_ACK_MODEL", "qwen2.5:7b")
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
                    "options": {"temperature": 1.0, "top_p": 0.95, "num_predict": 60},
                    "keep_alive": "1h",
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
    # "yes" can't be mis-embedded as GREETING or OTHERS.
    try:
        resolved = pending_action_resolver.resolve(session_id, prompt)
    except Exception as e:
        logger.warning("pipeline: resolver failed: %s", e)
        resolved = None
    if resolved:
        pending = resolved.get("pending") or {}
        if resolved["action"] == "confirm":
            result = _resolve_pending_sms_confirmation(pending)
        else:
            result = _cancel_pending_sms_confirmation(pending)
        cls = "send message"
        conf = "High"
        logger.info("jane_v2 pipeline: pending-action resolver → %s", resolved["action"])
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
        _persist_turn_to_fifo(
            body.session_id, prompt, visible_text or text,
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
    # FIFO record for Stage 3 turn so the next pending-action resolver /
    # Stage 3 state block sees continuity. v1 has its own long-term memory,
    # so we only record a minimal handoff summary here.
    _persist_turn_to_fifo(
        body.session_id, prompt, v1_body.get("response", "") or "",
        stage="stage3",
        intent=state["cls"],
        confidence=state["conf"],
    )
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
            _persist_turn_to_fifo(
                body.session_id, prompt, visible_text or text,
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
        # Accumulate streamed deltas so we can persist a FIFO record at the end.
        _stage3_text_parts: list[str] = []
        async for ev in stage3_escalate.escalate_stream(
            effective_body, request, dynamic_ack, reason=reason
        ):
            # Best-effort: sniff `delta` events for accumulated Stage 3 text.
            try:
                payload = json.loads(ev)
                if payload.get("type") == "delta" and isinstance(payload.get("data"), str):
                    _stage3_text_parts.append(payload["data"])
            except Exception:
                pass
            yield ev
        _persist_turn_to_fifo(
            body.session_id, prompt, "".join(_stage3_text_parts),
            stage="stage3",
            intent=state["cls"],
            confidence=state["conf"],
        )

    return StreamingResponse(_stream(), media_type="application/x-ndjson")
