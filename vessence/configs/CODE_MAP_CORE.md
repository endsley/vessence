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
_Auto-generated on 2026-04-17 08:15 UTC by `generate_code_map.py`_

## Priority Files

### jane_web/jane_proxy.py (3060 lines)
  class ToolMarkerExtractor → L51-315
  class _SkipRouterSignal → L331-335
  class JaneSessionState → L668-681
    __init__() → L65-67
    feed() → L70-80
    flush() → L82-92
    _drain() → L95-182
    _partial_opener_suffix_len() → L185-192
    _partial_fence_suffix_len() → L195-202
    _find_marker_end() → L205-288
    _parse_marker() → L291-315
  _extract_tool_results() → L342-411
  _neutralize_delimiters() → L424-444
  _format_tool_results_for_brain() → L447-487
  _execute_email_tool_serverside() → L490-553
  _maybe_prepend_code_map() → L660-664
  run_prefetch_memory() → L696-732
  get_prefetch_result() → L735-740
  _get_brain_name() → L743-756
  _session_log_id() → L759-760
  _get_timeout_seconds() → L763-764
  _get_execution_profile() → L767-768
  _use_gemini_api() → L771-773
  _use_persistent_gemini() → L775-777
  _use_persistent_claude() → L780-781
  _use_persistent_codex() → L784-785
  _get_web_chat_model() → L788-807
  _prune_stale_sessions() → L810-823
  _execute_brain_sync() → L826-892
  _execute_brain_stream() → L895-976
  _get_session() → L979-995
  _resolve_file_context() → L1020-1029
  _message_for_persistence() → L1032-1036
  prewarm_session() → L1039-1090
  _await_prewarm_if_running() → L1093-1110
  end_session() → L1113-1185
  _progress_snapshot() → L1188-1202
  _truncate_log_if_needed() → L1208-1215
  _log_stage() → L1218-1229
  _log_start() → L1232-1240
  _dump_prompt() → L1243-1275
  _persist_turns_async() → L1278-1331
  send_message() → L1339-1366
  _send_message_inner() → L1369-1516
  _pick_ack() → L1519-1785
  stream_message() → L1788-3043
  _log_chat_to_work_log() → L3046-3048
  get_active_brain() → L3051-3053
  get_tunnel_url() → L3056-3060
  _TOOL_RESULT_OPEN = ... → L338

### jane_web/main.py (4960 lines)
  class RateLimiter → L91-117
  class ChatMessage → L2707-2712
  class SessionControl → L2715-2716
  class SwitchProviderRequest → L2794-2795
  GET /health → L694
  POST /api/admin/reset-gate → L700
  POST /api/jane/warmup → L734
  GET /sw.js → L759
  GET /manifest.webmanifest → L764
  GET / → L972
  GET /share → L998
  GET /vault → L1003
  GET /guide → L1026
  GET /architecture → L1032
  GET /chat → L1038
  GET /essences → L1061
  GET /worklog → L1065
  GET /api/job-queue → L1069
  GET /api/job-queue/completed → L1083
  GET /briefing → L1097
  POST /api/crash-report → L1102
  POST /api/contacts/sync → L1115
  GET /api/contacts/search → L1151
  GET /api/contacts → L1175
  POST /api/contacts/alias → L1185
  POST /api/messages/sync → L1210
  GET /api/messages/search → L1271
  GET /api/messages/recent → L1294
  POST /api/device-diagnostics → L1309
  GET /api/device-diagnostics → L1339
  GET /settings/devices → L1358
  GET /downloads/{filename} → L1364
  GET /api/tts-server/health → L1464
  POST /api/tts-server/generate → L1470
  POST /api/tts-server/stream → L1478
  POST /api/tts/generate → L1490
  GET /api/app/settings → L1574
  PUT /api/app/settings → L1580
  POST /api/app/installed → L1590
  GET /api/app/latest-version → L1602
  GET /auth/google → L1635
  GET /auth/google/callback → L1649
  POST /api/auth/google-token → L1693
  POST /api/auth/verify-share → L1731
  POST /api/auth/verify-otp → L1741
  POST /api/auth/logout → L1766
  GET /api/auth/devices → L1778
  DELETE /api/auth/devices/{device_id} → L1783
  POST /api/auth/check → L1789
  POST /api/auth/is-new-device → L1802

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

