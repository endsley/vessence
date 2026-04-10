"""Jane's initial ack layer — classifies prompts as SELF_HANDLE, MUSIC_PLAY, or DELEGATE.

This is the fast front half of Jane. It speaks first (the initial ack), handles
trivial turns itself, routes music commands, and otherwise emits a contextual
ack with an ETA hint before delegating the real work to Jane's mind (the
standing brain). It is NOT a separate agent — it is an aspect of Jane.

The slot is pluggable across four providers — matched to whichever provider
is currently hosting Jane's mind so the pairing stays coherent by default:

  - "ollama"    → gemma4:e4b (local, no API key required; fallback default)
  - "anthropic" → claude-haiku-4-5-20251001 (pairs with Claude-Opus mind)
  - "google"    → gemini-2.5-flash         (pairs with Gemini-Pro mind)
  - "openai"    → gpt-5-nano               (pairs with OpenAI mind)

Provider selection:
  1. JANE_ACK_PROVIDER env var — explicit override (ollama|anthropic|google|openai)
  2. Otherwise auto-derived from JANE_BRAIN (claude→anthropic, gemini→google,
     openai→openai) *if* the matching API key is set.
  3. Otherwise fallback to "ollama".

Model override: JANE_ACK_MODEL — if set, overrides the per-provider default.

See configs/Jane_architecture.md → "Roles vs models" for the architectural
picture and the vocabulary rules (user-facing = "Jane", internal = "initial
ack" / "mind" / "standing brain").

Includes cached personal info + last 5 conversation turns for context.

Returns (classification, response_text):
  - ("self_handle", "Hey! ...") — ack layer handled it, skip the mind
  - ("music_play", "<search query>")  — user wants music; route to player
  - ("delegate", "<contextual ack>")  — send to Jane's mind
  - ("unknown", None)                 — couldn't parse, send to Jane's mind anyway
"""

import asyncio
import logging
import os
import re
import time

import aiohttp

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

# Ollama endpoint (used when provider == "ollama"). rstrip trailing slashes so
# f"{OLLAMA_URL}/api/chat" never produces "...//api/chat".
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")

# Legacy env var kept for backwards compatibility — only used when
# JANE_ACK_MODEL is unset AND provider == "ollama". Prefer JANE_ACK_MODEL.
_LEGACY_OLLAMA_MODEL = os.environ.get("GEMMA_ROUTER_MODEL", "").strip()

# Overall request budget (per provider call). Weather context adds +3s.
ROUTER_TIMEOUT = float(os.environ.get("GEMMA_ROUTER_TIMEOUT", "10.0"))

# History budget for the initial-ack router. Capped by CHARACTER COUNT rather
# than turn count because one long assistant turn can use as many tokens as
# 5 short turns. The budget is conservative: Gemma4:e4b's format compliance
# degrades as total context grows past ~3K chars, and the system prompt is
# already ~1.9K chars, so we cap history at ~600 chars to stay well under
# the reliability threshold.
MAX_HISTORY_CHARS = 600

# Per-provider default model. User can override globally via JANE_ACK_MODEL.
_DEFAULT_ACK_MODELS = {
    "ollama": "gemma4:e4b",
    "anthropic": "claude-haiku-4-5-20251001",
    "google": "gemini-2.5-flash",
    "openai": "gpt-5-nano",
}

# Map JANE_BRAIN value → initial-ack provider (auto-pairing default).
_BRAIN_TO_ACK_PROVIDER = {
    "claude": "anthropic",
    "gemini": "google",
    "openai": "openai",
}

# API key env vars per provider. If the key for a provider isn't set, the
# provider is considered unavailable and we fall back to ollama.
_API_KEY_ENV = {
    "anthropic": ("ANTHROPIC_API_KEY",),
    "google": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "openai": ("OPENAI_API_KEY",),
}

_VALID_PROVIDERS = ("ollama", "anthropic", "google", "openai")


