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
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ── Output-parsing guards ─────────────────────────────────────────────────────
#
# These run AFTER qwen and only correct narrow parse-layer failures.
# They do NOT add new classifier logic and do NOT bypass chroma+qwen —
# classifier fixes belong in exemplars / class descriptions, per the
# pipeline architecture guideline in
# agent_skills/transcript_quality_review.py.

# Guard against "delete" phrasing being misclassified as send_email. After
# a read_messages / read_email turn, "delete it / delete that / delete them"
# should route to Stage 3 (Opus) rather than the send_email handler, which
# has no way to produce a valid send action from a delete request. See
# transcript review Issue 15 (2026-04-20 21:28:47).
_DELETE_INTENT_RE = re.compile(
    r"^\s*(?:can\s+you\s+|could\s+you\s+|please\s+)?"
    r"delete\s+(?:it|that|them|this|those|these|the\s+\w+)\b",
    re.IGNORECASE,
)


def _is_delete_intent(user_prompt: str) -> bool:
    if not user_prompt:
        return False
    return bool(_DELETE_INTENT_RE.match(user_prompt.strip()))


def _handler_name_from_classifier_label(label: str | None) -> str:
    return (label or "").lower().replace("_", " ").strip()


def _allowed_classifier_classes(registry: dict) -> set[str]:
    allowed = {"others"}
    for meta in (registry or {}).values():
        n = (meta.get("name") or "").strip().lower()
        if n:
            allowed.add(n)
    return allowed


def _chosen_class_distance(ranked: list[dict], cls: str) -> float | None:
    for rec in ranked:
        if _handler_name_from_classifier_label(rec["class"]) == cls:
            return float(rec["best_distance"])
    return None


def _should_floor_distance_confidence(
    *,
    conf: str,
    cls: str,
    chosen_distance: float | None,
    is_pending_choice: bool,
    stage2_max_distance: float | None = None,
) -> bool:
    max_distance = STAGE2_MAX_DISTANCE if stage2_max_distance is None else stage2_max_distance
    return (
        conf in _STAGE2_CONFS
        and cls != "others"
        and cls != "send message"
        and not is_pending_choice
        and chosen_distance is not None
        and chosen_distance > max_distance
    )


def _params_for_chosen_class(params: dict, cls: str, schema_class: str) -> dict:
    if params and cls != (schema_class or "").lower():
        return {}
    return params


def _parse_qwen_classification_response(raw: str) -> tuple[str, str, dict] | None:
    text = raw.strip().strip("`").strip()
    if text.lower().startswith("json"):
        text = text.split("\n", 1)[-1].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    parsed = json.loads(text)
    cls = str(parsed.get("class", "")).strip().lower().strip("[]").strip()
    conf = str(parsed.get("confidence", "Low")).strip().title()
    if conf not in ("Very High", "High", "Medium", "Low"):
        conf = "Low"
    params = parsed.get("params") if isinstance(parsed.get("params"), dict) else {}
    if not cls:
        return None
    return cls, conf, params

# ── Config ────────────────────────────────────────────────────────────────────

TOP_K = int(os.environ.get("JANE_V3_TOP_K", "5"))
MAX_DISTANCE = float(os.environ.get("JANE_V3_MAX_DISTANCE", "0.40"))
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
STAGE2_MAX_DISTANCE = float(os.environ.get("JANE_V3_STAGE2_MAX_DISTANCE", "0.22"))
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
# Output budget — bare {class, confidence} is ~40 tokens, but classes that
# declare a PARAMS_SCHEMA add a small JSON object on top. 200 fits the
# largest realistic case without runaway generation.
_NUM_PREDICT = int(os.environ.get("JANE_V3_NUM_PREDICT", "200"))

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


@dataclass(frozen=True)
class ClassifierCandidateState:
    candidates: list[dict]
    ranked: list[dict]
    winner: dict
    runnerup: dict | None
    winner_handler: str
    runnerup_handler: str | None