### jane_web/reverse_proxy.py (405 lines)
  class _ProxyRateLimiter → L43-67
    __init__() → L46-48
    check() → L50-61
    _cleanup() → L63-67
  _PROXY_MAX_REQUESTS_PER_MINUTE = ... → L71
  _get_proxy_client_ip() → L74-81
  STATE_FILE = ... → L83
  _get_upstream_session() → L100-114
  class ProxyState → L120-158
    __init__() → L123-131
    upstream_url() → L134-135
    switch() → L137-145
    drain_active() → L147-151
    _persist() → L153-158
  _is_localhost() → L167-172
  handle_switch() → L175-190
  handle_status() → L193-205
  CONNECT_TIMEOUT = ... → L213
  HOP_BY_HOP = ... → L216
  proxy_handler() → L223-313
  _proxy_websocket() → L316-352
  create_app() → L359-377
  main() → L380-401

### jane_web/task_classifier.py (97 lines)
  _BIG_TASK_PATTERNS = ... → L6
  _QUICK_QUERY_PATTERNS = ... → L26
  _MIN_LENGTH_FOR_OFFLOAD = ... → L33
  classify_task() → L39-92
  strip_bg_prefix() → L95-97

### jane_web/task_offloader.py (214 lines)
  CODE_ROOT = ... → L13
  ANNOUNCEMENTS_PATH = ... → L20
  _PROGRESS_INTERVAL = ... → L22
  _write_announcement() → L25-29
  _now_iso() → L32-33
  offload_task() → L36-56
  _run_task() → L59-208
  _truncate() → L211-214

### jane/config.py (283 lines)
  _resolve_roots() → L16-39
  get_chroma_client() → L71-97
  TOOLS_DIR = ... → L45
  HOME_DIR = ... → L46
  USER_NAME = ... → L47
  ESSENCE_TEMPLATE_DIR = ... → L50
  AGENT_ROOT = ... → L54
  LOGS_DIR = ... → L55
  CONFIGS_DIR = ... → L56
  AMBER_DIR = ... → L57
  DATA_DIR = ... → L58
  DYNAMIC_QUERY_MARKERS_PATH = ... → L59
  CREDENTIALS_DIR = ... → L60
  ENV_FILE_PATH = ... → L61
  CHROMA_HOST = ... → L64
  CHROMA_PORT = ... → L65
  VECTOR_DB_DIR = ... → L99
  VECTOR_DB_USER_MEMORIES = ... → L100
  VECTOR_DB_SHORT_TERM = ... → L101
  VECTOR_DB_LONG_TERM = ... → L102
  VECTOR_DB_FILE_INDEX = ... → L103
  CHROMA_COLLECTION_USER_MEMORIES = ... → L106
  CHROMA_COLLECTION_SHORT_TERM = ... → L107
  CHROMA_COLLECTION_LONG_TERM = ... → L108
  CHROMA_COLLECTION_FILE_INDEX = ... → L109
  PROMPT_LIST_PATH = ... → L112
  ACCOMPLISHED_PATH = ... → L113
  LEDGER_DB_PATH = ... → L114
  JANITOR_REPORT = ... → L115
  _USER_NAME = ... → L118
  USER_ESSAY = ... → L119
  JANE_ESSAY = ... → L120
  AMBER_ESSAY = ... → L121
  USER_STATE_PATH = ... → L124
  IDLE_STATE_PATH = ... → L125
  ACTIVE_QUEUE_PATH = ... → L126
  QUEUE_SESSION_PATH = ... → L127
  PENDING_UPDATES_PATH = ... → L128
  CONTEXT_SUMMARY_PATH = ... → L129
  JANE_SESSIONS_PATH = ... → L130
  JANE_SESSION_SUMMARY_DIR = ... → L131
  TASK_SPINE_PATH = ... → L132
  INTERRUPT_STACK_PATH = ... → L133
  PROMPT_QUEUE_LOG = ... → L136
  JOB_QUEUE_LOG = ... → L137
  JANE_WRAPPER_RAW_LOG = ... → L138
  AMBIENT_HEARTBEAT_LOG = ... → L139
  VAULT_TUNNEL_LOG = ... → L140
  ADK_VENV_PYTHON = ... → L143
  CLAUDE_BIN = ... → L144

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

### jane/audit_wrapper.py (61 lines)
  ROOT = ... → L6
  main() → L12-58

### jane/research_router.py (84 lines)
  RESEARCH_HINTS = ... → L13
  RESEARCH_VERBS = ... → L23
  RESEARCH_OBJECTS = ... → L36
  should_offload_research() → L50-58
  run_research_offload() → L61-84

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

### agent_skills/essence_scheduler.py (191 lines)
  TOOLS_DIR = ... → L31
  STATE_FILE = ... → L34
  PYTHON_BIN = ... → L35
  IDLE_THRESHOLD_SECONDS = ... → L36
  _load_state() → L39-44
  _save_state() → L47-53
  _is_user_idle() → L56-67
  _matches_schedule() → L70-98
  run_scheduler() → L101-187

