"""gemma_stage1.py — LEGACY (v1) Stage 1.

DEPRECATED. The active Stage 1 is `jane_web/jane_v2/stage1_classifier.py`
(ChromaDB embedding-based, no LLM). The active Stage 2 is qwen2.5:7b via
`jane_web/jane_v2/stage2_dispatcher.py`. The "Gemma" naming here is historical —
the running model is `qwen2.5:7b` (see `vessence-data/.env: JANE_STAGE2_MODEL`).
Kept only because jane_proxy still imports from it for a fallback path.

Stage 1 of the two-pass v1 architecture.

Responsibility: classify the user's message. That's it. No response text,
no ack generation — except GREETING, which generates its own 1-sentence reply
so the proxy can short-circuit without calling Stage 2 at all.

Classes:
  GREETING         — standalone greetings (no task attached) — includes RESPONSE
  SELF_HANDLE      — simple Q&A, trivia, time/date, weather questions
  MUSIC_PLAY       — "play X" style commands
  SHOPPING_LIST    — add/remove/show items
  READ_MESSAGES    — read/check SMS
  READ_EMAIL       — read/check email
  SYNC_MESSAGES    — force SMS re-sync
  SEND_MESSAGE     — text/SMS a person
  END_CONVERSATION — cancel/stop/thanks/bye after a prior proposal
  DELEGATE_OPUS    — everything else (complex, ambiguous, bug reports)

Per-class metadata:
  SEND_MESSAGE    → RECIPIENT, BODY, COHERENT
  MUSIC_PLAY      → QUERY
  SHOPPING_LIST   → ACTION
  READ_MESSAGES   → FILTER (optional sender name)
  READ_EMAIL      → QUERY (optional sender/count)

Context:
  FIFO short-term memory: last 4 turn summaries from recent_turns, capped
  at ~600 tokens (2400 chars).
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

_VAULT_WEB_DIR = Path(__file__).resolve().parents[2] / "vault_web"
if str(_VAULT_WEB_DIR) not in sys.path:
    sys.path.insert(0, str(_VAULT_WEB_DIR))

logger = logging.getLogger(__name__)

FIFO_TURN_COUNT = 4
FIFO_CHAR_CAP = 2400  # ~600 tokens

STAGE1_TIMEOUT_S = float(os.environ.get("JANE_STAGE1_TIMEOUT", "4.0"))

# Valid classifications — kept in one place so regex + dispatcher stay aligned.
VALID_CLASSES = (
    "GREETING",
    "SELF_HANDLE",
    "MUSIC_PLAY",
    "SHOPPING_LIST",
    "READ_MESSAGES",
    "READ_EMAIL",
    "SYNC_MESSAGES",
    "SEND_MESSAGE",
    "END_CONVERSATION",
    "GET_TIME",
    "DELEGATE_OPUS",
)

SYSTEM_PROMPT = """You are a narrow intent classifier. Output ONE line:
CLASSIFICATION: <one of GREETING SELF_HANDLE MUSIC_PLAY SHOPPING_LIST READ_MESSAGES READ_EMAIL SYNC_MESSAGES SEND_MESSAGE END_CONVERSATION GET_TIME DELEGATE_OPUS>
Plus a CONFIDENCE line: CONFIDENCE: 0.0-1.0
Plus any class-specific metadata lines listed below. Do NOT write response text — another stage handles that (except GREETING, which outputs its own short reply).

CLASS RULES:

GREETING — a standalone greeting with NO task or question attached.
Triggers: "hey", "hi", "hello", "good morning", "good evening", "what's up", "yo", "sup", "hey jane", etc.
ONLY use GREETING when:
  1. The entire message is the greeting — no follow-up request, AND
  2. The history context does NOT suggest the user is checking on an ongoing task/project.
     If history shows active work (a build in progress, a task Jane is doing, a question she asked),
     treat the greeting as a follow-up/status check — use DELEGATE_OPUS or SELF_HANDLE instead.
(No metadata needed — a separate module generates the response.)

SELF_HANDLE — simple math, trivia, weather question, or STT garbage.
STT garbage ("was that meant for me?") also counts.