def _provider_has_key(provider: str) -> bool:
    """Return True if at least one API key env var for the provider is set."""
    if provider == "ollama":
        return True  # no key needed
    for env_name in _API_KEY_ENV.get(provider, ()):
        if os.environ.get(env_name):
            return True
    return False


def _resolve_provider() -> str:
    """Pick the initial-ack provider at call time.

    Priority:
      1. JANE_ACK_PROVIDER env var, if valid and (for cloud providers) key is set.
      2. Auto-pair from JANE_BRAIN, if matching API key is set.
      3. Fallback to "ollama".
    """
    explicit = os.environ.get("JANE_ACK_PROVIDER", "").lower().strip()
    if explicit in _VALID_PROVIDERS:
        if _provider_has_key(explicit):
            return explicit
        logger.warning(
            "Initial ack: JANE_ACK_PROVIDER=%s requested but no API key in env; "
            "falling back to ollama.",
            explicit,
        )
        return "ollama"

    brain = os.environ.get("JANE_BRAIN", "").lower().strip()
    paired = _BRAIN_TO_ACK_PROVIDER.get(brain)
    if paired and _provider_has_key(paired):
        return paired

    return "ollama"


def _resolve_model(provider: str) -> str:
    """Pick the model for the given provider, honoring JANE_ACK_MODEL override."""
    override = os.environ.get("JANE_ACK_MODEL", "").strip()
    if override:
        return override
    if provider == "ollama" and _LEGACY_OLLAMA_MODEL:
        return _LEGACY_OLLAMA_MODEL
    return _DEFAULT_ACK_MODELS.get(provider, "gemma4:e4b")


# Personal info loaded from ChromaDB at runtime — see memory/v1/memory_retrieval.py
_PERSONAL_INFO = ""  # Populated by _load_personal_info() on first call

SYSTEM_PROMPT = f"""Classify each message. Output exactly two lines:
CLASSIFICATION: SELF_HANDLE or MUSIC_PLAY or SHOPPING_LIST or READ_MESSAGES or READ_EMAIL or SYNC_MESSAGES or DELEGATE_OPUS
RESPONSE: <response>

{_PERSONAL_INFO}

SELF_HANDLE — greetings, simple math, jokes, weather (use cached data), trivia, time/date.
STT garbage → "was that meant for me?"
IMPORTANT: If prior assistant message asked a question or proposed an action, short replies (yes/no/sure/ok/go ahead/do it/yes please/cancel) are CONFIRMATIONS → DELEGATE, not self-handle.
NEVER classify as SELF_HANDLE if the message mentions: email, text, message, call, play, music, shopping, list, sync. Those ALWAYS go to their specific category or DELEGATE.

MUSIC_PLAY — ONLY when the user's FIRST WORD is: play/put/throw/listen/shuffle.
RESPONSE = just the artist or song name (nothing else).
If the message is a QUESTION about music (why/how/what/check/is/are/can/do/where) → DELEGATE, NOT music_play.
If the message contains words like: why, check, problem, empty, broken, think, wrong, fix → DELEGATE, NOT music_play.

SHOPPING_LIST — add/remove/show/check items on shopping/grocery lists. RESPONSE = action + item.

READ_MESSAGES — check/read text messages. RESPONSE = read_inbox [+ sender].

READ_EMAIL — check/read/search email or inbox. RESPONSE = read_email [+ query].
Examples: "check my email", "read my inbox", "any new emails", "read email from Bob".
NOT for sending email — that's DELEGATE_OPUS.

SYNC_MESSAGES — sync/resync/refresh text messages or SMS. RESPONSE = sync.
Examples: "sync my messages", "resync my texts", "refresh my messages", "sync sms".
NOT for reading messages — that's READ_MESSAGES. Only for explicit sync/resync requests.

DELEGATE_OPUS — everything else. SMS, calls, files, code, complex questions, complaints, follow-ups.
Never say "I can't do that" — DELEGATE. Jane CAN do it.
RESPONSE = short ack referencing their topic + time hint.

Examples:
User: "hey" → SELF_HANDLE / Hey!
User: "play shakira" → MUSIC_PLAY / shakira
User: "play sky full of stars" → MUSIC_PLAY / sky full of stars
User: "why is the playlist empty" → DELEGATE_OPUS / Checking the playlist — one sec.
User: "I don't think this is working" → DELEGATE_OPUS / Let me look into that.
User: "can you check why there were no songs" → DELEGATE_OPUS / Investigating the music issue.
User: "add milk to the list" → SHOPPING_LIST / add milk
User: "read my texts" → READ_MESSAGES / read_inbox
User: "sync my messages" → SYNC_MESSAGES / sync
User: "resync my texts" → SYNC_MESSAGES / sync
User: "are you able to read my email" → READ_EMAIL / read_email
User: "can you check my email" → READ_EMAIL / read_email
User: "check my email" → READ_EMAIL / read_email
User: "any new emails" → READ_EMAIL / read_email
User: "read the top 3 emails" → READ_EMAIL / read_email 3
User: "email from Bob" → READ_EMAIL / read_email from:bob
User: "fix the auth bug" → DELEGATE_OPUS / Looking into the auth bug — one sec.
User: "call my wife" → DELEGATE_OPUS / Calling now."""

