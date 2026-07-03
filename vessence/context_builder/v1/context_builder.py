import os
import sys
import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from memory.v1.memory_retrieval import build_memory_sections
from jane.config import VESSENCE_DATA_HOME, VESSENCE_HOME
from jane.research_router import run_research_offload
from context_builder.v1.essence_context import (
    get_active_essence_chromadb_path as _get_active_essence_chromadb_path,
    get_active_essence_personality as _get_active_essence_personality,
    get_essence_tools_description as _get_essence_tools_description,
)
from context_builder.v1.prompt_profiles import (
    AI_CODING_KEYWORDS,
    MUSIC_KEYWORDS,
    PromptProfile,
    _classify_prompt_profile,
    _is_task_related,
    _message_lower,
    _profile_for_intent_level,
    _profile_for_message_category,
    _should_include_conversation_summary,
)
from context_builder.v1.memory_summary import normalize_memory_summary as _normalize_memory_summary
from context_builder.v1.memory_plan import build_memory_summary_plan as _build_memory_summary_plan
from context_builder.v1.context_assembly import (
    assemble_context_parts as _assemble_context_parts,
    platform_context_line as _platform_context_line,
)
from context_builder.v1.context_sources import (
    read_json_summary_file as _read_json_summary_file,
    read_text_file as _read_text_file,
)
from context_builder.v1.managed_user_context import (
    build_managed_user_context as _build_managed_user_context,
)
from context_builder.v1.recent_history import (
    build_user_transcript as _build_user_transcript,
    format_recent_history as _format_recent_history,
)
from context_builder.v1.saved_articles_context import (
    build_saved_articles_context as _build_saved_articles_context,
    should_include_saved_articles as _should_include_saved_articles,
)
from context_builder.v1.system_prompt_sections import default_operational_sections
from context_builder.v1.tool_protocols import (
    CLASSIFICATION_TO_INTENT,
    PHONE_TOOLS_PROTOCOL,
    TOOL_CTX_CALL,
    TOOL_CTX_READ_EMAIL,
    TOOL_CTX_READ_MESSAGES,
    TOOL_CTX_SMS,
)
from context_builder.v1.user_background import (
    PERSONAL_FACTS_FILE,
    _format_fact_snippet,
    _load_personal_facts,
    _select_user_background,
)

# Add vault_web to path for database access
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "vault_web"))


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
BASE_SYSTEM_PROMPT = (
    "You are Jane, the user's long-lived technical partner. Speak as Jane."
)

