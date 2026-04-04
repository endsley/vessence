import os
import sys
import json
import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from agent_skills.search_memory import get_memory_summary
from jane.config import VESSENCE_DATA_HOME, VESSENCE_HOME
from jane.research_router import run_research_offload, should_offload_research


MAX_DOC_CHARS = 4000

# ── In-memory cache for static context parts ─────────────────────────────────
_context_cache: dict[str, tuple[float, object]] = {}
_CACHE_TTL = 300  # 5 minutes — static parts rarely change
_CACHE_MAX_ENTRIES = 20  # safety cap; only a handful of keys are expected

def _cached(key: str, loader, ttl: float = _CACHE_TTL):
    """Cache a value in memory with TTL. Avoids disk reads on every request."""
    now = time.time()
    if key in _context_cache:
        ts, val = _context_cache[key]
        if now - ts < ttl:
            return val
    val = loader()
    _context_cache[key] = (now, val)
    # Evict expired entries if cache grows unexpectedly
    if len(_context_cache) > _CACHE_MAX_ENTRIES:
        expired = [k for k, (ts, _) in _context_cache.items() if now - ts >= ttl]
        for k in expired:
            _context_cache.pop(k, None)
    return val
MAX_MEMORY_CHARS = 6000
BASE_SYSTEM_PROMPT = (
    "You are Jane, the user's long-lived technical partner. Speak as Jane."
)

CODE_MAP_PROTOCOL = (
    "## Code Map Protocol\n"
    "A [Code Map] may be injected into your context for code-related prompts. "
    "It is a file-level index of the Vessence codebase: every function, class, "
    "and constant with its file path and line number.\n\n"
    "When you receive a [Code Map], follow this workflow:\n"
    "1. **Locate** — Search the Code Map for the relevant file and function before reading any code.\n"
    "2. **Read precisely** — Use the line numbers from the map to read only the relevant section, not the whole file.\n"
    "3. **Verify** — Confirm the code at that line matches what the map says (the map regenerates nightly; code may have shifted).\n"
    "4. **Act** — Edit, explain, or debug based on what you found.\n\n"
    "Do NOT guess file paths or grep blindly when the Code Map is available. "
    "The map is your first lookup tool for navigating this codebase."
)
logger = logging.getLogger(__name__)

TASK_KEYWORDS = (
    "task", "project", "working on", "roadmap", "transition", "migration",
    "bug", "fix", "implement", "patch", "code", "repo", "architecture",
    "deploy", "systemd", "cron", "backup", "chromadb", "optimiz", "todo",
)
AI_CODING_KEYWORDS = (
    "ml", "machine learning", "llm", "prompt engineering", "token usage", "coding",
    "code", "python", "javascript", "typescript", "bug", "debug", "api endpoint",
    "system prompt", "architecture", "repo", "database", "chromadb",
)
MUSIC_KEYWORDS = (
    "piano", "music", "song", "melody", "harmony", "chord", "practice", "compose",
)
PERSONAL_FACTS_FILE = "user_profile_facts.json"
SIMPLE_FACTUAL_PREFIXES = (
    "who", "what", "when", "where", "which", "favorite", "my favorite", "do you know",
)


@dataclass
class JaneRequestContext:
    system_prompt: str
    transcript: str
    retrieved_memory_summary: str = ""


@dataclass(frozen=True)
class PromptProfile:
    name: str
    include_user_background: bool = False
    include_task_state: bool = False
    include_conversation_summary: bool = False
    include_memory_summary: bool = True
    include_research: bool = False
    include_file_context: bool = False
    include_code_map: bool = False


def _read_text(path: Path, max_chars: int = MAX_DOC_CHARS) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars].strip()
    except Exception:
        return ""


def _read_json_summary(path: Path, max_chars: int = 600) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return ""
    return json.dumps(data, ensure_ascii=True)[:max_chars]


ANAPHORIC_TOKENS = {
    "it", "that", "this", "them", "those", "these", "the button",
    "the file", "the page", "the link", "the thing", "the one",
}


