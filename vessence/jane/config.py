"""
config.py — Single source of truth for Vessence path and runtime configuration.

Root model:
- VESSENCE_HOME: shippable code/config repo
- VESSENCE_DATA_HOME: mutable runtime state (logs, env, credentials, vector DB)
- VAULT_HOME: user-owned files

AMBIENT_HOME is kept only as a compatibility alias to the runtime data root.
"""

import os
from pathlib import Path


def _resolve_roots() -> tuple[str, str, str, str]:
    home = str(Path.home())
    ambient_base = os.environ.get("AMBIENT_BASE", os.path.join(home, "ambient"))

    code_root = os.environ.get("VESSENCE_HOME")
    if not code_root:
        code_root = os.path.join(ambient_base, "vessence")

    data_root = os.environ.get("VESSENCE_DATA_HOME")
    if not data_root:
        ambient_home = os.environ.get("AMBIENT_HOME", "").strip()
        default_data_root = os.path.join(ambient_base, "vessence-data")
        if ambient_home and os.path.normpath(ambient_home) != os.path.normpath(ambient_base):
            data_root = ambient_home
        else:
            data_root = default_data_root

    tools_root = os.environ.get("SKILLS_DIR",
                                  os.environ.get("TOOLS_DIR",  # legacy env var
                                                  os.path.join(ambient_base, "skills")))
    essences_root = os.path.join(ambient_base, "essences")

    vault_root = os.environ.get("VAULT_HOME", os.path.join(ambient_base, "vault"))
    return code_root, data_root, vault_root, tools_root, essences_root

# ── Root paths ────────────────────────────────────────────────────────────────
VESSENCE_HOME, VESSENCE_DATA_HOME, VAULT_DIR, SKILLS_DIR, ESSENCES_DIR = _resolve_roots()

# Legacy alias — code that imported TOOLS_DIR should migrate to SKILLS_DIR.
TOOLS_DIR = SKILLS_DIR  # backward compat
HOME_DIR = str(Path.home())
USER_NAME = os.environ.get("USER_NAME", "the user")

# ── Essence / tool paths ──────────────────────────────────────────────────────
ESSENCE_TEMPLATE_DIR = f"{VESSENCE_HOME}/configs/templates/essence_template"

# Legacy alias kept during migration. Historically AGENT_ROOT meant the live
# ambient root; it now points at the runtime data root.
AGENT_ROOT      = VESSENCE_DATA_HOME
LOGS_DIR        = f"{VESSENCE_DATA_HOME}/logs"
CONFIGS_DIR     = f"{VESSENCE_HOME}/configs"
AMBER_DIR       = f"{VESSENCE_HOME}/amber"
DATA_DIR        = f"{VESSENCE_DATA_HOME}/data"
DYNAMIC_QUERY_MARKERS_PATH = f"{VESSENCE_DATA_HOME}/data/dynamic_query_markers.json"
CREDENTIALS_DIR = f"{VESSENCE_DATA_HOME}/credentials"
ENV_FILE_PATH   = f"{VESSENCE_DATA_HOME}/.env"

# ── Vector DB paths ───────────────────────────────────────────────────────────
CHROMA_HOST = os.environ.get("CHROMA_HOST", "")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", "8000"))

_chroma_client_cache: dict = {}
_chroma_client_lock = __import__("threading").Lock()


def get_chroma_client(path: str):
    """
    Returns the appropriate ChromaDB client.
    If CHROMA_HOST is set (e.g. running in Docker), it uses the HttpClient to avoid
    dual-access SQLite corruption. Otherwise, it uses PersistentClient on the local path.
    Note: When using HttpClient, 'path' is ignored by the server, so collections must be uniquely named.

    Cached per-path: each PersistentClient spawns its own tokio runtime
    (~20 worker threads) + sqlx-sqlite pool. Creating fresh clients per
    call leaked hundreds of threads and GBs of memory over a multi-hour
    session, triggering OOM kills of jane-web.
    """
    import chromadb
    key = f"http:{CHROMA_HOST}:{CHROMA_PORT}" if CHROMA_HOST else f"persistent:{path}"
    cached = _chroma_client_cache.get(key)
    if cached is not None:
        return cached
    with _chroma_client_lock:
        cached = _chroma_client_cache.get(key)
        if cached is not None:
            return cached
        if CHROMA_HOST:
            client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        else:
            client = chromadb.PersistentClient(path=path)
        _chroma_client_cache[key] = client
        return client

