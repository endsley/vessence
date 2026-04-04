# Architecture

## Web Request Lifecycle
```
Browser/Android → Cloudflare Tunnel → jane_web/main.py (routes)
  → jane_proxy.py: stream_message() or send_message()
    → intent_classifier.py (gemma3:4b): classify level → greeting/simple/medium/hard
    → context_builder.py: build system prompt (greeting=slim, hard=full memory+task state)
    → standing_brain.py: StandingBrainManager.send(tier, message, system_prompt)
        (persistent_claude.py / persistent_gemini.py as fallback cold-start)
    → conversation_manager.py: persist turns to ChromaDB
```

## Model Routing
```
gemma3:4b (classifier only, never responds) → determines tier
  greeting/simple → light  (slim context, no memory retrieval)
  medium          → medium (full context + memory + task state)
  hard            → heavy  (full context + memory + task state + research)

Default models per provider (all overridable via env vars):
  Claude  → light=haiku-4-5, medium=sonnet-4-6,   heavy=opus-4-6
  Gemini  → light=flash,     medium=pro,           heavy=pro
  OpenAI  → light=gpt-4.1-mini, medium=gpt-4.1,   heavy=o3
Active provider set by JANE_BRAIN env var (claude|gemini|openai)
```

## Standing Brain Sessions
```
3 long-lived CLI processes per provider (light/medium/heavy tiers)
  System prompt injected on turn 1 only — subsequent turns send raw message
  Forced restart after 20 turns (MAX_TURNS_BEFORE_REFRESH) to refresh context
  Reaper (every 60s): auto-restart dead brains; kill only if idle (5+ min) AND
    CPU >15% sustained for 1 hour — never kills brains actively handling work
Prompt Queue: dedicated "prompt_queue_session" via internal API (localhost:8081)
```

## Memory Flow
```
User message → librarian (gemma3:4b) queries ChromaDB
  → short_term_memory (14-day TTL, concise summaries)
  → long_term_memory (permanent facts, shared with Amber)
  → context_builder assembles into system prompt
Write: conversation_manager.py summarizes turns → ChromaDB
```

## Cron Pipeline (nightly 2:00-6:00 AM)
```
2:00  usb_sync.py          (incremental backup)
2:10  run_briefing.py       (daily news, gemma3:12b summaries)
2:15  janitor_memory.py     (ChromaDB cleanup)
2:30  check_for_updates.py
3:00  janitor_system.py     (system maintenance)
3:15  regenerate_jane_context.py
4:00  generate_identity_essay.py
4:15  generate_code_map.py  (this index)
5:00  ambient_heartbeat.py
```

## Key Directories
```
jane_web/     → FastAPI web server (routes, auth, streaming)
jane/         → Brain adapters, persistent sessions, context builder
vault_web/    → HTML templates (jane.html, app.html, briefing.html)
agent_skills/ → Standalone scripts (classifier, memory, TTS, queue)
amber/        → Google ADK agent (Amber's brain)
essences/     → Self-contained AI agent packages
android/      → Native Android app (Kotlin, Jetpack Compose)
```

<!-- AUTO-GENERATED BELOW — do not edit below this line -->

# Code Map — Core (Python Backend)
_Auto-generated on 2026-03-27 08:15 UTC by `generate_code_map.py`_

## Priority Files

### jane_web/jane_proxy.py (1075 lines)
  CODE_MAP_KEYWORDS = ... → L27
  _maybe_prepend_code_map() → L47-51
  class JaneSessionState → L55-63
  _MAX_SESSIONS = ... → L67
  REQUEST_TIMING_LOG = ... → L68
  PROMPT_DUMP_LOG = ... → L69
  SESSION_IDLE_TTL_SECONDS = ... → L70
  _PREFETCH_CACHE_MAX = ... → L74
  PREFETCH_TTL = ... → L75
  run_prefetch_memory() → L78-114
  get_prefetch_result() → L117-122
  _get_brain_name() → L125-126
  _session_log_id() → L129-130
  _get_timeout_seconds() → L133-134
  _get_execution_profile() → L137-138
  _use_persistent_gemini() → L141-142
  _use_persistent_claude() → L145-146
  _prune_stale_sessions() → L149-162
  _execute_brain_sync() → L165-201
  _execute_brain_stream() → L204-246
  _get_session() → L249-265
  _FOLLOWUP_FILE_MARKERS = ... → L268
  _resolve_file_context() → L290-299
  _message_for_persistence() → L302-306
  prewarm_session() → L309-363
  _await_prewarm_if_running() → L366-383
  end_session() → L386-420
  _progress_snapshot() → L423-437
  _LOG_MAX_BYTES = ... → L440
  _truncate_log_if_needed() → L443-450
  _log_stage() → L453-464
  _log_start() → L467-475
  _dump_prompt() → L478-510
  _persist_turns_async() → L513-551
  send_message() → L559-693
  stream_message() → L696-1058
  _log_chat_to_work_log() → L1061-1063
  get_active_brain() → L1066-1068
  get_tunnel_url() → L1071-1075

### jane_web/main.py (2677 lines)
  class ChatMessage → L1581-1586
  class SessionControl → L1589-1590
  GET /health → L406
  GET /sw.js → L412
  GET /manifest.webmanifest → L417
  GET / → L526
  GET /share → L552
  GET /vault → L557
  GET /guide → L580
  GET /architecture → L586
  GET /chat → L592
  GET /essences → L615
  GET /worklog → L619
  GET /briefing → L623
  POST /api/crash-report → L628
  GET /settings/devices → L639
  GET /downloads/{filename} → L645
  POST /api/tts/generate → L697
  GET /api/app/settings → L742
  PUT /api/app/settings → L748
  POST /api/app/installed → L758
  GET /api/app/latest-version → L770
  GET /auth/google → L782
  GET /auth/google/callback → L794
  POST /api/auth/google-token → L822
  POST /api/auth/verify-share → L859
  POST /api/auth/verify-otp → L869
  POST /api/auth/logout → L894
  GET /api/auth/devices → L906
  DELETE /api/auth/devices/{device_id} → L911
  POST /api/auth/check → L917
  POST /api/auth/is-new-device → L930
  GET /api/jane/announcements → L936
  GET /api/settings/models → L962
  POST /api/settings/models → L979
  GET /api/jane/live → L1033
  POST /api/jane/prefetch-memory → L1067
  GET /api/files → L1097
  GET /api/files/list/{path:path} → L1107
  GET /api/files/meta/{path:path} → L1137
  PATCH /api/files/description/{path:path} → L1142
  GET /api/files/thumbnail/{path:path} → L1148
  GET /api/files/serve/{path:path} → L1157
  GET /api/files/changes → L1206
  GET /api/files/find → L1211
  GET /api/files/search → L1237
  GET /api/files/play/{path:path} → L1324
  GET /api/files/content/{path:path} → L1341
  PUT /api/files/content/{path:path} → L1358
  POST /api/files/upload → L1375

### jane_web/broadcast.py (256 lines)
  SUMMARY_INTERVAL_SECONDS = ... → L16
  CLAUDE_CLI = ... → L17
  _SUMMARY_SYSTEM = ... → L19
  _summarize_sync() → L29-84
  class BroadcastEvent → L88-105
    to_json() → L97-105
  class BroadcastManager → L108-148
    __init__() → L111-113
    subscribe() → L115-122
    unsubscribe() → L124-133
    has_listeners() → L135-136
    publish() → L138-148
  class StreamBroadcaster → L155-256
    __init__() → L169-186
    start() → L188-199
    feed_delta() → L201-214
    _summarize_and_publish() → L216-229
    finish() → L231-244
    error() → L246-256