_CLASSIFY_RE = re.compile(r"(?:CLASSIFICATION:\s*)?(SELF_HANDLE|MUSIC_PLAY|SHOPPING_LIST|READ_MESSAGES|READ_EMAIL|SYNC_MESSAGES|DELEGATE_OPUS)", re.IGNORECASE)
_RESPONSE_RE = re.compile(r"RESPONSE:\s*(.*)", re.DOTALL)

# Weather keywords — if detected, inject cached weather data into gemma's context
_WEATHER_KEYWORDS = {"weather", "temperature", "rain", "snow", "forecast", "humid", "air quality",
                     "cold", "warm", "hot", "umbrella", "jacket", "sunny", "cloudy", "wind"}

# MCP loader — discovers installed tools and their capabilities
_MCP_CACHE: dict[str, dict] | None = None


def _load_all_mcps() -> dict[str, dict]:
    """Load all mcp.json files from installed tools/essences."""
    global _MCP_CACHE
    if _MCP_CACHE is not None:
        return _MCP_CACHE
    import json as _json
    from pathlib import Path
    tools_dir = Path(os.environ.get("TOOLS_DIR", os.path.expanduser("~/ambient/skills")))
    essences_dir = Path(os.environ.get("ESSENCES_DIR", os.path.expanduser("~/ambient/essences")))
    mcps = {}
    for base in (tools_dir, essences_dir):
        if not base.exists():
            continue
        for mcp_file in base.glob("*/mcp.json"):
            try:
                data = _json.loads(mcp_file.read_text())
                name = data.get("name", mcp_file.parent.name)
                mcps[name.lower()] = data
            except Exception:
                pass
    _MCP_CACHE = mcps
    logger.info("Loaded %d MCPs: %s", len(mcps), list(mcps.keys()))
    return mcps


def _get_tool_capabilities_summary(tool_name: str) -> str | None:
    """Get a human-readable summary of what a tool can do from its MCP."""
    mcps = _load_all_mcps()
    # Fuzzy match tool name
    matched = None
    for name, mcp in mcps.items():
        if tool_name.lower() in name or name in tool_name.lower():
            matched = mcp
            break
    if not matched:
        return None
    lines = [f"**{matched['name']}**: {matched.get('description', '')}"]
    lines.append("\nYou can ask me to:")
    for cmd in matched.get("commands", []):
        examples = cmd.get("examples", [])
        example_str = f' (e.g., "{examples[0]["input"]}")' if examples else ""
        lines.append(f"- {cmd['description']}{example_str}")
    return "\n".join(lines)