### agent_skills/janitor_system.py (112 lines)
  TEMP_FILES = ... → L13
  MAX_LOG_SIZE_MB = ... → L18
  LOG_RETENTION_DAYS = ... → L19
  LOG_PATTERNS = ... → L20
  clean_temp_files() → L22-29
  rotate_logs() → L31-43
  prune_old_logs() → L45-65
  _truncate_log_tail() → L68-86
  archive_completed_jobs() → L88-95

### agent_skills/nightly_audit.py (322 lines)
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
  main() → L262-318

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

### agent_skills/system_load.py (343 lines)
  MAX_PARALLEL = ... → L26
  CPU_THRESHOLD_HIGH = ... → L27
  CPU_THRESHOLD_MED = ... → L28
  MEM_FREE_MIN_GB = ... → L29
  GPU_THRESHOLD_HIGH = ... → L30
  VRAM_FREE_MIN_MB = ... → L31
  NIGHT_START_HOUR = ... → L32
  NIGHT_END_HOUR = ... → L33
  _is_nighttime() → L36-43
  _query_gpu() → L46-79
  get_system_load() → L82-116
  recommended_parallelism() → L119-155
  should_defer() → L158-188
  has_ample_resources() → L191-217
  wait_until_safe() → L220-247
  load_summary() → L250-269
  _CACHE_FILE = ... → L272
  _CACHE_TTL_SECS = ... → L273
  _cached_oneline() → L276-286
  _save_cache() → L289-296
  oneline() → L299-332

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

### agent_skills/ambient_heartbeat.py (400 lines)
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
  main() → L310-396

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

### agent_skills/llm_summarize.py (193 lines)
  _REQUIRED_PYTHON = ... → L19
  TRANSCRIPT_DIR = ... → L27
  SHORT_TERM_DB = ... → L31
  TURNS_TO_INCLUDE = ... → L37
  MIN_TEXT_LEN = ... → L38
  silence_stderr() → L41-47
  restore_stderr() → L50-52
  extract_text_from_content() → L55-73
  read_recent_turns() → L76-109
  summarize_with_local_llm() → L112-134
  save_to_short_term() → L137-164
  main() → L167-189

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

### vault_web/files.py (293 lines)
  THUMBNAIL_SIZE = ... → L21
  ICON_MAP = ... → L23
  IMAGE_EXTS = ... → L40
  VIDEO_EXTS = ... → L41
  AUDIO_EXTS = ... → L42
  TEXT_EXTS = ... → L43
  TEXT_SIZE_LIMIT = ... → L49
  is_text() → L52-53
  safe_vault_path() → L56-62
  ext() → L65-66
  file_icon() → L69-70
  is_image() → L73-74
  is_video() → L77-78
  is_audio() → L81-82
  is_text() → L84-85
  get_mime() → L88-90
  make_descriptive_filename() → L93-105
  build_file_index_document() → L108-112
  upsert_file_index_entry() → L115-140
  list_directory() → L143-192
  get_file_metadata() → L195-247
  update_description() → L250-260
  get_last_change_timestamp() → L263-268
  generate_thumbnail() → L271-285
  _human_size() → L288-293

### vault_web/auth.py (255 lines)
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
  validate_session() → L151-170
  is_device_trusted() → L173-178
  register_trusted_device() → L181-198
  get_trusted_device_by_id() → L201-213
  get_trusted_device_by_fingerprint() → L216-228
  get_trusted_devices() → L231-234
  revoke_device() → L237-244
  device_fingerprint_from_request() → L247-255

### vault_web/oauth.py (66 lines)
  _normalized_email() → L8-9
  _configured_value() → L12-13
  _configured_public_base_url() → L16-21
  google_oauth_configured() → L24-30
  build_external_url() → L47-55
  allowed_email() → L58-66

### vault_web/database.py (166 lines)
  DB_PATH = ... → L6
  get_db() → L12-18
  init_db() → L21-166

### vault_web/playlists.py (72 lines)
  list_playlists() → L6-13
  get_playlist() → L16-29
  create_playlist() → L32-45
  update_playlist() → L48-67
  delete_playlist() → L70-72

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

### startup_code/regenerate_jane_context.py (178 lines)
  BASE = ... → L29
  DATA_ROOT = ... → L30
  VAULT_ROOT = ... → L31
  OUTPUT = ... → L40
  WEB_OUTPUT = ... → L44
  read_file() → L49-54
  extract_section() → L56-71
  extract_cron_jobs() → L73-99
  extract_projects() → L101-108
  build_context() → L110-155
  _write_atomic() → L157-163

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

