# Dead Code Report — 2026-04-21 01:16

## Dead files — review needed (40)

(Candidates for deletion, but failed an auto-delete safety check —
 usually means the file is too new, too large, or outside agent_skills/test_code.)

- `agent_skills/update_identity.py`
- `agent_skills/verify_thematic_archivist.py`
- `agent_skills/browser_utils.py`
- `agent_skills/update_idle_state.py`
- `test_code/test_build_docker_bundle_version.py`
- `test_code/test_jane_cli_login.py`
- `test_code/test_tax_accountant.py`
- `test_code/test_brain_adapters.py`
- `test_code/test_jane_context_builder.py`
- `test_code/test_show_job_queue.py`
- `test_code/test_stage2_followup_pending_resolution.py`
- `test_code/test_persistent_gemini_recovery.py`
- `test_code/test_calendar_tools.py`
- `test_code/benchmark_gemma_weather_class_nocontext.py`
- `test_code/test_self_improve_2026_04_18.py`
- `test_code/test_standing_brain_provider_sync.py`
- `test_code/test_pending_action_resolver.py`
- `test_code/test_jane_session_wrapper_unit.py`
- `test_code/test_onboarding_installer_paths.py`
- `test_code/test_google_oauth_config.py`
- `test_code/test_installer_simulation.py`
- `test_code/benchmark_gemma_weather_class_schema.py`
- `test_code/test_onboarding_settings.py`
- `test_code/test_jane_proxy_persistence.py`
- `test_code/benchmark_v2_stages_v2.py`
- `test_code/benchmark_gemma_weather_class.py`
- `test_code/test_jane_platform_parity.py`
- `test_code/test_recent_turns_structured.py`
- `test_code/test_share_summarize_flow.py`
- `test_code/benchmark_fifo_flow.py`
- `test_code/benchmark_gemma_routing_multi.py`
- `test_code/benchmark_v3_model_compare.py`
- `test_code/test_stage3_awaiting_marker.py`
- `vault_web/setup_totp.py`
- `intent_classifier/v2/classes/restart_server.py`
- `memory/v1/persistence_batch.py`
- `memory/v2/benchmarks/benchmark_baseline.py`
- `startup_code/send_jane_announcement.py`
- `startup_code/build_seed_db.py`
- `startup_code/build_windows_exe.py`

## Possibly-dead functions (35)

(No references found via grep. May be false positives if called via
 getattr, dynamic dispatch, or HTTP route registration.)

- `agent_skills/janitor_system.py` :: `prune_turn_dedupe()`
- `agent_skills/nightly_self_improve.py` :: `write_readable_report()`
- `agent_skills/nightly_code_auditor.py` :: `run_claude()`
- `agent_skills/nightly_code_auditor.py` :: `phase1_generate_tests()`
- `agent_skills/nightly_code_auditor.py` :: `phase2_run_tests()`
- `agent_skills/nightly_code_auditor.py` :: `phase3_attempt_fix()`
- `test_code/test_jane_cli_login.py` :: `fake_attempt()`
- `test_code/test_jane_cli_login.py` :: `fake_status()`
- `test_code/generate_test_registry.py` :: `extract_summary()`
- `test_code/test_janitor_logs.py` :: `setup_test()`
- `test_code/test_jane_session_wrapper_unit.py` :: `close_manager()`
- `test_code/test_vault_web.py` :: `inject_session()`
- `test_code/test_vault_web.py` :: `inject_otp()`
- `test_code/test_vault_web.py` :: `clear_failed_attempts()`
- `memory/v1/local_vector_memory.py` :: `list_all_for_reorg()`
- `memory/v1/index_vault.py` :: `is_already_tracked()`
- `memory/v1/index_vault.py` :: `add_to_chromadb()`
- `memory/v1/index_vault.py` :: `load_hash_index()`
- `memory/v1/index_vault.py` :: `save_hash_index()`
- `memory/v1/index_vault.py` :: `describe_image()`
- `memory/v1/index_vault.py` :: `extract_readable_text()`
- `memory/v1/index_vault.py` :: `describe_readable_file()`
- `memory/v1/index_vault.py` :: `scan_vault()`
- `memory/v1/topic_memory.py` :: `process_turn()`
- `memory/v1/topic_memory.py` :: `fire_and_forget()`
- `memory/v1/persistence_batch.py` :: `update_persistence_batched_sync()`
- `memory/v1/janitor_memory.py` :: `purge_expired_forgettable()`
- `memory/v1/janitor_memory.py` :: `backfill_thematic_archival()`
- `memory/v1/janitor_memory.py` :: `dedup_cross_session_themes()`
- `memory/v2/benchmarks/benchmark_baseline.py` :: `run_baseline()`
- `startup_code/build_windows_exe.py` :: `find_latest_zip()`
- `startup_code/build_windows_exe.py` :: `extract_version()`
- `startup_code/build_windows_exe.py` :: `update_download_links()`
- `startup_code/build_windows_exe.py` :: `add_windows_download_if_missing()`
- `startup_code/build_windows_exe.py` :: `build_exe()`

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

