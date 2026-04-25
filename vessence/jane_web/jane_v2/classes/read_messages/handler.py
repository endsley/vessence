"""Read Messages Stage 2 handler — params-aware.

Stage 1 (qwen extraction) supplies optional `filter_sender`,
`unread_only`, and `limit` per the PARAMS_SCHEMA. The handler:

  - Refuses architecture / meta-debug phrasing (wrong_class)
  - Honours `limit` and `filter_sender`
  - Routes to Qwen for specific questions (sender filter or
    interrogative phrasing); falls back to a deterministic dump
    otherwise

The fetch / format / dump helpers are unchanged — only the dispatch
layer learned to read params.
"""

from __future__ import annotations

import datetime
import logging
import sys
from pathlib import Path

import httpx

_VAULT_WEB_DIR = Path(__file__).resolve().parents[4] / "vault_web"
if str(_VAULT_WEB_DIR) not in sys.path:
    sys.path.insert(0, str(_VAULT_WEB_DIR))

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 10
MAX_LIMIT = 50

from jane_web.jane_v2.models import LOCAL_LLM as MODEL, LOCAL_LLM_NUM_CTX, LOCAL_LLM_TIMEOUT, OLLAMA_URL  # noqa: E402

_ARCH_WORDS = ("architecture", "infrastructure", "pipeline", "handler", "classifier", "stage")

_META_PHRASES = (
    "your last message", "your last reply", "your previous message",
    "your previous reply", "the last message you", "the last reply you",
    "last message took", "last reply took", "last message when i asked",
    "took a while", "took so long", "so slow", "explain why",
    "why did you", "why was your",
)

_SPECIFIC_WORDS = ("who", "what did", "how many", "when did", "did anyone",
                   "did i get", "any", "is there", "from", "last message",
                   "most recent", "latest", "newest")


def _coerce_limit(raw) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    if n <= 0:
        return DEFAULT_LIMIT
    return min(n, MAX_LIMIT)


def _fetch_messages(limit: int = DEFAULT_LIMIT, contact_only: bool = False) -> list[dict]:
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


def _filter_by_sender(messages: list[dict], needle: str) -> list[dict]:
    needle_low = needle.lower().strip()
    if not needle_low:
        return messages
    out = []
    for m in messages:
        sender = (m.get("sender") or "").lower()
        if sender.startswith("me → "):
            sender = sender[len("me → "):]
        if needle_low in sender:
            out.append(m)
    return out


def _is_personal(msg: dict) -> bool:
    return bool(msg.get("is_contact")) and msg.get("msg_type") != "spam"


def _fmt_time(ts_ms: int) -> str:
    return datetime.datetime.fromtimestamp(ts_ms / 1000).strftime("%I:%M %p").lstrip("0")


def _format_for_llm(messages: list[dict]) -> str:
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
                recipient = sender[len("Me → "):].strip()
                parts.append(f"You sent to {recipient} at {ts}: {body}")
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
        "options": {"temperature": 0.1, "num_predict": 400, "num_ctx": LOCAL_LLM_NUM_CTX},
        "keep_alive": -1,
    }
    try:
        async with httpx.AsyncClient(timeout=LOCAL_LLM_TIMEOUT) as client:
            r = await client.post(OLLAMA_URL, json=body)
            r.raise_for_status()
            try:
                from jane_web.jane_v2.models import record_ollama_activity
                record_ollama_activity()
            except Exception:
                pass
            text = (r.json().get("response") or "").strip()
            return text or None
    except Exception as e:
        logger.warning("read_messages LLM answer failed: %s", e)
        return None


async def handle(prompt: str, context: str = "", params: dict | None = None) -> dict | None:
    """Read recent texts using classifier params when available."""
    p_lower = prompt.lower()
    if any(w in p_lower for w in _ARCH_WORDS):
        return {"wrong_class": True}
    if any(p in p_lower for p in _META_PHRASES):
        logger.info("read_messages handler: meta/self-reference phrase → wrong_class")
        return {"wrong_class": True}

    params = params or {}
    filter_sender = (params.get("filter_sender") or "").strip()
    limit = _coerce_limit(params.get("limit") or DEFAULT_LIMIT)
    # unread_only is currently informational — synced_messages has no
    # is_read column, so "unread" maps to "most recent" already covered
    # by the limit + DESC ordering.

    fetch_limit = max(limit, 20) if filter_sender else limit
    messages = _fetch_messages(limit=fetch_limit)
    if not messages:
        return {"text": "You don't have any synced messages yet."}

    if filter_sender:
        messages = _filter_by_sender(messages, filter_sender)
        if not messages:
            return {"text": f"No recent messages from {filter_sender}."}

    is_specific = bool(filter_sender) or any(w in p_lower for w in _SPECIFIC_WORDS)
    if is_specific:
        answer = await _llm_answer(prompt, messages[:limit], context)
        if answer:
            logger.info("read_messages handler: specific Q answered (%d msgs)", len(messages))
            return {"text": answer}
        logger.warning("read_messages handler: LLM answer failed, falling back to dump")

    text = _generic_dump(messages[:limit])
    logger.info("read_messages handler: generic dump (%d msgs)", len(messages))
    return {"text": text}
