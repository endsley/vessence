# Dead Code Report — 2026-04-22 01:14

## Dead files — review needed (1)

(Candidates for deletion, but failed an auto-delete safety check —
 usually means the file is too new, too large, or outside agent_skills/test_code.)

- `test_code/test_device_diagnostics_auth.py`

## Possibly-dead functions (13)

(No references found via grep. May be false positives if called via
 getattr, dynamic dispatch, or HTTP route registration.)

- `agent_skills/dead_code_auditor.py` :: `is_dynamically_imported()`
- `test_code/test_vault_unit.py` :: `vault_dir()`
- `test_code/test_vault_unit.py` :: `authed_client()`
- `test_code/test_vault_unit.py` :: `totp_secret()`
- `jane_web/task_offloader.py` :: `heartbeat_loop()`
- `jane_web/main.py` :: `get_trusted_device_cookie_id()`
- `jane_web/main.py` :: `check_share_or_auth()`
- `jane_web/main.py` :: `is_android_webview_request()`
- `jane_web/main.py` :: `queue_device_command()`
- `jane_web/main.py` :: `iter_file()`
- `memory/v1/janitor_memory.py` :: `refresh_dynamic_query_markers()`
- `memory/v1/janitor_memory.py` :: `verify_code_memories()`
- `memory/v1/janitor_memory.py` :: `purge_old_self_improve_reports()`

## Duplicate function bodies (9 groups)

(Identical bodies — candidates for extraction into a shared helper.)

- group `0544497f123a`:
    - `agent_skills/job_queue_runner.py`
    - `agent_skills/prompt_queue_runner.py`
- group `2801b6ebda51`:
    - `agent_skills/ambient_heartbeat.py`
    - `agent_skills/ambient_task_research.py`
- group `e70d20004e7a`:
    - `agent_skills/nightly_audit.py`
    - `startup_code/usb_sync.py`
    - `startup_code/usb_rotation.py`
- group `803f372feb5b`:
    - `test_code/web_automation/test_actions_and_skill.py`
    - `test_code/web_automation/test_artifacts.py`
- group `fd46e5d42a29`:
    - `jane_web/jane_v3/pipeline.py`
    - `jane_web/jane_v2/pipeline.py`
    - `jane_web/jane_v2/stage3_escalate.py`
- group `5fb0436bf3f6`:
    - `context_builder/v1/query_live_memory.py`
    - `startup_code/memory_daemon.py`
- group `8105d9a2dea2`:
    - `context_builder/v1/query_live_memory.py`
    - `startup_code/codex_memory_mcp.py`
- group `cea6d22860a3`:
    - `context_builder/v1/query_live_memory.py`
    - `memory/v1/local_vector_memory.py`
    - `memory/v1/conversation_manager.py`
    - `memory/v1/memory_retrieval.py`
    - `memory/v1/add_forgettable_memory.py`
    - `startup_code/codex_memory_mcp.py`
- group `009ebe3dcd3c`:
    - `memory/v1/local_vector_memory.py`
    - `memory/v1/conversation_manager.py`
    - `memory/v1/memory_retrieval.py`
    - `memory/v1/add_forgettable_memory.py`

