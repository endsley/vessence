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


async def dispatch(
    class_name: str,
    prompt: str,
    *,
    context: str = "",
) -> dict | None:
    """Call the Stage 2 handler for `class_name` and return its result.

    Args:
        class_name: which class pack to route to (e.g. "weather").
        prompt:     the user's current prompt.
        context:    optional recent-conversation context string (from
                    the recent_turns FIFO). Handlers that know how to
                    use context accept it as a `context=` kwarg;
                    handlers that don't ignore it silently.

    Returns None when:
      - no such class is registered
      - the class has no handler (e.g. "others")
      - the handler raised
      - the handler returned None (declining the request)
    """
    registry = class_registry.get_registry()
    meta = registry.get(class_name)
    if not meta:
        logger.info("dispatcher: no class %r in registry", class_name)
        return None

    handler = meta.get("handler")
    if handler is None:
        logger.info("dispatcher: class %r has no handler (fallback class)", class_name)
        return None

    # Pass context only to handlers that declare it as a parameter.
    # This keeps old handlers backward-compatible with no signature change.
    try:
        sig = inspect.signature(handler)
        wants_context = "context" in sig.parameters
    except (TypeError, ValueError):
        wants_context = False

    try:
        if inspect.iscoroutinefunction(handler):
            if wants_context:
                result = await handler(prompt, context=context)
            else:
                result = await handler(prompt)
        else:
            if wants_context:
                result = await asyncio.to_thread(handler, prompt, context=context)
            else:
                result = await asyncio.to_thread(handler, prompt)
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