GET_TIME — user asks the current time or current date.
Triggers: "what time is it", "what's the time", "current time", "tell me the time",
"what day is it", "what's today's date", "what's the date".
(No metadata needed.)

MUSIC_PLAY — user's first word is play/put/throw/listen/shuffle (or a polite variant like "can you play").
Also emit: QUERY: <artist or song name, nothing else>

SHOPPING_LIST — add/remove/show/check items on shopping/grocery lists.
Also emit: ACTION: <verb + item, e.g. "add milk">

READ_MESSAGES — check/read existing text messages.
Also emit: FILTER: <sender name if mentioned, else "all">

READ_EMAIL — check/read/search email or inbox.
Also emit: QUERY: <sender filter or count if mentioned, else "unread">

SYNC_MESSAGES — sync/resync/refresh SMS.

SEND_MESSAGE — user wants to TEXT/SMS a person. Triggers: "text [person]", "tell [person]", "message [person]", "let [person] know", "send [person]".
Also emit:
  RECIPIENT: <short name as user said it — keep "my wife" / "mom" / "Kathia" literal>
  BODY: <message text only>
  COHERENT: yes | no   (yes = clean sentence; no = garbled/cut off/random words)

END_CONVERSATION — user is ending the turn. Triggers: cancel, stop, don't send, never mind,
forget it, nope, no thanks, not now, skip it, be quiet, silence, shush, enough, leave me
alone, that's all, that's it, we're done, i'm done, drop it, bye, goodbye, see you later,
talk to you later, later, ok thanks, thanks, thank you, dismissed, go to sleep.
IMPORTANT: Only emit END_CONVERSATION if the prior assistant turn (see history) proposed
an action, asked a question, or completed a task. If history is empty or the message is a
NEW command, classify it normally instead.

DELEGATE_OPUS — everything else: complex questions, bug reports, code, ambiguous follow-ups,
phone calls ("call X"), multi-step commands, complaints.
ALSO use DELEGATE_OPUS for short affirmatives ("yes", "yea", "yeah", "sure", "ok", "please",
"yea please", "yes please", "go ahead", "do it", "sounds good", "that works") when the history
shows Jane asked a question or proposed an action — Opus already knows what it proposed and
can follow through. Do NOT classify these as SELF_HANDLE.
ALSO use DELEGATE_OPUS for status/update statements like "ok sent it", "ok I sent it",
"sent it", or "I did it". These are NOT conversation endings.

CONFIDENCE rules:
- Clear match for the class rule → ≥ 0.90
- Reasonable match but some ambiguity → 0.70-0.89
- Ambiguous / could be multiple classes → ≤ 0.70

EXAMPLES:

User: "hey"
CLASSIFICATION: GREETING
CONFIDENCE: 0.99
RESPONSE: Hey!

User: "good morning jane"
CLASSIFICATION: GREETING
CONFIDENCE: 0.99
RESPONSE: Morning!

User: "what's up"
CLASSIFICATION: GREETING
CONFIDENCE: 0.97
RESPONSE: Not much — what do you need?

[history: assistant: "Would you like me to add milk to your shopping list?"]
User: "yea please"
CLASSIFICATION: DELEGATE_OPUS
CONFIDENCE: 0.96

[history: assistant: "I can text Kathia that you'll be late — want me to send it?"]
User: "yes go ahead"
CLASSIFICATION: DELEGATE_OPUS
CONFIDENCE: 0.97

[history: assistant: "I found two contacts named John — did you mean John Smith or John Lee?"]
User: "the first one"
CLASSIFICATION: DELEGATE_OPUS
CONFIDENCE: 0.95

[history empty]
User: "yea please"
CLASSIFICATION: SELF_HANDLE
CONFIDENCE: 0.60

[history: assistant: "I'm building the Docker bundle now, should take a few minutes."]
User: "hey"
CLASSIFICATION: DELEGATE_OPUS
CONFIDENCE: 0.88

[history: assistant: "I found a bug in the auth module and I'm looking into it."]
User: "hey what's going on"
CLASSIFICATION: DELEGATE_OPUS
CONFIDENCE: 0.92

