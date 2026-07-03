"""Stage 2 dispatcher.

Given a class name and user prompt, look up the class's handler in the
registry and invoke it. Returns the handler result (dict with "text"
and optional extras) or None if the handler doesn't exist, declined,
or crashed.

When a handler returns None because it detected WRONG_CLASS (the LLM
disagreed with Stage 1's classification), the dispatcher kicks off a
background self-correction task that adds the misclassified prompt as
a DELEGATE_OPUS exemplar in ChromaDB so Stage 1 gets it right next time.

Sync handlers are offloaded to a thread so they don't block the event
loop; async handlers are awaited directly.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
from typing import Any

from . import classes as class_registry
from jane_web.jane_v2.stage2_dispatcher_prompts import (
    CLASS_DESCRIPTIONS as _CLASS_DESCRIPTIONS,
    continuation_check_prompt as _continuation_check_prompt,
    gate_check_prompt as _gate_check_prompt,
)
from jane_web.jane_v2.stage2_handler_invocation import (
    build_handler_kwargs as _build_handler_kwargs,
)
from jane_web.jane_v2.ollama_client import post_ollama_response as _post_ollama_response

logger = logging.getLogger(__name__)


def _self_correct_classification(prompt: str, wrong_class: str):
    """Background task: add a misclassified prompt to DELEGATE_OPUS in ChromaDB.

    This teaches Stage 1 to not repeat the same mistake. Runs in a separate
    thread so it doesn't block the response.
    """
    # DISABLED per user request (2026-04-21). Writes to Chroma are
    # ephemeral (wiped on next source-edit rebuild) and were biasing the
    # DELEGATE_OPUS corpus toward bare affirmatives. Re-enable by removing
    # this early return.
    logger.info(
        "self-correct DISABLED: would have added %r (wrong_class=%s) to DELEGATE_OPUS",
        prompt[:60], wrong_class,
    )
    return
    try:
        from intent_classifier.v2.classifier import CHROMA_PATH, _embed_fn, _load, _collection
        from jane.config import get_chroma_client
        import time

        # Ensure classifier is loaded (for the embedding function)
        _load()

        client = get_chroma_client(str(CHROMA_PATH))
        col = client.get_collection("intent_v2")

        # Generate a unique ID
        ts = int(time.time())
        doc_id = f"DELEGATE_OPUS_auto_{ts}"

        # Embed and add
        vec = _embed_fn([prompt])[0]
        col.add(
            ids=[doc_id],
            documents=[prompt],
            embeddings=[vec],
            metadatas=[{"class": "DELEGATE_OPUS"}],
        )
        logger.info(
            "self-correct: added %r to DELEGATE_OPUS (was: %s, id: %s)",
            prompt[:60], wrong_class, doc_id,
        )
    except Exception as e:
        logger.warning("self-correct failed: %s", e)


async def _continuation_check(
    class_name: str,
    prompt: str,
    context: str,
    pending_question: str | None = None,
) -> bool:
    """When a STAGE2_FOLLOWUP is active, check if the user's reply answers
    the pending question or changes the subject. Returns True if it's an
    on-topic answer (continue with the handler), False if they've pivoted
    (dispatcher should abandon the pending and let the pipeline re-route
    via Stage 1).

    When `pending_question` is supplied, the LLM is shown the literal text
    Jane asked — this is much stronger signal than a generic class
    description. Handlers supply the question via their pending_action's
    `question` field (see _pending() in each handler). If absent, we fall
    back to the class description (legacy path).

    Short replies (≤ 5 words) are assumed to be direct answers and skip
    the LLM call entirely. Anything longer gets gated.
    """
    word_count = len(prompt.split())
    if word_count <= 5:
        return True

    from jane_web.jane_v2.models import (
        LOCAL_LLM as model,
        LOCAL_LLM_NUM_CTX,
        LOCAL_LLM_TIMEOUT,
        OLLAMA_KEEP_ALIVE,
        OLLAMA_URL,
    )
    check_prompt = _continuation_check_prompt(
        class_name,
        prompt,
        context,
        pending_question=pending_question,
    )
    body = {
        "model": model,
        "prompt": check_prompt,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 5, "num_ctx": LOCAL_LLM_NUM_CTX},
        "keep_alive": OLLAMA_KEEP_ALIVE,
    }
    try:
        ans = (
            await _post_ollama_response(
                OLLAMA_URL,
                body,
                timeout=LOCAL_LLM_TIMEOUT,
                activity_recorder=lambda: None,
            )
        ).upper()
        is_same = not ans.startswith("CHANGED")
        logger.info(
            "dispatcher: continuation check for %r → %s (q=%r raw=%r)",
            class_name, "SAME" if is_same else "CHANGED",
            (pending_question or "")[:50], ans[:20],
        )
        return is_same
    except Exception as e:
        logger.warning("dispatcher: continuation check failed (%s) — assuming same topic", e)
        return True


async def _gate_check(class_name: str, prompt: str, context: str) -> bool:
    """Quick LLM gate: does this prompt actually match the predicted class?
    Returns True if the prompt fits the class, False if WRONG_CLASS.

    Universal safety net — runs BEFORE every handler so misclassifications
    get caught even by handlers that don't implement their own check.
    Uses qwen2.5:7b with a tiny prompt (~50 tokens) — adds ~300ms.
    """
    gate_prompt = _gate_check_prompt(class_name, prompt, context)
    if not gate_prompt:
        return True  # unknown class → no gate (fail open)

    p_lower = prompt.lower()
    META_SIGNALS = ("how does", "why does", "explain the", "debug",
                    " handler", " classifier", " pipeline",
                    "the time you told me", "you got", "was wrong",
                    "incorrect", "fix it", "broken", "stale", "should auto",
                    "in your code", "in the codebase", "the way you handled",
                    "shouldn't", "doesn't sync", "keep failing")

    from jane_web.jane_v2.models import (
        LOCAL_LLM as model,
        LOCAL_LLM_NUM_CTX,
        LOCAL_LLM_TIMEOUT,
        OLLAMA_KEEP_ALIVE,
        OLLAMA_URL,
    )
    body = {
        "model": model,
        "prompt": gate_prompt,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 5, "num_ctx": LOCAL_LLM_NUM_CTX},
        "keep_alive": OLLAMA_KEEP_ALIVE,
    }
    try:
        ans = (
            await _post_ollama_response(
                OLLAMA_URL,
                body,
                timeout=LOCAL_LLM_TIMEOUT,
            )
        ).upper()
        return not ans.startswith("NO")
    except Exception as e:
        logger.warning("dispatcher gate check failed (%s) — failing open", e)
        return True


_NEAR_IDENTICAL_DIST = 0.10


async def dispatch(
    class_name: str,
    prompt: str,
    *,
    context: str = "",
    pending: dict | None = None,
    stage1_conf: str = "",
    min_dist: float = 1.0,
    params: dict | None = None,
) -> dict | None:
    """Call the Stage 2 handler for `class_name` and return its result.

    Args:
        class_name: which class pack to route to (e.g. "weather").
        prompt:     the user's current prompt.
        context:    optional recent-conversation context string (from
                    the recent_turns FIFO). Handlers that know how to
                    use context accept it as a `context=` kwarg;
                    handlers that don't ignore it silently.
        pending:    optional dict of state collected over prior turns of
                    a multi-turn Stage 2 conversation (see
                    pending_action_resolver STAGE2_FOLLOWUP flow).
        stage1_conf: Stage 1 confidence ("High" or "Low"). When "High",
                    the gate check is skipped — Stage 1 already passed
                    its maturity gate with sufficient confidence.
                    Handlers that support follow-up conversations accept
                    it as a `pending=` kwarg and read its `awaiting`
                    field to know what the user's reply answers.

    Returns None when:
      - no such class is registered
      - the class has no handler (e.g. "others")
      - the handler raised
      - the handler returned None (declining the request)
      - the universal gate check says the prompt doesn't match the class
        (skipped during a follow-up resume — we already know the class)
    """
    registry = class_registry.get_registry()
    meta = registry.get(class_name)
    if not meta:
        logger.info("dispatcher: no class %r in registry", class_name)
        return None

    # Universal WRONG_CLASS gate — runs for EVERY class before the handler.
    # Handlers may also have their own deeper checks, but this catches the
    # obvious misclassifications uniformly.
    # Skip when Stage 1 already passed with "High" confidence — its own
    # maturity gate (conf + margin thresholds) already validated the class.
    # The LLM gate adds ~300ms-12s latency for no gain in that case.
    # Skip the gate LLM when Stage 1 had a near-identical chroma match —
    # the prompt is basically a verbatim exemplar, so the gate can only
    # add latency and introduce false negatives (e.g. rejecting because
    # recent FIFO context is about a different topic). The coarse voting
    # margin ("High") already gave some confidence; the tight min_dist
    # threshold is the real guard.
    skip_gate = pending is None and min_dist <= _NEAR_IDENTICAL_DIST
    if skip_gate:
        logger.info(
            "dispatcher: gate skipped for %r (class=%r, min_dist=%.3f ≤ %.2f)",
            prompt[:60], class_name, min_dist, _NEAR_IDENTICAL_DIST,
        )
    if pending is None and not skip_gate:
        if not await _gate_check(class_name, prompt, context):
            logger.info("dispatcher: gate check rejected %r for class %r → escalating",
                        prompt[:60], class_name)
            # Skip the ChromaDB self-correct write when Stage 1 was High
            # confidence. The gate LLM and the Stage 1 classifier disagree
            # often on edge phrasings ("what is all my to-do list", "what's
            # on my todo", "why what's on my to-do list") and poisoning a
            # legitimate High-conf class into DELEGATE_OPUS breaks future
            # classifications. The escalate-on-rejection behavior still
            # runs — we just stop corrupting training data.
            # See transcript review 2026-04-18 Issues 2, 8, 16, 17.
            if stage1_conf != "High":
                threading.Thread(
                    target=_self_correct_classification,
                    args=(prompt, class_name),
                    daemon=True,
                ).start()
            else:
                logger.info(
                    "dispatcher: skipping self-correct for %r "
                    "(stage1_conf=High — trust classifier)",
                    class_name,
                )
            return None
    else:
        # Follow-up resume: the class was decided in the prior turn. Short
        # answers ("clinic", "2") pass through, but longer replies get an
        # LLM check to catch topic changes like "what about Google Docs?"
        # mid-TODO-flow. When the pending includes a `question` field with
        # the literal text Jane asked, the LLM gets much sharper signal than
        # from the generic class description.
        pending_question = ""
        if isinstance(pending, dict):
            pending_question = str(pending.get("question") or "")
        if not await _continuation_check(
            class_name, prompt, context, pending_question=pending_question or None,
        ):
            logger.info(
                "dispatcher: topic change detected during %r followup → abandoning (q=%r)",
                class_name, pending_question[:60],
            )
            return {"abandon_pending": True}

    handler = meta.get("handler")
    if handler is None:
        logger.info("dispatcher: class %r has no handler (fallback class)", class_name)
        return None

    kwargs = _build_handler_kwargs(
        handler,
        context=context,
        pending=pending,
        params=params,
    )

    try:
        if inspect.iscoroutinefunction(handler):
            result = await handler(prompt, **kwargs)
        else:
            result = await asyncio.to_thread(handler, prompt, **kwargs)
    except Exception as e:
        logger.exception("dispatcher: handler for %r crashed: %s", class_name, e)
        return None

    if result is None:
        logger.info("dispatcher: handler for %r declined (returned None)", class_name)
        return None

    # Handler is intentionally abandoning an active STAGE2_FOLLOWUP so
    # the pipeline can reroute the user's pivot/follow-up question.
    if isinstance(result, dict) and result.get("abandon_pending"):
        return result

    # Handler explicitly signals WRONG_CLASS — teach Stage 1 to avoid this
    if result.get("wrong_class"):
        logger.info(
            "dispatcher: handler for %r says WRONG_CLASS — self-correcting",
            class_name,
        )
        threading.Thread(
            target=_self_correct_classification,
            args=(prompt, class_name),
            daemon=True,
        ).start()
        return None

    if not isinstance(result, dict) or "text" not in result:
        logger.warning(
            "dispatcher: handler for %r returned invalid shape: %r", class_name, type(result)
        )
        return None

    return result


def metadata_for(class_name: str) -> dict[str, Any] | None:
    """Return the class's metadata dict (for ack text, priority, etc.)."""
    return class_registry.get_registry().get(class_name)