### jane_web/reverse_proxy.py (281 lines)
  class ProxyState → L38-58
    __init__() → L41-46
    upstream_url() → L49-50
    switch() → L52-58
  _is_localhost() → L67-72
  handle_switch() → L75-90
  handle_status() → L93-103
  CONNECT_TIMEOUT = ... → L111
  HOP_BY_HOP = ... → L114
  proxy_handler() → L121-197
  _proxy_websocket() → L200-236
  create_app() → L243-253
  main() → L256-277

### jane_web/task_classifier.py (82 lines)
  _BIG_TASK_PATTERNS = ... → L6
  _QUICK_QUERY_PATTERNS = ... → L26
  _MIN_LENGTH_FOR_OFFLOAD = ... → L33
  classify_task() → L39-77
  strip_bg_prefix() → L80-82

### jane_web/task_offloader.py (195 lines)
  CODE_ROOT = ... → L13
  ANNOUNCEMENTS_PATH = ... → L20
  _PROGRESS_INTERVAL = ... → L22
  _write_announcement() → L25-29
  _now_iso() → L32-33
  offload_task() → L36-56
  _run_task() → L59-189
  _truncate() → L192-195

### jane/brain_adapters.py (428 lines)
  _kill_pgroup() → L12-22
  class ExecutionProfile → L26-30
  PROVIDER_TIMEOUT_DEFAULTS = ... → L33
  PROVIDER_IDLE_DEFAULTS = ... → L40
  PROVIDER_WALL_DEFAULTS = ... → L47
  class BrainAdapterError → L55-56
  class BrainAdapter → L59-112
    __init__() → L64-65
    _missing_env() → L67-68
    build_command() → L70-71
    parse_output() → L73-74
    execute_stream() → L76-79
    execute() → L81-112
  class GeminiBrainAdapter → L115-128
    build_command() → L120-125
    execute_stream() → L127-128
  class ClaudeBrainAdapter → L131-153
    build_command() → L140-146
    execute() → L148-150
    execute_stream() → L152-153
  class OpenAIBrainAdapter → L156-212
    execute() → L161-212
  class CodexBrainAdapter → L215-218
  resolve_timeout_seconds() → L221-237
  _resolve_idle_timeout() → L240-248
  _resolve_wall_timeout() → L251-259
  build_execution_profile() → L262-273
  get_brain_adapter() → L276-284
  _execute_subprocess_streaming() → L287-428

### jane/standing_brain.py (568 lines)
  _PROVIDER = ... → L30
  _DEFAULT_MODELS = ... → L33
  _ENV_VAR_FOR_MODEL = ... → L39
  _get_model() → L46-55
  RESPONSE_TIMEOUT_SECS = ... → L59
  MAX_FAILURES = ... → L61
  MAX_TURNS_BEFORE_REFRESH = ... → L63
  CPU_THRESHOLD_PERCENT = ... → L65
  CPU_HOT_DURATION_SECS = ... → L67
  _log_crash() → L70-76
  class BrainProcess → L82-113
    alive() → L94-95
    idle_seconds() → L98-101
    cpu_percent() → L104-113
  class StandingBrainManager → L116-556
    __init__() → L119-122
    brain() → L125-127
    start() → L129-144
    _build_cmd() → L146-188
    _spawn() → L190-224
    send() → L226-313
    get_model() → L315-317
    health_check() → L319-331
    _reap_loop() → L333-366
    _read_ndjson_line() → L368-385
    _read_claude_line() → L387-410
    _read_claude_response() → L412-510
    _read_text_response() → L512-529
    _kill() → L531-546
    shutdown() → L548-556
  get_standing_brain_manager() → L564-568

### jane/persistent_claude.py (626 lines)
  _MODEL_CONTEXT_LIMITS = ... → L32
  _ROTATION_THRESHOLD = ... → L40
  _get_context_limit() → L43-50
  class ClaudePersistentSession → L54-84
    is_fresh() → L66-67
    estimated_tokens() → L70-76
    should_rotate() → L78-84
  _kill_process_tree() → L87-105
  class ClaudePersistentManager → L108-615
    __init__() → L115-119
    get() → L121-136
    end() → L138-143
    force_shutdown_all() → L145-159
    reap_stale_sessions() → L161-178
    run_turn() → L180-283
    _rotate_session() → L285-355
    _generate_session_summary() → L357-391
    _execute_streaming() → L407-497
    _process_ndjson_line() → L499-600
    prune_stale() → L602-615
  get_claude_persistent_manager() → L622-626

### jane/persistent_gemini.py (404 lines)
  ANSI_ESCAPE_RE = ... → L13
  PROMPT_PATTERNS = ... → L14
  NOISE_INDICATORS = ... → L17
  class _PendingTurn → L34-37
  class TurnInterruptedError → L40-43
    __init__() → L41-43
  class GeminiPersistentSession → L46-329
    __init__() → L47-62
    ensure_started() → L64-79
    _spawn_locked() → L81-122
    _close_locked() → L124-161
    shutdown() → L163-166
    run_turn() → L168-185
    _run_turn_once() → L187-216
    _clean_text() → L218-220
    _find_prompt() → L222-227
    _is_meaningful() → L229-236
    _emit_safe_delta() → L238-248
    _finish_turn_if_prompt_seen() → L250-266
    _read_loop() → L268-329
  class GeminiPersistentManager → L332-394
    __init__() → L336-339
    get() → L341-350
    shutdown() → L352-356
    end() → L359-360
    reap_stale_sessions() → L362-379
    _evict_oldest_locked() → L381-394
  get_gemini_persistent_manager() → L400-404

### jane/context_builder.py (798 lines)
  MAX_DOC_CHARS = ... → L15
  _CACHE_TTL = ... → L19
  _CACHE_MAX_ENTRIES = ... → L20
  _cached() → L22-36
  MAX_MEMORY_CHARS = ... → L37
  BASE_SYSTEM_PROMPT = ... → L38
  CODE_MAP_PROTOCOL = ... → L42
  TASK_KEYWORDS = ... → L57
  AI_CODING_KEYWORDS = ... → L62
  MUSIC_KEYWORDS = ... → L67
  PERSONAL_FACTS_FILE = ... → L70
  SIMPLE_FACTUAL_PREFIXES = ... → L71
  class JaneRequestContext → L77-80
  class PromptProfile → L84-92
  _read_text() → L95-101
  _read_json_summary() → L104-111
  ANAPHORIC_TOKENS = ... → L114
  _is_short_anaphoric() → L120-127
  _message_lower() → L130-131
  _is_task_related() → L134-136
  _should_include_conversation_summary() → L139-151
  _classify_prompt_profile() → L154-219
  _normalize_memory_summary() → L222-229
  _safe_get_memory_summary() → L232-271
  _load_personal_facts() → L274-282
  _format_fact_snippet() → L285-290
  _select_user_background() → L293-319
  _get_active_essence_personality() → L322-360
  _get_active_essence_chromadb_path() → L363-393
  _get_essence_tools_description() → L396-474
  _extract_tool_signatures() → L477-496
  CODE_MAP_CORE_PATH = ... → L499
  _load_code_map() → L502-504
  _build_system_sections() → L507-557
  _format_recent_history() → L560-585
  TTS_SPOKEN_BLOCK_INSTRUCTION = ... → L588
  build_jane_context() → L607-668
  build_jane_context_async() → L671-798