User: "hey can you play shakira"
CLASSIFICATION: MUSIC_PLAY
CONFIDENCE: 0.95
QUERY: shakira

User: "play shakira"
CLASSIFICATION: MUSIC_PLAY
CONFIDENCE: 0.99
QUERY: shakira

User: "add milk to the list"
CLASSIFICATION: SHOPPING_LIST
CONFIDENCE: 0.99
ACTION: add milk

User: "read my texts from kathia"
CLASSIFICATION: READ_MESSAGES
CONFIDENCE: 0.97
FILTER: kathia

User: "any new emails from bob"
CLASSIFICATION: READ_EMAIL
CONFIDENCE: 0.98
QUERY: from:bob

User: "sync my messages"
CLASSIFICATION: SYNC_MESSAGES
CONFIDENCE: 0.99

User: "what time is it"
CLASSIFICATION: GET_TIME
CONFIDENCE: 0.99

User: "what's today's date"
CLASSIFICATION: GET_TIME
CONFIDENCE: 0.97

User: "text my wife that i'll be home late"
CLASSIFICATION: SEND_MESSAGE
CONFIDENCE: 0.98
RECIPIENT: wife
BODY: I'll be home late
COHERENT: yes

User: "tell kathia i miss her"
CLASSIFICATION: SEND_MESSAGE
CONFIDENCE: 0.97
RECIPIENT: kathia
BODY: I miss you
COHERENT: yes

User: "text my wife purple elephant banana"
CLASSIFICATION: SEND_MESSAGE
CONFIDENCE: 0.90
RECIPIENT: wife
BODY: purple elephant banana
COHERENT: no

User: "text my wife i'll"
CLASSIFICATION: SEND_MESSAGE
CONFIDENCE: 0.85
RECIPIENT: wife
BODY: i'll
COHERENT: no

[history: assistant: "Here's your message to Kathia..."]
User: "cancel"
CLASSIFICATION: END_CONVERSATION
CONFIDENCE: 0.98

[history: assistant: "Checking your email..."]
User: "ok thanks"
CLASSIFICATION: END_CONVERSATION
CONFIDENCE: 0.95

[history: assistant: "Try sending that now."]
User: "ok sent it"
CLASSIFICATION: DELEGATE_OPUS
CONFIDENCE: 0.95

[history empty]
User: "thanks"
CLASSIFICATION: SELF_HANDLE
CONFIDENCE: 0.80

User: "call my wife"
CLASSIFICATION: DELEGATE_OPUS
CONFIDENCE: 0.95

User: "fix the auth bug"
CLASSIFICATION: DELEGATE_OPUS
CONFIDENCE: 0.98