_WEATHER_CACHE = os.path.join(
    os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data")),
    "cache", "weather.json",
)


def _load_weather_context(message: str) -> str:
    """If message mentions weather, load cached data for gemma's context."""
    lowered = message.lower()
    if not any(kw in lowered for kw in _WEATHER_KEYWORDS):
        return ""
    try:
        import json as _json
        from pathlib import Path
        cache = Path(_WEATHER_CACHE)
        if not cache.exists():
            return ""
        data = _json.loads(cache.read_text())
        # Check staleness (>36 hours = stale)
        from datetime import datetime
        fetched = datetime.strptime(data["fetched"], "%Y-%m-%d %H:%M")
        age_hours = (datetime.now() - fetched).total_seconds() / 3600
        if age_hours > 36:
            return ""  # stale — let Claude handle it
        # Compact format to minimize tokens
        lines = [f"\n\nWeather for {data['location']} (fetched {data['fetched']}):"]
        c = data.get("current", {})
        aq = data.get("air_quality", {})
        forecast = data.get("forecast", [])
        today = forecast[0] if forecast else {}
        lines.append(f"Now: {c.get('temperature','?')}, feels {c.get('feels_like','?')}, {c.get('condition','?')}, humidity {c.get('humidity','?')}, wind {c.get('wind','?')}")
        lines.append(f"Today high: {today.get('high','?')}, low: {today.get('low','?')}")
        lines.append(f"Air quality: AQI {aq.get('us_aqi','?')}")
        for day in forecast[1:]:
            lines.append(f"{day['date']}: {day['high']}/{day['low']}, {day['condition']}, rain {day['precipitation']}")
        lines.append(
            "\nFor RESPONSE line use EXACTLY: "
            "\"A high of [high], a low of [low], feels like [feels_like], [condition], "
            "with an air quality of [AQI].\" "
            "No humidity, wind, or UV."
        )
        return "\n".join(lines)
    except Exception:
        return ""


# Persistent aiohttp session — reused across calls to avoid TCP overhead
_session: aiohttp.ClientSession | None = None


def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        # No default timeout — each request passes its own to honor per-call budgets.
        _session = aiohttp.ClientSession()
    return _session


def _build_history(session_history: list[dict]) -> list[dict]:
    """Extract recent turns from session history for router context.

    Budget is capped by total CHARACTER COUNT (MAX_HISTORY_CHARS) instead of
    turn count, because one long assistant turn can eat the whole budget.
    Walks backwards from the most recent turn, adding entries until the
    character budget is exhausted. Each individual entry is also capped at
    200 chars to prevent a single monster turn from consuming everything.

    Returns list of {role, content} dicts in the generic OpenAI-style shape.
    """
    messages: list[dict] = []
    chars_used = 0
    # Walk backwards through history (most recent first).
    for entry in reversed(session_history):
        role = entry.get("role", "")
        content = entry.get("content", "")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        # Cap individual entry length.
        if len(content) > 200:
            content = content[:200] + "..."
        # Check budget.
        entry_cost = len(content)
        if chars_used + entry_cost > MAX_HISTORY_CHARS:
            break
        chars_used += entry_cost
        messages.append({"role": role, "content": content})
    # Reverse so the list is chronological (oldest first).
    messages.reverse()
    return messages


def _normalize_history_for_strict_providers(history: list[dict]) -> list[dict]:
    """Make history safe for Anthropic/Google which require:
      - first message role == 'user'
      - strictly alternating user/assistant

    Ollama and OpenAI are lenient about both; they get history as-is.
    This function drops leading non-user entries and collapses consecutive
    same-role entries (keeping the most recent of each run). The current
    user turn is appended *after* this normalization.
    """
    if not history:
        return []
    out: list[dict] = []
    # Drop leading assistant/model entries — conversation must start with user.
    idx = 0
    while idx < len(history) and history[idx].get("role") != "user":
        idx += 1
    # Collapse consecutive same-role entries: keep only the latest of each run.
    for entry in history[idx:]:
        if out and out[-1].get("role") == entry.get("role"):
            out[-1] = entry  # overwrite with newer same-role turn
        else:
            out.append(entry)
    return out


