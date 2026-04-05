"""Gemma4 e4b prompt router — classifies prompts as SELF_HANDLE or DELEGATE.

Runs gemma4:e4b locally via Ollama with thinking disabled for sub-1s latency.
Includes cached personal info + last 5 conversation turns for context.

Returns (classification, response_text):
  - ("self_handle", "Hey Chieh! ...") — gemma handled it
  - ("delegate", None) — send to Claude
  - ("unknown", None) — gemma couldn't classify, send to Claude
"""

import asyncio
import logging
import os
import re
import time

import aiohttp

logger = logging.getLogger(__name__)

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
ROUTER_MODEL = os.environ.get("GEMMA_ROUTER_MODEL", "gemma4:e4b")
ROUTER_TIMEOUT = float(os.environ.get("GEMMA_ROUTER_TIMEOUT", "10.0"))
MAX_HISTORY_TURNS = 5

# Cached personal info — loaded once, never changes during runtime.
_PERSONAL_INFO = """User info:
- Name: Chieh
- Role: CS professor at Northeastern, ML researcher (kernel methods)
- Style: Direct, technical, no filler. Treat as equal collaborator.
- Preferences: No "Professor", no "Is there anything else?", no emoji unless asked
- Project: Vessence (AI assistant platform with Android app)
- Wife: spouse, REDACTED_PROFESSION at REDACTED_BUSINESS"""

SYSTEM_PROMPT = f"""You are a prompt router for Jane, an AI assistant.
Classify prompts as SELF_HANDLE, MUSIC_PLAY, or DELEGATE_OPUS.

SELF_HANDLE — ONLY these categories:
- Pure greetings: "hey", "hi", "good morning", "how are you"
- Simple math: "what is 7 times 8", "convert 5 miles to km"
- Basic definitions: "what is REST", "what does API stand for"
- Jokes: "tell me a joke"
- Weather questions (use cached data below): ALWAYS include current temp, today's high/low, condition, AND air quality (AQI). For forecast questions, include the relevant days.
- Acknowledgments: "thanks", "ok", "sounds good", "got it", "nice", "cool"
- Simple factual/trivia: "what year did WW2 end", "who wrote hamlet", "what's the capital of France"
- Time/date questions: "what time is it", "what day is today", "what's the date"
- Unit conversions: "how many cups in a gallon", "celsius to fahrenheit"
- Casual follow-ups to previous messages: "haha", "that's funny", "yeah", "true", "makes sense", "right"

MUSIC_PLAY — User wants to hear music/songs. Any phrasing:
- "play the scientist", "put on some coldplay", "throw on a random song"
- "can you play X", "please play X", "hey jane play X"
- "I want to hear X", "listen to X", "play me something", "shuffle my music"
For MUSIC_PLAY, RESPONSE must be ONLY the clean search query (artist/song/album name),
with NO extra words, NO sentences, NO quotes. Use "random" for shuffle requests.
Examples:
  "play the scientist" → RESPONSE: the scientist
  "hey jane can you put on some coldplay please" → RESPONSE: coldplay
  "play me a random song" → RESPONSE: random
  "I want to hear shakira" → RESPONSE: shakira

DELEGATE_OPUS — EVERYTHING ELSE, including:
- Any question about the system, app, features, or project
- Any question you're not 100% sure about
- Anything technical, code-related, or requiring context
- When in doubt, ALWAYS delegate

IMPORTANT: If you are not completely certain the prompt fits a SELF_HANDLE or MUSIC_PLAY category, classify as DELEGATE_OPUS. False delegation is safe. False self-handling gives wrong answers.

{_PERSONAL_INFO}

Format: CLASSIFICATION: [SELF_HANDLE or MUSIC_PLAY or DELEGATE_OPUS]
RESPONSE: [If SELF_HANDLE, provide the actual response. If MUSIC_PLAY, provide ONLY the search query (nothing else). If DELEGATE_OPUS, write a brief acknowledgment that proves you understood the specific ask.

STRICT RULES for DELEGATE_OPUS acks:
- MUST reference at least one concrete noun or concept from the user's message (e.g., "ViewModel", "wake word", "auth system", "the bug with X"). Copy the key term verbatim.
- NEVER use generic phrases like "good question", "digging into that", "let me think", "interesting question". These are banned.
- NEVER mention "looking it up" or "checking" unless the user actually asked to look something up.
- Match tone to content: focused for code/bugs, warm for personal, direct for factual.
- One short sentence. This is spoken aloud.

Good examples (do NOT copy verbatim — paraphrase using the user's actual words):
  User: "can you benchmark the kernel gradient implementation"
  Ack: "On it — profiling the kernel gradient code now."

  User: "the discord bot stopped posting to the server this morning"
  Ack: "Looking into why the discord bot went silent this morning."

  User: "help me draft an email to the conference organizers"
  Ack: "Sure, let me help you put together that email to the organizers."

Bad examples (never do this):
  "Ooh, good question — digging into that."   ← generic, banned
  "Let me think about that one."                ← generic, banned
  "Interesting question — looking into it."     ← generic, banned
]"""