### jane/config.py (256 lines)
  _resolve_roots() → L16-39
  HOME_DIR = ... → L48
  USER_NAME = ... → L49
  ESSENCE_TEMPLATE_DIR = ... → L52
  AGENT_ROOT = ... → L56
  LOGS_DIR = ... → L57
  CONFIGS_DIR = ... → L58
  AMBER_DIR = ... → L59
  DATA_DIR = ... → L60
  CREDENTIALS_DIR = ... → L61
  ENV_FILE_PATH = ... → L62
  CHROMA_HOST = ... → L71
  CHROMA_PORT = ... → L72
  VECTOR_DB_DIR = ... → L73
  VECTOR_DB_USER_MEMORIES = ... → L74
  VECTOR_DB_SHORT_TERM = ... → L75
  VECTOR_DB_LONG_TERM = ... → L76
  VECTOR_DB_FILE_INDEX = ... → L77
  CHROMA_COLLECTION_USER_MEMORIES = ... → L80
  CHROMA_COLLECTION_SHORT_TERM = ... → L81
  CHROMA_COLLECTION_LONG_TERM = ... → L82
  CHROMA_COLLECTION_FILE_INDEX = ... → L83
  PROMPT_LIST_PATH = ... → L86
  ACCOMPLISHED_PATH = ... → L87
  LEDGER_DB_PATH = ... → L88
  JANITOR_REPORT = ... → L89
  _USER_NAME = ... → L92
  USER_ESSAY = ... → L93
  JANE_ESSAY = ... → L94
  AMBER_ESSAY = ... → L95
  CHIEH_ESSAY = ... → L96
  USER_STATE_PATH = ... → L99
  IDLE_STATE_PATH = ... → L100
  ACTIVE_QUEUE_PATH = ... → L101
  QUEUE_SESSION_PATH = ... → L102
  PENDING_UPDATES_PATH = ... → L103
  CONTEXT_SUMMARY_PATH = ... → L104
  JANE_SESSIONS_PATH = ... → L105
  JANE_SESSION_SUMMARY_DIR = ... → L106
  TASK_SPINE_PATH = ... → L107
  INTERRUPT_STACK_PATH = ... → L108
  PROMPT_QUEUE_LOG = ... → L111
  JOB_QUEUE_LOG = ... → L112
  JANE_WRAPPER_RAW_LOG = ... → L113
  AMBIENT_HEARTBEAT_LOG = ... → L114
  VAULT_TUNNEL_LOG = ... → L115
  ADK_VENV_PYTHON = ... → L118
  CLAUDE_BIN = ... → L119
  CODEX_BIN = ... → L120
  JANE_BRIDGE_ENV = ... → L121

### jane/session_summary.py (198 lines)
  MAX_TOPICS = ... → L10
  MAX_TOPIC_CHARS = ... → L11
  MAX_STATE_CHARS = ... → L12
  MAX_OPEN_LOOP_CHARS = ... → L13
  _WRITE_LOCK = ... → L14
  _summary_path() → L17-19
  load_session_summary() → L22-30
  format_session_summary() → L33-50
  update_session_summary_async() → L53-59
  _update_session_summary() → L62-103
  _extract_json_object() → L106-116
  _sanitize_summary() → L119-140
  _clean_field() → L143-146
  _fallback_summary() → L149-175
  _guess_topic_label() → L178-198

### jane/automation_runner.py (92 lines)
  class AutomationError → L9-10
  get_automation_provider() → L13-14
  run_automation_prompt() → L17-41
  _run_codex() → L44-92

### jane/jane_session_wrapper.py (529 lines)
  _REQUIRED_PYTHON = ... → L16
  CURRENT_DIR = ... → L20
  REPO_ROOT = ... → L21
  SKILLS_PATH = ... → L46
  ANSI_ESCAPE_RE = ... → L50
  DEFAULT_PROMPT_PATTERNS = ... → L51
  NOISE_INDICATORS = ... → L55
  class JaneSessionWrapper → L71-511
    __init__() → L72-102
    initialize() → L104-125
    handle_signal() → L127-147
    _log_raw() → L149-151
    _append_raw_log() → L153-159
    _log_writer_loop() → L161-185
    _is_meaningful_text() → L187-194
    _extract_prompt_split() → L196-201
    _normalize_output() → L203-204
    _schedule_commit() → L206-216
    write_to_master() → L218-227
    close_process() → L229-251
    spawn_gemini() → L253-280
    restart_gemini() → L282-297
    _commit_message() → L299-329
    read_from_gemini() → L331-384
    run_loop() → L386-466
    shutdown() → L468-477
    _shutdown_impl() → L479-511
  main() → L514-522

### jane/discord_bridge.py (381 lines)
  TOKEN = ... → L40
  CHANNEL_ID_STR = ... → L41
  DIAGNOSTIC_MODE = ... → L42
  BRAIN_MODE = ... → L43
  LOCAL_BRAIN = ... → L45
  TOKEN = ... → L51
  CHANNEL_ID = ... → L52
  clean_ansi() → L54-56
  class DiscordBridge → L58-355
    __init__() → L59-61
    on_ready() → L63-67
    create_session() → L69-76
    run_fallback() → L78-92
    handle_fallback_attachments() → L94-136
    on_message() → L138-355
  ensure_singleton() → L357-366
  start_bridge() → L368-371

### jane/task_spine.py (115 lines)
  _utc_now() → L8-9
  _read_json() → L12-19
  _write_json() → L22-25
  load_task_spine() → L28-45
  save_task_spine() → L48-51
  load_interrupt_stack() → L54-56
  save_interrupt_stack() → L59-60
  set_primary_goal() → L63-70
  set_current_step() → L73-80
  push_side_quest() → L83-101
  pop_side_quest() → L104-115

### jane/tts.py (105 lines)
  _CLEAN_PATTERNS = ... → L20
  _clean_for_speech() → L32-38
  class TTSEngine → L41-105
    __init__() → L42-45
    speak() → L47-58
    _speak_impl() → L60-92
    stop() → L94-101
    shutdown() → L103-105

### jane/audit_wrapper.py (61 lines)
  ROOT = ... → L6
  main() → L12-58

### jane/research_router.py (84 lines)
  RESEARCH_HINTS = ... → L13
  RESEARCH_VERBS = ... → L23
  RESEARCH_OBJECTS = ... → L36
  should_offload_research() → L50-58
  run_research_offload() → L61-84

### agent_skills/conversation_manager.py (743 lines)
  class silence_stderr_fd → L16-29
    __enter__() → L17-22
    __exit__() → L24-29
  TOKEN_ENCODING_MODEL = ... → L54
  COMPACTION_THRESHOLD_PERCENT = ... → L55
  ARCHIVIST_MODEL = ... → L56
  WRITEBACK_TIMING_LOG = ... → L57
  get_token_count() → L66-68
  _append_writeback_log() → L71-77
  class ConversationManager → L80-743
    __init__() → L95-136
    add_message() → L146-169
    add_messages() → L171-186
    get_stats() → L188-199
    close() → L201-233
    _reset_idle_timer() → L239-246
    _on_idle() → L248-269
    _run_archival() → L275-337
    _should_wait_for_smart_archival() → L339-341
    _select_archivist_model() → L343-347
    _triage_memory() → L349-384
    _promote_to_long_term() → L386-399
    _compact_context_window_if_needed() → L406-448
    _generate_summary() → L450-464
    _init_db() → L470-483
    _log_to_ledger() → L485-502
    _write_to_short_term() → L508-561
    _should_store_short_term_turn() → L564-611
    _release_short_term_handles() → L613-619
    _looks_like_code_edit() → L622-646
    _summarize_for_short_term() → L649-714
    _normalize_short_term_summary() → L717-743

