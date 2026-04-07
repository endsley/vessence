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
jane_web/     → FastAPI web server (routes, auth, streaming, SSE) — listens on 8081
jane/         → Brain adapters, persistent sessions, context builder
vault_web/    → Shared library modules (auth, files, playlists, share, database,
                oauth) + HTML templates (templates/jane.html, app.html, briefing.html)
                — NO standalone FastAPI app (retired in v0.1.71).
agent_skills/ → Standalone scripts (classifier, memory, TTS, queue, essence runtime)
essences/     → Self-contained AI agent packages
android/      → Native Android app (Kotlin, Jetpack Compose)
relay_server/ → Multi-user tunnel relay (port 8082) — WebSocket router for Docker
                clients connecting to jane.vessences.com
```

Note: `amber/` (Google ADK agent) and `jane/discord_bridge.py` were retired in
v0.1.71 when Jane became the sole agent. See `configs/Amber_architecture.md`
for historical context.

<!-- AUTO-GENERATED BELOW — do not edit below this line -->

# Code Map — Core (Python Backend)
_Auto-generated on 2026-04-05 01:57 UTC by `generate_code_map.py`_

## Priority Files

### jane_web/jane_proxy.py (1653 lines)
  CODE_MAP_KEYWORDS = ... → L26
  _maybe_prepend_code_map() → L69-73
  class JaneSessionState → L77-85
  _MAX_SESSIONS = ... → L89
  REQUEST_TIMING_LOG = ... → L90
  PROMPT_DUMP_LOG = ... → L91
  SESSION_IDLE_TTL_SECONDS = ... → L92
  _PREFETCH_CACHE_MAX = ... → L96
  PREFETCH_TTL = ... → L97
  run_prefetch_memory() → L100-136
  get_prefetch_result() → L139-144
  _get_brain_name() → L147-160
  _session_log_id() → L163-164
  _get_timeout_seconds() → L167-168
  _get_execution_profile() → L171-172
  _use_gemini_api() → L175-177
  _use_persistent_gemini() → L179-181
  _use_persistent_claude() → L184-185
  _use_persistent_codex() → L188-189
  _get_web_chat_model() → L192-211
  _prune_stale_sessions() → L214-227
  _execute_brain_sync() → L230-296
  _execute_brain_stream() → L299-380
  _get_session() → L383-399
  _FOLLOWUP_FILE_MARKERS = ... → L402
  _resolve_file_context() → L424-433
  _message_for_persistence() → L436-440
  prewarm_session() → L443-494
  _await_prewarm_if_running() → L497-514
  end_session() → L517-589
  _progress_snapshot() → L592-606
  _LOG_MAX_BYTES = ... → L609
  _truncate_log_if_needed() → L612-619
  _log_stage() → L622-633
  _log_start() → L636-644
  _dump_prompt() → L647-679
  _persist_turns_async() → L682-730
  send_message() → L738-872
  _pick_ack() → L875-1141
  stream_message() → L1144-1636
  _log_chat_to_work_log() → L1639-1641
  get_active_brain() → L1644-1646
  get_tunnel_url() → L1649-1653

### jane_web/main.py (3912 lines)
  class ChatMessage → L1901-1906
  class SessionControl → L1909-1910
  class SwitchProviderRequest → L1971-1972
  GET /health → L460
  GET /sw.js → L466
  GET /manifest.webmanifest → L471
  GET / → L597
  GET /share → L623
  GET /vault → L628
  GET /guide → L651
  GET /architecture → L657
  GET /chat → L663
  GET /essences → L686
  GET /worklog → L690
  GET /api/job-queue → L694
  GET /api/job-queue/completed → L708
  GET /briefing → L722
  POST /api/crash-report → L727
  POST /api/device-diagnostics → L738
  GET /api/device-diagnostics → L752
  GET /settings/devices → L771
  GET /downloads/{filename} → L777
  POST /api/tts/generate → L867
  GET /api/app/settings → L951
  PUT /api/app/settings → L957
  POST /api/app/installed → L967
  GET /api/app/latest-version → L979
  GET /auth/google → L1010
  GET /auth/google/callback → L1022
  POST /api/auth/google-token → L1050
  POST /api/auth/verify-share → L1088
  POST /api/auth/verify-otp → L1098
  POST /api/auth/logout → L1123
  GET /api/auth/devices → L1135
  DELETE /api/auth/devices/{device_id} → L1140
  POST /api/auth/check → L1146
  POST /api/auth/is-new-device → L1159
  GET /api/jane/announcements → L1165
  GET /api/settings/models → L1191
  POST /api/settings/models → L1224
  GET /api/jane/live → L1278
  POST /api/jane/prefetch-memory → L1312
  GET /api/files → L1342
  GET /api/files/list/{path:path} → L1352
  GET /api/files/meta/{path:path} → L1382
  PATCH /api/files/description/{path:path} → L1387
  GET /api/files/thumbnail/{path:path} → L1393
  GET /api/files/serve/{path:path} → L1402
  GET /api/files/changes → L1451
  GET /api/files/find → L1456

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

### jane/brain_adapters.py (470 lines)
  _load_runtime_env_keys() → L12-35
  _kill_pgroup() → L38-48
  class ExecutionProfile → L52-56
  PROVIDER_TIMEOUT_DEFAULTS = ... → L59
  PROVIDER_IDLE_DEFAULTS = ... → L66
  PROVIDER_WALL_DEFAULTS = ... → L73
  class BrainAdapterError → L81-82
  class BrainAdapter → L85-142
    __init__() → L90-91
    _missing_env() → L93-98
    build_command() → L100-101
    parse_output() → L103-104
    execute_stream() → L106-109
    execute() → L111-142
  class GeminiBrainAdapter → L145-170
    _missing_env() → L151-160
    build_command() → L162-167
    execute_stream() → L169-170
  class ClaudeBrainAdapter → L173-195
    build_command() → L182-188
    execute() → L190-192
    execute_stream() → L194-195
  class OpenAIBrainAdapter → L198-254
    execute() → L203-254
  class CodexBrainAdapter → L257-260
  resolve_timeout_seconds() → L263-279
  _resolve_idle_timeout() → L282-290
  _resolve_wall_timeout() → L293-301
  build_execution_profile() → L304-315
  get_brain_adapter() → L318-326
  _execute_subprocess_streaming() → L329-470

### jane/standing_brain.py (930 lines)
  ALL_PROVIDERS = ... → L61
  _provider_uses_standing_process() → L64-66
  _classify_stderr_line() → L69-78
  _available_providers() → L81-83
  _PROVIDER = ... → L88
  _DEFAULT_MODELS = ... → L91
  _ENV_VAR_FOR_MODEL = ... → L97
  _configured_provider() → L104-121
  _get_model() → L124-133
  RESPONSE_TIMEOUT_SECS = ... → L138
  _READ_CHUNK_TIMEOUT = ... → L141
  MAX_FAILURES = ... → L143
  MAX_TURNS_BEFORE_REFRESH = ... → L145
  CPU_THRESHOLD_PERCENT = ... → L147
  CPU_HOT_DURATION_SECS = ... → L149
  _log_crash() → L152-158
  class BrainProcess → L164-197
    alive() → L178-179
    idle_seconds() → L182-185
    cpu_percent() → L188-197
  class StandingBrainManager → L200-918
    __init__() → L203-207
    brain() → L210-212
    start() → L214-232
    _build_cmd() → L234-276
    _spawn() → L278-325
    _read_stderr() → L327-364
    set_provider_error_callback() → L366-368
    get_last_provider_error() → L370-374
    clear_provider_error() → L376-379
    switch_provider() → L381-494
    _update_env_file() → L497-526
    send() → L528-641
    get_model() → L643-645
    health_check() → L647-659
    _reap_loop() → L661-694
    _read_ndjson_line() → L696-727
    _read_claude_line() → L729-761
    _read_claude_response() → L763-869
    _read_text_response() → L871-888
    _kill() → L890-908
    shutdown() → L910-918
  get_standing_brain_manager() → L926-930

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

### jane/persistent_gemini.py (417 lines)
  ANSI_ESCAPE_RE = ... → L13
  PROMPT_PATTERNS = ... → L14
  NOISE_INDICATORS = ... → L17
  class _PendingTurn → L34-37
  class TurnInterruptedError → L40-43
    __init__() → L41-43
  class GeminiPersistentSession → L46-342
    __init__() → L47-62
    ensure_started() → L64-79
    _spawn_locked() → L81-128
    _close_locked() → L130-167
    shutdown() → L169-172
    run_turn() → L174-191
    _run_turn_once() → L193-222
    _clean_text() → L224-226
    _find_prompt() → L228-233
    _is_meaningful() → L235-242
    _emit_safe_delta() → L244-254
    _finish_turn_if_prompt_seen() → L256-272
    _read_loop() → L274-342
  class GeminiPersistentManager → L345-407
    __init__() → L349-352
    get() → L354-363
    shutdown() → L365-369
    end() → L372-373
    reap_stale_sessions() → L375-392
    _evict_oldest_locked() → L394-407
  get_gemini_persistent_manager() → L413-417

### jane/context_builder.py (855 lines)
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
  _build_system_sections() → L507-626
  _format_recent_history() → L629-654
  TTS_SPOKEN_BLOCK_INSTRUCTION = ... → L657
  build_jane_context() → L678-739
  build_jane_context_async() → L742-855

### jane/config.py (267 lines)
  _resolve_roots() → L16-39
  get_chroma_client() → L68-78
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
  CHROMA_HOST = ... → L65
  CHROMA_PORT = ... → L66
  VECTOR_DB_DIR = ... → L80
  VECTOR_DB_USER_MEMORIES = ... → L81
  VECTOR_DB_SHORT_TERM = ... → L82
  VECTOR_DB_LONG_TERM = ... → L83
  VECTOR_DB_FILE_INDEX = ... → L84
  CHROMA_COLLECTION_USER_MEMORIES = ... → L87
  CHROMA_COLLECTION_SHORT_TERM = ... → L88
  CHROMA_COLLECTION_LONG_TERM = ... → L89
  CHROMA_COLLECTION_FILE_INDEX = ... → L90
  PROMPT_LIST_PATH = ... → L93
  ACCOMPLISHED_PATH = ... → L94
  LEDGER_DB_PATH = ... → L95
  JANITOR_REPORT = ... → L96
  _USER_NAME = ... → L99
  USER_ESSAY = ... → L100
  JANE_ESSAY = ... → L101
  AMBER_ESSAY = ... → L102
  USER_ESSAY = ... → L100
  USER_STATE_PATH = ... → L106
  IDLE_STATE_PATH = ... → L107
  ACTIVE_QUEUE_PATH = ... → L108
  QUEUE_SESSION_PATH = ... → L109
  PENDING_UPDATES_PATH = ... → L110
  CONTEXT_SUMMARY_PATH = ... → L111
  JANE_SESSIONS_PATH = ... → L112
  JANE_SESSION_SUMMARY_DIR = ... → L113
  TASK_SPINE_PATH = ... → L114
  INTERRUPT_STACK_PATH = ... → L115
  PROMPT_QUEUE_LOG = ... → L118
  JOB_QUEUE_LOG = ... → L119
  JANE_WRAPPER_RAW_LOG = ... → L120
  AMBIENT_HEARTBEAT_LOG = ... → L121
  VAULT_TUNNEL_LOG = ... → L122
  ADK_VENV_PYTHON = ... → L125
  CLAUDE_BIN = ... → L126
  CODEX_BIN = ... → L127

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

### agent_skills/conversation_manager.py (1117 lines)
  class silence_stderr_fd → L16-29
    __enter__() → L17-22
    __exit__() → L24-29
  TOKEN_ENCODING_MODEL = ... → L55
  COMPACTION_THRESHOLD_PERCENT = ... → L56
  ARCHIVIST_MODEL = ... → L57
  WRITEBACK_TIMING_LOG = ... → L58
  get_token_count() → L67-69
  _append_writeback_log() → L72-78
  class ConversationManager → L81-1117
    __init__() → L96-138
    add_message() → L148-167
    add_messages() → L169-180
    get_stats() → L182-193
    close() → L195-227
    _fetch_session_transcript() → L229-247
    _thematic_archival() → L249-299
    _reset_idle_timer() → L305-312
    _on_idle() → L314-335
    _run_archival() → L341-406
    _should_wait_for_smart_archival() → L408-410
    _select_archivist_model() → L412-416
    _triage_memory() → L418-461
    _promote_to_long_term() → L463-539
    _compact_context_window_if_needed() → L547-589
    _generate_summary() → L591-605
    _init_db() → L611-624
    _log_to_ledger() → L626-643
    update_thematic_memory() → L655-681
    _do_thematic_update() → L683-765
    _fetch_session_themes() → L767-802
    _classify_turn_theme() → L804-855
    _update_theme_summary() → L857-888
    _fallback_raw_theme() → L890-933
    _should_store_short_term_turn() → L938-985
    _release_short_term_handles() → L987-993
    _looks_like_code_edit() → L996-1020
    _summarize_for_short_term() → L1023-1088
    _normalize_short_term_summary() → L1091-1117

### agent_skills/memory_retrieval.py (661 lines)
  class silence_stderr_fd → L11-24
    __enter__() → L12-17
    __exit__() → L19-24
  class MemorySummaryCacheEntry → L60-64
  PERSONAL_QUERY_MARKERS = ... → L71
  PROJECT_QUERY_MARKERS = ... → L75
  LOW_SIGNAL_SHARED_PREFIXES = ... → L80
  _utcnow() → L92-93
  _normalize_query() → L96-97
  _get_query_embedding_fn() → L100-113
  _embed_query_text() → L116-132
  _cosine_similarity() → L135-143
  _prune_cache_entries() → L146-152
  _lookup_cached_memory_summary() → L155-170
  _CACHE_MAX_SESSIONS = ... → L173
  _store_cached_memory_summary() → L176-196
  invalidate_memory_summary_cache() → L199-204
  _is_expired() → L207-222
  _is_too_old() → L225-237
  _is_none_content() → L240-243
  _recency_label() → L246-263
  _fmt_memory() → L266-273
  _extract_content_key() → L276-289
  _dedupe_fact_lines() → L292-311
  _query_collection() → L314-344
  _within_distance() → L347-353
  _is_file_index_record() → L356-376
  _is_file_query() → L379-407
  _classify_query_intent() → L410-418
  _is_low_signal_shared_memory() → L421-430
  build_memory_sections() → L433-657

### agent_skills/local_vector_memory.py (268 lines)
  class silence_stderr_fd → L12-25
    __enter__() → L13-18
    __exit__() → L20-25
  FORGETTABLE_TTL_DAYS = ... → L48
  class LocalVectorMemoryService → L51-268
    __init__() → L57-72
    _user_filter() → L74-75
    add_memory() → L77-111
    search_memory() → L113-226
    delete_memory() → L228-248
    _extract_text() → L250-253
    list_all_for_reorg() → L255-259
    add_session_to_memory() → L261-268

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

### agent_skills/essence_loader.py (337 lines)
  class EssenceState → L33-41
  _log_to_work_log() → L51-57
  _get_tools_dir() → L60-66
  _get_essences_dir() → L69-73
  load_essence() → L80-142
  unload_essence() → L145-161
  delete_essence() → L164-209
  list_loaded_essences() → L212-214
  list_available_essences() → L217-277
  list_available() → L280-286
  main() → L293-333

### agent_skills/essence_runtime.py (429 lines)
  class EssenceState → L35-43
  class EssenceRuntime → L50-285
    __new__() → L55-59
    __init__() → L61-69
    load_essence() → L73-116
    unload_essence() → L118-127
    delete_essence() → L129-143
    get_loaded() → L147-149
    list_available() → L151-174
    get_capabilities_map() → L176-182
    route_to_essence() → L184-214
    set_active_essence() → L218-222
    get_active_essence() → L224-233
    _port_memory() → L237-285
  class JaneOrchestrator → L292-366
    __init__() → L295-296
    decompose_task() → L298-330
    execute_plan() → L332-366
  class CapabilityRegistry → L373-429
    __init__() → L377-378
    register() → L380-385
    unregister() → L387-393
    find_provider() → L395-398
    request_service() → L400-429

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

### agent_skills/index_vault.py (379 lines)
  _REQUIRED_PYTHON = ... → L28
  class _silence → L34-41
    __enter__() → L35-38
    __exit__() → L39-41
  VAULT_PATH = ... → L59
  HASH_INDEX_PATH = ... → L60
  SKIP_FILES = ... → L62
  SKIP_EXTENSIONS = ... → L63
  IMAGE_EXTENSIONS = ... → L65
  TEXT_EXTENSIONS = ... → L66
  READABLE_EXTENSIONS = ... → L72
  MAX_EXTRACT_CHARS = ... → L73
  get_collection() → L78-84
  is_already_tracked() → L87-97
  add_to_chromadb() → L100-117
  load_hash_index() → L122-128
  save_hash_index() → L131-132
  hash_file() → L135-140
  describe_image() → L145-167
  _extract_text_file() → L170-174
  _extract_pdf_text() → L177-195
  _extract_docx_text() → L198-219
  extract_readable_text() → L222-230
  _fallback_text_description() → L233-254
  describe_readable_file() → L257-287
  scan_vault() → L292-369

### agent_skills/janitor_memory.py (694 lines)
  DB_PATH = ... → L28
  SHORT_TERM_DB_PATH = ... → L29
  JANITOR_LOG = ... → L30
  VAULT_IMAGES_DIR = ... → L31
  MEMORY_JANITOR_MODEL = ... → L34
  _llm_json() → L37-82
  _is_expired() → L85-95
  purge_expired_short_term() → L98-127
  purge_expired_forgettable() → L131-132
  purge_old_forgettable_memories() → L135-162
  backfill_thematic_archival() → L165-212
  dedup_cross_session_themes() → L215-288
  run_janitor() → L291-480
  LOG_MAX_AGE_DAYS = ... → L482
  _PROTECTED_LOG_PATTERNS = ... → L485
  purge_old_log_files() → L493-527
  IMAGE_EXTENSIONS = ... → L530
  cluster_vault_images() → L533-694

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

### agent_skills/nightly_audit.py (317 lines)
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
  LATEST_AUDIT_SUMMARY = ... → L41
  read_file() → L53-60
  read_script_body() → L63-69
  KEY_SCRIPTS = ... → L73
  get_crontab() → L83-88
  get_skill_files() → L91-92
  IDLE_THRESHOLD_SECONDS = ... → L99
  ACTIVITY_INDICATORS = ... → L102
  is_user_idle() → L108-145
  _run_cmd() → L148-152
  _extract_health_summary() → L155-169
  _write_latest_summary() → L172-181
  run_audit_and_fix() → L184-258
  main() → L262-313

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

### agent_skills/generate_code_map.py (514 lines)
  VESSENCE_HOME = ... → L24
  CONFIGS_DIR = ... → L25
  CORE_PRIORITY_FILES = ... → L29
  CORE_SECONDARY_DIRS = ... → L94
  WEB_PRIORITY_FILES = ... → L105
  WEB_SECONDARY_DIRS = ... → L110
  ANDROID_ROOT = ... → L116
  SKIP_DIRS = ... → L120
  SKIP_FILES = ... → L121
  MARKER = ... → L123
  MAX_ENTRIES_PRIORITY = ... → L125
  MAX_ENTRIES_SECONDARY = ... → L126
  count_lines() → L133-138
  index_python_file() → L141-178
  index_html_file() → L181-207
  index_kotlin_file() → L210-272
  _index_file() → L275-289
  _should_skip() → L292-297
  _cap_entries() → L304-316
  generate_core_map() → L319-371
  generate_web_map() → L374-419
  generate_android_map() → L422-460
  _write_map() → L467-481
  main() → L484-510

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

### agent_skills/show_job_queue.py (180 lines)
  VESSENCE_HOME = ... → L9
  QUEUE_DIR = ... → L10
  SYSTEM_DEFAULTS_PATH = ... → L11
  DEFAULT_JOB_QUEUE_COLUMNS = ... → L12
  PRIORITY_LABEL = ... → L14
  PRIORITY_SORT = ... → L20
  STATUS_ICON = ... → L22
  load_job_queue_columns() → L30-40
  load_jobs() → L43-60
  _parse_job_file() → L63-107
  load_completed_jobs() → L110-122
  get_job_queue_data() → L125-132
  get_completed_jobs_data() → L135-142
  format_markdown_table() → L145-166
  main() → L169-176

### vault_web/files.py (294 lines)
  THUMBNAIL_SIZE = ... → L20
  ICON_MAP = ... → L22
  IMAGE_EXTS = ... → L39
  VIDEO_EXTS = ... → L40
  AUDIO_EXTS = ... → L41
  TEXT_EXTS = ... → L42
  TEXT_SIZE_LIMIT = ... → L48
  is_text() → L51-52
  safe_vault_path() → L55-61
  ext() → L64-65
  file_icon() → L68-69
  is_image() → L72-73
  is_video() → L76-77
  is_audio() → L80-81
  is_text() → L83-84
  get_mime() → L87-89
  make_descriptive_filename() → L92-104
  build_file_index_document() → L107-111
  upsert_file_index_entry() → L114-140
  list_directory() → L143-192
  get_file_metadata() → L195-248
  update_description() → L251-261
  get_last_change_timestamp() → L264-269
  generate_thumbnail() → L272-286
  _human_size() → L289-294

### vault_web/auth.py (248 lines)
  MAX_ATTEMPTS = ... → L18
  LOCKOUT_MINUTES = ... → L19
  SESSION_TRUSTED_DAYS = ... → L20
  TOTP_SECRET = ... → L22
  get_allowed_emails() → L25-27
  is_allowed_email() → L30-35
  user_id_from_email() → L38-40
  default_user_id() → L43-50
  get_totp() → L53-54
  send_otp_discord() → L58-60
  create_otp() → L63-65
  verify_otp() → L68-86
  get_totp_uri() → L89-92
  _record_failed_attempt() → L95-109
  unlock_ip() → L112-118
  create_session() → L121-134
  get_session_user() → L137-148
  validate_session() → L151-167
  is_device_trusted() → L170-175
  register_trusted_device() → L178-195
  get_trusted_device_by_id() → L198-210
  get_trusted_device_by_fingerprint() → L213-225
  get_trusted_devices() → L228-231
  revoke_device() → L234-241
  device_fingerprint_from_request() → L244-248

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

### vault_web/playlists.py (72 lines)
  list_playlists() → L6-13
  get_playlist() → L16-29
  create_playlist() → L32-45
  update_playlist() → L48-67
  delete_playlist() → L70-72

### onboarding/main.py (435 lines)
  DATA_DIR = ... → L20
  VAULT_DIR = ... → L21
  ENV_FILE = ... → L22
  PROFILE = ... → L23
  default_auth_method_for_brain() → L30-31
  _read_env_values() → L34-44
  GET /health → L50
  onboarding_complete() → L56-62
  is_first_run() → L65-67
  GET / → L71
  POST /api/setup → L107
  JANE_URL = ... → L205
  POST /api/cli-login → L209
  GET /api/cli-login/status → L223
  POST /api/cli-login/code → L234
  GET /interview → L250
  POST /api/interview/submit → L255
  _build_profile() → L264-310
  POST /api/settings → L316
  POST /api/validate-key → L365
  GET /success → L422

### startup_code/jane_bootstrap.py (199 lines)
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
  main() → L145-195

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

### startup_code/regenerate_jane_context.py (146 lines)
  BASE = ... → L29
  DATA_ROOT = ... → L30
  VAULT_ROOT = ... → L31
  OUTPUT = ... → L32
  read_file() → L34-39
  extract_section() → L41-56
  extract_cron_jobs() → L58-84
  extract_projects() → L86-93
  build_context() → L95-140

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

### startup_code/build_docker_bundle.py (691 lines)
  REPO_ROOT = ... → L18
  MARKETING_ROOT = ... → L19
  DOWNLOADS_DIR = ... → L20
  INSTALLERS_DIR = ... → L21
  _INSTALLER_VERSION_RE = ... → L23
  _next_installer_version() → L28-47
  VERSION = ... → L50
  PLATFORMS = ... → L52
  update_marketing_download_links() → L81-120
  reset_dir() → L123-126
  copy_tree() → L129-130
  _ensure_crlf() → L133-138
  _check_bat_block_parens() → L141-161
  build_readme() → L164-232
  build_platform_package() → L235-369
  _match_image_bins() → L383-390
  _parse_compose_services() → L393-410
  validate() → L413-555
  verify_packages() → L558-657
  build_all() → L660-687

### startup_code/query_live_memory.py (125 lines)
  ROOT = ... → L16
  LIVE_VECTOR_ROOT = ... → L23
  CACHE_FILE = ... → L28
  CACHE_TTL_SECS = ... → L29
  CACHE_MAX_ENTRIES = ... → L30
  CACHE_SIMILARITY_THRESHOLD = ... → L31
  _cosine_similarity() → L34-42
  _embed_query() → L45-50
  _load_cache() → L53-61
  _save_cache() → L64-70
  _lookup_cache() → L73-81
  main() → L84-121

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

### jane_web/gemma_router.py (335 lines)
  OLLAMA_URL = ... → L22
  ROUTER_MODEL = ... → L23
  ROUTER_TIMEOUT = ... → L24
  MAX_HISTORY_TURNS = ... → L25
  _PERSONAL_INFO = ... → L28
  SYSTEM_PROMPT = ... → L36
  _CLASSIFY_RE = ... → L99
  _RESPONSE_RE = ... → L100
  _WEATHER_KEYWORDS = ... → L103
  _load_all_mcps() → L110-132
  _get_tool_capabilities_summary() → L135-152
  _WEATHER_CACHE = ... → L154
  _load_weather_context() → L160-188
  _get_session() → L195-201
  _build_history() → L204-217
  classify_prompt() → L220-335

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

### jane_web/wake_word_verify.py (73 lines)
  _get_model() → L19-27
  _WAKE_WORD_MATCHES = ... → L31
  verify_wake_word() → L34-73

### jane/gemini_api_brain.py (335 lines)
  TOOL_BRIDGE_PORT = ... → L24
  TOOL_BRIDGE_URL = ... → L25
  TOOL_DECLARATIONS = ... → L28
  class GeminiApiBrain → L133-324
    __init__() → L136-140
    _ensure_client() → L142-154
    _ensure_bridge() → L156-195
    _execute_tool() → L197-209
    send_streaming() → L211-313
    remove_session() → L315-317
    shutdown() → L319-324
  get_gemini_api_brain() → L331-335

### jane/persistent_codex.py (401 lines)
  _kill_process_tree() → L22-31
  class CodexPersistentSession → L35-42
    is_fresh() → L41-42
  class CodexPersistentManager → L45-391
    __init__() → L49-54
    get() → L56-71
    end() → L73-78
    run_turn() → L80-127
    _build_cmd() → L129-146
    _execute_streaming() → L148-316
    _format_command() → L319-329
    _flush_pending_thought() → L332-343
    _extract_item_text() → L346-365
    _format_tool_result() → L367-376
    _normalize_error_message() → L379-391
  get_codex_persistent_manager() → L397-401

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

### agent_skills/claude_cli_llm.py (116 lines)
  _build_command() → L25-45
  completion() → L48-78
  completion_orchestrator() → L81-84
  completion_agent() → L87-89
  completion_utility() → L92-94
  completion_smart() → L97-99
  completion_json() → L102-116

### agent_skills/code_lock.py (130 lines)
  VESSENCE_DATA_HOME = ... → L28
  LOCK_DIR = ... → L29
  LOCK_FILE = ... → L30
  LOCK_TIMEOUT = ... → L31
  acquire_lock() → L34-71
  release_lock() → L74-80
  who_holds_lock() → L83-101
  code_edit_lock() → L105-111

### agent_skills/consult_panel.py (232 lines)
  FRONTIER_CLIS = ... → L29
  SKIP_CLIS = ... → L36
  CLI_TIMEOUT = ... → L39
  detect_available_clis() → L42-54
  query_cli() → L57-119
  synthesize() → L122-151
  consult_panel() → L154-194

### agent_skills/cron_utils.py (65 lines)
  send_discord() → L18-44
  load_cron_env() → L47-65

### agent_skills/daily_code_review.py (185 lines)
  LOG_FILE = ... → L23
  REVIEW_DIR = ... → L24
  REVIEW_EXTENSIONS = ... → L38
  SKIP_PATTERNS = ... → L41
  MAX_DIFF_CHARS = ... → L51
  get_changed_files() → L54-80
  get_diff_summary() → L83-116
  run_team_review() → L119-142
  main() → L145-181

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

### agent_skills/fetch_weather.py (110 lines)
  LAT = ... → L16
  LON = ... → L17
  LOCATION = ... → L18
  VESSENCE_DATA_HOME = ... → L20
  CACHE_DIR = ... → L24
  OUTPUT_PATH = ... → L25
  WMO_CODES = ... → L27
  fetch_weather() → L39-99
  main() → L102-106

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

### agent_skills/notify_audit_results.py (126 lines)
  LOG_FILE = ... → L16
  AUDIT_LOG_DIR = ... → L17
  LATEST_AUDIT_SUMMARY = ... → L18
  ANNOUNCEMENTS_PATH = ... → L19
  STATE_PATH = ... → L20
  _load_json() → L30-34
  _save_json() → L37-41
  _load_latest_audit() → L44-59
  _extract_brief() → L62-67
  _write_announcement() → L70-80
  main() → L83-122

### agent_skills/notify_updates.py (57 lines)
  NOTIFY_FILE = ... → L15
  DISCORD_TOKEN = ... → L18
  CHANNEL_ID = ... → L19
  send_notification() → L21-54

### agent_skills/process_watchdog.py (151 lines)
  PROTECTED_NAMES = ... → L26
  MAX_CONTAINER_AGE_MINUTES = ... → L27
  MAX_RAM_PERCENT = ... → L28
  kill_old_tts_containers() → L31-57
  _parse_minutes() → L60-71
  kill_idle_build_daemons() → L74-102
  kill_memory_hogs() → L105-139
  main() → L142-147

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

### agent_skills/safe_docker.py (108 lines)
  run_docker() → L36-94
  _force_kill() → L97-108

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

### agent_skills/topic_memory.py (295 lines)
  MAX_TOPIC_CHARS = ... → L38
  TRIGGER_EVERY_N_TURNS = ... → L39
  TURN_COUNTER_FILE = ... → L40
  _silence_stderr() → L46-52
  _restore_stderr() → L55-57
  _get_collection() → L60-66
  _find_nearest_topics() → L69-92
  _call_claude() → L95-147
  _should_skip() → L150-164
  _increment_turn_counter() → L167-179
  process_turn() → L182-258
  fire_and_forget() → L261-271
  main() → L274-291

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

### startup_code/bump_android_version.py (152 lines)
  VESSENCE_HOME = ... → L19
  VERSION_FILE = ... → L20
  ANDROID_DIR = ... → L21
  DOWNLOADS_DIR = ... → L22
  CHANGELOG = ... → L23
  MAIN_PY = ... → L24
  load_version() → L27-29
  save_version() → L32-35
  bump_patch() → L38-41
  update_main_py() → L44-51
  build_apk() → L54-72
  verify_apk_version() → L75-101
  deploy_apk() → L104-111
  main() → L114-148

### startup_code/claude_full_startup_context.py (55 lines)
  DATA_ROOT = ... → L13
  VESSENCE_ROOT = ... → L14
  VAULT_ROOT = ... → L15
  DOCS = ... → L17
  read_doc() → L32-39
  main() → L42-51

### startup_code/installer_simulation.py (222 lines)
  class InstallerSimulationError → L13-14
  _write_executable() → L17-19
  _assert_install_result() → L22-43
  _simulate_unix() → L46-110
  _winepath() → L113-123
  _simulate_windows() → L126-210
  simulate_installer_package() → L213-222

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