### startup_code/usb_rotation.py (330 lines)
  _USER = ... → L21
  _DEFAULT_USB = ... → L22
  find_usb_mount() → L24-29
  USB_MOUNT_POINT = ... → L31
  SOURCES = ... → L34
  EXCLUDES = ... → L47
  ADK_PYTHON = ... → L62
  ADK_PIP = ... → L63
  run() → L67-71
  generate_manifest() → L74-268
  main() → L272-326

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

### jane_web/verify_first_policy.py (299 lines)
  _CODE_TRIGGER_RE = ... → L44
  _MEMORY_TRIGGER_RE = ... → L82
  _EMPTY_MEMORY_SENTINELS = ... → L105
  class EvidenceRequirements → L113-127
    any() → L118-119
    labels() → L121-127
  needs_verification() → L130-138
  needs_memory_evidence() → L141-145
  classify_evidence_requirements() → L148-153
  has_meaningful_memory() → L156-163
  STRONGER_VERIFY_INSTRUCTION = ... → L168
  MEMORY_VERIFY_INSTRUCTION = ... → L198
  instruction_for_requirements() → L222-228
  class ToolUseCounter → L233-270
    __init__() → L247-250
    __call__() → L254-270
  summarize_verification_status() → L273-299

### jane_web/wake_word_verify.py (73 lines)
  _get_model() → L19-27
  _WAKE_WORD_MATCHES = ... → L31
  verify_wake_word() → L34-73

### jane_web/jane_v2/models.py (66 lines)
  LOCAL_LLM = ... → L43

### jane_web/jane_v2/pending_action_resolver.py (242 lines)
  _is_expired() → L38-54
  _CONFIRM = ... → L59
  _EDIT_PREFIXES = ... → L71
  _STAGE3_CANCEL_STRONG = ... → L84
  _CANCEL = ... → L90
  _PUNCT_RE = ... → L97
  _normalize() → L100-101
  _is_confirm() → L104-105
  _is_cancel() → L108-109
  _is_edit_intent() → L112-121
  resolve() → L124-242

### jane_web/jane_v2/pipeline.py (1586 lines)
  _DEFAULT_ESCALATE_ACK = ... → L51
  _AWAITING_RE = ... → L57
  _inject_self_improvement_context() → L62-136
  _copy_body_with_appended_message() → L139-149
  _copy_body_with_prepended_message() → L152-171
  _fetch_required_memory_evidence() → L174-188
  _JANE_CTX_WEB_PATH = ... → L197
  _JANE_CTX_MAX_CHARS = ... → L201
  _load_jane_architecture_context() → L204-219
  _dedup_memory_for_session() → L222-241
  _apply_evidence_policy() → L244-316
  class _AwaitingDeltaStripper → L319-390
    __init__() → L349-351
    feed() → L353-377
    flush() → L379-390
  _extract_awaiting_marker() → L393-411
  _persist_turn_to_fifo() → L414-464
  _persist_stage2_to_fifo() → L469-470
  _ack_for() → L473-481
  _fifo_as_fake_history() → L484-502

### jane_web/jane_v2/recent_context.py (213 lines)
  _CHARS_PER_TOKEN = ... → L21
  DEFAULT_MAX_TURNS = ... → L27
  DEFAULT_MAX_TOKENS = ... → L28
  get_recent_context() → L31-84
  get_stage1_context_packet() → L90-122
  render_stage2_context() → L125-141
  render_stage3_context() → L144-165
  _render_state_header() → L168-183
  _render_state_block() → L186-213

### jane_web/jane_v2/stage1_classifier.py (288 lines)
  _TOOL_RESULT_RE = ... → L22
  _SYS_PREFIX_RE = ... → L24
  _SYS_TAIL_RE = ... → L29
  _strip_system_markers() → L35-41
  _GATE_NEW = ... → L52
  _GATE_PROVEN = ... → L53
  _GATE_STRICT = ... → L54
  PROVEN_CLASSES = ... → L56
  STRICT_CLASSES = ... → L70
  _STRICT_KEYWORDS = ... → L80
  _END_CONVERSATION_RE = ... → L86
  _gate_for() → L111-114
  _strict_keyword_ok() → L117-127
  _end_conversation_phrase_ok() → L130-139
  _CLASS_MAP = ... → L143
  FORCE_STAGE3_PHRASES = ... → L165
  _FORCE_STAGE3_RE = ... → L199
  classify() → L204-288

### jane_web/jane_v2/stage2_dispatcher.py (268 lines)
  _self_correct_classification() → L30-64
  _CLASS_DESCRIPTIONS = ... → L67
  _gate_check() → L81-148
  dispatch() → L151-263
  metadata_for() → L266-268