# ── Provider clients ─────────────────────────────────────────────────────────
#
# Each client takes the same inputs and returns the raw assistant text (a
# string containing "CLASSIFICATION: ...\nRESPONSE: ..."). Parsing happens
# once in classify_prompt(). Clients raise on transport errors; they return
# empty string if the provider responded with an empty body.


async def _call_ollama(
    system: str,
    history: list[dict],
    message: str,
    model: str,
    timeout_s: float,
) -> str:
    """Call local Ollama /api/chat."""
    messages = [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": message},
    ]
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        # Never unload — model stays in VRAM/RAM indefinitely. Ollama default
        # is 5 minutes which is too short for our usage pattern.
        "keep_alive": -1,
        "options": {
            "temperature": 0.1,
            # Gemma4 supports 128K context. We set 32K here to give headroom
            # for future prompt expansion without wasting VRAM on the full 128K.
            "num_ctx": 32768,
            # Classification output is CLASSIFICATION: X\nRESPONSE: one short sentence
            # — never more than ~60 tokens. Capping tight makes cold-starts fast.
            "num_predict": 80,
        },
    }
    session = _get_session()
    async with session.post(
        f"{OLLAMA_URL}/api/chat",
        json=payload,
        timeout=aiohttp.ClientTimeout(total=timeout_s),
    ) as resp:
        if resp.status != 200:
            logger.warning("Initial ack (ollama) HTTP %d", resp.status)
            return ""
        try:
            data = await resp.json()
        except Exception:
            logger.warning("Initial ack (ollama): invalid JSON response")
            return ""
    return data.get("message", {}).get("content", "") or ""