### agent_skills/memory_retrieval.py (718 lines)
  class silence_stderr_fd → L10-23
    __enter__() → L11-16
    __exit__() → L18-23
  class MemoryRetrievalResult → L60-63
  class MemorySummaryCacheEntry → L67-71
  PERSONAL_QUERY_MARKERS = ... → L78
  PROJECT_QUERY_MARKERS = ... → L82
  LOW_SIGNAL_SHARED_PREFIXES = ... → L87
  _utcnow() → L99-100
  _normalize_query() → L103-104
  _get_query_embedding_fn() → L107-120
  _embed_query_text() → L123-139
  _cosine_similarity() → L142-150
  _prune_cache_entries() → L153-159
  _lookup_cached_memory_summary() → L162-177
  _CACHE_MAX_SESSIONS = ... → L180
  _store_cached_memory_summary() → L183-203
  invalidate_memory_summary_cache() → L206-211
  _is_expired() → L214-229
  _is_too_old() → L232-244
  _is_none_content() → L247-250
  _recency_label() → L253-270
  _fmt_memory() → L273-278
  _dedupe_fact_lines() → L281-290
  _query_collection() → L293-323
  _within_distance() → L326-332
  _is_file_index_record() → L335-355
  _is_file_query() → L358-386
  _classify_query_intent() → L389-397
  _is_low_signal_shared_memory() → L400-409
  build_memory_sections() → L412-626
  synthesize_memory_summary() → L629-675
  retrieve_memory_context() → L678-702
  get_memory_summary() → L705-718

### agent_skills/local_vector_memory.py (267 lines)
  class silence_stderr_fd → L11-24
    __enter__() → L12-17
    __exit__() → L19-24
  FORGETTABLE_TTL_DAYS = ... → L47
  class LocalVectorMemoryService → L50-267
    __init__() → L56-71
    _user_filter() → L73-74
    add_memory() → L76-110
    search_memory() → L112-225
    delete_memory() → L227-247
    _extract_text() → L249-252
    list_all_for_reorg() → L254-258
    add_session_to_memory() → L260-267

### agent_skills/prompt_queue_runner.py (680 lines)
  is_idle() → L59-97
  send_discord() → L101-103
  load_prompts() → L107-164
  mark_prompt() → L167-214
  add_prompt() → L217-236
  delete_prompt() → L239-284
  _renumber_prompts() → L287-303
  run_prompt() → L306-412
  log_queue_mutation() → L416-430
  log_to_memory() → L433-459
  prompt_summary() → L463-477
  archive_completed_prompts() → L481-554
  _acquire_run_lock() → L558-567
  main() → L570-676

### agent_skills/essence_builder.py (855 lines)
  VESSENCE_DATA_HOME = ... → L26
  STATE_PATH = ... → L30
  TEMPLATE_DIR = ... → L32
  SECTION_NAMES = ... → L41
  class EssenceInterviewState → L245-265
    to_dict() → L256-259
    from_dict() → L262-265
  save_state() → L273-277
  load_state() → L280-285
  clear_state() → L288-291
  _section_display_name() → L299-315
  _format_questions() → L318-328
  _section_intro() → L331-338
  start_interview() → L346-362
  process_answer() → L365-429
  _extract_essence_name() → L432-448
  get_progress() → L451-466
  generate_spec_document() → L474-489
  generate_manifest() → L492-593
  generate_personality_md() → L596-624
  build_essence_from_spec() → L632-740
  _create_folder_structure() → L743-759
  _extract_role_title() → L767-785
  _extract_list_from_answer() → L788-805
  _extract_quoted_strings() → L808-823
  _extract_section_fragment() → L826-834

### agent_skills/essence_loader.py (336 lines)
  class EssenceState → L32-40
  _log_to_work_log() → L50-56
  _get_tools_dir() → L59-65
  _get_essences_dir() → L68-72
  load_essence() → L79-141
  unload_essence() → L144-160
  delete_essence() → L163-208
  list_loaded_essences() → L211-213
  list_available_essences() → L216-276
  list_available() → L279-285
  main() → L292-332

### agent_skills/essence_runtime.py (427 lines)
  class EssenceState → L33-41
  class EssenceRuntime → L48-283
    __new__() → L53-57
    __init__() → L59-67
    load_essence() → L71-114
    unload_essence() → L116-125
    delete_essence() → L127-141
    get_loaded() → L145-147
    list_available() → L149-172
    get_capabilities_map() → L174-180
    route_to_essence() → L182-212
    set_active_essence() → L216-220
    get_active_essence() → L222-231
    _port_memory() → L235-283
  class JaneOrchestrator → L290-364
    __init__() → L293-294
    decompose_task() → L296-328
    execute_plan() → L330-364
  class CapabilityRegistry → L371-427
    __init__() → L375-376
    register() → L378-383
    unregister() → L385-391
    find_provider() → L393-396
    request_service() → L398-427

### agent_skills/essence_scheduler.py (182 lines)
  TOOLS_DIR = ... → L31
  STATE_FILE = ... → L34
  PYTHON_BIN = ... → L35
  IDLE_THRESHOLD_SECONDS = ... → L36
  _load_state() → L39-44
  _save_state() → L47-53
  _is_user_idle() → L56-67
  _matches_schedule() → L70-98
  run_scheduler() → L101-178

### agent_skills/index_vault.py (378 lines)
  _REQUIRED_PYTHON = ... → L28
  class _silence → L34-41
    __enter__() → L35-38
    __exit__() → L39-41
  VAULT_PATH = ... → L58
  HASH_INDEX_PATH = ... → L59
  SKIP_FILES = ... → L61
  SKIP_EXTENSIONS = ... → L62
  IMAGE_EXTENSIONS = ... → L64
  TEXT_EXTENSIONS = ... → L65
  READABLE_EXTENSIONS = ... → L71
  MAX_EXTRACT_CHARS = ... → L72
  get_collection() → L77-83
  is_already_tracked() → L86-96
  add_to_chromadb() → L99-116
  load_hash_index() → L121-127
  save_hash_index() → L130-131
  hash_file() → L134-139
  describe_image() → L144-166
  _extract_text_file() → L169-173
  _extract_pdf_text() → L176-194
  _extract_docx_text() → L197-218
  extract_readable_text() → L221-229
  _fallback_text_description() → L232-253
  describe_readable_file() → L256-286
  scan_vault() → L291-368

### agent_skills/janitor_memory.py (537 lines)
  DB_PATH = ... → L27
  SHORT_TERM_DB_PATH = ... → L28
  JANITOR_LOG = ... → L29
  VAULT_IMAGES_DIR = ... → L30
  MEMORY_JANITOR_MODEL = ... → L33
  _llm_json() → L36-81
  _is_expired() → L84-94
  purge_expired_short_term() → L97-126
  purge_expired_forgettable() → L130-131
  purge_old_forgettable_memories() → L134-161
  run_janitor() → L164-336
  LOG_MAX_AGE_DAYS = ... → L338
  purge_old_log_files() → L341-370
  IMAGE_EXTENSIONS = ... → L373
  cluster_vault_images() → L376-537

### agent_skills/janitor_system.py (110 lines)
  TEMP_FILES = ... → L13
  MAX_LOG_SIZE_MB = ... → L18
  LOG_RETENTION_DAYS = ... → L19
  LOG_PATTERNS = ... → L20
  clean_temp_files() → L22-29
  rotate_logs() → L31-41
  prune_old_logs() → L43-63
  _truncate_log_tail() → L66-84
  archive_completed_jobs() → L86-93