APPROVED_PROJECT_ROOTS = (
    "## Approved Writable Project Roots\n"
    "Jane Web is allowed to read and write source files in these local project roots "
    "when Chieh explicitly asks for code work there:\n\n"
    "- `/home/chieh/ambient/vessence` — Jane/Vessence runtime code.\n"
    "- `/home/chieh/code/chieh_class_v2` — education project for `classes.chiehwu.com`.\n\n"
    "Do not treat `/home/chieh/code/chieh_class_v2` as read-only just because the "
    "standing brain process starts from the Vessence repo. Use absolute paths or "
    "`cd /home/chieh/code/chieh_class_v2` before running commands there. Continue "
    "to avoid committing secrets such as `.env`, service-account JSON, OAuth files, "
    "API keys, local databases, and logs."
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

@dataclass
class JaneRequestContext:
    system_prompt: str
    transcript: str
    retrieved_memory_summary: str = ""


def _read_text(path: Path, max_chars: int = MAX_DOC_CHARS) -> str:
    return _read_text_file(path, max_chars)


def _read_json_summary(path: Path, max_chars: int = 600) -> str:
    return _read_json_summary_file(path, max_chars)


def _managed_user_runtime_context(user_id: str | None) -> tuple[dict, str | None, str]:
    if not user_id:
        return {}, None, ""
    try:
        from agent_skills.user_manager import AVAILABLE_CAPABILITIES, get_user_config, user_config_exists
        if not user_config_exists(user_id):
            return {}, None, ""
        config = get_user_config(user_id)
    except Exception:
        logger.exception("Failed to load managed user config for %s", user_id)
        return {}, None, ""
    if not config.get("managed"):
        return {}, None, ""

    user_context = _build_managed_user_context(config, user_id, AVAILABLE_CAPABILITIES)
    return config, user_context.memory_path, user_context.context_block


def _safe_get_memory_summary(
    message: str,
    conversation_summary: str,
    session_id: str,
    fallback_summary: str | None = None,
    user_id: str | None = None,
) -> str:
    _managed_user_config, user_memory_path, _user_context = _managed_user_runtime_context(user_id)
    if _managed_user_config and not user_memory_path:
        return ""
    if user_memory_path:
        try:
            sections = build_memory_sections(
                message,
                assistant_name="Jane",
                user_memory_path=user_memory_path,
                user_id=user_id,
            )
            memory_summary = "\n\n".join(sections) if sections else "No relevant context found."
        except Exception:
            logger.exception("Managed user memory retrieval failed for %s", user_id)
            return _normalize_memory_summary("", fallback_summary)
        return _normalize_memory_summary(memory_summary, fallback_summary)

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
        sections = build_memory_sections(
            message,
            assistant_name="Jane",
            essence_chromadb_path=essence_chromadb,
            user_id=user_id,
        )
        memory_summary = "\n\n".join(sections) if sections else "No relevant context found."
    except Exception:
        logger.exception("Jane memory retrieval failed")
        return _normalize_memory_summary("", fallback_summary)
    return _normalize_memory_summary(memory_summary, fallback_summary)


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
    saved_articles_context: str = "",
) -> list[str]:
    user_background = _select_user_background(message, personal_facts) if profile.include_user_background else ""
    system_sections = [BASE_SYSTEM_PROMPT, APPROVED_PROJECT_ROOTS, AWAITING_MARKER_INSTRUCTION]

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
    # Memory injection: skip if the brain runs from the project directory,
    # because Claude Code's UserPromptSubmit hooks will inject ChromaDB
    # memory per-turn via <system-reminder> blocks — fresher and more
    # relevant than the context builder's turn-1-only retrieval. Including
    # both paths would cause duplicate memories in context (wasting tokens
    # for zero extra information). The hooks are the preferred memory path;
    # the context builder's memory section is the fallback for non-project
    # CWD (legacy /tmp mode).
    # Inject retrieved memory into the system prompt.
    # The context builder is called from jane_web (standing brain) and never
    # from interactive Claude Code sessions (which use hooks for memory).
    # So always inject — no duplication risk.
    if profile.include_memory_summary and memory_summary and memory_summary != "No relevant context found.":
        system_sections.append(f"## Retrieved Memory\n{memory_summary}")
    if profile.include_research and research_brief:
        system_sections.append(f"## Research Brief\n{research_brief}")
    if profile.include_file_context and file_context:
        system_sections.append(f"## Active File Context\nThe user is currently viewing or referring to: {file_context}")
    if saved_articles_context:
        system_sections.append(f"## Saved Daily Briefing Articles\n{saved_articles_context}")
    # Code map injection disabled — the brain has tools (Grep/Read) to find
    # symbols on demand, which costs fewer tokens than pre-loading the full index.
    # if profile.include_code_map:
    #     code_map = _cached("code_map_core", _load_code_map, ttl=600)
    #     if code_map:
    #         system_sections.append(f"## Code Map\n...")
    # Tool prompt sections — conditional based on profile.
    # tool_mode/data_mode: inject only the specific tool context (or nothing).
    # Full profiles: load all tool prompt.md sections from skills/<name>/.
    if profile.tool_context_override:
        # Gemma classified a specific tool intent — inject only that tool's rules.
        system_sections.append(profile.tool_context_override)
    elif profile.include_tool_protocols:
        try:
            from jane.tool_loader import all_prompt_sections
            for section in all_prompt_sections():
                if section:
                    system_sections.append(section)
        except Exception as e:
            logger.warning("tool_loader prompt section load failed, falling back: %s", e)
            system_sections.append(PHONE_TOOLS_PROTOCOL)
    # else: no tool protocols injected (tool_mode with data pre-fetched, greeting, etc.)

    system_sections.extend(default_operational_sections())
    return system_sections


