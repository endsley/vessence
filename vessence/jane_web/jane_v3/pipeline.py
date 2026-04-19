"""jane_v3 pipeline — simplified routing via FIFO-aware Haiku classification.

Flow per request:
  1. Canonical session id + FIFO context (reuse v2 helpers).
  2. Classify via `intent_classifier/v3/classifier.classify()`.
     - Returns ("<class>", "Very High"|"High") when Haiku is confident AND
       the class has a registered Stage 2 handler.
     - Returns ("others", "Low") on any ambiguity / pivot / error — the
       caller treats that as "escalate to Stage 3".
  3. If Stage-2-bound: invoke the handler directly (no gate check, no
     continuation check, no pending_action_resolver STAGE2_FOLLOWUP branch
     — Haiku has already taken all three decisions upstream).
  4. Otherwise: escalate to Stage 3 via v2's `stage3_escalate.escalate_stream`
     (or v2's non-streaming brain chat for the non-stream entry point).

Everything under `jane_web/jane_v2/classes/` is reused unchanged. Everything
under `jane_web/jane_v2/` — streaming helpers, Stage 3 escalation, FIFO
persistence, ack generation — is imported directly; no code is copied.

Dropping from v2 (on purpose):
  - `_gate_check` — Haiku's confidence gate supersedes it.
  - `_continuation_check` — Haiku+FIFO natively handles follow-up vs pivot.
  - `pending_action_resolver` STAGE2_FOLLOWUP routing — same.
  - SMS confirmation / draft short-circuits — Haiku sees the FIFO marker
    ("about to send: <body>") and classifies "yes"/"send it" as
    `send_message`; the handler reads its own pending state from FIFO.
    (If this misroutes in practice, re-add the resolver as a pre-check.)

v2 is never imported into anything that runs under the v2 flag.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

logger = logging.getLogger(__name__)


# ── Helpers pulled from v2 (single source of truth) ──────────────────────────

from jane_web.jane_v2 import classes as class_registry  # handler metadata
from jane_web.jane_v2 import stage3_escalate  # Stage 3 streaming + ack layer
from jane_web.jane_v2.pipeline import (
    _ack_for,
    _canonical_session_id,
    _persist_turn_to_fifo,
    _stage2_response_parts,
)
from jane_web.session_context import set_current_session_id
from intent_classifier.v3 import classifier as v3_classifier


# ── Shared routing decision ──────────────────────────────────────────────────


async def _classify_and_maybe_handle(prompt: str, session_id: str) -> dict:
    """Run v3 classifier + handler dispatch. Shared by chat + chat_stream.

    Returns a state dict:
      {
        "cls":             str,                       # class name (lowercased)
        "conf":            str,                       # "Very High"|"High"|"Low"
        "classification":  str,                       # "<cls>:<conf>"
        "stage1_ms":       int,
        "stage2_ms":       int,                       # 0 when escalating
        "result":          dict | None,               # handler output if Stage 2 ran
        "stage2_ack":      str | None,
        "fallback_ack":    str | None,
        "force_stage3":    bool,
      }
    """
    # ── Stage 1 (v3): Haiku classification ───────────────────────────────
    t1 = time.perf_counter()
    try:
        cls, conf = await v3_classifier.classify(prompt, session_id=session_id)
    except Exception as e:
        logger.exception("jane_v3: classifier crashed: %s", e)
        cls, conf = ("others", "Low")
    stage1_ms = int((time.perf_counter() - t1) * 1000)
    classification = f"{cls}:{conf}"
    logger.info("jane_v3 pipeline: stage1 %s (%dms)", classification, stage1_ms)

    state: dict[str, Any] = {
        "cls": cls,
        "conf": conf,
        "classification": classification,
        "stage1_ms": stage1_ms,
        "stage2_ms": 0,
        "result": None,
        "stage2_ack": None,
        "fallback_ack": None,
        "force_stage3": False,
    }

    # The v3 classifier already enforces the confidence gate — it only
    # returns a real class when confidence is "Very High" or "High" AND
    # the class has a registered handler. Anything else comes back as
    # ("others", "Low") which we escalate here.
    if cls == "others" or conf not in ("Very High", "High"):
        state["force_stage3"] = True
        state["stage2_ack"] = None
        state["fallback_ack"] = _ack_for(cls, escalate=True)
        return state

    # ── End-conversation short-circuit ──────────────────────────────────
    # `end conversation` has no handler.py by design — the class only
    # emits two things: a tiny "Ok." acknowledgment and the
    # `conversation_end: True` signal that tells the client to close the
    # voice loop (stop STT, fall back to wake-word passive mode). v2's
    # pipeline handles this inline at pipeline.py:1080-1087; we mirror
    # that here so the voice loop actually terminates when v3 is active.
    if cls == "end conversation":
        state["result"] = {"text": "Ok.", "conversation_end": True}
        state["stage2_ack"] = None
        state["fallback_ack"] = None
        state["stage2_ms"] = 0
        logger.info("jane_v3 pipeline: end_conversation short-circuit")
        return state

    # ── Stage 2: dispatch to the handler (no gate, no continuation check) ──
    registry = class_registry.get_registry()
    meta = registry.get(cls)
    if not meta:
        logger.info("jane_v3: class %r not in registry → Stage 3", cls)
        state["force_stage3"] = True
        state["fallback_ack"] = _ack_for(cls, escalate=True)
        return state
    handler = meta.get("handler")
    if handler is None:
        # Registered class but no handler (e.g. "others", rare stub classes)
        logger.info("jane_v3: class %r has no handler → Stage 3", cls)
        state["force_stage3"] = True
        state["fallback_ack"] = _ack_for(cls, escalate=True)
        return state

    # Pull optional pending state + FIFO context from v2's helpers, for
    # handlers that implement multi-turn internal state (timer awaiting
    # label, todo_list awaiting category, etc.). The handler still owns
    # its state machine; we just pass the raw read-through.
    pending_data: dict | None = None
    fifo_ctx = ""
    try:
        from jane_web.jane_v2 import recent_context
        from vault_web.recent_turns import get_active_state
        fifo_ctx = recent_context.render_stage2_context(session_id, max_turns=4) or ""
        active_state = get_active_state(session_id) or {}
        pa = active_state.get("pending_action") or {}
        if pa.get("handler_class") == cls and pa.get("status") == "awaiting_user":
            pending_data = pa.get("data") or pa
    except Exception as e:
        logger.warning("jane_v3: recent_context load failed: %s", e)

    # Introspect handler signature (same pattern v2 uses) so we pass only
    # the kwargs the handler accepts. Backward-compatible with older handlers.
    import inspect
    kwargs: dict = {}
    try:
        sig = inspect.signature(handler)
        if "context" in sig.parameters:
            kwargs["context"] = fifo_ctx
        if "pending" in sig.parameters:
            kwargs["pending"] = pending_data
    except (TypeError, ValueError):
        pass

    t2 = time.perf_counter()
    result = None
    try:
        import asyncio
        if inspect.iscoroutinefunction(handler):
            result = await handler(prompt, **kwargs)
        else:
            result = await asyncio.to_thread(lambda: handler(prompt, **kwargs))
    except Exception as e:
        logger.exception("jane_v3: handler %r crashed: %s", cls, e)
        result = None
    state["stage2_ms"] = int((time.perf_counter() - t2) * 1000)

    # Handler declined OR returned an invalid shape → escalate.
    if not isinstance(result, dict) or "text" not in result:
        logger.info("jane_v3: handler %r returned invalid shape → Stage 3", cls)
        state["force_stage3"] = True
        state["fallback_ack"] = _ack_for(cls, escalate=True)
        return state

    # Handler explicitly wants Stage 3 (abandon_pending / force_stage3).
    if result.get("abandon_pending") or result.get("force_stage3"):
        logger.info("jane_v3: handler %r requested escalation → Stage 3", cls)
        state["force_stage3"] = True
        state["fallback_ack"] = _ack_for(cls, escalate=True)
        # Preserve any pending-action resolution the handler wanted to emit.
        structured = result.get("structured") or {}
        if structured.get("pending_action"):
            state["resolve_pending_action"] = structured.get("pending_action")
        return state

    # Handler says WRONG_CLASS — Haiku's guess was wrong even after its own
    # second-check inside the handler. Escalate.
    if result.get("wrong_class"):
        logger.info("jane_v3: handler %r flagged WRONG_CLASS → Stage 3", cls)
        state["force_stage3"] = True
        state["fallback_ack"] = _ack_for(cls, escalate=True)
        return state

    state["result"] = result
    state["stage2_ack"] = _ack_for(cls, escalate=False)
    state["fallback_ack"] = _ack_for(cls, escalate=True)
    logger.info(
        "jane_v3 pipeline: stage2 %s handler (%dms)",
        cls, state["stage2_ms"],
    )
    return state


# ── Non-streaming entry point ────────────────────────────────────────────────


async def handle_chat(body, request: Request):
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

    canonical_sid = _canonical_session_id(body, request) or body.session_id
    set_current_session_id(canonical_sid)
    state = await _classify_and_maybe_handle(prompt, canonical_sid)

    # ── Stage 2 success: return directly ────────────────────────────────
    if state["result"] is not None and not state["force_stage3"]:
        text, extras = _stage2_response_parts(state["result"])
        from jane_web.jane_proxy import ToolMarkerExtractor
        _extractor = ToolMarkerExtractor()
        visible, tool_calls = _extractor.feed(text)
        tail, tail_calls = _extractor.flush()
        visible_text = (visible or "") + (tail or "")
        all_tool_calls = tool_calls + tail_calls
        resp: dict[str, Any] = {
            "response": visible_text or text,
            "ack": None,
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
            handler_structured=state["result"].get("structured")
                if isinstance(state["result"], dict) else None,
            extras=extras,
        )
        return JSONResponse(resp)

    # ── Stage 3 escalation: delegate to v1's brain via v2's helper ──────
    # Reuse v2's `handle_chat` escalation path: since this function owns
    # the Stage-2-bypass, we construct a minimal state dict v2's Stage 3
    # path can read, then call into v1's _handle_jane_chat (the same
    # function v2 calls via its `_load_v1_chat` helper).
    from jane_web.jane_v2.pipeline import _load_v1_chat, _generate_delegate_ack
    dynamic_ack = await _generate_delegate_ack(
        body.message or "", canonical_sid, cls=state["cls"]
    )
    v1_chat = _load_v1_chat()
    if v1_chat is None:
        return JSONResponse({
            "response": "Jane v3 pipeline is unavailable.",
            "ack": dynamic_ack,
            "classification": state["classification"],
            "stage": "stage3",
            "stage1_ms": state["stage1_ms"],
            "stage2_ms": 0,
            "stage3_ms": 0,
            "files": [],
        })

    t3 = time.perf_counter()
    v1_response = await v1_chat(body, request)
    stage3_ms = int((time.perf_counter() - t3) * 1000)

    # Annotate v1's response with v3 classification metadata.
    try:
        raw = v1_response.body.decode("utf-8") if hasattr(v1_response, "body") else "{}"
        v1_body = json.loads(raw) if raw else {}
    except Exception:
        v1_body = {}
    v1_body["classification"] = state["classification"]
    v1_body["stage"] = "stage3"
    v1_body["stage1_ms"] = state["stage1_ms"]
    v1_body["stage2_ms"] = 0
    v1_body["stage3_ms"] = stage3_ms
    v1_body["ack"] = dynamic_ack
    cleaned_text = v1_body.get("response") or ""
    _persist_turn_to_fifo(
        canonical_sid, prompt, cleaned_text,
        stage="stage3",
        intent=state["cls"],
        confidence=state["conf"],
    )
    return JSONResponse(v1_body)


# ── Streaming entry point ────────────────────────────────────────────────────


def _ndjson(event_type: str, data=None, **extra) -> str:
    payload = {"type": event_type}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=True) + "\n"


async def handle_chat_stream(body, request: Request):
    """Streaming handler — emits NDJSON events compatible with v2's client protocol."""
    prompt = (body.message or "").strip()

    async def _stream():
        if not prompt:
            yield _ndjson("error", "Empty prompt")
            yield _ndjson("done", "")
            return

        canonical_sid = _canonical_session_id(body, request) or body.session_id
        set_current_session_id(canonical_sid)
        state = await _classify_and_maybe_handle(prompt, canonical_sid)

        # ── Stage 2 success ──────────────────────────────────────────────
        if state["result"] is not None and not state["force_stage3"]:
            text, extras = _stage2_response_parts(state["result"])
            # Emit the structured extras (client_tool_calls + any pending_action)
            # before the text so the client can set up state before rendering.
            structured = state["result"].get("structured") if isinstance(state["result"], dict) else None
            if structured and structured.get("pending_action"):
                yield _ndjson("pending_action", json.dumps(structured["pending_action"], ensure_ascii=True))
            # Extract embedded CLIENT_TOOL markers
            from jane_web.jane_proxy import ToolMarkerExtractor
            _extractor = ToolMarkerExtractor()
            visible, tool_calls = _extractor.feed(text)
            tail, tail_calls = _extractor.flush()
            visible_text = (visible or "") + (tail or "")
            for tc in (tool_calls or []) + (tail_calls or []):
                yield _ndjson("client_tool_call", json.dumps(tc, ensure_ascii=True))
            yield _ndjson("delta", visible_text or text)
            # Emit the conversation_end signal BEFORE `done` so the client
            # sees it in the same turn and falls back to wake-word passive
            # mode instead of reopening active STT after TTS finishes.
            # end_conversation is the only flow that sets this flag; other
            # extras (playlist_id, etc.) ride along in the non-streaming
            # path's JSON body and are not needed in the event stream.
            if extras.get("conversation_end"):
                yield _ndjson("conversation_end", "true")
            yield _ndjson("done", visible_text or text,
                          classification=state["classification"],
                          stage="stage2",
                          stage1_ms=state["stage1_ms"],
                          stage2_ms=state["stage2_ms"],
                          stage3_ms=0)
            _persist_turn_to_fifo(
                canonical_sid, prompt, visible_text or text,
                stage="stage2",
                intent=state["cls"],
                confidence=state["conf"],
                handler_structured=structured,
                extras=extras,
            )
            return

        # ── Stage 3 escalation — reuse v2's streaming path ──────────────
        from jane_web.jane_v2.pipeline import _generate_delegate_ack
        dynamic_ack = await _generate_delegate_ack(
            body.message or "", canonical_sid, cls=state["cls"]
        )
        reason = f"{state['cls']}:{state['conf']}"
        t3 = time.perf_counter()
        try:
            async for ev in stage3_escalate.escalate_stream(
                body, request, dynamic_ack, reason=reason,
                session_id_override=canonical_sid,
            ):
                yield ev
        except Exception as e:
            logger.exception("jane_v3: stage3 stream crashed: %s", e)
            yield _ndjson("error", f"Stage 3 error: {e}")
            yield _ndjson("done", "")
        finally:
            stage3_ms = int((time.perf_counter() - t3) * 1000)
            logger.info("jane_v3 pipeline: stage3 end-to-end (%dms)", stage3_ms)

    return StreamingResponse(_stream(), media_type="application/x-ndjson")