User: "why is the playlist empty"
CLASSIFICATION: DELEGATE_OPUS
CONFIDENCE: 0.93"""

# ── Regexes for parsing ──────────────────────────────────────────────────────
_CLASS_PATTERN = "|".join(VALID_CLASSES)
_CLASSIFY_RE = re.compile(rf"CLASSIFICATION:\s*({_CLASS_PATTERN})", re.IGNORECASE)
_CONFIDENCE_RE = re.compile(r"CONFIDENCE:\s*([0-9]*\.?[0-9]+)", re.IGNORECASE)
_RECIPIENT_RE = re.compile(r"RECIPIENT:\s*(.+?)(?:\n|$)", re.IGNORECASE)
_BODY_RE = re.compile(r"BODY:\s*(.+?)(?=\n(?:COHERENT|CLASSIFICATION|CONFIDENCE|QUERY|ACTION|FILTER|RECIPIENT):|\Z)",
                      re.IGNORECASE | re.DOTALL)
_COHERENT_RE = re.compile(r"COHERENT:\s*(yes|no)", re.IGNORECASE)
_QUERY_RE = re.compile(r"QUERY:\s*(.+?)(?:\n|$)", re.IGNORECASE)
_ACTION_RE = re.compile(r"ACTION:\s*(.+?)(?:\n|$)", re.IGNORECASE)
_FILTER_RE = re.compile(r"FILTER:\s*(.+?)(?:\n|$)", re.IGNORECASE)


def _build_fifo_context(session_id: str) -> str:
    """Return oldest→newest FIFO summaries for this session, capped at FIFO_CHAR_CAP."""
    if not session_id:
        return ""
    try:
        from vault_web.recent_turns import get_recent
        summaries = get_recent(session_id, n=FIFO_TURN_COUNT)
    except Exception as e:
        logger.warning("stage1 FIFO fetch failed: %s", e)
        return ""
    if not summaries:
        return ""
    total = sum(len(s) + 1 for s in summaries)
    while summaries and total > FIFO_CHAR_CAP:
        dropped = summaries.pop(0)
        total -= len(dropped) + 1
    return "\n".join(summaries)


def _clean_body(raw: str) -> str:
    """Strip trailing metadata fragments and quotes from an extracted BODY."""
    if not raw:
        return ""
    out = raw.strip().strip('"').strip("'").strip()
    # If the DOTALL regex over-captured, trim at the first metadata header.
    out = re.split(r"\n(?:COHERENT|CLASSIFICATION|CONFIDENCE|QUERY|ACTION|FILTER|RECIPIENT):",
                   out, maxsplit=1)[0]
    return out.strip()


def _parse_stage1_output(raw: str) -> dict:
    """Turn Gemma's raw text into a structured dict."""
    if not raw:
        return {"classification": "DELEGATE_OPUS", "confidence": 0.0}
    m_cls = _CLASSIFY_RE.search(raw)
    if not m_cls:
        return {"classification": "DELEGATE_OPUS", "confidence": 0.0}
    cls = m_cls.group(1).upper()
    m_conf = _CONFIDENCE_RE.search(raw)
    confidence = float(m_conf.group(1)) if m_conf else 0.0
    result: dict = {"classification": cls, "confidence": confidence}

    if cls == "SEND_MESSAGE":
        m_r = _RECIPIENT_RE.search(raw)
        m_b = _BODY_RE.search(raw)
        m_c = _COHERENT_RE.search(raw)
        result["recipient"] = m_r.group(1).strip().strip('"').strip("'") if m_r else ""
        result["body"] = _clean_body(m_b.group(1)) if m_b else ""
        result["coherent"] = (m_c.group(1).lower() == "yes") if m_c else False
    elif cls == "MUSIC_PLAY":
        m_q = _QUERY_RE.search(raw)
        result["query"] = m_q.group(1).strip().strip('"').strip("'") if m_q else ""
    elif cls == "SHOPPING_LIST":
        m_a = _ACTION_RE.search(raw)
        result["action"] = m_a.group(1).strip().strip('"').strip("'") if m_a else ""
    elif cls == "READ_MESSAGES":
        m_f = _FILTER_RE.search(raw)
        filt = m_f.group(1).strip().strip('"').strip("'") if m_f else ""
        result["filter"] = filt if filt and filt.lower() != "all" else ""
    elif cls == "READ_EMAIL":
        m_q = _QUERY_RE.search(raw)
        q = m_q.group(1).strip().strip('"').strip("'") if m_q else ""
        result["query"] = q if q and q.lower() != "unread" else ""
    return result


OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


async def _stage1_via_ollama(full_prompt: str, model: str) -> Optional[str]:
    """Call ollama HTTP API directly. Returns raw text or None on failure."""
    import json as _json
    import urllib.request
    import urllib.error
    url = f"{OLLAMA_URL}/api/generate"
    # MUST match every other local-LLM caller's num_ctx. Divergent num_ctx
    # forces Ollama to evict/reload the runner on each caller swap.
    try:
        from jane_web.jane_v2.models import LOCAL_LLM_NUM_CTX as _NUM_CTX
    except Exception:
        _NUM_CTX = int(os.environ.get("JANE_LOCAL_LLM_NUM_CTX", "8192"))
    payload = _json.dumps({
        "model": model,
        "prompt": full_prompt,
        "stream": False,
        "options": {"num_ctx": _NUM_CTX},
        "keep_alive": -1,
    }).encode()
    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type": "application/json"}, method="POST")
    loop = asyncio.get_event_loop()
    try:
        raw = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=int(STAGE1_TIMEOUT_S)).read()),
            timeout=STAGE1_TIMEOUT_S + 0.5,
        )
        data = _json.loads(raw)
        return data.get("response", "")
    except asyncio.TimeoutError:
        logger.info("stage1 ollama: timeout (%.1fs)", STAGE1_TIMEOUT_S)
        return None
    except Exception as e:
        logger.debug("stage1 ollama: HTTP error: %s", e)
        return None


