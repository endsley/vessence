"""recent_context.py — fetch the last N turns for a session, budgeted.

Thin wrapper around vault_web.recent_turns.get_recent that:
  - reads the FIFO for a given session
  - trims the combined summary block to a char budget (stand-in for
    a token budget — we use chars because gemma4 doesn't need an exact
    tokenizer for this use case and 1 token ≈ 4 chars is close enough)
  - formats the result as a prompt-ready block, newest-last

Stage 2 class handlers can import this to get conversation context
without a ChromaDB similarity search. ~1ms SQLite read.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Rough char → token conversion. gemma4 tokens are ~4 chars on average.
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