### jane_web/jane_v2/stage3_escalate.py (438 lines)
  _CLASSES_DIR = ... → L34
  _CLASS_NAME_RE = ... → L38
  _VOICE_HINT = ... → L52
  _maybe_voice_wrap() → L60-69
  _inject_structured_state() → L72-97
  _reason_to_class() → L100-124
  _metadata_for_class_pkg() → L127-138
  _synthesize_class_protocol() → L141-178
  _load_protocol_extension() → L181-211
  _load_class_protocol() → L214-221
  _inject_class_protocol() → L224-250
  _ndjson() → L253-258
  _load_v1_stream() → L261-272
  _load_session_helpers() → L275-305
  escalate_stream() → L308-438

### jane_web/jane_v2/classes/todo_list/handler.py (386 lines)
  _VESSENCE_DATA_HOME = ... → L28
  _CACHE_PATH = ... → L32
  _PIVOT_PREFIXES = ... → L39
  _PIVOT_SUBSTRINGS = ... → L52
  _looks_like_pivot() → L71-75
  _load_cache() → L79-86
  _CATEGORY_ALIASES = ... → L92
  _EXCLUDED_CATEGORY_NAMES = ... → L124
  _normalize() → L127-130
  _visible_categories() → L133-139
  _match_category() → L142-170
  _direct_category_query() → L174-180
  _friendly_category_name() → L184-202
  _speak_items() → L205-222
  _speak_category_list() → L225-257
  _expires_at() → L261-264
  _pending() → L267-275
  _handle_resume() → L279-312
  handle() → L316-386

### jane_web/jane_v2/classes/weather/handler.py (126 lines)
  WEATHER_PATH = ... → L22
  _ANSWER_TEMPLATE = ... → L25
  _ESCALATE_RE = ... → L70
  _FORCE_ESCALATE_PHRASES = ... → L75
  handle() → L84-126

### jane_web/jane_v2/classes/weather/metadata.py (62 lines)
  WEATHER_PATH = ... → L12
  _description() → L15-47
  METADATA = ... → L50

### jane_web/jane_v2/classes/send_message/handler.py (343 lines)
  _SKILLS_DIR = ... → L24
  _VAULT_WEB_DIR = ... → L27
  _EXTRACT_PROMPT = ... → L35
  _DANGLING_ENDINGS = ... → L76
  _FILLER_WORDS = ... → L84
  _DEVICE_COMMANDS = ... → L87
  _is_coherent() → L90-112
  _WRONG_CLASS_SENTINEL = ... → L115
  _parse_extraction() → L118-149
  _check_open_draft() → L152-225
  handle() → L228-343

### jane_web/jane_v2/classes/music_play/handler.py (148 lines)
  _normalize() → L30-31
  _extract_query() → L34-46
  _match_existing_playlist() → L49-96
  _ephemeral_from_library() → L99-106
  handle() → L109-148

### jane_web/jane_v2/classes/music_play/metadata.py (60 lines)
  METADATA = ... → L3

### jane_web/jane_v2/classes/greeting/handler.py (146 lines)
  _CANNED_REPLIES = ... → L25
  _CANNED_PATTERNS = ... → L55
  _canned_reply() → L73-80
  _PROMPT_TEMPLATE = ... → L82
  handle() → L95-146

### jane_web/jane_v2/classes/shopping_list/handler.py (172 lines)
  _SKILLS_DIR = ... → L17
  _EXTRACT_PROMPT = ... → L31
  _WRONG_CLASS_SENTINEL = ... → L72
  _parse_extraction() → L75-97
  handle() → L100-172

### jane_web/jane_v2/classes/read_messages/handler.py (220 lines)
  _VAULT_WEB_DIR = ... → L23
  DEFAULT_LIMIT = ... → L29
  _ARCH_WORDS = ... → L34
  _META_PHRASES = ... → L39
  _SPECIFIC_WORDS = ... → L48
  _fetch_messages() → L53-73
  _is_personal() → L76-77
  _fmt_time() → L80-81
  _format_for_llm() → L84-103
  _generic_dump() → L106-141
  _llm_answer() → L144-188
  handle() → L191-220