### agent_skills/nightly_audit.py (297 lines)
  ENV_FILE = ... → L30
  AUDIT_LOG_DIR = ... → L31
  SKILLS_DIR = ... → L32
  CONFIGS_DIR = ... → L33
  CRON_JOBS_DOC = ... → L34
  SKILLS_REGISTRY = ... → L35
  JANE_ARCH = ... → L36
  AMBER_ARCH = ... → L37
  MEMORY_ARCH = ... → L38
  LOG_FILE = ... → L40
  read_file() → L52-59
  read_script_body() → L62-68
  KEY_SCRIPTS = ... → L72
  get_crontab() → L82-87
  get_skill_files() → L90-91
  get_amber_tool_files() → L94-98
  IDLE_THRESHOLD_SECONDS = ... → L105
  ACTIVITY_INDICATORS = ... → L108
  is_user_idle() → L114-151
  _run_cmd() → L154-158
  run_audit_and_fix() → L161-238
  main() → L242-293

### agent_skills/audit_auto_fixer.py (498 lines)
  AUDIT_DIR = ... → L36
  FIX_REPORT_DIR = ... → L37
  MAX_FIXES_PER_RUN = ... → L38
  LOG_FILE = ... → L40
  SAFE_EXTENSIONS = ... → L54
  FORBIDDEN_PATTERNS = ... → L57
  find_latest_audit_report() → L64-73
  find_todays_audit_report() → L76-85
  is_safe_to_modify() → L89-107
  create_backup() → L110-121
  verify_python_syntax() → L124-135
  restore_from_backup() → L138-145
  analyze_audit_report() → L149-228
  apply_fix() → L232-311
  generate_fix_report() → L315-376
  main() → L380-494

### agent_skills/system_load.py (245 lines)
  MAX_PARALLEL = ... → L25
  CPU_THRESHOLD_HIGH = ... → L26
  CPU_THRESHOLD_MED = ... → L27
  MEM_FREE_MIN_GB = ... → L28
  NIGHT_START_HOUR = ... → L29
  NIGHT_END_HOUR = ... → L30
  _is_nighttime() → L33-40
  get_system_load() → L43-73
  recommended_parallelism() → L76-112
  should_defer() → L115-135
  wait_until_safe() → L138-165
  load_summary() → L168-179
  _CACHE_FILE = ... → L182
  _CACHE_TTL_SECS = ... → L183
  _cached_oneline() → L186-196
  _save_cache() → L199-206
  oneline() → L209-234

### agent_skills/fallback_query.py (185 lines)
  CODE_ROOT = ... → L11
  CAPABILITIES_PATH = ... → L24
  _USER_NAME = ... → L25
  IDENTITY_ESSAYS = ... → L26
  _load_file() → L32-37
  get_amber_persona() → L39-82
  get_jane_persona() → L84-96
  PERSONAS = ... → L98
  query_deepseek() → L103-120
  query_openai() → L122-138
  query_deepseek_local() → L140-148
  main() → L150-182

### agent_skills/generate_code_map.py (524 lines)
  VESSENCE_HOME = ... → L24
  CONFIGS_DIR = ... → L25
  CORE_PRIORITY_FILES = ... → L29
  CORE_SECONDARY_DIRS = ... → L103
  WEB_PRIORITY_FILES = ... → L115
  WEB_SECONDARY_DIRS = ... → L120
  ANDROID_ROOT = ... → L126
  SKIP_DIRS = ... → L130
  SKIP_FILES = ... → L131
  MARKER = ... → L133
  MAX_ENTRIES_PRIORITY = ... → L135
  MAX_ENTRIES_SECONDARY = ... → L136
  count_lines() → L143-148
  index_python_file() → L151-188
  index_html_file() → L191-217
  index_kotlin_file() → L220-282
  _index_file() → L285-299
  _should_skip() → L302-307
  _cap_entries() → L314-326
  generate_core_map() → L329-381
  generate_web_map() → L384-429
  generate_android_map() → L432-470
  _write_map() → L477-491
  main() → L494-520

### agent_skills/ambient_heartbeat.py (395 lines)
  SPEC_PATH = ... → L37
  CLAUDE_SESSIONS = ... → L38
  ENV_FILE = ... → L39
  LOG_FILE = ... → L40
  RESEARCH_CACHE = ... → L41
  IDLE_MINUTES = ... → L42
  MODEL = ... → L43
  RESEARCH_TOPICS = ... → L47
  is_user_active() → L124-139
  load_cache() → L143-147
  save_cache() → L150-152
  is_stale() → L155-160
  web_search() → L164-166
  synthesize_with_automation() → L170-187
  append_research_to_spec() → L191-217
  check_implementation_readiness() → L221-260
  implement_task() → L263-291
  mark_task_complete() → L294-302
  main() → L310-391

### agent_skills/ambient_task_research.py (331 lines)
  SPEC_PATH = ... → L28
  CLAUDE_SESSIONS = ... → L29
  ENV_FILE = ... → L30
  LOG_FILE = ... → L31
  RESEARCH_CACHE = ... → L32
  IDLE_MINUTES = ... → L33
  MAX_TASKS_PER_RUN = ... → L34
  CACHE_TTL_DAYS = ... → L35
  MODEL = ... → L36
  is_user_active() → L52-67
  extract_unchecked_tasks() → L71-106
  load_cache() → L110-117
  save_cache() → L120-122
  task_cache_key() → L125-127
  is_stale() → L130-138
  build_search_query() → L142-174
  web_search() → L178-180
  synthesize_with_openai() → L184-229
  main() → L237-327

### agent_skills/gemma_summarize.py (181 lines)
  _REQUIRED_PYTHON = ... → L19
  TRANSCRIPT_DIR = ... → L27
  SHORT_TERM_DB = ... → L31
  GEMMA_MODEL = ... → L32
  TURNS_TO_INCLUDE = ... → L33
  MIN_TEXT_LEN = ... → L34
  silence_stderr() → L37-43
  restore_stderr() → L46-48
  extract_text_from_content() → L51-69
  read_recent_turns() → L72-105
  summarize_with_gemma() → L108-122
  save_to_short_term() → L125-152
  main() → L155-177

### agent_skills/qwen_orchestrator.py (260 lines)
  class QwenOrchestrator → L27-175
    __init__() → L28-43
    check_hardware_lock() → L45-52
    query_qwen() → L54-74
    update_state() → L76-80
    stage_1_spec() → L82-91
    stage_2_research() → L93-98
    stage_3_dependency() → L100-130
    stage_4_harvest() → L132-154
    stage_5_implement() → L156-161
    stage_6_audit() → L163-168
    stage_7_validate() → L170-175

### agent_skills/validate_essence.py (161 lines)
  REQUIRED_MANIFEST_FIELDS = ... → L18
  REQUIRED_MODEL_FIELDS = ... → L31
  REQUIRED_CAPABILITIES_FIELDS = ... → L32
  REQUIRED_UI_FIELDS = ... → L33
  REQUIRED_PATHS = ... → L35
  validate_manifest() → L43-91
  validate_folder_structure() → L94-113
  validate_essence() → L116-139
  main() → L142-157

### agent_skills/show_job_queue.py (113 lines)
  QUEUE_DIR = ... → L8
  load_jobs() → L14-60
  PRIORITY_LABEL = ... → L63
  PRIORITY_SORT = ... → L69
  format_table() → L72-104
  main() → L107-109