_CLASSIFY_RE = re.compile(r"CLASSIFICATION:\s*(SELF_HANDLE|MUSIC_PLAY|DELEGATE_OPUS)", re.IGNORECASE)
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
    tools_dir = Path(os.environ.get("TOOLS_DIR", os.path.expanduser("~/ambient/tools")))
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
        lines.append(f"Now: {c.get('temperature','?')}, feels {c.get('feels_like','?')}, {c.get('condition','?')}, humidity {c.get('humidity','?')}, wind {c.get('wind','?')}")
        aq = data.get("air_quality", {})
        lines.append(f"Air quality: AQI {aq.get('us_aqi','?')}")
        for day in data.get("forecast", []):
            lines.append(f"{day['date']}: {day['high']}/{day['low']}, {day['condition']}, rain {day['precipitation']}, humidity {day['humidity']}")
        return "\n".join(lines)
    except Exception:
        return ""


# Persistent aiohttp session — reused across calls to avoid TCP overhead
_session: aiohttp.ClientSession | None = None


def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=ROUTER_TIMEOUT)
        )
    return _session


def _build_history(session_history: list[dict]) -> list[dict]:
    """Extract last N turns from session history for router context."""
    messages = []
    recent = session_history[-(MAX_HISTORY_TURNS * 2):]
    for entry in recent:
        role = entry.get("role", "")
        content = entry.get("content", "")
        # Only include user/assistant turns with string content
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        if len(content) > 200:
            content = content[:200] + "..."
        messages.append({"role": role, "content": content})
    return messages


async def classify_prompt(
    message: str,
    session_history: list[dict] | None = None,
) -> tuple[str, str | None]:
    """Classify a prompt using gemma4:e4b.

    Special case: "what can you do with X" returns the tool's MCP summary directly.

    Returns:
        ("self_handle", response_text) — gemma answered it
        ("delegate", None) — send to Claude
        ("unknown", None) — couldn't parse, send to Claude
    """
    # Check for "what can you do with X" / "what can I ask X" meta-queries
    lowered = message.lower()
    capability_keywords = ["what can you do", "what can i do", "what can i ask", "capabilities of", "what does", "help with"]
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
    messages = [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": message},
    ]

    payload = {
        "model": ROUTER_MODEL,
        "messages": messages,
        "stream": False,
        "think": False,
        # Never unload — model stays in VRAM/RAM indefinitely. Ollama default
        # is 5 minutes which is too short for our usage pattern.
        "keep_alive": -1,
        "options": {
            "temperature": 0.1,
            # Classification output is CLASSIFICATION: X\nRESPONSE: one short sentence
            # — never more than ~60 tokens. Capping tight makes cold-starts fast.
            "num_predict": 80,
        },
    }

    try:
        t0 = time.perf_counter()
        session = _get_session()
        req_timeout = aiohttp.ClientTimeout(total=timeout_override)
        async with session.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
            timeout=req_timeout,
        ) as resp:
            if resp.status != 200:
                logger.warning("Gemma router HTTP %d", resp.status)
                return ("unknown", None)
            try:
                data = await resp.json()
            except Exception:
                logger.warning("Gemma router: invalid JSON response")
                return ("unknown", None)

        elapsed = time.perf_counter() - t0
        content = data.get("message", {}).get("content", "")
        if not content:
            logger.warning("Gemma router: empty content")
            return ("unknown", None)
        logger.info("Gemma router: %.2fs, %d chars", elapsed, len(content))

        # Parse classification
        cls_match = _CLASSIFY_RE.search(content)
        if not cls_match:
            logger.info("Gemma router: no classification found in output")
            return ("unknown", None)

        classification = cls_match.group(1).upper()

        if classification == "MUSIC_PLAY":
            # Extract the clean search query from the RESPONSE line
            resp_match = _RESPONSE_RE.search(content)
            query = resp_match.group(1).strip().rstrip('"').strip() if resp_match else None
            return ("music_play", query or None)

        if classification == "DELEGATE_OPUS":
            # Extract the contextual ack from the RESPONSE line
            resp_match = _RESPONSE_RE.search(content)
            delegate_ack = resp_match.group(1).strip().rstrip('"').strip() if resp_match else None
            return ("delegate", delegate_ack or None)

        # SELF_HANDLE — extract only the RESPONSE portion
        resp_match = _RESPONSE_RE.search(content)
        if not resp_match:
            # No RESPONSE: tag — don't leak raw model output, fall back to unknown
            logger.info("Gemma router: SELF_HANDLE but no RESPONSE tag, falling back")
            return ("unknown", None)

        response_text = resp_match.group(1).strip().rstrip('"').strip()
        if not response_text:
            return ("unknown", None)

        return ("self_handle", response_text)

    except asyncio.TimeoutError:
        logger.warning("Gemma router timed out (%.1fs limit)", ROUTER_TIMEOUT)
        return ("unknown", None)
    except Exception as e:
        logger.warning("Gemma router error: %s", e)
        return ("unknown", None)