VECTOR_DB_DIR        = f"{VESSENCE_DATA_HOME}/memory/v1/vector_db"
VECTOR_DB_USER_MEMORIES = VECTOR_DB_DIR                          # main shared ChromaDB
VECTOR_DB_SHORT_TERM = f"{VECTOR_DB_DIR}/short_term_memory"
VECTOR_DB_LONG_TERM  = f"{VECTOR_DB_DIR}/long_term_memory"       # Jane's archived KB
VECTOR_DB_FILE_INDEX = f"{VECTOR_DB_DIR}/file_index_memory"

# ── ChromaDB collection names ─────────────────────────────────────────────────
CHROMA_COLLECTION_USER_MEMORIES = "user_memories"
CHROMA_COLLECTION_SHORT_TERM    = "short_term_memory"
CHROMA_COLLECTION_LONG_TERM     = "long_term_knowledge"
CHROMA_COLLECTION_FILE_INDEX    = "file_index_memories"

# ── Important document paths ──────────────────────────────────────────────────
PROMPT_LIST_PATH   = f"{VAULT_DIR}/documents/prompt_list.md"
ACCOMPLISHED_PATH  = f"{VAULT_DIR}/documents/completed_prompts.md"
LEDGER_DB_PATH     = f"{VAULT_DIR}/conversation_history_ledger.db"
JANITOR_REPORT     = f"{LOGS_DIR}/janitor_report.json"

# Identity essays (read at session start)
_USER_NAME   = os.environ.get("USER_NAME", "user")
USER_ESSAY   = f"{VAULT_DIR}/documents/{_USER_NAME}_identity_essay.txt"
JANE_ESSAY   = f"{VAULT_DIR}/documents/jane_identity_essay.txt"
AMBER_ESSAY  = f"{VAULT_DIR}/documents/amber_identity_essay.txt"

# ── State / session files ─────────────────────────────────────────────────────
USER_STATE_PATH   = f"{AGENT_ROOT}/user_state.json"
IDLE_STATE_PATH   = f"{AGENT_ROOT}/idle_state.json"
ACTIVE_QUEUE_PATH = f"{AGENT_ROOT}/active_queue.json"
QUEUE_SESSION_PATH = f"{AGENT_ROOT}/queue_session.json"
PENDING_UPDATES_PATH = f"{AGENT_ROOT}/pending_updates.json"
CONTEXT_SUMMARY_PATH = f"{AGENT_ROOT}/context_summary_last.json"
JANE_SESSIONS_PATH = f"{DATA_DIR}/jane_sessions.json"
JANE_SESSION_SUMMARY_DIR = f"{DATA_DIR}/jane_session_summaries"
TASK_SPINE_PATH = f"{DATA_DIR}/task_spine.json"
INTERRUPT_STACK_PATH = f"{DATA_DIR}/interrupt_stack.json"

# ── Log file paths ────────────────────────────────────────────────────────────
PROMPT_QUEUE_LOG     = f"{LOGS_DIR}/prompt_queue.log"   # legacy alias
JOB_QUEUE_LOG        = f"{LOGS_DIR}/job_queue.log"
JANE_WRAPPER_RAW_LOG = f"{LOGS_DIR}/JaneWrapper_raw.log"
AMBIENT_HEARTBEAT_LOG = f"{LOGS_DIR}/ambient_heartbeat.log"
VAULT_TUNNEL_LOG     = f"{LOGS_DIR}/vault_tunnel.log"