def _candidate_state(candidates: list[dict]) -> ClassifierCandidateState | None:
    ranked = _vote(candidates)
    if not ranked:
        return None

    winner = ranked[0]
    runnerup = ranked[1] if len(ranked) > 1 else None
    winner_handler = _handler_name_from_classifier_label(winner["class"])
    runnerup_handler = (
        _handler_name_from_classifier_label(runnerup["class"]) if runnerup else None
    )
    return ClassifierCandidateState(
        candidates=candidates,
        ranked=ranked,
        winner=winner,
        runnerup=runnerup,
        winner_handler=winner_handler,
        runnerup_handler=runnerup_handler,
    )


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


def _class_param_schema(class_name: str) -> dict:
    """Return the class's PARAMS_SCHEMA dict, or {} if unset.

    Classes that declare params_schema in metadata get those fields
    extracted by the same qwen call that classifies the intent. The
    handler then dispatches on those fields (no Python regex / intent
    detection in the handler). Classes without a schema behave exactly
    as before — qwen still emits {class, confidence} only.
    """
    try:
        from jane_web.jane_v2 import classes as class_registry
        reg = class_registry.get_registry()
        normalized = class_name.replace("_", " ").strip().lower()
        for meta in reg.values():
            n = (meta.get("name") or "").strip().lower()
            if n == normalized:
                schema = meta.get("params_schema") or {}
                return dict(schema) if isinstance(schema, dict) else {}
    except Exception as e:
        logger.warning("v3: params_schema lookup failed for %r: %s", class_name, e)
    return {}


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


@dataclass(frozen=True)
class PromptCandidateContext:
    has_pending: bool
    primary_class: str
    primary_def: str
    alt_class: str | None
    alt_def: str


def _prompt_candidate_context(
    *,
    winner_class: str,
    winner_def: str,
    runnerup_class: str | None,
    runnerup_def: str,
    pending_class: str = "",
    pending_def: str = "",
) -> PromptCandidateContext:
    has_pending = bool(
        pending_class
        and pending_class.lower() != (winner_class or "").lower()
    )
    if has_pending:
        return PromptCandidateContext(
            has_pending=True,
            primary_class=pending_class,
            primary_def=pending_def,
            alt_class=winner_class,
            alt_def=winner_def,
        )

    alt_class = runnerup_class if (runnerup_class and runnerup_class != winner_class) else None
    return PromptCandidateContext(
        has_pending=False,
        primary_class=winner_class,
        primary_def=winner_def,
        alt_class=alt_class,
        alt_def=runnerup_def if alt_class else "",
    )


@dataclass(frozen=True)
class ClassifierPromptState:
    fifo_block: str
    winner_def: str
    runnerup_def: str
    pending_class: str
    pending_def: str
    pending_question: str
    primary_param_schema: dict
    schema_class: str


async def _load_prompt_state(
    session_id: str,
    winner_handler: str,
    runnerup_handler: str | None,
) -> ClassifierPromptState:
    fifo_block = await _recent_fifo(session_id)
    winner_def = _class_definition(winner_handler) or ""
    runnerup_def = (
        _class_definition(runnerup_handler) if runnerup_handler else ""
    ) or ""
    primary_param_schema = _class_param_schema(winner_handler)
    schema_class = winner_handler

    raw_pending_class, pending_question = _pending_action_class(session_id)
    pending_class = _handler_name_from_classifier_label(raw_pending_class)
    pending_def = _class_definition(pending_class) if pending_class else ""

    candidate_context = _prompt_candidate_context(
        winner_class=winner_handler,
        winner_def=winner_def,
        runnerup_class=runnerup_handler,
        runnerup_def=runnerup_def,
        pending_class=pending_class,
        pending_def=pending_def,
    )
    if candidate_context.has_pending:
        primary_param_schema = _class_param_schema(pending_class)
        schema_class = pending_class

    return ClassifierPromptState(
        fifo_block=fifo_block,
        winner_def=winner_def,
        runnerup_def=runnerup_def,
        pending_class=pending_class,
        pending_def=pending_def,
        pending_question=pending_question,
        primary_param_schema=primary_param_schema,
        schema_class=schema_class,
    )