### jane_web/jane_v2/classes/timer/handler.py (479 lines)
  _CANCEL_WORDS = ... → L36
  _LIST_WORDS = ... → L38
  _NUM_WORDS = ... → L44
  _HALF_HOUR_RE = ... → L51
  _AND_HALF_RE = ... → L52
  _NUM_UNIT_RE = ... → L53
  _unit_to_ms() → L61-69
  _parse_duration_ms() → L72-102
  _extract_label() → L105-123
  _pretty_duration() → L126-137
  _extract_delete_target() → L140-174
  _COUNT_PHRASES = ... → L177
  _NO_LABEL_REPLIES = ... → L186
  _PIVOT_PREFIXES = ... → L198
  _label_from_reply() → L207-221
  _looks_like_new_timer() → L224-232
  _looks_like_pivot() → L235-239
  _expires_at() → L242-246
  _pending() → L249-258
  _ask_duration() → L261-269

### jane/tool_loader.py (248 lines)
  class ToolHooks → L51-68
  class LoadedTool → L72-77
  _TOOLS_DIR_ENV = ... → L80
  _DEFAULT_TOOLS_DIR = ... → L81
  _tools_dir() → L86-90
  load_all_tools() → L93-146
  _load_single_tool() → L149-173
  _load_server_hooks() → L176-208
  _hooks_summary() → L211-212
  all_prompt_sections() → L218-220
  all_pre_dispatch_filters() → L223-228
  get_tool_mcp() → L231-235
  should_skip_initial_ack() → L238-248

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

### agent_skills/auto_commit_wip.py (97 lines)
  VESSENCE_HOME = ... → L28
  _git() → L33-39
  main() → L42-93

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

### agent_skills/calendar_tools.py (164 lines)
  _PRIMARY = ... → L29
  _service() → L32-53
  list_events() → L56-73
  create_event() → L76-107
  quick_add() → L110-118
  update_event() → L121-144
  delete_event() → L147-151
  _slim() → L154-164

### agent_skills/chat_error_audit.py (190 lines)
  VESSENCE_HOME = ... → L28
  JOB_QUEUE_DIR = ... → L29
  _FRAME_RE = ... → L32
  _next_job_number() → L38-51
  _slugify() → L54-56
  _first_android_frame() → L59-74
  _find_source_path() → L77-89
  create_audit_job() → L92-190

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

### agent_skills/dead_code_auditor.py (299 lines)
  VESSENCE_HOME = ... → L35
  REPORT_PATH = ... → L36
  SCAN_DIRS = ... → L39
  HARD_SKIP_PREFIXES = ... → L44
  HARD_KEEP = ... → L51
  AUTO_DELETE_AGE_DAYS = ... → L59
  MAX_AUTO_DELETE_LINES = ... → L60
  log() → L68-69
  in_hard_skip() → L72-73
  gather_python_files() → L76-87
  grep_references() → L90-103
  scan_dead_files() → L109-123
  scan_dead_functions() → L129-144
  normalize_body() → L150-158
  scan_duplicates() → L161-180
  can_auto_delete() → L186-203
  auto_delete_safe_files() → L206-215
  write_report() → L221-265
  commit_if_changed() → L268-280
  main() → L283-295

### agent_skills/doc_drift_auditor.py (279 lines)
  VESSENCE_HOME = ... → L26
  CONFIGS = ... → L27
  DRIFT_REPORT = ... → L28
  log() → L35-36
  warn() → L39-41
  record_change() → L44-46
  audit_cron() → L52-91
  audit_auditable_modules() → L97-115
  audit_pipeline_classes() → L121-147
  audit_class_packs() → L153-163
  audit_skills_registry() → L170-181
  write_report() → L187-201
  commit_if_changed() → L204-218
  _log_vocal() → L221-262
  main() → L265-275

### agent_skills/email_oauth.py (128 lines)
  _VESSENCE_DATA_HOME = ... → L15
  _CREDS_DIR = ... → L19
  _TOKEN_FILE = ... → L20
  _ensure_creds_dir() → L23-24
  store_gmail_token() → L27-51
  load_gmail_token() → L54-71
  refresh_token_if_needed() → L74-128

### agent_skills/email_tools.py (287 lines)
  get_gmail_service() → L29-53
  _parse_headers() → L60-67
  _extract_plain_body() → L70-95
  _extract_attachments() → L98-112
  read_inbox() → L119-155
  read_email() → L158-187
  send_email() → L190-228
  delete_email() → L231-243
  search_emails() → L246-256

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

### agent_skills/fetch_todo_list.py (243 lines)
  _VESSENCE_DATA_HOME = ... → L51
  _DEFAULT_CACHE = ... → L55
  _DEFAULT_DOC_ID = ... → L58
  _cache_path() → L61-62
  _doc_id() → L65-66
  _export_url() → L69-70
  _LOGIN_WALL_MARKERS = ... → L74
  fetch_doc_text() → L83-118
  _LIST_MARKER_RE = ... → L143
  parse_categories() → L146-190
  write_cache() → L193-216
  main() → L219-239