async def _call_anthropic(
    system: str,
    history: list[dict],
    message: str,
    model: str,
    timeout_s: float,
) -> str:
    """Call Anthropic Messages API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("Initial ack (anthropic): ANTHROPIC_API_KEY not set")
        return ""
    # Anthropic expects history WITHOUT the system in the messages list; system
    # is a separate top-level field. Roles must alternate user/assistant and
    # the first message must be 'user'. Normalize before appending the current
    # user turn.
    safe_hist = _normalize_history_for_strict_providers(history)
    # If after normalization the last entry is also 'user', merge by dropping
    # the old one — the new message supersedes the stale pending user turn.
    if safe_hist and safe_hist[-1].get("role") == "user":
        safe_hist = safe_hist[:-1]
    conv = [*safe_hist, {"role": "user", "content": message}]
    payload = {
        "model": model,
        "system": system,
        "messages": conv,
        "max_tokens": 150,
        "temperature": 0.1,
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    session = _get_session()
    async with session.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=payload,
        timeout=aiohttp.ClientTimeout(total=timeout_s),
    ) as resp:
        if resp.status != 200:
            body = await resp.text()
            logger.warning(
                "Initial ack (anthropic) HTTP %d: %s", resp.status, body[:300]
            )
            return ""
        try:
            data = await resp.json()
        except Exception:
            logger.warning("Initial ack (anthropic): invalid JSON response")
            return ""
    # Response shape: {"content": [{"type": "text", "text": "..."}, ...], ...}
    # Harden against multiple blocks (e.g., thinking + text) and non-text items
    # by concatenating every block whose type is "text".
    content = data.get("content") or []
    if isinstance(content, list):
        parts = []
        for blk in content:
            if isinstance(blk, dict) and blk.get("type") == "text":
                text = blk.get("text")
                if isinstance(text, str):
                    parts.append(text)
        if parts:
            return "".join(parts)
    return ""


async def _call_google(
    system: str,
    history: list[dict],
    message: str,
    model: str,
    timeout_s: float,
) -> str:
    """Call Google Generative Language (Gemini) generateContent API."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
    if not api_key:
        logger.warning("Initial ack (google): GEMINI_API_KEY/GOOGLE_API_KEY not set")
        return ""
    # Google uses 'user' / 'model' instead of 'user' / 'assistant'. Same
    # alternation + first-must-be-user rules as Anthropic — normalize first.
    safe_hist = _normalize_history_for_strict_providers(history)
    if safe_hist and safe_hist[-1].get("role") == "user":
        safe_hist = safe_hist[:-1]
    contents = []
    for m in safe_hist:
        role = "user" if m.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})
    contents.append({"role": "user", "parts": [{"text": message}]})
    # Gemini 2.5 Flash has a "thinking" mode that consumes output tokens as
    # internal reasoning before any visible text is emitted. With a tight
    # maxOutputTokens, thinking can eat the entire budget and return an empty
    # text part. Set thinkingBudget=0 to turn thinking off for this fast-path
    # classification (we don't need the model to reason deeply for a 2-line
    # CLASSIFICATION/RESPONSE output). Older flash models ignore the field.
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 300,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    session = _get_session()
    async with session.post(
        url,
        headers=headers,
        json=payload,
        timeout=aiohttp.ClientTimeout(total=timeout_s),
    ) as resp:
        if resp.status != 200:
            body = await resp.text()
            logger.warning(
                "Initial ack (google) HTTP %d: %s", resp.status, body[:300]
            )
            return ""
        try:
            data = await resp.json()
        except Exception:
            logger.warning("Initial ack (google): invalid JSON response")
            return ""
    # Response shape: {"candidates": [{"content": {"parts": [{"text": "..."}, ...]}}]}
    # Concatenate every part that has text so we don't silently drop multi-part
    # responses.
    candidates = data.get("candidates") or []
    if not candidates:
        return ""
    parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
    if isinstance(parts, list):
        texts = [p.get("text", "") for p in parts if isinstance(p, dict) and isinstance(p.get("text"), str)]
        if texts:
            return "".join(texts)
    return ""


