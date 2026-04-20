"""v3 classifier — top-5 ChromaDB vote + qwen2.5:7b validation with FIFO awareness.

Architecture (unchanged from the Haiku draft; only the LLM transport swapped):
  1. Embed the user prompt once.
  2. Query the v2 ChromaDB intent collection for top-5 nearest documents.
  3. Filter by distance threshold — matches beyond MAX_DISTANCE are pure
     noise and get dropped.
  4. Tally surviving documents' class labels; the winner is the voted
     candidate. Ties broken by lowest (best) distance within that class.
  5. If NO candidate survives the threshold → return ("others", "Low") so
     the v3 pipeline falls through to Stage 3.
  6. Otherwise: assemble a soft-framing prompt (the candidate class + its
     definition + recent FIFO + current prompt, with explicit instructions
     explaining that the embedding can be wrong on short follow-ups and
     asking the LLM to veto-check it) and send to qwen2.5:7b via Ollama.
  7. Parse {class, confidence ∈ Very High|High|Medium|Low}. Very High /
     High → route to Stage 2; Medium / Low → escalate to Stage 3.

Why qwen, not Haiku: Haiku via the Claude CLI pays ~3s of per-turn CLI
framing overhead (measured) that can't be reduced without ANTHROPIC_API_KEY.
qwen2.5:7b runs locally in Ollama with the same `keep_alive=-1` warm
runner v2's gate-check uses, delivering sub-second classifications.
v3's structural wins (one FIFO-aware call instead of three scattered
checks) do NOT depend on which LLM sits behind it — so we use the fast
one.

Failure modes all return ("others", "Low"). Never raises.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

TOP_K = int(os.environ.get("JANE_V3_TOP_K", "5"))
MAX_DISTANCE = float(os.environ.get("JANE_V3_MAX_DISTANCE", "0.60"))
FIFO_TURNS = int(os.environ.get("JANE_V3_FIFO_TURNS", "4"))
# If the winner's nearest exemplar is within this cosine distance, treat
# the embedding vote as authoritative and tell qwen to trust it.
# 0.05 ≈ "essentially the same string" (perfect match is 0.0).
#
# We deliberately DO NOT short-circuit on "unanimous top-K vote" — the
# bge-small model embeds question/statement variants of the same topic
# too close together (e.g. "what song is this?" and "play this song" both
# land unanimously in MUSIC_PLAY's neighborhood). A unanimous vote means
# vocabulary overlap, not semantic correctness. Only verbatim matches
# (distance ≈ 0) are safe to bypass qwen on.
NEAR_IDENTICAL_DIST = float(os.environ.get("JANE_V3_NEAR_IDENTICAL_DIST", "0.05"))
# Stage 2 auto-routing gate on the winner's best chroma distance. Above this,
# the match is "same vibe, different sentence" territory for bge-small-en — too
# loose to auto-short-circuit on a canned stage2 response. Breaches floor qwen's
# confidence to "Medium" so the pipeline escalates to Opus / Stage 3.
# Set after 2026-04-19 misclassification: "so we should save the conversation
# somewhere right based on session of course" matched "talk later" at 0.241
# and short-circuited to end_conversation ("Ok.") when it was a topical
# statement that belonged on Opus.
STAGE2_MAX_DISTANCE = float(os.environ.get("JANE_V3_STAGE2_MAX_DISTANCE", "0.15"))
# Per-call timeout for the qwen HTTP call. Reads the SINGLE source of
# truth from jane_web.jane_v2.models so every Ollama caller agrees.
# JANE_V3_LLM_TIMEOUT_S overrides for this specific call site if needed.
def _load_timeout() -> float:
    try:
        from jane_web.jane_v2.models import LOCAL_LLM_TIMEOUT as _t
        return float(os.environ.get("JANE_V3_LLM_TIMEOUT_S", str(_t)))
    except Exception:
        return float(os.environ.get("JANE_V3_LLM_TIMEOUT_S", "40.0"))
_LLM_TIMEOUT = _load_timeout()
# Output budget — the expected response is a ~40-token JSON object.
_NUM_PREDICT = int(os.environ.get("JANE_V3_NUM_PREDICT", "60"))

_STAGE2_CONFS = {"Very High", "High"}


# ── Top-5 ChromaDB vote ──────────────────────────────────────────────────────


def _top_k_candidates(user_prompt: str) -> list[dict]:
    """Reuse v2's loaded ChromaDB collection + embedding fn for top-K.

    Returns [{"class": str, "distance": float}, ...], filtered by MAX_DISTANCE.
    Empty list on any error — caller falls through to Stage 3.
    """
    try:
        from intent_classifier.v2 import classifier as v2c
        v2c._load()
        if v2c._collection is None or v2c._embed_fn is None:
            return []
        vec = v2c._embed_fn([user_prompt])[0]
        results = v2c._collection.query(
            query_embeddings=[vec],
            n_results=min(TOP_K, v2c._collection.count()),
            include=["metadatas", "distances"],
        )
        metas = results["metadatas"][0]
        dists = results["distances"][0]
        out: list[dict] = []
        for meta, dist in zip(metas, dists):
            if dist is None or dist > MAX_DISTANCE:
                continue
            cls = (meta or {}).get("class")
            if not cls:
                continue
            out.append({"class": cls, "distance": float(dist)})
        return out
    except Exception as e:
        logger.warning("v3: top-K query failed: %s", e)
        return []


def _vote(candidates: list[dict]) -> list[dict]:
    """Tally class labels, return ranked list of classes with vote stats.

    Each entry: {"class": str, "count": int, "best_distance": float}.
    Sorted by (most votes desc, lowest distance asc). First element is the
    winner; second (if any) is the runner-up — we show both to qwen so it
    can pick the alternative if the winner looks wrong for the context.
    """
    if not candidates:
        return []
    tally: dict[str, dict] = {}
    for c in candidates:
        cls, dist = c["class"], c["distance"]
        t = tally.setdefault(cls, {"count": 0, "best_dist": dist})
        t["count"] += 1
        if dist < t["best_dist"]:
            t["best_dist"] = dist
    ranked = sorted(
        tally.items(),
        key=lambda kv: (-kv[1]["count"], kv[1]["best_dist"]),
    )
    return [
        {"class": cls, "count": stats["count"], "best_distance": stats["best_dist"]}
        for cls, stats in ranked
    ]


# ── Class definition lookup ──────────────────────────────────────────────────


def _class_definition(class_name: str) -> str:
    """Pull the human description from the handler's metadata.py."""
    try:
        from jane_web.jane_v2 import classes as class_registry
        reg = class_registry.get_registry()
        normalized = class_name.replace("_", " ").strip().lower()
        for meta in reg.values():
            n = (meta.get("name") or "").strip().lower()
            if n == normalized:
                desc = meta.get("description")
                if callable(desc):
                    try:
                        desc = desc()
                    except Exception:
                        desc = ""
                return str(desc or "").strip()
    except Exception as e:
        logger.warning("v3: class definition lookup failed for %r: %s", class_name, e)
    return ""


