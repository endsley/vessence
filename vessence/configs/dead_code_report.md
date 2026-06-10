# Dead Code Report — 2026-06-10 01:13

## Possibly-dead functions (1)

(No references found via grep. May be false positives if called via
 getattr, dynamic dispatch, or HTTP route registration.)

- `memory/v1/embedding_helpers.py` :: `embed_many()`

## Duplicate function bodies (10 groups)

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
- group `11aebc14d001`:
    - `jane_web/jane_v2/classes/read_calendar/handler.py`
    - `jane_web/jane_v2/classes/weather/handler.py`
    - `jane_web/jane_v2/classes/timer/handler.py`
- group `5fb0436bf3f6`:
    - `context_builder/v1/query_live_memory.py`
    - `startup_code/memory_daemon.py`
- group `8105d9a2dea2`:
    - `context_builder/v1/query_live_memory.py`
    - `startup_code/codex_memory_mcp.py`
    - `startup_code/codex_auto_memory.py`
- group `cea6d22860a3`:
    - `context_builder/v1/query_live_memory.py`
    - `memory/v1/local_vector_memory.py`
    - `memory/v1/conversation_manager.py`
    - `memory/v1/add_forgettable_memory.py`
    - `startup_code/codex_memory_mcp.py`
    - `startup_code/codex_auto_memory.py`
- group `009ebe3dcd3c`:
    - `memory/v1/local_vector_memory.py`
    - `memory/v1/conversation_manager.py`
    - `memory/v1/add_forgettable_memory.py`