### amber/agent.py (273 lines)
  _extract_user_query() → L45-59
  _extract_session_id() → L62-73
  _fetch_ambient_memory() → L76-86
  unified_instruction_provider() → L89-149
  create_app() → L151-271

### amber/logic/agent_logic.py (134 lines)
  ANALYZER_MODEL = ... → L20
  FACT_EXTRACTION_PROMPT = ... → L28
  detect_facts_and_contradictions() → L47-134

### amber/tools/vault_tools.py (1092 lines)
  class VaultSaveTool → L199-375
  class VaultSendFileTool → L377-472
  class VaultDeleteTool → L474-516
  class VaultReadFileTool → L518-603
  class VaultAnalyzePdfTool → L606-678
  class TerminalTool → L681-737
  class VaultSearchTool → L739-767
  class MemorySaveTool → L769-812
  class MemoryUpdateTool → L815-852
  class VaultTunnelURLTool → L854-888
  class VaultReorganizeTool → L891-913
  class VaultIndexTool → L916-959
  class VaultFindAudioTool → L962-1007
  class VaultPlaylistTool → L1010-1092
  _add_fact() → L37-45
  _search_memory() → L48-58
  _delete_memory_by_query() → L61-81
  _looks_like_garbage_filename() → L83-94
  _generate_descriptive_filename() → L97-121
  _get_hash_index_path() → L127-128
  _load_hash_index() → L131-138
  _save_hash_index() → L141-144
  _hash_content() → L147-155
  _check_duplicate() → L158-168
  _register_hash() → L171-180
  get_file_category() → L183-197
    __init__() → L202-214
    _get_declaration() → L216-231
    run_async() → L233-375
    __init__() → L380-389
    _get_declaration() → L391-402
    process_llm_request() → L405-427
    run_async() → L429-472
    __init__() → L477-486
    _get_declaration() → L488-500
    run_async() → L502-516
    __init__() → L521-530
    _get_declaration() → L532-549
    run_async() → L551-603
    __init__() → L609-619
    _get_declaration() → L621-633
    run_async() → L635-678
    __init__() → L684-690
    _get_declaration() → L692-704
    run_async() → L706-737
    __init__() → L742-747
    _get_declaration() → L749-760
    run_async() → L762-767
    __init__() → L772-782
    _get_declaration() → L784-797

### amber/tools/local_computer.py (332 lines)
  class LocalComputer → L38-332
    __init__() → L43-50
    _get_omni() → L52-55
    _launch_browser() → L57-65
    screen_size() → L67-69
    current_state() → L71-132
    get_crop() → L134-145
    open_web_browser() → L147-150
    click_at() → L152-157
    hover_at() → L159-162
    type_text_at() → L164-177
    scroll_document() → L179-185
    scroll_at() → L187-193
    wait() → L195-197
    go_back() → L199-204
    go_forward() → L206-211
    search() → L213-216
    navigate() → L218-223
    key_combination() → L225-236
    drag_and_drop() → L238-246
    list_windows() → L248-271
    focus_window() → L273-275
    find_and_focus_window() → L277-311
    _get_active_window_title() → L313-329
    environment() → L331-332

### amber/tools/speech_tools.py (117 lines)
  ROOT = ... → L9
  VOICE_MAP = ... → L18
  DEFAULT_VOICE = ... → L29
  class TextToSpeechTool → L32-117
    __init__() → L38-50
    _get_declaration() → L52-70
    run_async() → L72-117

### vault_web/main.py (1167 lines)
  class ChatMessage → L886-889
  GET /health → L95
  GET /sw.js → L100
  GET /manifest.webmanifest → L105
  GET / → L183
  GET /share → L208
  GET /essences → L216
  GET /jane → L221
  GET /settings/devices → L250
  GET /chat → L262
  GET /auth/google → L293
  GET /auth/google/callback → L305
  POST /api/auth/google-token → L331
  POST /api/auth/verify-share → L367
  POST /api/auth/verify-otp → L377
  POST /api/auth/logout → L388
  GET /api/auth/devices → L399
  DELETE /api/auth/devices/{device_id} → L404
  POST /api/auth/check → L410
  POST /api/auth/is-new-device → L423
  GET /api/settings/personality → L431
  POST /api/settings/personality → L444
  GET /api/app/latest-version → L458
  GET /downloads/{filename} → L468
  GET /api/files → L495
  GET /api/files/list/{path:path} → L505
  GET /api/files/meta/{path:path} → L535
  PATCH /api/files/description/{path:path} → L540
  GET /api/files/thumbnail/{path:path} → L547
  GET /api/files/serve/{path:path} → L556
  GET /api/files/changes → L612
  GET /api/files/find → L617
  GET /api/files/content/{path:path} → L628
  PUT /api/files/content/{path:path} → L645
  GET /api/shares → L665
  POST /api/shares → L670
  DELETE /api/shares/{share_id} → L678
  GET /api/playlists → L686
  GET /api/playlists/{playlist_id} → L691
  POST /api/playlists → L699
  PUT /api/playlists/{playlist_id} → L706
  DELETE /api/playlists/{playlist_id} → L714
  POST /api/files/upload → L736
  POST /api/files/upload/single → L840
  POST /api/amber/chat → L893
  POST /api/amber/chat/stream → L921
  GET /api/amber/tunnel-url → L988
  POST /api/amber/unlock → L996
  GET /api/essences → L1041
  GET /api/essences/active → L1070

### vault_web/files.py (297 lines)
  THUMBNAIL_SIZE = ... → L23
  ICON_MAP = ... → L25
  IMAGE_EXTS = ... → L42
  VIDEO_EXTS = ... → L43
  AUDIO_EXTS = ... → L44
  TEXT_EXTS = ... → L45
  TEXT_SIZE_LIMIT = ... → L51
  is_text() → L54-55
  safe_vault_path() → L58-64
  ext() → L67-68
  file_icon() → L71-72
  is_image() → L75-76
  is_video() → L79-80
  is_audio() → L83-84
  is_text() → L86-87
  get_mime() → L90-92
  make_descriptive_filename() → L95-107
  build_file_index_document() → L110-114
  upsert_file_index_entry() → L117-143
  list_directory() → L146-195
  get_file_metadata() → L198-251
  update_description() → L254-264
  get_last_change_timestamp() → L267-272
  generate_thumbnail() → L275-289
  _human_size() → L292-297

### vault_web/auth.py (251 lines)
  MAX_ATTEMPTS = ... → L21
  LOCKOUT_MINUTES = ... → L22
  SESSION_TRUSTED_DAYS = ... → L23
  TOTP_SECRET = ... → L25
  get_allowed_emails() → L28-30
  is_allowed_email() → L33-38
  user_id_from_email() → L41-43
  default_user_id() → L46-53
  get_totp() → L56-57
  send_otp_discord() → L61-63
  create_otp() → L66-68
  verify_otp() → L71-89
  get_totp_uri() → L92-95
  _record_failed_attempt() → L98-112
  unlock_ip() → L115-121
  create_session() → L124-137
  get_session_user() → L140-151
  validate_session() → L154-170
  is_device_trusted() → L173-178
  register_trusted_device() → L181-198
  get_trusted_device_by_id() → L201-213
  get_trusted_device_by_fingerprint() → L216-228
  get_trusted_devices() → L231-234
  revoke_device() → L237-244
  device_fingerprint_from_request() → L247-251