async def stage1_classify(message: str, session_id: str) -> dict:
    """Run Stage 1 classification.

    Returns a dict with at minimum {classification, confidence}. On any error
    or timeout, returns DELEGATE_OPUS — the caller should then route to the
    brain as a safe fallback.
    """
    if not message or not message.strip():
        return {"classification": "DELEGATE_OPUS", "confidence": 0.0}

    parts = [SYSTEM_PROMPT.strip(), "---"]
    history_block = _build_fifo_context(session_id)
    if history_block:
        parts.append("Recent history (oldest first, summaries):")
        parts.append(history_block)
        parts.append("---")
    parts.append(f"user: {message.strip()}")
    full_prompt = "\n".join(parts)

    try:
        from jane_web.jane_v2.models import STAGE2_MODEL
        model = os.environ.get("JANE_STAGE1_MODEL") or STAGE2_MODEL
    except Exception:
        model = (
            os.environ.get("JANE_STAGE1_MODEL")
            or os.environ.get("JANE_LOCAL_LLM")
            or os.environ.get("JANE_STAGE2_MODEL")
        )
        if not model:
            raise RuntimeError(
                "Cannot resolve Stage 1 model: models.py import failed AND "
                "no JANE_STAGE1_MODEL / JANE_LOCAL_LLM / JANE_STAGE2_MODEL "
                "env var is set"
            )

    # If the model is a gemma/ollama model, always go direct to ollama HTTP —
    # CLI backends like 'claude' or 'gemini' cannot run local ollama models.
    is_ollama_model = not any(x in model for x in ("gemini", "gpt", "claude", "anthropic"))
    if is_ollama_model:
        raw_text = await _stage1_via_ollama(full_prompt, model)
        if raw_text is not None:
            parsed = _parse_stage1_output(raw_text)
            logger.info(
                "stage1 (ollama): %s (conf=%.2f) msg=%r",
                parsed.get("classification"), parsed.get("confidence", 0.0), message[:60],
            )
            return parsed
        # ollama failed — fall through to CLI attempt below

    try:
        from jane.config import PROVIDER_CLI
    except Exception:
        PROVIDER_CLI = "gemini"
    cli = os.environ.get("PROVIDER_CLI", PROVIDER_CLI)
    # Skip CLI if it's the claude binary — it can't run non-Anthropic models.
    if cli == "claude" or not shutil.which(cli):
        logger.debug("stage1: CLI '%s' not usable for model %r", cli, model)
        return {"classification": "DELEGATE_OPUS", "confidence": 0.0}

    if "gemini" in cli:
        cmd = [cli, "-p", full_prompt]
    else:
        cmd = [cli, "-p", full_prompt, "--output-format", "text", "--model", model]

    loop = asyncio.get_event_loop()
    try:
        result = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=int(STAGE1_TIMEOUT_S), env=os.environ.copy(),
            )),
            timeout=STAGE1_TIMEOUT_S + 0.5,
        )
    except asyncio.TimeoutError:
        logger.info("stage1: timeout (%.1fs)", STAGE1_TIMEOUT_S)
        return {"classification": "DELEGATE_OPUS", "confidence": 0.0}
    except Exception as e:
        logger.warning("stage1: subprocess error: %s", e)
        return {"classification": "DELEGATE_OPUS", "confidence": 0.0}

    if result.returncode != 0:
        logger.info("stage1: CLI exit %d, stderr=%r", result.returncode, (result.stderr or "")[:200])
        return {"classification": "DELEGATE_OPUS", "confidence": 0.0}

    parsed = _parse_stage1_output(result.stdout or "")
    logger.info(
        "stage1: %s (conf=%.2f) msg=%r",
        parsed.get("classification"), parsed.get("confidence", 0.0), message[:60],
    )
    return parsed
