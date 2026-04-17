"""recent_context.py — fetch the last N turns for a session, budgeted.

Thin wrapper around vault_web.recent_turns.get_recent that:
  - reads the FIFO for a given session
  - trims the combined summary block to a char budget (stand-in for
    a token budget — we use chars because the local LLM doesn't need an exact
    tokenizer for this use case and 1 token ≈ 4 chars is close enough)
  - formats the result as a prompt-ready block, newest-last

Stage 2 class handlers can import this to get conversation context
without a ChromaDB similarity search. ~1ms SQLite read.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Rough char → token conversion. Local LLM tokens are ~4 chars on average.
_CHARS_PER_TOKEN = 4

# Default budgets for recent-turn context injection.
# 10 turns × ~190 chars/summary ≈ 1900 chars ≈ 475 tokens — so 600 tokens
# leaves comfortable headroom for occasional longer summaries, without
# dominating the Stage 2 prompt (which is already ~900 tokens for weather).
DEFAULT_MAX_TURNS = 10
DEFAULT_MAX_TOKENS = 600


def get_recent_context(
    session_id: str | None,
    max_turns: int = DEFAULT_MAX_TURNS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """Return a newline-joined block of recent turn summaries, oldest-first.

    Args:
        session_id: the v1 session id this request belongs to.
        max_turns:  hard cap on how many turns to fetch from the FIFO.
        max_tokens: soft cap on the combined size (converted to chars
                    via a 4-chars-per-token heuristic). When exceeded,
                    we drop the OLDEST turns first so the newest context
                    is always preserved.

    Returns empty string if no session id, no history, or any failure.
    Never raises.
    """
    if not session_id:
        return ""
    try:
        from vault_web.recent_turns import get_recent
    except Exception as e:
        logger.warning("recent_context: failed to import FIFO: %s", e)
        return ""

    try:
        turns = get_recent(session_id, n=max_turns)
    except Exception as e:
        logger.warning("recent_context: fifo read failed: %s", e)
        return ""

    if not turns:
        return ""

    max_chars = max(0, int(max_tokens * _CHARS_PER_TOKEN))

    # Build from newest-backward so that when we trim for the budget we
    # drop the OLDEST entries first, preserving the most recent context.
    kept: list[str] = []
    running_chars = 0
    for line in reversed(turns):
        line = line.strip()
        if not line:
            continue
        cost = len(line) + 1  # +1 for the joining newline
        if running_chars + cost > max_chars and kept:
            break
        kept.append(line)
        running_chars += cost

    # kept is newest-first; reverse to oldest-first (natural reading order)
    kept.reverse()
    return "\n".join(kept)


# ─── Structured renderers (v2 3-stage pipeline, job 069) ──────────────────


def get_stage1_context_packet(session_id: str | None) -> dict:
    """Return a compact structured state packet for Stage 1's use.

    Stage 1 itself is currently prompt-only (Chroma k-NN embedding), so
    it does not consume this packet directly. It is instead used by the
    pre-Stage-1 resolver and can be logged for diagnostics.

    Keys:
      pending_action: dict or None — most recent unresolved action
      last_intent:    str — last known classifier intent
      last_entities:  dict — entities from the most recent structured turn
      recent_summary: str — compact prose snippet of the last turn
    """
    if not session_id:
        return {"pending_action": None, "last_intent": "",
                "last_entities": {}, "recent_summary": ""}
    try:
        from vault_web.recent_turns import get_active_state
    except Exception:
        return {"pending_action": None, "last_intent": "",
                "last_entities": {}, "recent_summary": ""}
    try:
        state = get_active_state(session_id)
    except Exception:
        return {"pending_action": None, "last_intent": "",
                "last_entities": {}, "recent_summary": ""}
    summaries = state.get("recent_summaries") or []
    return {
        "pending_action": state.get("pending_action"),
        "last_intent": state.get("last_intent", ""),
        "last_entities": state.get("last_entities", {}) or {},
        "recent_summary": summaries[-1] if summaries else "",
    }


def render_stage2_context(session_id: str | None, max_turns: int = 3) -> str:
    """Prose context block for Stage 2 handlers, augmented with a
    structured state line when an unresolved pending action exists.

    Handlers that already accept a prose `context=` kwarg (send_message,
    greeting) get the same FIFO summary they expect — plus, when
    relevant, a compact state header so they can see what's pending.
    """
    if not session_id:
        return ""
    prose = get_recent_context(session_id, max_turns=max_turns)
    packet = get_stage1_context_packet(session_id)
    pa = packet.get("pending_action")
    if not pa:
        return prose
    header = _render_state_header(packet)
    return (header + "\n\n" + prose).strip() if prose else header


def render_stage3_context(session_id: str | None, max_turns: int = 10) -> str:
    """Stage 3 (Opus) gets prose FIFO + a clearly-delimited state block.

    Avoids dumping raw JSON. Example output:

        [CURRENT CONVERSATION STATE]
        - Last intent: send message.
        - Pending action: awaiting confirmation to send SMS to Kathia.
        - Draft: "I love you".
        [END CURRENT CONVERSATION STATE]

        user: …
        jane: …
    """
    if not session_id:
        return ""
    prose = get_recent_context(session_id, max_turns=max_turns)
    packet = get_stage1_context_packet(session_id)
    if not (packet.get("pending_action") or packet.get("last_intent")):
        return prose
    block = _render_state_block(packet)
    return (block + "\n\n" + prose).strip() if prose else block


def _render_state_header(packet: dict) -> str:
    """Single-line compact state header for Stage 2 handlers."""
    pa = packet.get("pending_action") or {}
    intent = packet.get("last_intent") or ""
    parts = []
    if intent:
        parts.append(f"last_intent={intent}")
    if pa:
        ptype = pa.get("type", "pending")
        data = pa.get("data") or {}
        who = data.get("display_name") or data.get("recipient")
        if who:
            parts.append(f"pending={ptype}→{who}")
        else:
            parts.append(f"pending={ptype}")
    return "[STATE: " + "; ".join(parts) + "]" if parts else ""


def _render_state_block(packet: dict) -> str:
    """Multi-line state block for Stage 3 (Opus)."""
    lines = ["[CURRENT CONVERSATION STATE]"]
    intent = packet.get("last_intent") or ""
    if intent:
        lines.append(f"- Last intent: {intent}.")
    pa = packet.get("pending_action") or {}
    if pa:
        ptype = pa.get("type", "pending action")
        data = pa.get("data") or {}
        who = data.get("display_name") or data.get("recipient")
        body = data.get("body") or data.get("message_body")
        if ptype == "SEND_MESSAGE_CONFIRMATION":
            if who and body:
                lines.append(f'- Pending action: awaiting confirmation to SMS {who}: "{body}".')
            elif who:
                lines.append(f"- Pending action: awaiting confirmation to SMS {who}.")
            else:
                lines.append("- Pending action: awaiting confirmation to send an SMS.")
            lines.append("- User may confirm, revise, or cancel.")
        else:
            lines.append(f"- Pending action: {ptype}.")
    entities = packet.get("last_entities") or {}
    if entities and not pa:
        ent_str = ", ".join(f"{k}={v}" for k, v in list(entities.items())[:4])
        lines.append(f"- Recent entities: {ent_str}.")
    lines.append("[END CURRENT CONVERSATION STATE]")
    return "\n".join(lines)
