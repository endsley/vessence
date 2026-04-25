"""Stage 2 handler for TELL_JOKE — local-LLM-generated single joke.

The user asked Jane for a joke. We ask the local LLM (qwen2.5:7b) for ONE
short clean joke and return it as the spoken reply. No Opus, no client
tools. The recent FIFO is included so the model can avoid repeating a
joke it just told (e.g. "another joke" pivots to a new one).
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


_PROMPT_TEMPLATE = """\
You are Jane, a voice assistant. The user just asked you to tell a joke.

{context_block}User: "{prompt}"

Tell ONE short clean joke. Setup + punchline. Two short sentences max.
If the recent conversation already has a joke from you, pick a NEW joke —
different topic, different style. No preamble like "Sure, here's one" —
just the joke itself.

Format your response as exactly TWO fields:

THOUGHT: <one short line: which joke style fits, anything to avoid>
REPLY: <the joke itself, plain spoken English for TTS, no markdown, no emoji>"""


async def _call_local_llm(prompt_text: str) -> str:
    import httpx
    from jane_web.jane_v2.models import (
        LOCAL_LLM,
        LOCAL_LLM_NUM_CTX,
        LOCAL_LLM_TIMEOUT,
        OLLAMA_KEEP_ALIVE,
        OLLAMA_URL,
    )
    body = {
        "model": LOCAL_LLM,
        "prompt": prompt_text,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.9,
            "num_predict": 100,
            "num_ctx": LOCAL_LLM_NUM_CTX,
        },
        "keep_alive": OLLAMA_KEEP_ALIVE,
    }
    async with httpx.AsyncClient(timeout=LOCAL_LLM_TIMEOUT) as client:
        r = await client.post(OLLAMA_URL, json=body)
        r.raise_for_status()
        try:
            from jane_web.jane_v2.models import record_ollama_activity
            record_ollama_activity()
        except Exception:
            pass
        return (r.json().get("response") or "").strip()


async def handle(prompt: str, context: str = "") -> dict | None:
    context_block = ""
    if context and context.strip():
        context_block = f"Recent conversation:\n{context.strip()}\n\n"

    full_prompt = _PROMPT_TEMPLATE.format(
        prompt=prompt.strip(),
        context_block=context_block,
    )

    t0 = time.perf_counter()
    try:
        raw = await _call_local_llm(full_prompt)
    except Exception as e:
        logger.warning("tell_joke: LLM call failed (%s) — escalating", e)
        return None
    latency_ms = int((time.perf_counter() - t0) * 1000)

    thought = ""
    reply = raw.strip()
    saw_reply_tag = False
    for line in raw.splitlines():
        s = line.strip()
        if s.upper().startswith("THOUGHT:"):
            thought = s.split(":", 1)[1].strip()
        elif s.upper().startswith("REPLY:"):
            reply = s.split(":", 1)[1].strip()
            saw_reply_tag = True
    # If the model emitted only a THOUGHT line and no REPLY tag, the
    # fallback `reply = raw.strip()` would speak "THOUGHT: ..." literally.
    # Strip the THOUGHT prefix in that case so the joke text alone is read.
    if not saw_reply_tag and thought:
        cleaned = []
        for line in raw.splitlines():
            if line.strip().upper().startswith("THOUGHT:"):
                continue
            cleaned.append(line)
        reply = "\n".join(cleaned).strip() or thought
    reply = reply.strip().strip('"').strip("'").strip()
    if not reply:
        return None

    logger.info(
        "tell_joke: LLM %dms — thought=%r reply=%r",
        latency_ms, thought[:80], reply[:120],
    )
    return {"text": reply, "thought": thought}