def _is_short_anaphoric(message: str) -> bool:
    """Return True when the message is short and relies on conversational context
    (pronouns/demonstratives) rather than standing on its own semantically."""
    words = (message or "").strip().split()
    if len(words) > 8:
        return False
    lowered = " ".join(words).lower()
    return any(token in lowered for token in ANAPHORIC_TOKENS)


def _message_lower(message: str) -> str:
    return (message or "").strip().lower()


def _is_task_related(message: str) -> bool:
    lowered = _message_lower(message)
    return any(keyword in lowered for keyword in TASK_KEYWORDS)


def _should_include_conversation_summary(message: str) -> bool:
    lowered = _message_lower(message)
    if not lowered:
        return False
    if _is_task_related(message):
        return True
    if any(keyword in lowered for keyword in AI_CODING_KEYWORDS):
        return True
    if lowered.startswith(SIMPLE_FACTUAL_PREFIXES):
        return False
    if len(lowered) <= 40 and "?" in lowered:
        return False
    return True


def _classify_prompt_profile(message: str, file_context: str | None = None, intent_level: str | None = None) -> PromptProfile:
    # Greeting: minimal context — just personality + user name, no memory or task state
    if intent_level == "greeting":
        return PromptProfile(
            name="greeting",
            include_user_background=False,
            include_task_state=False,
            include_conversation_summary=False,
            include_memory_summary=False,
            include_research=False,
            include_file_context=False,
        )
    # Simple: include user background but skip memory retrieval and task state
    if intent_level == "simple":
        return PromptProfile(
            name="simple_query",
            include_user_background=True,
            include_task_state=False,
            include_conversation_summary=False,
            include_memory_summary=False,
            include_research=False,
            include_file_context=bool(file_context),
        )
    lowered = _message_lower(message)
    if file_context or any(marker in lowered for marker in ("file", "folder", "document", "pdf", "vault", "path")):
        return PromptProfile(
            name="file_lookup",
            include_user_background=False,
            include_task_state=False,
            include_conversation_summary=False,
            include_memory_summary=True,
            include_research=False,
            include_file_context=True,
            include_code_map=True,
        )
    if _is_task_related(message) or any(keyword in lowered for keyword in AI_CODING_KEYWORDS):
        return PromptProfile(
            name="project_work",
            include_user_background=True,
            include_task_state=True,
            include_conversation_summary=True,
            include_memory_summary=True,
            include_research=should_offload_research(message),
            include_file_context=bool(file_context),
            include_code_map=True,
        )
    if lowered.startswith(SIMPLE_FACTUAL_PREFIXES) or (len(lowered) <= 40 and "?" in lowered):
        return PromptProfile(
            name="factual_personal",
            include_user_background=True,
            include_task_state=False,
            include_conversation_summary=False,
            include_memory_summary=True,
            include_research=False,
            include_file_context=False,
        )
    return PromptProfile(
        name="casual_followup",
        include_user_background=True,
        include_task_state=False,
        include_conversation_summary=False,
        include_memory_summary=True,
        include_research=False,
        include_file_context=bool(file_context),
        include_code_map=False,
    )


def _normalize_memory_summary(memory_summary: str, fallback_summary: str | None = None) -> str:
    summary = (memory_summary or "").strip()
    if summary and summary != "No relevant context found.":
        return summary[:MAX_MEMORY_CHARS]
    fallback = (fallback_summary or "").strip()
    if fallback and fallback != "No relevant context found.":
        return fallback[:MAX_MEMORY_CHARS]
    return ""