# ── Binary / script paths ─────────────────────────────────────────────────────
ADK_VENV_PYTHON  = os.environ.get("ADK_VENV_PYTHON", os.path.join(HOME_DIR, "google-adk-env", "adk-venv", "bin", "python"))
CLAUDE_BIN       = os.environ.get("CLAUDE_BIN", os.path.join(HOME_DIR, ".local", "bin", "claude"))
CODEX_BIN        = os.environ.get("CODEX_BIN", "codex")
JANE_BRIDGE_ENV  = os.environ.get("JANE_BRIDGE_ENV", os.path.join(HOME_DIR, "gemini_cli_bridge", ".env"))

FALLBACK_SCRIPT       = f"{VESSENCE_HOME}/agent_skills/fallback_query.py"
ADD_MEMORY_SCRIPT     = f"{VESSENCE_HOME}/agent_skills/memory/v1/add_forgettable_memory.py"
ADD_FACT_SCRIPT       = f"{VESSENCE_HOME}/agent_skills/memory/v1/add_fact.py"
SEARCH_MEMORY_SCRIPT  = f"{VESSENCE_HOME}/agent_skills/memory/v1/search_memory.py"
PROMPT_QUEUE_RUNNER   = f"{VESSENCE_HOME}/agent_skills/prompt_queue_runner.py"
RESEARCH_ASSISTANT_SCRIPT = f"{VESSENCE_HOME}/agent_skills/research_assistant.py"
VAULT_WEB_DB_PATH     = f"{VESSENCE_DATA_HOME}/vault_web/vault_web.db"
ADK_SESSION_DB_DIR    = f"{VESSENCE_DATA_HOME}/adk"
QWEN_QUERY_SCRIPT     = f"{VESSENCE_HOME}/agent_skills/qwen_query.py"
INDEX_VAULT_SCRIPT    = f"{VESSENCE_HOME}/agent_skills/memory/v1/index_vault.py"
VAULT_WEB_MODULE_DIR  = f"{VESSENCE_HOME}/vault_web"

# ── Amber / ADK ───────────────────────────────────────────────────────────────
AMBER_APP_NAME  = "amber"
ADK_SERVER_URL  = "http://localhost:8000"
ADK_RUN_URL     = f"{ADK_SERVER_URL}/run"

# ── Discord ───────────────────────────────────────────────────────────────────
DISCORD_API_BASE      = "https://discord.com/api/v10"
DISCORD_MAX_MSG_LEN   = 2000
DISCORD_SAFE_CHUNK    = 1900   # leave headroom for Discord's limit
OWNER_USER_ID         = os.environ.get("OWNER_USER_ID", "")

# Progress-snippet settings for the Jane bridge
DISCORD_PROGRESS_INTERVAL  = 25   # seconds between progress updates
DISCORD_PROGRESS_MIN_CHARS = 80   # minimum new chars before sending a snippet
DISCORD_PROGRESS_MAX_CHARS = 350  # max chars in a snippet

# ── Idle / activity thresholds ────────────────────────────────────────────────
IDLE_THRESHOLD_SECS    = 5 * 60   # 5 min — stop queue if user is active
IDLE_TIMEOUT_SECS      = 60       # inactivity before triggering archival in ConvManager

# ── Memory TTLs ───────────────────────────────────────────────────────────────
SHORT_TERM_TTL_DAYS    = 14   # short-term memories expire after this many days
SHORT_TERM_MAX_THEMES  = 20   # rolling theme slots per session in short-term memory
FORGETTABLE_MAX_AGE_DAYS = 14 # hard age cap enforced by nightly janitor

# ── HTTP timeouts (seconds) ───────────────────────────────────────────────────
HTTP_TIMEOUT_DEFAULT   = 30
HTTP_TIMEOUT_DISCORD   = 10
HTTP_TIMEOUT_ADK_RUN   = int(os.getenv("HTTP_TIMEOUT_ADK_RUN", "600"))   # 10 min — web and agent runs can be long
HTTP_TIMEOUT_CLAUDE    = 600   # 10 min — prompt queue tasks can be long