# ── FIFO context ─────────────────────────────────────────────────────────────


async def _recent_fifo(session_id: str) -> str:
    if not session_id:
        return ""
    try:
        from jane_web.jane_v2 import recent_context
        return (recent_context.render_stage2_context(session_id, max_turns=FIFO_TURNS) or "").strip()
    except Exception as e:
        logger.warning("v3: FIFO load failed: %s", e)
        return ""


# ── Pending-action lookup ─────────────────────────────────────────────────────


def _pending_action_class(session_id: str) -> tuple[str, str]:
    """Return (handler_class, question) from the session's pending_action,
    IFF the pending is STAGE2_FOLLOWUP and not expired. Otherwise ("", "").

    The handler_class tells us what class ASKED the question, so on the next
    turn we should inject THAT class as the primary candidate to qwen —
    overriding chroma, which has no conversation awareness.
    """
    if not session_id:
        return ("", "")
    try:
        from vault_web.recent_turns import get_active_state
        from jane_web.jane_v2.pending_action_resolver import _is_expired
        state = get_active_state(session_id) or {}
        pending = state.get("pending_action") or {}
        if pending.get("type") != "STAGE2_FOLLOWUP":
            return ("", "")
        if _is_expired(pending):
            return ("", "")
        handler_class = (pending.get("handler_class") or "").strip()
        question = (pending.get("question") or "").strip()
        return (handler_class, question)
    except Exception as e:
        logger.warning("v3: pending_action lookup failed: %s", e)
        return ("", "")