def _prompt_class_blocks(candidate_context: PromptCandidateContext) -> str:
    primary_block = (
        f"[{candidate_context.primary_class}] "
        f"{_compact_def(candidate_context.primary_def)}"
    ).rstrip()
    alt_block = (
        f"[{candidate_context.alt_class}] {_compact_def(candidate_context.alt_def)}".rstrip()
        if candidate_context.alt_class
        else ""
    )
    others_block = "[others] neither specific class fits; need reasoning / memory / meta Q."
    unclear_block = (
        "[unclear] Pick UNCLEAR only when the user's message AS A WHOLE has "
        "no recoverable intent. Specifically: (a) cut off mid-phrase "
        "(\"what's the weather in\", \"turn on the\"); (b) word-soup with no "
        "verb or coherent subject (\"apple meeting blue\", \"I got to "
        "seaweed\", \"origin\"); (c) background speech bleeding in. Do NOT "
        "pick unclear just because one word looks mistranscribed — if the "
        "rest of the sentence has a clear verb + object (\"who is the next "
        "patient\", \"what's the clinic schedule like X\"), pick the matching "
        "content class even if a name or noun looks wrong. Test: would a "
        "human listener say \"I have no idea what they want\" (unclear) or "
        "\"they want X but mangled a word\" (pick the content class)?"
    )
    return "\n".join(
        b for b in (primary_block, alt_block, others_block, unclear_block) if b
    )


def _prompt_header(candidate_context: PromptCandidateContext) -> str:
    if candidate_context.has_pending:
        return (
            "Classify a voice message for Jane.\n"
            "Judge the SURFACE TEXT of the user message. The recent turns "
            "are context, not a directive — do not extend a previous topic "
            "if the current message is gibberish or unrelated."
        )
    runnerup = (
        f" (runner-up: {candidate_context.alt_class})"
        if candidate_context.alt_class
        else ""
    )
    return (
        "Classify a voice message for Jane. Embedding suggests "
        f"{candidate_context.primary_class}{runnerup}. Validate."
    )


def _near_identical_prompt_callout(
    *,
    candidate_context: PromptCandidateContext,
    winner_best_distance: float,
) -> str:
    if candidate_context.has_pending or winner_best_distance > NEAR_IDENTICAL_DIST:
        return ""
    return (
        f"Note: prompt embeds near a '{candidate_context.primary_class}' exemplar "
        f"(d={winner_best_distance:.3f}). Treat this as supporting "
        f"evidence, not a verdict — your own read of the SURFACE TEXT "
        f"and FIFO is what decides. If the prompt looks cut off, vague, "
        f"or off-topic, prefer 'unclear' or 'others' over the suggested "
        f"class.\n"
    )


def _jane_question_callout(fifo_block: str, pending_question: str) -> str:
    janes_q = _janes_last_question(fifo_block) or pending_question
    return f"Jane's last question: \"{janes_q}\"\n" if janes_q else ""


def _fifo_section(fifo_block: str) -> str:
    return f"Recent turns:\n{fifo_block}\n" if fifo_block else "Recent turns: (none)\n"


