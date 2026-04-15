"""Read Messages Stage 2 handler.

Two paths:
  - Specific question ("who sent the last message", "what did Romeo say",
    "how many texts today") → fetch + Qwen answers the specific question
  - Generic dump ("read my messages", "check my texts") → deterministic
    summary (verbatim contact messages, collapsed tail for promo/spam)

Both paths use the same SQL fetch from synced_messages — only the
answer step differs.
"""

from __future__ import annotations

import datetime
import logging
import os
import sys
from pathlib import Path

import httpx

_VAULT_WEB_DIR = Path(__file__).resolve().parents[4] / "vault_web"
if str(_VAULT_WEB_DIR) not in sys.path:
    sys.path.insert(0, str(_VAULT_WEB_DIR))

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 10

from jane_web.jane_v2.models import LOCAL_LLM as MODEL, OLLAMA_URL  # noqa: E402

# Architecture/code-question keywords → escalate (not a real read request)
_ARCH_WORDS = ("architecture", "infrastructure", "pipeline", "handler", "classifier", "stage")

# Words that signal a SPECIFIC question (not just "dump everything")
_SPECIFIC_WORDS = ("who", "what did", "how many", "when did", "did anyone",
                   "did i get", "any", "is there", "from", "last message",
                   "most recent", "latest", "newest")


def _fetch_messages(limit: int = DEFAULT_LIMIT, contact_only: bool = False) -> list[dict]:
    """Fetch recent messages from the synced_messages database."""
    try:
        from database import get_db
    except Exception as e:
        logger.warning("read_messages handler: database import failed: %s", e)
        return []

    try:
        with get_db() as conn:
            where = "WHERE is_contact = 1" if contact_only else ""
            rows = conn.execute(
                f"SELECT sender, body, timestamp_ms, is_contact, msg_type "
                f"FROM synced_messages {where} "
                f"ORDER BY timestamp_ms DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("read_messages handler: query failed: %s", e)
        return []


def _is_personal(msg: dict) -> bool:
    return bool(msg.get("is_contact")) and msg.get("msg_type") != "spam"


def _fmt_time(ts_ms: int) -> str:
    return datetime.datetime.fromtimestamp(ts_ms / 1000).strftime("%I:%M %p").lstrip("0")


def _format_for_llm(messages: list[dict]) -> str:
    """Format messages as a compact list for the LLM to reason over.
    Direction is made explicit (SENT vs RECEIVED) so the LLM doesn't
    confuse who's the sender. The DB marks outgoing messages with a
    "Me → " prefix on the sender field — we strip it and emit a
    direction tag instead.
    """
    lines = []
    for i, m in enumerate(messages):
        ts = _fmt_time(m["timestamp_ms"])
        date = datetime.datetime.fromtimestamp(m["timestamp_ms"] / 1000).strftime("%m/%d")
        sender_raw = m["sender"] or "Unknown"
        body = (m["body"] or "").strip()[:200]
        kind = "contact" if _is_personal(m) else (m.get("msg_type") or "unknown")
        if sender_raw.startswith("Me → "):
            other = sender_raw[len("Me → "):].strip()
            lines.append(f"{i+1}. [{date} {ts}] (SENT by you to {other}) ({kind}): {body}")
        else:
            lines.append(f"{i+1}. [{date} {ts}] (RECEIVED from {sender_raw}) ({kind}): {body}")
    return "\n".join(lines)


def _generic_dump(messages: list[dict]) -> str:
    """Deterministic summary for generic 'read my messages' requests."""
    personal = [m for m in messages if _is_personal(m)]
    other = [m for m in messages if not _is_personal(m)]

    parts: list[str] = []
    if personal:
        if len(personal) == 1:
            parts.append("You have 1 message from a contact.")
        else:
            parts.append(f"You have {len(personal)} messages from contacts.")
        for m in personal:
            sender = m["sender"] or "Unknown"
            body = (m["body"] or "").strip()
            ts = _fmt_time(m["timestamp_ms"])
            if sender.startswith("Me → "):
                other = sender[len("Me → "):].strip()
                parts.append(f"You sent to {other} at {ts}: {body}")
            else:
                parts.append(f"From {sender} at {ts}: {body}")
    else:
        parts.append("No new messages from contacts.")

    if other:
        senders = []
        seen = set()
        for m in other:
            s = (m["sender"] or "Unknown").split(":")[0].strip()
            if s not in seen:
                seen.add(s)
                senders.append(s)
        sender_list = ", ".join(senders[:3])
        more = "" if len(senders) <= 3 else f" and {len(senders) - 3} others"
        noun = "texts" if len(other) > 1 else "text"
        parts.append(f"Plus {len(other)} other {noun} from {sender_list}{more} — mostly promo or automated.")
    return "\n\n".join(parts)


async def _llm_answer(prompt: str, messages: list[dict], context: str = "") -> str | None:
    """Use Qwen to answer a specific question about the messages."""
    formatted = _format_for_llm(messages)
    context_block = ""
    if context and context.strip():
        context_block = f"Recent conversation:\n{context.strip()}\n\n"

    full_prompt = f"""You are Jane, a personal AI assistant. The user asked a SPECIFIC \
question about their text messages. Answer it directly and concisely.

RULES:
- DIRECTION MATTERS. Each message has a tag:
    "(SENT by you to <person>)" — the USER wrote this and sent it OUT
    "(RECEIVED from <person>)" — the OTHER person wrote it and the user got it
  Never confuse who sent vs. who received. If the user asks "who texted me",
  list only RECEIVED messages, not the user's own SENT messages.
- When citing a CONTACT message (kind=contact), QUOTE THE BODY VERBATIM.
- When referring to SPAM / PROMO / AUTOMATED messages (kind != contact), summarize them briefly (e.g. "a Chase statement alert"). Never quote spam verbatim.
- Do NOT dump all messages — only answer what was asked.
- Keep your framing sentence short (1 sentence); the contact quote itself can be as long as the original.

Messages (most recent first):
{formatted}

{context_block}User question: {prompt.strip()}

Your answer:"""

    body = {
        "model": MODEL,
        "prompt": full_prompt,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.1, "num_predict": 400},
        "keep_alive": -1,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(OLLAMA_URL, json=body)
            r.raise_for_status()
            text = (r.json().get("response") or "").strip()
            return text or None
    except Exception as e:
        logger.warning("read_messages LLM answer failed: %s", e)
        return None


async def handle(prompt: str, context: str = "") -> dict | None:
    """Read recent texts. Specific questions go to Qwen; generic dumps stay deterministic."""
    p_lower = prompt.lower()
    if any(w in p_lower for w in _ARCH_WORDS):
        return {"wrong_class": True}

    messages = _fetch_messages(limit=DEFAULT_LIMIT)
    if not messages:
        return {"text": "You don't have any synced messages yet."}

    # Specific question → use Qwen to answer that exact question
    is_specific = any(w in p_lower for w in _SPECIFIC_WORDS)
    if is_specific:
        answer = await _llm_answer(prompt, messages, context)
        if answer:
            logger.info("read_messages handler: specific Q answered (%d msgs)", len(messages))
            return {"text": answer}
        # LLM failed → fall back to generic dump rather than escalating
        logger.warning("read_messages handler: LLM answer failed, falling back to dump")

    # Generic dump
    text = _generic_dump(messages)
    logger.info("read_messages handler: generic dump (%d msgs)", len(messages))
    return {"text": text}