### vault_web/amber_proxy.py (182 lines)
  BRAIN_MODE = ... → L22
  LOCAL_BRAIN = ... → L23
  _unwrap_local_text() → L26-40
  ADK_BASE = ... → L42
  WEB_SESSION_PREFIX = ... → L43
  ensure_session() → L46-54
  _vault_rel() → L57-61
  send_message() → L64-160
  get_tunnel_url() → L163-182

### vault_web/oauth.py (62 lines)
  _normalized_email() → L8-9
  _configured_value() → L12-13
  _configured_public_base_url() → L16-21
  google_oauth_configured() → L24-30
  build_external_url() → L43-51
  allowed_email() → L54-62

### vault_web/database.py (83 lines)
  DB_PATH = ... → L6
  get_db() → L12-18
  init_db() → L21-83

### vault_web/playlists.py (75 lines)
  list_playlists() → L9-16
  get_playlist() → L19-32
  create_playlist() → L35-48
  update_playlist() → L51-70
  delete_playlist() → L73-75

### onboarding/main.py (354 lines)
  DATA_DIR = ... → L20
  VAULT_DIR = ... → L21
  ENV_FILE = ... → L22
  PROFILE = ... → L23
  _read_env_values() → L29-39
  GET /health → L45
  is_first_run() → L51-57
  GET / → L61
  POST /api/setup → L89
  JANE_URL = ... → L140
  POST /api/cli-login → L144
  GET /api/cli-login/status → L158
  GET /interview → L171
  POST /api/interview/submit → L176
  _build_profile() → L185-231
  POST /api/settings → L237
  POST /api/validate-key → L286
  GET /success → L343

### startup_code/jane_bootstrap.py (200 lines)
  DATA_ROOT = ... → L21
  VESSENCE_ROOT = ... → L22
  DOCS_DIR = ... → L23
  VECTOR_ROOT = ... → L24
  USER_MEMORIES = ... → L26
  SHORT_TERM = ... → L27
  LONG_TERM = ... → L28
  QUERY_SET = ... → L30
  class MemoryStore → L39-42
  read_text() → L45-48
  first_paragraph() → L51-56
  parse_ts() → L59-71
  age_label() → L74-84
  get_collection() → L87-89
  collection_count() → L92-96
  recent_entries() → L99-118
  query_entries() → L121-142
  main() → L145-196

### startup_code/memory_daemon.py (162 lines)
  ROOT = ... → L19
  CACHE_TTL_SECS = ... → L32
  CACHE_MAX_ENTRIES = ... → L33
  CACHE_SIMILARITY_THRESHOLD = ... → L34
  _cosine_similarity() → L40-48
  _prune_cache() → L51-55
  _lookup_cache() → L58-68
  _store_cache() → L71-81
  load_models() → L86-93
  GET /query → L98
  GET /health → L130
  MAX_MEMORY_MB = ... → L137
  _memory_watchdog() → L139-148
  POST /cache/invalidate → L154

### startup_code/regenerate_jane_context.py (160 lines)
  BASE = ... → L29
  DATA_ROOT = ... → L30
  VAULT_ROOT = ... → L31
  OUTPUT = ... → L32
  read_file() → L34-39
  extract_section() → L41-56
  extract_amber_capabilities() → L58-64
  extract_cron_jobs() → L66-92
  extract_projects() → L94-101
  build_context() → L103-154

### startup_code/seed_chromadb.py (173 lines)
  _REQUIRED_PYTHON = ... → L28
  _resolve_paths() → L52-64
  load_seeds() → L67-81
  seed_collection() → L84-121
  write_flag() → L124-133
  main() → L136-169

### startup_code/usb_sync.py (420 lines)
  HOME = ... → L25
  AMBIENT_BASE = ... → L26
  VESSENCE_HOME = ... → L27
  VESSENCE_DATA_HOME = ... → L28
  VAULT_HOME = ... → L29
  SOURCES = ... → L31
  EXCLUDES = ... → L45
  SNAPSHOT_INTERVAL_DAYS = ... → L61
  SNAPSHOT_RETENTION_DAYS = ... → L62
  STALE_TOP_LEVEL_ENTRIES = ... → L63
  ADK_PYTHON = ... → L76
  ADK_PIP = ... → L77
  find_usb_mount() → L81-87
  rsync_source() → L92-130
  should_take_snapshot() → L135-146
  take_snapshot() → L149-164
  rotate_snapshots() → L167-182
  remove_stale_layout_entries() → L185-198
  run() → L203-207
  write_restore_docs() → L210-326
  main() → L331-416

### startup_code/usb_rotation.py (329 lines)
  _DEFAULT_USB = ... → L21
  find_usb_mount() → L23-28
  USB_MOUNT_POINT = ... → L30
  SOURCES = ... → L33
  EXCLUDES = ... → L46
  ADK_PYTHON = ... → L61
  ADK_PIP = ... → L62
  run() → L66-70
  generate_manifest() → L73-267
  main() → L271-325

### startup_code/build_docker_bundle.py (413 lines)
  VERSION = ... → L12
  REPO_ROOT = ... → L14
  MARKETING_ROOT = ... → L15
  DOWNLOADS_DIR = ... → L16
  INSTALLERS_DIR = ... → L17
  PLATFORMS = ... → L19
  reset_dir() → L45-48
  copy_tree() → L51-52
  build_readme() → L55-122
  build_platform_package() → L125-199
  _match_image_bins() → L213-220
  _parse_compose_services() → L223-240
  validate() → L243-385
  build_all() → L388-409

### startup_code/query_live_memory.py (136 lines)
  ROOT = ... → L16
  LIVE_VECTOR_ROOT = ... → L24
  CACHE_FILE = ... → L29
  CACHE_TTL_SECS = ... → L30
  CACHE_MAX_ENTRIES = ... → L31
  CACHE_SIMILARITY_THRESHOLD = ... → L32
  _cosine_similarity() → L35-43
  _embed_query() → L46-51
  _load_cache() → L54-62
  _save_cache() → L65-71
  _lookup_cache() → L74-82
  main() → L85-132

### startup_code/claude_smart_context.py (121 lines)
  CODE_MAP_KEYWORDS = ... → L37
  DATA_ROOT = ... → L50
  VESSENCE_ROOT = ... → L51
  JANE_IDENTITY_COMPACT = ... → L54
  OPERATIONAL_RULES = ... → L63
  _read_prompt_from_stdin() → L70-75
  _get_task_state() → L78-80
  main() → L83-117

## Other Files

### jane_web/permission_broker.py (166 lines)
  PERMISSION_TIMEOUT_SECONDS = ... → L25
  class PermissionRequest → L29-37
  class PermissionBroker → L40-151
    __init__() → L43-46
    register_emitter() → L50-52
    unregister_emitter() → L54-56
    create_request() → L60-99
    wait_for_response() → L101-112
    resolve() → L116-126
    get_pending() → L130-132
    get_all_pending() → L134-136
    cleanup_stale() → L138-151
  get_permission_broker() → L160-166

### jane/hooks/permission_gate.py (139 lines)
  APPROVAL_REQUIRED = ... → L22
  READONLY_PREFIXES = ... → L25
  DANGEROUS_PATTERNS = ... → L33
  JANE_WEB_PORT = ... → L41
  PERMISSION_URL = ... → L42
  TIMEOUT_SECONDS = ... → L43
  _is_readonly_bash() → L46-58
  _is_dangerous() → L61-64
  _request_permission() → L67-100
  main() → L103-135

### agent_skills/add_fact.py (84 lines)
  _REQUIRED_PYTHON = ... → L23
  class _silence → L27-36
    __enter__() → L28-32
    __exit__() → L33-36
  add_fact() → L47-71