def _janes_last_question(fifo_block: str) -> str:
    """Extract Jane's most recent utterance from the FIFO IF it ended with a '?'.

    We call this out explicitly in the prompt because qwen tends to weight
    the embedding vote over the FIFO on short-reply follow-ups (e.g. a bare
    "pasta" replying to "what should I call this timer?"). A direct callout
    forces qwen to see that there's an open question on the table.
    """
    if not fifo_block:
        return ""
    last_jane_line = ""
    for line in fifo_block.splitlines():
        s = line.strip()
        if not s:
            continue
        # Lines are rendered as "jane: ..." or "user: ..." by recent_context.
        if s.lower().startswith("jane:"):
            last_jane_line = s[len("jane:"):].strip()
        # We keep overwriting so we end with Jane's MOST RECENT utterance.
    if last_jane_line.endswith("?"):
        return last_jane_line
    return ""


# ── Prompt assembly ──────────────────────────────────────────────────────────


def _compact_def(text: str, max_chars: int = 280) -> str:
    """Return the first paragraph of a class description, capped in length.

    Class metadata descriptions often start with `[class_name]\\n` and contain
    long example lists and edge-case notes. The classifier only needs the
    summary paragraph — examples come via FIFO and few-shot tuning.
    """
    if not text:
        return ""
    s = text.strip()
    # Drop a leading `[class name]` header line; we add our own wrapper.
    if s.startswith("["):
        nl = s.find("\n")
        if nl > 0 and s[:nl].rstrip().endswith("]"):
            s = s[nl + 1:].lstrip()
    # Keep only the first paragraph (up to the first blank line).
    head = s.split("\n\n", 1)[0].strip()
    if len(head) > max_chars:
        head = head[:max_chars].rsplit(" ", 1)[0] + "…"
    return head


def _build_prompt(
    winner_class: str,
    winner_def: str,
    winner_count: int,
    winner_best_distance: float,
    runnerup_class: str | None,
    runnerup_def: str,
    runnerup_count: int,
    total_votes: int,
    fifo_block: str,
    user_prompt: str,
    pending_class: str = "",
    pending_def: str = "",
    pending_question: str = "",
) -> str:
    """Build the qwen classifier prompt.

    Modes:
    - Pending: Jane asked a clarifying question on behalf of a specific class;
      that class is option 1, chroma winner is option 2.
    - Default: chroma winner is option 1, runner-up is option 2.
    Both modes always offer `others` and `unclear`.
    """
    has_pending = bool(
        pending_class
        and pending_class.lower() != (winner_class or "").lower()
    )
    if has_pending:
        primary_class, primary_def = pending_class, pending_def
        alt_class = winner_class
        alt_def = winner_def
    else:
        primary_class, primary_def = winner_class, winner_def
        alt_class = runnerup_class if (runnerup_class and runnerup_class != winner_class) else None
        alt_def = runnerup_def if alt_class else ""

    primary_block = f"[{primary_class}] {_compact_def(primary_def)}".rstrip()
    alt_block = (
        f"[{alt_class}] {_compact_def(alt_def)}".rstrip() if alt_class else ""
    )
    others_block = "[others] neither specific class fits; need reasoning / memory / meta Q."
    unclear_block = (
        "[unclear] STT garbled the raw text — cut off mid-phrase, or a bag "
        "of disconnected words with no coherent sentence. Examples: "
        "\"what's the weather in\", \"turn on the\", \"apple meeting blue\". "
        "Judge the SURFACE TEXT only; coherent grammatical sentences that "
        "merely mention unclear / garbled / broken input are NOT unclear."
    )

    if has_pending:
        header = (
            f"Classify a voice message for Jane.\n"
            f"Option 1 ({primary_class}) follows Jane's open question; "
            f"option 2 ({alt_class or 'n/a'}) is the embedding-only alternative. "
            f"Prefer option 1 if the reply plausibly answers it; option 2 only "
            f"on clear pivot."
        )
    else:
        header = (
            f"Classify a voice message for Jane. Embedding suggests {primary_class}"
            f"{f' (runner-up: {alt_class})' if alt_class else ''}. Validate."
        )

    if not has_pending and winner_best_distance <= NEAR_IDENTICAL_DIST:
        identical_callout = (
            f"Note: near-identical match to a '{primary_class}' exemplar "
            f"(d={winner_best_distance:.3f}) — trust it unless FIFO shows a pivot.\n"
        )
    else:
        identical_callout = ""

    janes_q = _janes_last_question(fifo_block) or pending_question
    jane_callout = (
        f"Jane's last question: \"{janes_q}\"\n" if janes_q else ""
    )
    fifo_section = (
        f"Recent turns:\n{fifo_block}\n" if fifo_block else "Recent turns: (none)\n"
    )

    classes_block = "\n".join(b for b in (primary_block, alt_block, others_block, unclear_block) if b)

    return f"""{header}
{identical_callout}Classes:
{classes_block}

{fifo_section}{jane_callout}User: "{user_prompt.strip()}"

Return ONLY JSON: {{"class": "<name>", "confidence": "Very High|High|Medium|Low"}}
Routing: Very High/High → handler. Medium/Low → escalate. "unclear" → ask user to repeat. "others" Low → escalate.

JSON:"""