def _safe_get_memory_summary(
    message: str,
    conversation_summary: str,
    session_id: str,
    fallback_summary: str | None = None,
) -> str:
    # Fast path: use the memory daemon (port 8083) if available
    try:
        import urllib.parse, urllib.request, json as _json
        essence_chromadb = _get_active_essence_chromadb_path()
        params = f"q={urllib.parse.quote(message)}"
        if essence_chromadb:
            params += f"&essence_path={urllib.parse.quote(essence_chromadb)}"
        url = f"http://127.0.0.1:8083/query?{params}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read())
            result = data.get("result", "")
            if result and result != "No relevant context found.":
                logger.info("Memory daemon fast path: %d chars", len(result))
                return _normalize_memory_summary(result, fallback_summary)
            else:
                logger.info("Memory daemon returned empty — using fallback summary")
                return _normalize_memory_summary("", fallback_summary)
    except Exception as exc:
        logger.warning("Memory daemon unavailable (%s) — falling back to slow path", exc)

    # Slow fallback: direct ChromaDB query (if daemon is down)
    try:
        essence_chromadb = _get_active_essence_chromadb_path()
        memory_summary = get_memory_summary(
            message,
            conversation_summary=conversation_summary,
            session_id=session_id,
            essence_chromadb_path=essence_chromadb,
        )
    except Exception:
        logger.exception("Jane memory retrieval failed")
        return _normalize_memory_summary("", fallback_summary)
    return _normalize_memory_summary(memory_summary, fallback_summary)


def _load_personal_facts(data_root: Path) -> dict:
    path = data_root / PERSONAL_FACTS_FILE
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _format_fact_snippet(fact: dict) -> str:
    label = str(fact.get("label", "")).strip()
    value = str(fact.get("value", "")).strip()
    if not label or not value:
        return ""
    return f"{label}: {value}"


def _select_user_background(message: str, personal_facts: dict) -> str:
    lowered = _message_lower(message)
    snippets: list[str] = []

    for fact in personal_facts.get("always", []):
        if isinstance(fact, dict):
            snippet = _format_fact_snippet(fact)
            if snippet:
                snippets.append(snippet)

    topical_groups = []
    if any(keyword in lowered for keyword in AI_CODING_KEYWORDS):
        topical_groups.append("ai_coding")
    if any(keyword in lowered for keyword in MUSIC_KEYWORDS):
        topical_groups.append("music")
    if "teach" in lowered or "student" in lowered or "class" in lowered or "lecture" in lowered:
        topical_groups.append("teaching")

    topic_map = personal_facts.get("topic_map", {})
    for group in topical_groups:
        for fact in topic_map.get(group, []):
            if isinstance(fact, dict):
                snippet = _format_fact_snippet(fact)
                if snippet and snippet not in snippets:
                    snippets.append(snippet)

    return "\n".join(snippets)