def _params_instruction_block(
    primary_class: str,
    primary_param_schema: dict | None,
) -> str:
    if not primary_param_schema:
        return (
            "\nReturn ONLY JSON: "
            "{\"class\": \"<name>\", \"confidence\": \"Very High|High|Medium|Low\"}"
        )

    schema_lines = [f"  - {k}: {v}" for k, v in primary_param_schema.items()]
    return (
        f"\nIf you classify as {primary_class}, also extract these fields "
        f"into a `params` object (use null when a field is not mentioned):\n"
        + "\n".join(schema_lines)
        + "\n\nReturn ONLY JSON: "
        f"{{\"class\": \"<name>\", \"confidence\": \"Very High|High|Medium|Low\", "
        f"\"params\": {{...}}}}\n"
        f"For any other class, omit `params` (or set it to {{}})."
    )


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
    primary_param_schema: dict | None = None,
) -> str:
    """Build the qwen classifier prompt.

    Modes:
    - Pending: Jane asked a clarifying question on behalf of a specific class;
      that class is option 1, chroma winner is option 2.
    - Default: chroma winner is option 1, runner-up is option 2.
    Both modes always offer `others` and `unclear`.
    """
    candidate_context = _prompt_candidate_context(
        winner_class=winner_class,
        winner_def=winner_def,
        runnerup_class=runnerup_class,
        runnerup_def=runnerup_def,
        pending_class=pending_class,
        pending_def=pending_def,
    )
    primary_class = candidate_context.primary_class
    header = _prompt_header(candidate_context)
    identical_callout = _near_identical_prompt_callout(
        candidate_context=candidate_context,
        winner_best_distance=winner_best_distance,
    )
    classes_block = _prompt_class_blocks(candidate_context)
    fifo_section = _fifo_section(fifo_block)
    jane_callout = _jane_question_callout(fifo_block, pending_question)
    params_block = _params_instruction_block(primary_class, primary_param_schema)

    return f"""{header}
{identical_callout}Classes:
{classes_block}

{fifo_section}{jane_callout}User: "{user_prompt.strip()}"
{params_block}
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
) -> tuple[str, str, dict]:
    """Return (class_name, confidence_level, params). Never raises.

    confidence_level ∈ {"Very High", "High", "Medium", "Low"}.
    The v3 pipeline routes only "Very High" / "High" to Stage 2; anything
    else routes to Stage 3.

    `params` is a dict of fields the chosen class declared in
    `metadata.PARAMS_SCHEMA`, extracted by qwen alongside the
    classification. Empty dict for classes without a schema or when
    parsing failed.
    """
    if not user_prompt or not user_prompt.strip():
        return ("others", "Low", {})

    # 1. Embedding top-5 with distance filter
    candidates = _top_k_candidates(user_prompt)
    if not candidates:
        logger.info("v3: no candidates pass distance threshold → others:Low")
        return ("others", "Low", {})

    # 2. Vote — ranked list with winner + runner-up (if any)
    candidate_state = _candidate_state(candidates)
    if candidate_state is None:
        return ("others", "Low", {})

    # 3. Gather FIFO + definitions for qwen
    prompt_state = await _load_prompt_state(
        session_id or "",
        candidate_state.winner_handler,
        candidate_state.runnerup_handler,
    )

    prompt_text = _build_prompt(
        winner_class=candidate_state.winner_handler,
        winner_def=prompt_state.winner_def,
        winner_count=candidate_state.winner["count"],
        winner_best_distance=candidate_state.winner["best_distance"],
        runnerup_class=candidate_state.runnerup_handler,
        runnerup_def=prompt_state.runnerup_def,
        runnerup_count=candidate_state.runnerup["count"] if candidate_state.runnerup else 0,
        total_votes=len(candidates),
        fifo_block=prompt_state.fifo_block,
        user_prompt=user_prompt,
        pending_class=prompt_state.pending_class,
        pending_def=prompt_state.pending_def,
        pending_question=prompt_state.pending_question,
        primary_param_schema=prompt_state.primary_param_schema,
    )

    # 4. Send to qwen via Ollama (warm runner, sub-second typical)
    try:
        raw = await _call_qwen(prompt_text)
    except Exception as e:
        logger.warning("v3: qwen call failed (%s) — falling back to Stage 3", e)
        return ("others", "Low", {})

    # 5. Parse {class, confidence, params?}
    params: dict = {}
    try:
        parsed_response = _parse_qwen_classification_response(raw)
        if parsed_response is None:
            return ("others", "Low", {})
        cls, conf, params = parsed_response
        # Validate against the runtime handler registry; anything off-list
        # becomes "others".
        allowed = {"others"}
        try:
            from jane_web.jane_v2 import classes as class_registry
            allowed = _allowed_classifier_classes(class_registry.get_registry())
        except Exception:
            pass
        if cls not in allowed:
            logger.warning("v3: qwen returned unknown class %r → others", cls)
            return ("others", "Low", {})
        # Delete-intent guard: after read_messages / read_email, the user
        # saying "delete it" / "delete that" sometimes chroma-matches
        # send_email exemplars. send_email has no way to satisfy a delete
        # request and returns an invalid shape → wasted Stage 2 + Stage 3
        # round-trip. Force these to escalate so Opus can issue the right
        # delete tool call. See transcript review Issue 15 (2026-04-20).
        if cls in ("send email", "send message") and _is_delete_intent(user_prompt):
            logger.info(
                "v3: delete-intent guard: demoting %r → others for prompt=%r",
                cls, user_prompt[:80],
            )
            return ("others", "Low", {})
    except Exception as e:
        logger.warning("v3: parse failed (%s) — raw=%r", e, raw[:160])
        return ("others", "Low", {})

    # 6. Stage 2 distance gate — floor confidence when qwen's CHOSEN class
    # has no tight chroma support.
    #
    # Previous version only fired when `cls == winner_handler`, which missed
    # the case seen on 2026-04-20 08:23:54: chroma winner was 'shopping list'
    # (4/5, d=0.265), runnerup was 'end conversation' (1 vote), qwen picked
    # 'end conversation' Very High. The floor skipped because qwen overruled
    # chroma — but the chosen class itself had weak embedding support.
    #
    # New rule: find qwen's chosen class in the ranked chroma list and gate
    # on THAT entry's best distance. If the chosen class isn't in chroma at
    # all (0 votes), treat as weak → floor. Pending-mode exemption: when
    # qwen picks the pending-action class, skip the floor (the FIFO context
    # is the evidence, not chroma).
    winner_best_distance = float(candidate_state.winner.get("best_distance", 1.0))
    chosen_distance = _chosen_class_distance(candidate_state.ranked, cls)
    pending_class_normalized = _handler_name_from_classifier_label(prompt_state.pending_class)
    is_pending_choice = bool(pending_class_normalized) and cls == pending_class_normalized
    # Only floor when the chosen class IS in chroma top-K with a loose
    # distance. If chosen isn't in top-K at all, qwen is making a non-chroma-
    # supported call (FIFO context, world knowledge like "bye") and we trust
    # it — flooring there would penalize legitimate short farewells.
    # send_message is exempt from the distance floor: its handler has its
    # own COHERENT=yes/no guard from qwen, so a second classifier-level
    # safety net just routes legitimate texts to Opus unnecessarily. Trust
    # qwen here and let the handler decide whether to fast-path or escalate.
    if _should_floor_distance_confidence(
        conf=conf,
        cls=cls,
        chosen_distance=chosen_distance,
        is_pending_choice=is_pending_choice,
    ):
        logger.info(
            "v3: distance floor (chosen=%s dist=%.3f > %.3f, winner=%s dist=%.3f) — %s:%s → Medium (escalate)",
            cls, chosen_distance, STAGE2_MAX_DISTANCE, candidate_state.winner_handler, winner_best_distance, cls, conf,
        )
        conf = "Medium"

    # 7. Confidence gate
    if conf not in _STAGE2_CONFS or cls == "others":
        logger.info(
            "v3: qwen → %s:%s → escalating to Stage 3 (winner=%s runnerup=%s had_fifo=%s)",
            cls, conf, candidate_state.winner_handler, candidate_state.runnerup_handler, bool(prompt_state.fifo_block),
        )
        return ("others", "Low", {})

    # Param-leak guard: params were extracted against `schema_class` (chroma
    # winner, or pending-swap target). If qwen overrode to a different class,
    # those params describe the wrong intent — drop them so the handler for
    # the actual `cls` doesn't receive a sibling class's loader/slots.
    safe_params = _params_for_chosen_class(params, cls, prompt_state.schema_class)
    if params and not safe_params:
        logger.info(
            "v3: dropping params (extracted for %r, qwen chose %r) — params=%s",
            prompt_state.schema_class, cls, params,
        )
    params = safe_params

    logger.info(
        "v3: qwen → %s:%s params=%s (winner=%s %d/%d dist=%.3f, runnerup=%s %d, had_fifo=%s)",
        cls, conf, params or "{}", candidate_state.winner_handler, candidate_state.winner["count"], len(candidates),
        winner_best_distance,
        candidate_state.runnerup_handler, (candidate_state.runnerup["count"] if candidate_state.runnerup else 0),
        bool(prompt_state.fifo_block),
    )
    return (cls, conf, params)