async def _call_openai(
    system: str,
    history: list[dict],
    message: str,
    model: str,
    timeout_s: float,
) -> str:
    """Call OpenAI Chat Completions API."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("Initial ack (openai): OPENAI_API_KEY not set")
        return ""
    messages = [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": message},
    ]
    # Newer OpenAI models (gpt-5-*, o1-*, o3-*) reject `max_tokens` and require
    # `max_completion_tokens`. Older ones (gpt-4o, gpt-4, gpt-3.5) only accept
    # `max_tokens`. Heuristic: anything that starts with "gpt-5", "o1", "o3",
    # or "gpt-6" uses the new parameter name.
    new_param_models = ("gpt-5", "o1", "o3", "gpt-6")
    uses_new_param = any(model.startswith(p) for p in new_param_models)
    payload: dict = {
        "model": model,
        "messages": messages,
    }
    # Reasoning models also reject custom temperature; only send it for classic chat models.
    if not uses_new_param:
        payload["temperature"] = 0.1
        payload["max_tokens"] = 300
    else:
        # Reasoning models silently eat output tokens as "reasoning tokens" —
        # need a larger budget so the final text still fits.
        payload["max_completion_tokens"] = 512
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    session = _get_session()
    async with session.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=aiohttp.ClientTimeout(total=timeout_s),
    ) as resp:
        if resp.status != 200:
            body = await resp.text()
            logger.warning(
                "Initial ack (openai) HTTP %d: %s", resp.status, body[:300]
            )
            return ""
        try:
            data = await resp.json()
        except Exception:
            logger.warning("Initial ack (openai): invalid JSON response")
            return ""
    # Response shape: {"choices": [{"message": {"content": "..."}}], ...}
    # content can be either a plain string or (for some newer models) a list
    # of content parts with {"type": "text", "text": "..."} blocks.
    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = (choices[0] or {}).get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for blk in content:
            if isinstance(blk, dict):
                text = blk.get("text")
                if isinstance(text, str):
                    parts.append(text)
        if parts:
            return "".join(parts)
    return ""


_PROVIDER_DISPATCH = {
    "ollama": _call_ollama,
    "anthropic": _call_anthropic,
    "google": _call_google,
    "openai": _call_openai,
}


# ── Legacy public constants ──────────────────────────────────────────────────
#
# ROUTER_MODEL is the model name that was active at module-import time. It is
# kept for backward compatibility with `from jane_web.gemma_router import
# ROUTER_MODEL` (used by jane_web/jane_proxy.py to label which model generated
# a given ack in the UI). If the env changes, restart jane-web to refresh.
# For dynamic per-call lookup, use `get_active_model()` instead.
ROUTER_MODEL = _resolve_model(_resolve_provider())


def get_active_model() -> str:
    """Return the currently-active (provider, model) resolved from env, live.

    Useful for UI emission when the process is long-lived and env may have
    been updated externally; otherwise prefer the ROUTER_MODEL constant.
    """
    return _resolve_model(_resolve_provider())


# ── Public entry point ───────────────────────────────────────────────────────


async def classify_prompt(
    message: str,
    session_history: list[dict] | None = None,
) -> tuple[str, str | None]:
    """Classify a prompt via Jane's initial-ack layer.

    Dispatches to whichever provider is currently active (see _resolve_provider).

    Special case: "what can you do with X" returns the tool's MCP summary directly
    without calling any LLM.

    Returns:
        ("self_handle", response_text) — ack layer answered it
        ("music_play", query)          — user wants music; route to player
        ("delegate", ack_text)         — send to Jane's mind
        ("unknown", None)              — couldn't parse, send to Jane's mind anyway
    """
    # Check for "what can you do with X" / "what can I ask X" meta-queries
    lowered = message.lower()
    capability_keywords = [
        "what can you do", "what can i do", "what can i ask",
        "capabilities of", "what does", "help with",
    ]
    if any(kw in lowered for kw in capability_keywords):
        mcps = _load_all_mcps()
        for tool_name in mcps:
            if tool_name in lowered or tool_name.replace(" ", "") in lowered.replace(" ", ""):
                summary = _get_tool_capabilities_summary(tool_name)
                if summary:
                    return ("self_handle", summary)

    history = _build_history(session_history or [])
    # Inject weather data if the message mentions weather (compact format)
    weather_ctx = _load_weather_context(message)
    system = SYSTEM_PROMPT + weather_ctx if weather_ctx else SYSTEM_PROMPT
    # Weather context makes the prompt larger — allow more time
    timeout_override = ROUTER_TIMEOUT + 3.0 if weather_ctx else ROUTER_TIMEOUT

    provider = _resolve_provider()
    model = _resolve_model(provider)
    client = _PROVIDER_DISPATCH.get(provider, _call_ollama)

    try:
        t0 = time.perf_counter()
        content = await client(system, history, message, model, timeout_override)
        elapsed = time.perf_counter() - t0

        if not content:
            logger.warning("Initial ack (%s/%s): empty response", provider, model)
            return ("unknown", None)

        logger.info(
            "Initial ack (%s/%s): %.2fs, %d chars",
            provider, model, elapsed, len(content),
        )

        # Parse classification
        cls_match = _CLASSIFY_RE.search(content)
        if not cls_match:
            # Gemma sometimes skips the format entirely and just answers.
            # If weather keywords are present and we got a non-empty response,
            # treat it as self_handle (Gemma answered the weather question
            # directly using the injected data).
            lowered_msg = message.lower()
            if weather_ctx and content.strip():
                logger.info(
                    "Initial ack (%s/%s): no classification but weather context present — treating as self_handle. Raw: %r",
                    provider, model, content[:300],
                )
                return ("self_handle", content.strip())

            logger.info(
                "Initial ack (%s/%s): no classification in output. Raw: %r",
                provider, model, content[:300],
            )
            return ("unknown", None)

        classification = cls_match.group(1).upper()

        if classification == "MUSIC_PLAY":
            # Hard guard: only accept MUSIC_PLAY if the user's message contains
            # a play-like verb. Gemma4 often misclassifies follow-up questions
            # as music requests, so we also reject messages with question words.
            _msg_lower = message.strip().lower()
            _play_prefixes = ("play ", "put on ", "throw on ", "listen to ", "shuffle ")
            # Also accept polite phrasings like "can you play", "please play", etc.
            _polite_play_re = re.compile(
                r"^(?:can you|could you|would you|please|hey jane|jane)?\s*"
                r"(?:please\s+)?"
                r"(?:play|put on|throw on|listen to|shuffle)\s",
                re.IGNORECASE,
            )
            _question_words = ("why ", "how ", "what ", "check ", "is ", "are ", "do ", "where ", "fix ")
            _has_play = any(_msg_lower.startswith(p) for p in _play_prefixes) or bool(_polite_play_re.match(_msg_lower))
            _is_question = any(_msg_lower.startswith(q) for q in _question_words)
            if not _has_play or _is_question:
                logger.info(
                    "Initial ack (%s/%s): MUSIC_PLAY overridden → DELEGATE (message doesn't start with play verb: %r)",
                    provider, model, message[:80],
                )
                resp_match = _RESPONSE_RE.search(content)
                ack = resp_match.group(1).strip() if resp_match else "One sec."
                return ("delegate", ack)
            resp_match = _RESPONSE_RE.search(content)
            query = resp_match.group(1).strip().rstrip('"').strip() if resp_match else None
            return ("music_play", query or None)

        if classification == "SHOPPING_LIST":
            resp_match = _RESPONSE_RE.search(content)
            action = resp_match.group(1).strip().rstrip('"').strip() if resp_match else None
            return ("shopping_list", action or None)

        if classification == "READ_MESSAGES":
            resp_match = _RESPONSE_RE.search(content)
            action = resp_match.group(1).strip().rstrip('"').strip() if resp_match else None
            return ("read_messages", action or None)

        if classification == "SYNC_MESSAGES":
            resp_match = _RESPONSE_RE.search(content)
            action = resp_match.group(1).strip().rstrip('"').strip() if resp_match else None
            return ("sync_messages", action or None)

        if classification == "DELEGATE_OPUS":
            resp_match = _RESPONSE_RE.search(content)
            delegate_ack = resp_match.group(1).strip().rstrip('"').strip() if resp_match else None
            return ("delegate", delegate_ack or None)

        # SELF_HANDLE — extract the RESPONSE portion, or use raw content as fallback
        resp_match = _RESPONSE_RE.search(content)
        if resp_match:
            response_text = resp_match.group(1).strip().rstrip('"').strip()
        else:
            # Gemma sometimes outputs "SELF_HANDLE\n<answer>" without RESPONSE: tag
            # Strip the classification line and use the rest
            response_text = _CLASSIFY_RE.sub("", content).strip().rstrip('"').strip()
            if response_text:
                logger.info(
                    "Initial ack (%s/%s): SELF_HANDLE without RESPONSE tag, using raw content",
                    provider, model,
                )

        if not response_text:
            return ("unknown", None)

        return ("self_handle", response_text)

    except asyncio.TimeoutError:
        logger.warning(
            "Initial ack (%s/%s) timed out (%.1fs limit)",
            provider, model, timeout_override,
        )
        return ("unknown", None)
    except Exception as e:
        logger.warning("Initial ack (%s/%s) error: %s", provider, model, e)
        return ("unknown", None)