AWAITING_MARKER_INSTRUCTION = (
    "Multi-turn follow-ups: if your reply asks the user a question and you "
    "need their answer before you can finish the task, end your reply with "
    "the literal marker `[[AWAITING:<short_topic>]]` where <short_topic> is "
    "3-5 words naming what you're waiting for (e.g. "
    "`[[AWAITING:which_pasta_recipe]]` or `[[AWAITING:confirm_send_email]]`). "
    "The marker is stripped before display and tells the pipeline to route "
    "the user's next reply straight back to you with full context, skipping "
    "classification. Omit the marker if your reply is a statement, a "
    "rhetorical question, or already complete."
)


TTS_SPOKEN_BLOCK_INSTRUCTION = (
    "IMPORTANT — TTS mode is ON. The user is LISTENING, not reading. "
    "Keep your ENTIRE response short and conversational — like a spoken response, "
    "not a written document. For TTS, this is strict: keep the spoken part to "
    "1–2 short sentences, no more than 28 words, and no more than 120 words "
    "across the entire reply unless the user explicitly asks for detail.\n\n"
    "Rules for TTS mode:\n"
    "- Be concise. Answer like you're speaking out loud — 1-2 short sentences is preferred; "
    "2 is the hard upper bound unless the request is explicitly informational (for example, a recipe).\n"
    "- No markdown, no bullet lists, no code blocks, no tables in your main response.\n"
    "- No parentheses, brackets, asterisks, or symbols that sound awkward spoken aloud.\n"
    "- ALWAYS wrap your spoken reply in a <spoken>...</spoken> tag — even short casual "
    "answers. This is how the client knows what to voice. No tag = nothing spoken.\n"
    "- CRITICAL — <spoken> MUST be the VERY FIRST content in your reply, before ANY "
    "prose, markdown, commentary, or explanation. The client speaks text as it streams; "
    "any words that arrive before <spoken> get voiced out loud verbatim.\n"
    "- If the user asks something that genuinely needs detail (code, long explanation, "
    "lists, patient notes, schedules, specs), put the short spoken answer in <spoken> "
    "and the full detail AFTER the closing </spoken> tag. The spoken part MUST "
    "explicitly tell the user you've written the full details on screen (e.g. \"I've "
    "printed the full notes on screen\", \"the details are on screen for you to read\"). "
    "The user is listening, not looking — if you don't say it out loud, they'll never "
    "know the written part exists.\n\n"
    "Example (simple question — <spoken> wraps the whole reply):\n"
    "<spoken>Yeah, the timeout was set to 10 seconds. I bumped it to 30 and it should be fine now.</spoken>\n\n"
    "Example (needs detail — <spoken> is the first line, full detail after):\n"
    "<spoken>I fixed the timeout issue — I've printed the change on screen for you to read.</spoken>\n\n"
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
    tool_context: str | None = None,
    user_id: str | None = None,
) -> JaneRequestContext:
    data_root = Path(VESSENCE_DATA_HOME)
    vessence_root = Path(VESSENCE_HOME)
    profile = _classify_prompt_profile(message, file_context, intent_level=intent_level, tool_context=tool_context)
    managed_user_config, _user_memory_path, managed_user_block = _managed_user_runtime_context(user_id)
    current_task_state = _cached("task_state",
        lambda: _read_json_summary(vessence_root / "configs" / "project_specs" / "current_task_state.json"),
        ttl=30) if profile.include_task_state else ""
    personal_facts = {} if managed_user_config else _cached("personal_facts",
        lambda: _load_personal_facts(data_root),
        ttl=300)  # 5 min — rarely changes
    memory_plan = _build_memory_summary_plan(
        message,
        include_memory_summary=profile.include_memory_summary,
        enable_memory_retrieval=enable_memory_retrieval,
        memory_summary_override=memory_summary_override,
        memory_summary_fallback=memory_summary_fallback,
    )
    if memory_plan.should_retrieve:
        memory_summary = _safe_get_memory_summary(
            message,
            conversation_summary=conversation_summary,
            session_id=session_id,
            fallback_summary=memory_summary_fallback,
            user_id=user_id,
        )
    else:
        memory_summary = memory_plan.memory_summary
    research_brief = run_research_offload(message) if profile.include_research else ""
    saved_articles_context = _build_saved_articles_context(message)
    system_sections = _build_system_sections(
        message,
        conversation_summary,
        memory_summary,
        research_brief,
        file_context,
        current_task_state,
        personal_facts,
        profile,
        force_conversation_summary=memory_plan.force_conversation_summary,
        saved_articles_context=saved_articles_context,
    )

    if tts_enabled:
        tts_instruction = TTS_SPOKEN_BLOCK_INSTRUCTION
    else:
        tts_instruction = ""
    assembly = _assemble_context_parts(
        system_sections,
        message=message,
        history=history,
        retrieved_memory_summary=memory_summary,
        tts_instruction=tts_instruction,
        managed_user_block=managed_user_block,
    )
    return JaneRequestContext(**assembly.__dict__)


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
    tool_context: str | None = None,
    on_status: "Callable[[str], None] | None" = None,
    user_id: str | None = None,
) -> JaneRequestContext:
    _status = on_status or (lambda s: None)
    data_root = Path(VESSENCE_DATA_HOME)
    vessence_root = Path(VESSENCE_HOME)

    _status("Classifying prompt profile...")
    profile = _classify_prompt_profile(message, file_context, intent_level=intent_level, tool_context=tool_context)
    managed_user_config, _user_memory_path, managed_user_block = _managed_user_runtime_context(user_id)

    _status("Loading task state...")
    current_task_state = _cached("task_state",
        lambda: _read_json_summary(vessence_root / "configs" / "project_specs" / "current_task_state.json"),
        ttl=30) if profile.include_task_state else ""

    _status("Loading personal facts...")
    personal_facts = {} if managed_user_config else _cached("personal_facts",
        lambda: _load_personal_facts(data_root),
        ttl=300)  # 5 min — rarely changes

    memory_plan = _build_memory_summary_plan(
        message,
        include_memory_summary=profile.include_memory_summary,
        enable_memory_retrieval=enable_memory_retrieval,
        memory_summary_override=memory_summary_override,
        memory_summary_fallback=memory_summary_fallback,
    )
    memory_task = None
    if memory_plan.status_message:
        _status(memory_plan.status_message)
    if memory_plan.should_retrieve:
        memory_task = asyncio.create_task(
            asyncio.to_thread(
                _safe_get_memory_summary,
                message,
                conversation_summary,
                session_id,
                memory_summary_fallback,
                user_id,
            )
        )
    else:
        memory_summary = memory_plan.memory_summary
    research_task = None
    if profile.include_research:
        _status("Running research offload...")
        research_task = asyncio.create_task(asyncio.to_thread(run_research_offload, message))
    saved_articles_task = None
    if _should_include_saved_articles(message):
        _status("Checking saved Daily Briefing articles...")
        saved_articles_task = asyncio.create_task(asyncio.to_thread(_build_saved_articles_context, message))

    try:
        if memory_task is not None:
            memory_summary = _normalize_memory_summary(await memory_task, memory_summary_fallback)
            _status("Memory retrieved.")
        research_brief = ""
        if research_task:
            research_brief = await research_task
            _status("Research complete.")
        saved_articles_context = ""
        if saved_articles_task:
            saved_articles_context = await saved_articles_task
            if saved_articles_context:
                _status("Saved briefing article context loaded.")
    except Exception:
        # Cancel any pending tasks to avoid fire-and-forget coroutines
        if memory_task and not memory_task.done():
            memory_task.cancel()
        if research_task and not research_task.done():
            research_task.cancel()
        if saved_articles_task and not saved_articles_task.done():
            saved_articles_task.cancel()
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
        force_conversation_summary=memory_plan.force_conversation_summary,
        saved_articles_context=saved_articles_context,
    )

    # Navigation tag syntax removed from per-request context (2026-03-29).
    # Tag syntax ({{navigate:X}}, {{image:X}}, {{play:X}}, {{search_results:audio:X}})
    # is stored in ChromaDB memory and retrieved on demand when relevant.

    if tts_enabled:
        tts_instruction = TTS_SPOKEN_BLOCK_INSTRUCTION
    else:
        tts_instruction = ""
    assembly = _assemble_context_parts(
        system_sections,
        message=message,
        history=history,
        retrieved_memory_summary=memory_summary,
        platform=platform,
        tts_instruction=tts_instruction,
        managed_user_block=managed_user_block,
    )
    return JaneRequestContext(**assembly.__dict__)