# ── Process / session timeouts (seconds) ──────────────────────────────────────
GEMINI_READY_TIMEOUT   = 45    # wait for Gemini CLI to be ready after spawn
PROCESS_KILL_GRACE     = 2.0   # seconds before SIGKILL after SIGTERM
JANE_WRAPPER_LOG_FLUSH_INTERVAL = float(os.getenv("JANE_WRAPPER_LOG_FLUSH_INTERVAL", "0.25"))
JANE_WRAPPER_LOG_BATCH_BYTES = int(os.getenv("JANE_WRAPPER_LOG_BATCH_BYTES", "8192"))

# ── ChromaDB search limits ────────────────────────────────────────────────────
CHROMA_SEARCH_LIMIT      = 15   # semantic search top-N from user_memories (was 30 — too noisy)
CHROMA_SHORT_TERM_LIMIT  = 4    # top-N from short_term_memory (was 8)
CHROMA_LONG_TERM_LIMIT   = 5    # top-N from Jane's long-term archive (was 15)
CHROMA_USER_MAX_DISTANCE = float(os.getenv("CHROMA_USER_MAX_DISTANCE", "0.50"))
CHROMA_PERMANENT_MAX_DISTANCE = float(os.getenv("CHROMA_PERMANENT_MAX_DISTANCE", "1.0"))  # always inject permanent rules
CHROMA_SHORT_TERM_MAX_DISTANCE = float(os.getenv("CHROMA_SHORT_TERM_MAX_DISTANCE", "0.58"))
CHROMA_FILE_INDEX_MAX_DISTANCE = float(os.getenv("CHROMA_FILE_INDEX_MAX_DISTANCE", "0.76"))
CHROMA_LONG_TERM_MAX_DISTANCE = float(os.getenv("CHROMA_LONG_TERM_MAX_DISTANCE", "0.50"))
MEMORY_SUMMARY_CACHE_TTL_SECS = int(os.getenv("MEMORY_SUMMARY_CACHE_TTL_SECS", "300"))
MEMORY_SUMMARY_CACHE_SIMILARITY = float(os.getenv("MEMORY_SUMMARY_CACHE_SIMILARITY", "0.92"))
MEMORY_SUMMARY_CACHE_MAX_ENTRIES = int(os.getenv("MEMORY_SUMMARY_CACHE_MAX_ENTRIES", "3"))

# ── Context / compaction ──────────────────────────────────────────────────────
CONTEXT_COMPACTION_RATIO = 0.65   # compact at 65% of max context window
CONTEXT_MAX_SPEC_CHARS   = 6000   # max chars of spec fed to Claude in heartbeat
CONTEXT_MAX_SEARCH_CHARS = 15000  # max chars of raw web search for research

# ── Web search ────────────────────────────────────────────────────────────────
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")  # Tavily first; fallback to DuckDuckGo

# ── Prompt queue ──────────────────────────────────────────────────────────────
QUEUE_ARCHIVE_THRESHOLD  = 10     # archive completed items when list exceeds this
QUEUE_PAUSE_BETWEEN_SECS = 5      # pause between consecutive prompt runs

# ── LLM Provider Strategy ────────────────────────────────────────────────────
#
# JANE_BRAIN determines the primary provider. Each provider has a "smart" model
# (for Jane, Amber, user-facing tasks) and a "cheap" model (for background tasks
# like archivist, janitor, librarian). Users only need their subscription — no
# separate API keys required for the CLI-based providers.
#
# Provider    | Smart (Jane/Amber)        | Cheap (background)        | CLI
# ------------|---------------------------|---------------------------|----------
# claude      | claude-sonnet-4-6         | claude-haiku-4-5-20251001 | claude
# openai      | gpt-4o                   | gpt-4o-mini               | codex
# gemini      | gemini-2.5-pro           | gemini-2.5-flash          | gemini
#
_PROVIDER = os.getenv("JANE_BRAIN", "claude").lower()