# ── qwen call via Ollama (reuses the already-warm runner) ────────────────────


async def _call_qwen(prompt_text: str) -> str:
    """POST to Ollama's /api/generate. Returns the raw response text.

    MUST use LOCAL_LLM_NUM_CTX from jane_web/jane_v2/models.py — any
    different num_ctx would force Ollama to reload the runner (see
    `preference_registry.json::unified_local_llm_num_ctx`).
    """
    import httpx
    from jane_web.jane_v2.models import (
        LOCAL_LLM as model,
        LOCAL_LLM_NUM_CTX,
        OLLAMA_KEEP_ALIVE,
        OLLAMA_URL,
    )
    body = {
        "model": model,
        "prompt": prompt_text,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.0,
            "num_predict": _NUM_PREDICT,
            "num_ctx": LOCAL_LLM_NUM_CTX,
        },
        "keep_alive": OLLAMA_KEEP_ALIVE,
    }
    async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
        r = await client.post(OLLAMA_URL, json=body)
        r.raise_for_status()
        try:
            from jane_web.jane_v2.models import record_ollama_activity
            record_ollama_activity()
        except Exception:
            pass
        return (r.json().get("response") or "").strip()


# ── Main entry point ────────────────────────────────────────────────────────


async def classify(
    user_prompt: str,
    session_id: str | None = None,
) -> tuple[str, str]:
    """Return (class_name, confidence_level). Never raises.

    confidence_level ∈ {"Very High", "High", "Medium", "Low"}.
    The v3 pipeline routes only "Very High" / "High" to Stage 2; anything
    else routes to Stage 3.
    """
    if not user_prompt or not user_prompt.strip():
        return ("others", "Low")

    # 1. Embedding top-5 with distance filter
    candidates = _top_k_candidates(user_prompt)
    if not candidates:
        logger.info("v3: no candidates pass distance threshold → others:Low")
        return ("others", "Low")

    # 2. Vote — ranked list with winner + runner-up (if any)
    ranked = _vote(candidates)
    if not ranked:
        return ("others", "Low")

    winner = ranked[0]
    runnerup = ranked[1] if len(ranked) > 1 else None

    # Normalize UPPER_CASE embedding labels to lowercase-with-spaces
    # handler names (e.g. "TODO_LIST" → "todo list").
    winner_handler = winner["class"].lower().replace("_", " ")
    runnerup_handler = (
        runnerup["class"].lower().replace("_", " ") if runnerup else None
    )

    # 3. Gather FIFO + definitions for qwen
    fifo_block = await _recent_fifo(session_id or "")
    winner_def = _class_definition(winner_handler) or ""
    runnerup_def = (
        _class_definition(runnerup_handler) if runnerup_handler else ""
    ) or ""

    # 3a. Pending STAGE2_FOLLOWUP? If the previous turn's handler emitted
    # a pending_action with a clarifying question, THAT class should be
    # the primary candidate (chroma demotes to alternative). Chroma has
    # no conversation awareness and will routinely misroute short replies
    # like "pasta" → shopping_list when the user is actually answering
    # a timer-label question. Normalize underscore→space to match the
    # handler registry keys (handler_class comes in as "todo_list" but
    # the registry uses "todo list").
    raw_pending_class, pending_question = _pending_action_class(session_id or "")
    pending_class = raw_pending_class.lower().replace("_", " ").strip()
    pending_def = _class_definition(pending_class) if pending_class else ""

    prompt_text = _build_prompt(
        winner_class=winner_handler,
        winner_def=winner_def,
        winner_count=winner["count"],
        winner_best_distance=winner["best_distance"],
        runnerup_class=runnerup_handler,
        runnerup_def=runnerup_def,
        runnerup_count=runnerup["count"] if runnerup else 0,
        total_votes=len(candidates),
        fifo_block=fifo_block,
        user_prompt=user_prompt,
        pending_class=pending_class,
        pending_def=pending_def,
        pending_question=pending_question,
    )

    # 4. Send to qwen via Ollama (warm runner, sub-second typical)
    try:
        raw = await _call_qwen(prompt_text)
    except Exception as e:
        logger.warning("v3: qwen call failed (%s) — falling back to Stage 3", e)
        return ("others", "Low")

    # 5. Parse {class, confidence}
    try:
        text = raw.strip().strip("`").strip()
        if text.lower().startswith("json"):
            text = text.split("\n", 1)[-1].strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        parsed = json.loads(text)
        cls = str(parsed.get("class", "")).strip().lower()
        conf = str(parsed.get("confidence", "Low")).strip().title()
        if conf not in ("Very High", "High", "Medium", "Low"):
            conf = "Low"
        if not cls:
            return ("others", "Low")
        # Validate against the runtime handler registry; anything off-list
        # becomes "others".
        allowed = {"others"}
        try:
            from jane_web.jane_v2 import classes as class_registry
            for meta in class_registry.get_registry().values():
                n = (meta.get("name") or "").strip().lower()
                if n:
                    allowed.add(n)
        except Exception:
            pass
        if cls not in allowed:
            logger.warning("v3: qwen returned unknown class %r → others", cls)
            return ("others", "Low")
    except Exception as e:
        logger.warning("v3: parse failed (%s) — raw=%r", e, raw[:160])
        return ("others", "Low")

    # 6. Stage 2 distance gate — floor confidence when qwen agreed with a
    # chroma winner whose embedding distance is too loose for a canned
    # short-circuit. "Same vibe, different sentence" territory (0.15–0.30 for
    # bge-small-en) is where short farewell exemplars outrank topical
    # statements. Only applies when qwen's returned class equals the chroma
    # winner — if qwen picked the pending-action class or overruled chroma,
    # we don't penalize based on chroma's distance (which isn't the evidence
    # qwen used). Doesn't affect already-Medium/Low results.
    winner_best_distance = float(winner.get("best_distance", 1.0))
    if (
        conf in _STAGE2_CONFS
        and cls != "others"
        and cls == winner_handler
        and winner_best_distance > STAGE2_MAX_DISTANCE
    ):
        logger.info(
            "v3: distance floor (winner_dist=%.3f > %.3f) — %s:%s → Medium (escalate)",
            winner_best_distance, STAGE2_MAX_DISTANCE, cls, conf,
        )
        conf = "Medium"

    # 7. Confidence gate
    if conf not in _STAGE2_CONFS or cls == "others":
        logger.info(
            "v3: qwen → %s:%s → escalating to Stage 3 (winner=%s runnerup=%s had_fifo=%s)",
            cls, conf, winner_handler, runnerup_handler, bool(fifo_block),
        )
        return ("others", "Low")

    logger.info(
        "v3: qwen → %s:%s (winner=%s %d/%d dist=%.3f, runnerup=%s %d, had_fifo=%s)",
        cls, conf, winner_handler, winner["count"], len(candidates),
        winner_best_distance,
        runnerup_handler, (runnerup["count"] if runnerup else 0),
        bool(fifo_block),
    )
    return (cls, conf)