### agent_skills/add_forgettable_memory.py (116 lines)
  _REQUIRED_PYTHON = ... → L25
  class silence_stderr_fd → L30-43
    __enter__() → L31-36
    __exit__() → L38-43
  add_forgettable_memory() → L54-94

### agent_skills/backfill_file_index_descriptions.py (138 lines)
  _REQUIRED_PYTHON = ... → L8
  class _silence → L13-25
    __enter__() → L14-18
    __exit__() → L20-25
  _resolve_path() → L41-52
  _extract_path_from_doc() → L55-60
  _mime_for_path() → L63-65
  _build_memory_text() → L68-69
  backfill() → L72-128

### agent_skills/browser_skill.py (59 lines)
  class BrowserContextManager → L8-59
    __init__() → L9-13
    start() → L15-20
    stop() → L22-26
    get_compact_context() → L28-49
    navigate() → L51-54
    get_screenshot() → L56-59

### agent_skills/check_continuation.py (125 lines)
  ACTIVE_QUEUE_FILE = ... → L28
  IDLE_STATE_FILE = ... → L29
  IDLE_THRESHOLD = ... → L30
  JOBS_DIR = ... → L31
  PRIORITY_MAP = ... → L33
  get_next_pending_job() → L36-70
  queue_is_empty() → L73-79
  is_user_idle() → L82-90
  main() → L93-121

### agent_skills/check_for_updates.py (70 lines)
  NOTIFY_FILE = ... → L15
  CURRENT_MODEL = ... → L22
  check_for_new_models() → L24-67

### agent_skills/claude_cli_llm.py (89 lines)
  _build_command() → L20-40
  completion() → L43-73
  completion_smart() → L76-78
  completion_json() → L81-89

### agent_skills/cron_utils.py (65 lines)
  send_discord() → L18-44
  load_cron_env() → L47-65

### agent_skills/evolve_code_map_keywords.py (340 lines)
  VESSENCE_HOME = ... → L24
  LEDGER_DB = ... → L27
  JANE_PROXY_PATH = ... → L32
  CONTEXT_BUILDER_PATH = ... → L33
  CODE_MAP_PATH = ... → L34
  PYTHON_BIN = ... → L36
  STOPWORDS = ... → L47
  get_todays_user_messages() → L100-118
  parse_tuple_from_file() → L124-135
  load_all_keywords() → L138-145
  load_code_map_names() → L151-180
  is_code_related() → L186-195
  extract_candidates() → L201-240
  update_keywords_file() → L246-279
  restart_jane_web() → L285-298
  main() → L304-336

### agent_skills/generate_identity_essay.py (152 lines)
  DB_PATH = ... → L13
  _USER_NAME = ... → L14
  ESSAY_PATH = ... → L15
  JANE_ESSAY_PATH = ... → L16
  AMBER_ESSAY_PATH = ... → L17
  update_essay() → L21-149

### agent_skills/git_backup.py (115 lines)
  REPO_DIR = ... → L15
  LOG_FILE = ... → L16
  REMOTE_NAME = ... → L17
  run_cmd() → L31-36
  get_commit_summary() → L38-64
  main() → L66-112

### agent_skills/janitor_logs.py (114 lines)
  LOG_ROOT = ... → L16
  REPORT_PATH = ... → L17
  DEFAULT_MAX_BYTES = ... → L18
  DEFAULT_BACKUP_COUNT = ... → L19
  namer() → L25-27
  rotator() → L29-39
  get_rotating_logger() → L41-57
  run_janitor() → L59-111

### agent_skills/job_queue_runner.py (407 lines)
  JOBS_DIR = ... → L42
  COMPLETED_DIR = ... → L43
  is_idle() → L54-72
  PRIORITY_MAP = ... → L76
  _parse_job() → L79-89
  load_pending_jobs() → L92-110
  get_next_pending_job() → L113-115
  _set_status() → L119-129
  mark_job_complete() → L132-140
  mark_job_incomplete() → L143-145
  build_prompt() → L149-162
  run_job() → L166-262
  log_to_memory() → L266-284
  add_job_from_text() → L288-331
  _acquire_run_lock() → L335-343
  main() → L347-403

### agent_skills/job_queue_utils.py (92 lines)
  JOBS_DIR = ... → L16
  COMPLETED_DIR = ... → L20
  ARCHIVE_THRESHOLD = ... → L21
  list_jobs() → L24-49
  archive_completed() → L52-77

### agent_skills/notify_updates.py (57 lines)
  NOTIFY_FILE = ... → L15
  DISCORD_TOKEN = ... → L18
  CHANNEL_ID = ... → L19
  send_notification() → L21-54

### agent_skills/qwen_query.py (50 lines)
  check_ollama() → L11-17
  query_qwen() → L19-42

### agent_skills/research_analyzer.py (56 lines)
  analyze_search_results() → L11-47

### agent_skills/research_assistant.py (65 lines)
  analyze_research() → L12-57

### agent_skills/run_queue_next.py (81 lines)
  JOBS_DIR = ... → L24
  PRIORITY_MAP = ... → L25
  get_pending_jobs() → L28-56
  main() → L59-77

### agent_skills/save_context_summary.py (91 lines)
  PYTHON = ... → L27
  QWEN_SCRIPT = ... → L28
  ADD_MEMORY = ... → L29
  CONTEXT_LOG = ... → L30
  ask_qwen_summarize() → L33-50
  main() → L53-87

### agent_skills/screen_dimmer.py (94 lines)
  LAT = ... → L13
  LON = ... → L14
  DISPLAY_OUTPUT = ... → L15
  DIM_BRIGHTNESS = ... → L16
  get_sunset_time() → L19-35
  get_connected_outputs() → L38-49
  dim_screen() → L52-62
  main() → L65-90

### agent_skills/user_manager.py (86 lines)
  USERS_DIR = ... → L16
  PERSONALITIES_DIR = ... → L17
  VALID_PERSONALITIES = ... → L20
  get_user_config() → L23-28
  create_user_space() → L31-43
  set_user_personality() → L46-55
  get_personality_content() → L58-65
  list_personalities() → L68-76
  ensure_user_space_from_email() → L79-86

### agent_skills/vault_tunnel_url.py (55 lines)
  LOG_PATHS = ... → L12
  FIXED_VAULT_URL = ... → L18
  FIXED_JANE_URL = ... → L19
  get_tunnel_url() → L22-42
  main() → L45-51

### agent_skills/web_search_utils.py (87 lines)
  web_search() → L22-33
  _tavily_search() → L36-67
  _ddg_search() → L70-87

### agent_skills/work_log_tools.py (74 lines)
  _get_activity_log_path() → L15-23
  log_activity() → L26-56
  get_recent_activities() → L59-74

### amber/tools/research_tools.py (54 lines)
  class TechnicalResearchTool → L21-54
    __init__() → L26-30
    __call__() → L32-54

### startup_code/claude_full_startup_context.py (55 lines)
  DATA_ROOT = ... → L13
  VESSENCE_ROOT = ... → L14
  VAULT_ROOT = ... → L15
  DOCS = ... → L17
  read_doc() → L32-39
  main() → L42-51

### startup_code/session_memory_dedup.py (125 lines)
  _entry_key() → L22-24
  _load_seen() → L27-33
  _save_seen() → L36-40
  _cleanup_old_caches() → L43-51
  dedup() → L54-102
  main() → L105-121

### startup_code/usb_backup.py (137 lines)
  get_mounted_drives() → L8-34
  get_total_size() → L36-52
  main() → L54-134