### agent_skills/fetch_weather.py (166 lines)
  LAT = ... → L24
  LON = ... → L25
  LOCATION = ... → L26
  TOMORROW_IO_KEY = ... → L27
  VESSENCE_DATA_HOME = ... → L29
  CACHE_DIR = ... → L33
  OUTPUT_PATH = ... → L34
  WMO_CODES = ... → L36
  _POLLEN_LABELS = ... → L48
  fetch_pollen() → L51-85
  fetch_weather() → L88-155
  main() → L158-162

### agent_skills/gemma_summarize.py (196 lines)
  _REQUIRED_PYTHON = ... → L22
  TRANSCRIPT_DIR = ... → L30
  SHORT_TERM_DB = ... → L34
  TURNS_TO_INCLUDE = ... → L40
  MIN_TEXT_LEN = ... → L41
  silence_stderr() → L44-50
  restore_stderr() → L53-55
  extract_text_from_content() → L58-76
  read_recent_turns() → L79-112
  summarize_with_local_llm() → L115-137
  save_to_short_term() → L140-167
  main() → L170-192

### agent_skills/generate_identity_essay.py (152 lines)
  DB_PATH = ... → L13
  _USER_NAME = ... → L14
  ESSAY_PATH = ... → L15
  JANE_ESSAY_PATH = ... → L16
  AMBER_ESSAY_PATH = ... → L17
  update_essay() → L21-149

### agent_skills/git_backup.py (117 lines)
  REPO_DIR = ... → L15
  LOG_FILE = ... → L16
  REMOTE_NAME = ... → L17
  run_cmd() → L31-38
  get_commit_summary() → L40-66
  main() → L68-114

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

### agent_skills/nightly_code_auditor.py (426 lines)
  VESSENCE_HOME = ... → L32
  VESSENCE_DATA_HOME = ... → L33
  WHITELIST_PATH = ... → L34
  INTEGRATIONS_PATH = ... → L35
  STATE_PATH = ... → L36
  AUDIT_LOG_PATH = ... → L37
  FAILURE_LOG_PATH = ... → L38
  TEST_DIR = ... → L39
  CLAUDE_BIN = ... → L41
  TIME_BUDGET_SEC = ... → L42
  MAX_FIX_ATTEMPTS = ... → L43
  load_whitelist() → L55-67
  load_state() → L73-79
  save_state() → L82-84
  pick_next_module() → L87-92
  git() → L98-101
  is_clean_working_tree() → L104-147
  make_audit_branch() → L150-153
  revert_branch() → L156-161
  commit_changes() → L164-166

### agent_skills/nightly_self_improve.py (230 lines)
  VESSENCE_HOME = ... → L22
  VESSENCE_DATA_HOME = ... → L23
  PYTHON = ... → L24
  LOG_DIR = ... → L25
  ORCHESTRATOR_LOG = ... → L26
  SUMMARY_LOG = ... → L27
  log() → L30-35
  run_job() → L38-70
  _log_vocal_rollup() → L73-115
  write_summary() → L118-131
  JOBS = ... → L138
  main() → L212-226

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

### agent_skills/pipeline_audit_100.py (401 lines)
  VESSENCE_HOME = ... → L38
  VESSENCE_DATA_HOME = ... → L39
  PROMPT_DUMP = ... → L40
  REPORT_PATH = ... → L41
  SERVER = ... → L48
  KNOWN_CLASSES = ... → L53
  load_recent_prompts() → L63-89
  classify_only() → L95-103
  run_through_pipeline() → L106-168
  judge() → L174-230
  add_exemplar() → L236-262
  main() → L268-391

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

### agent_skills/safe_docker.py (124 lines)
  _ALLOWED_MOUNT_BASES = ... → L36
  _is_safe_mount() → L43-46
  run_docker() → L49-110
  _force_kill() → L113-124

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

### agent_skills/self_improve_log.py (143 lines)
  _VESSENCE_DATA_HOME = ... → L35
  VOCAL_LOG_PATH = ... → L39
  _SEVERITIES = ... → L41
  log_vocal_summary() → L44-104
  read_recent_summaries() → L107-143

### agent_skills/shopping_list.py (82 lines)
  VESSENCE_DATA_HOME = ... → L15
  LISTS_FILE = ... → L17
  _load() → L20-26
  _save() → L29-31
  get_all_lists() → L34-35
  get_list() → L38-39
  add_item() → L42-51
  remove_item() → L54-60
  clear_list() → L63-67
  format_for_context() → L70-82

### agent_skills/show_transcript.py (291 lines)
  DB_PATH = ... → L26
  get_conn() → L32-36
  _first_user_message() → L39-69
  list_sessions() → L72-101
  print_transcript() → L104-172
  search_sessions() → L175-236
  get_latest_session() → L239-252
  main() → L255-287