PROVIDER_MODELS = {
    "claude":  {"smart": "claude-sonnet-4-6",   "cheap": "claude-haiku-4-5-20251001",  "cli": "claude"},
    "openai":  {"smart": "gpt-4o",              "cheap": "gpt-4o-mini",                "cli": "codex"},
    "gemini":  {"smart": "gemini-2.5-pro",      "cheap": "gemini-2.5-flash",           "cli": "gemini"},
}

_models = PROVIDER_MODELS.get(_PROVIDER, PROVIDER_MODELS["claude"])

# Smart model — used for Jane, Amber, user-facing work
SMART_MODEL = os.getenv("SMART_MODEL", _models["smart"])

# Cheap model — used for archivist, janitor, librarian, summarization
CHEAP_MODEL = os.getenv("CHEAP_MODEL", _models["cheap"])

# CLI binary for the active provider
PROVIDER_CLI = os.getenv("PROVIDER_CLI", _models["cli"])

# Web/Android chat model — defaults to SMART_MODEL but can be overridden to a
# faster/cheaper model (e.g. Sonnet instead of Opus) without changing CLI Jane.
WEB_CHAT_MODEL = os.environ.get("JANE_BRAIN_WEB_MODEL", SMART_MODEL)

# Legacy aliases (backward compat)
OLLAMA_BASE_URL       = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434")
# LOCAL_LLM_MODEL is kept only as a backward-compatible import alias.
# The single local-model knob is JANE_LOCAL_LLM, falling back to JANE_STAGE2_MODEL.
LOCAL_LLM_MODEL       = os.getenv("JANE_LOCAL_LLM", os.getenv("JANE_STAGE2_MODEL", "qwen2.5:7b"))
LOCAL_LLM_MODEL_LITELLM = f"ollama/{LOCAL_LLM_MODEL}" if "/" not in LOCAL_LLM_MODEL else LOCAL_LLM_MODEL
ARCHIVIST_MODEL       = os.getenv("ARCHIVIST_MODEL", CHEAP_MODEL)
ARCHIVIST_MODEL_LITELLM = f"ollama/{ARCHIVIST_MODEL}" if "/" not in ARCHIVIST_MODEL else ARCHIVIST_MODEL
ARCHIVIST_SMART_MODEL = os.getenv("ARCHIVIST_SMART_MODEL", CHEAP_MODEL)
ARCHIVIST_SMART_MODEL_LITELLM = f"ollama/{ARCHIVIST_SMART_MODEL}" if "/" not in ARCHIVIST_SMART_MODEL else ARCHIVIST_SMART_MODEL
ARCHIVIST_SMART_AFTER_HOUR = int(os.getenv("ARCHIVIST_SMART_AFTER_HOUR", "12"))
ARCHIVIST_SMART_IDLE_SECS = int(os.getenv("ARCHIVIST_SMART_IDLE_SECS", "3600"))
JANITOR_LLM_MODEL       = CHEAP_MODEL
FALLBACK_GEMINI_MODEL   = "gemini-2.5-flash"
FALLBACK_OPENAI_MODEL   = "gpt-4o"

# ── TTS (edge-tts) ───────────────────────────────────────────────────────────
TTS_ENABLED      = os.getenv("TTS_ENABLED", "1") == "1"
TTS_VOICE        = os.getenv("TTS_VOICE", "en-US-AriaNeural")
TTS_RATE         = os.getenv("TTS_RATE", "+0%")       # e.g. "+20%" for faster
TTS_VOLUME       = os.getenv("TTS_VOLUME", "+0%")
TTS_MAX_CHARS    = int(os.getenv("TTS_MAX_CHARS", "2000"))  # truncate very long responses

# External API endpoints
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
OPENAI_API_URL   = "https://api.openai.com/v1/chat/completions"