def _get_active_essence_personality() -> str:
    """Read the active essence's personality.md and return its content."""
    data_home = os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data"))
    active_file = os.path.join(data_home, "data", "active_essence.json")
    if not os.path.isfile(active_file):
        return ""
    try:
        with open(active_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        active_list = data.get("active", [])
        if not active_list:
            # Also check the EssenceRuntime format
            active_name = data.get("active_essence")
            if active_name:
                active_list = [active_name]
        if not active_list:
            return ""
    except (json.JSONDecodeError, OSError):
        return ""

    ambient_base = os.environ.get("AMBIENT_BASE", os.path.expanduser("~/ambient"))
    tools_dir = os.environ.get("TOOLS_DIR",
                               os.environ.get("ESSENCES_DIR",
                                               os.path.join(ambient_base, "tools")))
    essences_dir = os.path.join(ambient_base, "essences")
    parts = []
    for name in active_list:
        # Check tools/ first, then essences/
        personality_path = os.path.join(tools_dir, name, "personality.md")
        if not os.path.isfile(personality_path):
            personality_path = os.path.join(essences_dir, name, "personality.md")
        if os.path.isfile(personality_path):
            try:
                content = Path(personality_path).read_text(encoding="utf-8", errors="replace").strip()
                if content:
                    parts.append(f"### Active Essence: {name}\n{content}")
            except Exception:
                pass
    return "\n\n".join(parts)


def _get_active_essence_chromadb_path() -> str | None:
    """Return the ChromaDB path for the currently active essence, if any."""
    data_home = os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data"))
    active_file = os.path.join(data_home, "data", "active_essence.json")
    if not os.path.isfile(active_file):
        return None
    try:
        with open(active_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        active_list = data.get("active", [])
        if not active_list:
            active_name = data.get("active_essence")
            if active_name:
                active_list = [active_name]
        if not active_list:
            return None
    except (json.JSONDecodeError, OSError):
        return None

    ambient_base = os.environ.get("AMBIENT_BASE", os.path.expanduser("~/ambient"))
    tools_dir = os.environ.get("TOOLS_DIR",
                               os.environ.get("ESSENCES_DIR",
                                               os.path.join(ambient_base, "tools")))
    essences_dir = os.path.join(ambient_base, "essences")
    # Return the first active essence's ChromaDB path (check tools/ then essences/)
    for name in active_list:
        for search_dir in [tools_dir, essences_dir]:
            chroma_path = os.path.join(search_dir, name, "knowledge", "chromadb")
            if os.path.isdir(chroma_path):
                return chroma_path
    return None


def _get_essence_tools_description() -> str:
    """Scan loaded essences/tools and build a description for Jane's context.

    Items with type=tool are listed as tools that Jane invokes directly.
    Items with type=essence are listed as AI agents that Jane delegates to.
    """
    ambient_base = os.environ.get("AMBIENT_BASE", os.path.expanduser("~/ambient"))
    tools_dir = os.environ.get("TOOLS_DIR",
                               os.environ.get("ESSENCES_DIR",
                                               os.path.join(ambient_base, "tools")))
    essences_dir = os.path.join(ambient_base, "essences")

    # Collect entries from both directories
    scan_entries: list[str] = []  # (dir, entry_name) tuples stored as full paths
    for scan_dir in [tools_dir, essences_dir]:
        if os.path.isdir(scan_dir):
            for entry in sorted(os.listdir(scan_dir)):
                scan_entries.append(os.path.join(scan_dir, entry))

    if not scan_entries:
        return ""

    tool_sections = []
    essence_sections = []
    for entry_path in scan_entries:
        entry = os.path.basename(entry_path)
        manifest_path = os.path.join(entry_path, "manifest.json")
        tools_path = os.path.join(entry_path, "functions", "custom_tools.py")
        if not os.path.isfile(manifest_path):
            continue

        try:
            with open(manifest_path) as f:
                m = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        name = m.get("essence_name", entry)
        item_type = m.get("type", "tool")  # default to "tool" for backward compat
        description = m.get("description", "")

        if item_type == "essence":
            # Essences are AI agents — Jane delegates to them
            section = f"### {name} (Essence — AI Agent)\n"
            section += f"Description: {description}\n"
            section += "Interaction: Delegate conversation to this essence. It has its own LLM brain and handles multi-step workflows autonomously.\n"
            # Still list callable tools if they exist
            if os.path.isfile(tools_path):
                tools = _extract_tool_signatures(tools_path)
                if tools:
                    python_bin = os.environ.get("PYTHON_BIN", sys.executable)
                    section += f"Direct tool invoke (optional): `{python_bin} {tools_path} <function_name> '<json_args>'`\n"
                    section += "Available functions:\n"
                    for t in tools:
                        section += f"- `{t}`\n"
            essence_sections.append(section)
        else:
            # Tools are utilities — Jane invokes directly
            if not os.path.isfile(tools_path):
                continue
            tools = _extract_tool_signatures(tools_path)
            if not tools:
                continue

            python_bin = os.environ.get("PYTHON_BIN", sys.executable)
            section = f"### {name} (Tool)\n"
            section += f"Invoke: `{python_bin} {tools_path} <function_name> '<json_args>'`\n"
            section += "Available tools:\n"
            for t in tools:
                section += f"- `{t}`\n"
            tool_sections.append(section)

    parts = []
    if tool_sections:
        parts.append("## Tools\nYou invoke these directly on the user's behalf.\n\n" + "\n".join(tool_sections))
    if essence_sections:
        parts.append("## Essences (AI Agents)\nYou delegate to these — hand off the conversation when the user needs their expertise.\n\n" + "\n".join(essence_sections))

    return "\n\n".join(parts)


def _extract_tool_signatures(tools_path: str) -> list[str]:
    """Extract public function signatures from a custom_tools.py file."""
    tools = []
    try:
        with open(tools_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("def ") and not line.startswith("def _"):
                    sig = line[4:]
                    paren_end = sig.find(") ->")
                    if paren_end == -1:
                        paren_end = sig.find("):")
                    if paren_end >= 0:
                        sig = sig[:paren_end + 1]
                    else:
                        sig = sig.rstrip(":").strip()
                    tools.append(sig.strip())
    except OSError:
        pass
    return tools


CODE_MAP_CORE_PATH = Path(VESSENCE_HOME) / "configs" / "CODE_MAP_CORE.md"


def _load_code_map() -> str:
    """Load the core code map for injection into system prompt."""
    return _read_text(CODE_MAP_CORE_PATH, max_chars=55000)


def _build_system_sections(
    message: str,
    conversation_summary: str,
    memory_summary: str,
    research_brief: str,
    file_context: str | None,
    current_task_state: str,
    personal_facts: dict,
    profile: PromptProfile,
    force_conversation_summary: bool = False,
) -> list[str]:
    user_background = _select_user_background(message, personal_facts) if profile.include_user_background else ""
    system_sections = [BASE_SYSTEM_PROMPT]

    # Inject active essence personality
    essence_personality = _cached("essence_personality", _get_active_essence_personality, ttl=300)
    if essence_personality:
        system_sections.append(f"## Active Essence Context\n{essence_personality}")

    # Inject essence tools so Jane can invoke them
    essence_tools = _cached("essence_tools", _get_essence_tools_description, ttl=300)
    if essence_tools:
        system_sections.append(essence_tools)

    if user_background:
        system_sections.append(f"## User Background\n{user_background}")
    if current_task_state and profile.include_task_state:
        system_sections.append(f"## Current Task State\n{current_task_state}")
    # For short anaphoric messages, always include session summary so the LLM can
    # resolve pronouns/demonstratives without needing ChromaDB memory.
    include_summary = force_conversation_summary or (
        profile.include_conversation_summary and _should_include_conversation_summary(message)
    )
    if conversation_summary and include_summary:
        system_sections.append(f"## Conversation Summary\n{conversation_summary}")
    if profile.include_memory_summary and memory_summary and memory_summary != "No relevant context found.":
        system_sections.append(f"## Retrieved Memory\n{memory_summary}")
    if profile.include_research and research_brief:
        system_sections.append(f"## Research Brief\n{research_brief}")
    if profile.include_file_context and file_context:
        system_sections.append(f"## Active File Context\nThe user is currently viewing or referring to: {file_context}")
    # Code map injection disabled — the brain has tools (Grep/Read) to find
    # symbols on demand, which costs fewer tokens than pre-loading the full index.
    # if profile.include_code_map:
    #     code_map = _cached("code_map_core", _load_code_map, ttl=600)
    #     if code_map:
    #         system_sections.append(f"## Code Map\n...")
    system_sections.append(
        "Prefer the user's most recent explicit message when it conflicts with older memory."
    )
    return system_sections


def _format_recent_history(history: list[dict], max_turns: int = 6, max_chars: int = 2400) -> str:
    if not history:
        return ""

    recent = history[-max_turns:]
    lines: list[str] = []
    remaining = max_chars

    for entry in recent:
        role = str(entry.get("role", "user")).strip().lower()
        content = " ".join(str(entry.get("content", "")).split()).strip()
        if not content:
            continue

        speaker = "Jane" if role == "assistant" else "User"
        line = f"{speaker}: {content}"
        if len(line) > remaining:
            if remaining <= len(speaker) + 2:
                break
            line = line[: remaining - 1].rstrip() + "..."
        lines.append(line)
        remaining -= len(line) + 1
        if remaining <= 0:
            break

    return "\n".join(lines).strip()


TTS_SPOKEN_BLOCK_INSTRUCTION = (
    "IMPORTANT — TTS mode is ON. The user will hear a short summary read aloud, "
    "and can expand to see the full detailed response.\n"
    "Structure your response as:\n"
    "<spoken>1-3 sentence summary in plain spoken English. No symbols, no markdown. "
    "Write exactly as you would speak — short sentences, conversational tone. "
    "NEVER use parentheses, brackets, braces, asterisks, dashes, slashes, pipes, "
    "colons for lists, or any symbols that sound awkward when read aloud.</spoken>\n\n"
    "Then provide the full detailed response below the <spoken> block "
    "(with markdown, code blocks, tables, bullet lists as needed). "
    "The spoken part is a brief conversational summary; the full response has all the detail.\n"
    "Example:\n"
    "<spoken>I updated the config file to fix the timeout. The change is on line 42.</spoken>\n\n"
    "Here's what I changed:\n"
    "- `timeout` was set to `10` — I bumped it to `30`\n"
    "```python\ntimeout = 30\n```"
)


def build_jane_context(
    message: str,
    history: list[dict],
    file_context: str | None = None,
    conversation_summary: str = "",
    session_id: str = "",
    enable_memory_retrieval: bool = True,
    memory_summary_override: str | None = None,
    memory_summary_fallback: str | None = None,
    tts_enabled: bool = False,
    intent_level: str | None = None,
) -> JaneRequestContext:
    data_root = Path(VESSENCE_DATA_HOME)
    vessence_root = Path(VESSENCE_HOME)
    profile = _classify_prompt_profile(message, file_context, intent_level=intent_level)
    current_task_state = _cached("task_state",
        lambda: _read_json_summary(vessence_root / "configs" / "project_specs" / "current_task_state.json"),
        ttl=30) if profile.include_task_state else ""
    personal_facts = _cached("personal_facts",
        lambda: _load_personal_facts(data_root),
        ttl=300)  # 5 min — rarely changes
    skip_memory_for_anaphora = _is_short_anaphoric(message)
    if skip_memory_for_anaphora:
        memory_summary = ""
    elif memory_summary_override is not None:
        memory_summary = _normalize_memory_summary(memory_summary_override, memory_summary_fallback)
    elif enable_memory_retrieval and profile.include_memory_summary:
        memory_summary = _safe_get_memory_summary(
            message,
            conversation_summary=conversation_summary,
            session_id=session_id,
            fallback_summary=memory_summary_fallback,
        )
    else:
        memory_summary = _normalize_memory_summary("", memory_summary_fallback)
    research_brief = run_research_offload(message) if profile.include_research else ""
    system_sections = _build_system_sections(
        message,
        conversation_summary,
        memory_summary,
        research_brief,
        file_context,
        current_task_state,
        personal_facts,
        profile,
        force_conversation_summary=skip_memory_for_anaphora,
    )

    if tts_enabled:
        system_sections.append(TTS_SPOKEN_BLOCK_INSTRUCTION)

    recent_history = _format_recent_history(history)
    user_sections: list[str] = []
    if recent_history:
        user_sections.append(f"Recent Conversation:\n{recent_history}")
    user_sections.extend([f"User: {message}", "Jane:"])

    return JaneRequestContext(
        system_prompt="\n\n".join(system_sections).strip(),
        transcript="\n\n".join(user_sections).strip(),
        retrieved_memory_summary=memory_summary,
    )


async def build_jane_context_async(
    message: str,
    history: list[dict],
    file_context: str | None = None,
    conversation_summary: str = "",
    session_id: str = "",
    enable_memory_retrieval: bool = True,
    memory_summary_override: str | None = None,
    memory_summary_fallback: str | None = None,
    platform: str | None = None,
    tts_enabled: bool = False,
    intent_level: str | None = None,
    on_status: "Callable[[str], None] | None" = None,
) -> JaneRequestContext:
    _status = on_status or (lambda s: None)
    data_root = Path(VESSENCE_DATA_HOME)
    vessence_root = Path(VESSENCE_HOME)

    _status("Classifying prompt profile...")
    profile = _classify_prompt_profile(message, file_context, intent_level=intent_level)

    _status("Loading task state...")
    current_task_state = _cached("task_state",
        lambda: _read_json_summary(vessence_root / "configs" / "project_specs" / "current_task_state.json"),
        ttl=30) if profile.include_task_state else ""

    _status("Loading personal facts...")
    personal_facts = _cached("personal_facts",
        lambda: _load_personal_facts(data_root),
        ttl=300)  # 5 min — rarely changes

    # Short anaphoric messages ("remove it", "do that", "fix this") — skip ChromaDB.
    # The session topic summary + last 2 exchanges give the LLM enough context to
    # resolve the reference; ChromaDB would just return irrelevant noise.
    skip_memory_for_anaphora = _is_short_anaphoric(message)

    memory_task = None
    if skip_memory_for_anaphora:
        _status("Short contextual message — using session context instead of memory.")
        memory_summary = ""
    elif memory_summary_override is not None:
        memory_summary = _normalize_memory_summary(memory_summary_override, memory_summary_fallback)
    elif enable_memory_retrieval and profile.include_memory_summary:
        _status("Retrieving memory from ChromaDB...")
        memory_task = asyncio.create_task(
            asyncio.to_thread(
                _safe_get_memory_summary,
                message,
                conversation_summary,
                session_id,
                memory_summary_fallback,
            )
        )
    else:
        memory_summary = _normalize_memory_summary("", memory_summary_fallback)
    research_task = None
    if profile.include_research:
        _status("Running research offload...")
        research_task = asyncio.create_task(asyncio.to_thread(run_research_offload, message))

    try:
        if memory_task is not None:
            memory_summary = _normalize_memory_summary(await memory_task, memory_summary_fallback)
            _status("Memory retrieved.")
        research_brief = ""
        if research_task:
            research_brief = await research_task
            _status("Research complete.")
    except Exception:
        # Cancel any pending tasks to avoid fire-and-forget coroutines
        if memory_task and not memory_task.done():
            memory_task.cancel()
        if research_task and not research_task.done():
            research_task.cancel()
        raise

    _status("Loading essence personality...")
    _status("Loading essence tools...")
    system_sections = _build_system_sections(
        message,
        conversation_summary,
        memory_summary,
        research_brief,
        file_context,
        current_task_state,
        personal_facts,
        profile,
        force_conversation_summary=skip_memory_for_anaphora,
    )

    # Inject platform context so Jane knows where the user is chatting from
    if platform:
        platform_labels = {"android": "Android app", "web": "web interface", "cli": "CLI terminal"}
        label = platform_labels.get(platform, platform)
        system_sections.append(f"[Platform] The user is chatting from the {label}.")

    # Essence navigation capability (web and Android only)
    if platform in ("android", "web"):
        system_sections.append(
            "[Navigation Actions] You can navigate the user to an essence or file by including "
            "these tags in your response (they render as tappable buttons):\n"
            "- {{navigate:Daily Briefing}} — opens the Daily Briefing essence\n"
            "- {{navigate:Music Playlist}} — opens the Music Playlist essence\n"
            "- {{navigate:Life Librarian}} — opens the file browser\n"
            "- {{navigate:Work Log}} — opens the work log\n"
            "- {{image:path/to/file.jpg}} — displays a vault image inline in the chat\n"
            "- {{play:path/to/song.mp3}} — shows a playable audio card with play button\n"
            "- {{search_results:audio:query}} — shows file search results for the query\n"
            "Use these when the user asks to go somewhere, play something, or view files. "
            "When the user asks to see an image or play a song, first search the vault using "
            "your knowledge of files. Then include the appropriate tag with the vault-relative path. "
            "Include the tag at the end of your response text."
        )

    if tts_enabled:
        system_sections.append(TTS_SPOKEN_BLOCK_INSTRUCTION)

    recent_history = _format_recent_history(history)
    user_sections: list[str] = []
    if recent_history:
        user_sections.append(f"Recent Conversation:\n{recent_history}")
    user_sections.extend([f"User: {message}", "Jane:"])

    return JaneRequestContext(
        system_prompt="\n\n".join(system_sections).strip(),
        transcript="\n\n".join(user_sections).strip(),
        retrieved_memory_summary=memory_summary,
    )