### agent_skills/sms_helpers.py (231 lines)
  _VAULT_WEB_DIR = ... → L26
  _STOP_PREFIXES = ... → L34
  DRAFT_TTL_SECONDS = ... → L37
  _normalize_name() → L40-47
  resolve_recipient() → L50-117
  add_alias() → L120-141
  create_draft() → L146-169
  get_latest_draft() → L172-201
  delete_draft() → L204-215
  cleanup_expired_drafts() → L218-231

### agent_skills/transcript_quality_review.py (537 lines)
  VESSENCE_HOME = ... → L40
  VESSENCE_DATA_HOME = ... → L44
  LOG_DIR = ... → L48
  REPORT_PATH = ... → L49
  CODEX_BIN = ... → L50
  CLAUDE_BIN = ... → L51
  PYTHON = ... → L52
  _load_prompt_dump() → L64-90
  _load_pipeline_events() → L93-110
  _load_android_events() → L113-147
  _build_condensed_context() → L150-181
  CODEX_PROMPT_TEMPLATE = ... → L187
  run_codex_review() → L251-294
  _log_vocal_summary_for_review() → L297-369
  write_codex_report() → L372-401
  CLAUDE_FIX_PROMPT_TEMPLATE = ... → L407
  run_claude_fixes() → L434-473
  main() → L479-533

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

### startup_code/bump_android_version.py (276 lines)
  VESSENCE_HOME = ... → L20
  VERSION_FILE = ... → L21
  ANDROID_DIR = ... → L22
  DOWNLOADS_DIR = ... → L23
  CHANGELOG = ... → L24
  MAIN_PY = ... → L25
  load_version() → L28-30
  save_version() → L33-36
  bump_patch() → L39-42
  update_main_py() → L45-52
  _load_env() → L55-66
  build_apk() → L69-89
  verify_apk_version() → L92-118
  ensure_changelog_entry() → L121-138
  update_marketing_links() → L141-159
  deploy_apk() → L162-169
  _aapt_path() → L172-183
  scan_deployed_max_version_code() → L186-214
  main() → L217-272

### startup_code/claude_full_startup_context.py (55 lines)
  DATA_ROOT = ... → L13
  VESSENCE_ROOT = ... → L14
  VAULT_ROOT = ... → L15
  DOCS = ... → L17
  read_doc() → L32-39
  main() → L42-51

### startup_code/first_run_setup.py (398 lines)
  VESSENCE_HOME = ... → L24
  VESSENCE_DATA_HOME = ... → L25
  ENV_FILE = ... → L28
  ENV_EXAMPLE = ... → L29
  read_env() → L37-48
  update_env() → L51-83
  bootstrap_env_file() → L86-105
  detect_cli_provider() → L113-119
  ask() → L122-132
  open_browser() → L135-140
  prompt_api_keys() → L148-181
  guide_google_oauth_setup() → L189-295
  main() → L303-394

### startup_code/installer_simulation.py (222 lines)
  class InstallerSimulationError → L13-14
  _write_executable() → L17-19
  _assert_install_result() → L22-43
  _simulate_unix() → L46-110
  _winepath() → L113-123
  _simulate_windows() → L126-210
  simulate_installer_package() → L213-222

### startup_code/intent_class_adversarial_hook.py (100 lines)
  CLASSES_DIR = ... → L24
  main() → L27-96

### startup_code/session_memory_dedup.py (125 lines)
  _entry_key() → L22-24
  _load_seen() → L27-33
  _save_seen() → L36-40
  _cleanup_old_caches() → L43-51
  dedup() → L54-102
  main() → L105-121

### startup_code/usb_backup.py (138 lines)
  get_mounted_drives() → L8-34
  get_total_size() → L36-52
  main() → L54-135

### vault_web/recent_turns.py (305 lines)
  DEFAULT_MAX_TURNS = ... → L41
  STRUCTURED_SCHEMA_VERSION = ... → L42
  add() → L45-76
  get_recent() → L79-102
  clear() → L105-113
  count() → L116-129
  _format_turn_compact() → L132-143
  _now_iso() → L159-160
  _normalize_record() → L163-176
  add_structured() → L179-208
  _row_to_record() → L211-228
  get_recent_structured() → L231-251
  _pending_is_active() → L254-268
  get_active_state() → L271-305

### vault_web/share.py (54 lines)
  SHARE_EXPIRY_DAYS = ... → L7
  create_share() → L10-20
  validate_share() → L23-41
  list_shares() → L44-49
  revoke_share() → L52-54
