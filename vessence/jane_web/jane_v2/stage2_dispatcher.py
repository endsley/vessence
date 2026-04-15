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

logger = logging.getLogger(__name__)


def _self_correct_classification(prompt: str, wrong_class: str):
    """Background task: add a misclassified prompt to DELEGATE_OPUS in ChromaDB.

    This teaches Stage 1 to not repeat the same mistake. Runs in a separate
    thread so it doesn't block the response.
    """
    try:
        from intent_classifier.v2.classifier import CHROMA_PATH, _embed_fn, _load, _collection
        import chromadb
        import time

        # Ensure classifier is loaded (for the embedding function)
        _load()

        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
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


_CLASS_DESCRIPTIONS = {
    "send message":  "the user wants to text/SMS another person",
    "read messages": "the user wants to read or check their text messages",
    "sync messages": "the user wants to force-sync SMS from the phone",
    "read email":    "the user wants to read or check their email inbox",
    "shopping list": "the user wants to add/remove/view items on a shopping list",
    "weather":       "the user wants the current/forecast weather",
    "music play":    "the user wants to play/queue music",
    "greeting":      "the user is just greeting (hi/hello/how are you)",
    "get time":      "the user wants the current time",
    "end conversation": "the user is ending the conversation (bye/cancel/stop/never mind)",
}


async def _gate_check(class_name: str, prompt: str, context: str) -> bool:
    """Quick LLM gate: does this prompt actually match the predicted class?
    Returns True if the prompt fits the class, False if WRONG_CLASS.

    Universal safety net — runs BEFORE every handler so misclassifications
    get caught even by handlers that don't implement their own check.
    Uses qwen2.5:7b with a tiny prompt (~50 tokens) — adds ~300ms.
    """
    desc = _CLASS_DESCRIPTIONS.get(class_name)
    if not desc:
        return True  # unknown class → no gate (fail open)

    # Fast bypass: short prompts (≤5 words) with no meta/complaint signals
    # are almost always real requests. Skip the LLM call entirely.
    word_count = len(prompt.split())
    p_lower = prompt.lower()
    META_SIGNALS = ("how does", "why does", "explain the", "debug",
                    " handler", " classifier", " pipeline",
                    "the time you told me", "you got", "was wrong",
                    "incorrect", "fix it", "broken", "stale", "should auto",
                    "in your code", "in the codebase", "the way you handled",
                    "shouldn't", "doesn't sync", "keep failing")
    if word_count <= 5 and not any(s in p_lower for s in META_SIGNALS):
        return True  # short clear request, no LLM needed

    import httpx
    from jane_web.jane_v2.models import LOCAL_LLM as model
    ctx_block = f"Recent conversation:\n{context.strip()}\n\n" if context and context.strip() else ""
    gate_prompt = (
        f"The classifier predicted: {desc}\n\n"
        f"Examples — judge if it's a real request (YES) or complaint/meta (NO):\n"
        f"  \"what time is it\" → YES\n"
        f"  \"the time you told me was wrong\" → NO (complaint)\n"
        f"  \"how do we get the time using the phone\" → NO (implementation question)\n"
        f"  \"hello jane\" → YES\n"
        f"  \"how does the greeting handler work\" → NO (meta)\n"
        f"  \"bye\" → YES\n"
        f"  \"don't send it like that\" → NO (correction)\n"
        f"  \"read my messages\" → YES\n"
        f"  \"why are you reading my messages wrong\" → NO (complaint)\n"
        f"  \"sync my messages\" → YES\n"
        f"  \"the sync isn't working can you debug it\" → NO (meta)\n\n"
        f"{ctx_block}User prompt: {prompt.strip()}\n\n"
        f"Is this a real fresh request? Answer ONE word — YES or NO:"
    )
    body = {
        "model": model,
        "prompt": gate_prompt,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 5},
        "keep_alive": -1,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post("http://localhost:11434/api/generate", json=body)
            r.raise_for_status()
            ans = (r.json().get("response") or "").strip().upper()
            return not ans.startswith("NO")
    except Exception as e:
        logger.warning("dispatcher gate check failed (%s) — failing open", e)
        return True


async def dispatch(
    class_name: str,
    prompt: str,
    *,
    context: str = "",
    pending: dict | None = None,
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
    # obvious misclassifications uniformly. Skipped for follow-up resumes
    # since the class was already decided in the prior turn and the user's
    # short reply ("5 minutes", "pasta") would fail the gate on its own.
    if pending is None:
        if not await _gate_check(class_name, prompt, context):
            logger.info("dispatcher: gate check rejected %r for class %r → escalating",
                        prompt[:60], class_name)
            threading.Thread(
                target=_self_correct_classification,
                args=(prompt, class_name),
                daemon=True,
            ).start()
            return None

    handler = meta.get("handler")
    if handler is None:
        logger.info("dispatcher: class %r has no handler (fallback class)", class_name)
        return None

    # Introspect the handler to see which optional kwargs it accepts.
    # Backward compatible — handlers declaring neither `context` nor
    # `pending` are called with just the prompt like they were before.
    try:
        sig = inspect.signature(handler)
        wants_context = "context" in sig.parameters
        wants_pending = "pending" in sig.parameters
    except (TypeError, ValueError):
        wants_context = False
        wants_pending = False

    kwargs: dict = {}
    if wants_context:
        kwargs["context"] = context
    if wants_pending:
        kwargs["pending"] = pending

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
