# Dead Code Report — 2026-04-13 23:11

## Dead files — review needed (38)

(Candidates for deletion, but failed an auto-delete safety check —
 usually means the file is too new, too large, or outside agent_skills/test_code.)

- `agent_skills/update_identity.py`
- `agent_skills/verify_thematic_archivist.py`
- `agent_skills/show_transcript.py`
- `agent_skills/browser_utils.py`
- `agent_skills/update_idle_state.py`
- `test_code/test_build_docker_bundle_version.py`
- `test_code/test_jane_cli_login.py`
- `test_code/test_tax_accountant.py`
- `test_code/test_brain_adapters.py`
- `test_code/test_jane_context_builder.py`
- `test_code/test_show_job_queue.py`
- `test_code/test_persistent_gemini_recovery.py`
- `test_code/benchmark_gemma_weather_class_nocontext.py`
- `test_code/test_standing_brain_provider_sync.py`
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
- `test_code/test_share_summarize_flow.py`
- `test_code/benchmark_fifo_flow.py`
- `test_code/benchmark_gemma_routing_multi.py`
- `test_code/benchmark_v2_live.py`
- `test_code/verify_empty_install.py`
- `vault_web/setup_totp.py`
- `intent_classifier/v2/stage2_benchmark.py`
- `intent_classifier/v1/greeting_handler.py`
- `memory/v2/benchmarks/benchmark_initial_ack.py`
- `memory/v2/benchmarks/benchmark_baseline.py`
- `memory/v2/benchmarks/benchmark_gemma4.py`
- `startup_code/send_jane_announcement.py`
- `startup_code/build_seed_db.py`
- `startup_code/build_logo_options.py`

## Possibly-dead functions (90)

(No references found via grep. May be false positives if called via
 getattr, dynamic dispatch, or HTTP route registration.)

- `agent_skills/pipeline_audit_100.py` :: `load_recent_prompts()`
- `agent_skills/pipeline_audit_100.py` :: `add_exemplar()`
- `agent_skills/doc_drift_auditor.py` :: `record_change()`
- `agent_skills/doc_drift_auditor.py` :: `audit_cron()`
- `agent_skills/doc_drift_auditor.py` :: `audit_auditable_modules()`
- `agent_skills/doc_drift_auditor.py` :: `audit_pipeline_classes()`
- `agent_skills/doc_drift_auditor.py` :: `audit_class_packs()`
- `agent_skills/doc_drift_auditor.py` :: `audit_skills_registry()`
- `agent_skills/system_load.py` :: `has_ample_resources()`
- `agent_skills/nightly_self_improve.py` :: `write_summary()`
- `agent_skills/dead_code_auditor.py` :: `in_hard_skip()`
- `agent_skills/dead_code_auditor.py` :: `gather_python_files()`
- `agent_skills/dead_code_auditor.py` :: `grep_references()`
- `agent_skills/dead_code_auditor.py` :: `scan_dead_files()`
- `agent_skills/dead_code_auditor.py` :: `scan_dead_functions()`
- `agent_skills/dead_code_auditor.py` :: `normalize_body()`
- `agent_skills/dead_code_auditor.py` :: `scan_duplicates()`
- `agent_skills/dead_code_auditor.py` :: `can_auto_delete()`
- `agent_skills/dead_code_auditor.py` :: `auto_delete_safe_files()`
- `agent_skills/show_transcript.py` :: `get_conn()`
- `agent_skills/show_transcript.py` :: `print_transcript()`
- `agent_skills/show_transcript.py` :: `search_sessions()`
- `agent_skills/show_transcript.py` :: `get_latest_session()`
- `agent_skills/email_oauth.py` :: `load_gmail_token()`
- `agent_skills/fetch_weather.py` :: `fetch_pollen()`
- `agent_skills/email_tools.py` :: `get_gmail_service()`
- `agent_skills/email_tools.py` :: `delete_email()`
- `agent_skills/nightly_code_auditor.py` :: `load_whitelist()`
- `agent_skills/nightly_code_auditor.py` :: `pick_next_module()`
- `agent_skills/nightly_code_auditor.py` :: `is_clean_working_tree()`
- `agent_skills/nightly_code_auditor.py` :: `make_audit_branch()`
- `agent_skills/nightly_code_auditor.py` :: `revert_branch()`
- `agent_skills/nightly_code_auditor.py` :: `commit_changes()`
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
- `test_code/inspect_librarian_input.py` :: `build_prompts()`
- `test_code/inspect_librarian_input.py` :: `rough_tokens()`
- `test_code/inspect_librarian_input.py` :: `section_stats()`
- `test_code/test_intelligent_archival.py` :: `run_archival_process()`
- `test_code/test_vault_unit.py` :: `vault_dir()`
- … and 40 more

## Duplicate function bodies (14 groups)

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
- group `4138f3b3d2e5`:
    - `agent_skills/backfill_file_index_descriptions.py`
    - `memory/v1/index_vault.py`
- group `ddbb8df95d1a`:
    - `agent_skills/backfill_file_index_descriptions.py`
    - `memory/v1/index_vault.py`
- group `93e0ff45d8ab`:
    - `test_code/test_chrome_popen.py`
    - `test_code/test_browser.py`
- group `bc8782450676`:
    - `test_code/reproduce_fix_1.py`
    - `test_code/reproduce_fix_2.py`
- group `8d2d9d40e0c5`:
    - `test_code/benchmark_v2_stages_table.py`
    - `test_code/benchmark_v2_live.py`
- group `fd46e5d42a29`:
    - `jane_web/jane_v2/pipeline.py`
    - `jane_web/jane_v2/stage3_escalate.py`
- group `5fb0436bf3f6`:
    - `context_builder/v1/query_live_memory.py`
    - `startup_code/memory_daemon.py`
- group `009ebe3dcd3c`:
    - `memory/v1/local_vector_memory.py`
    - `memory/v1/conversation_manager.py`
    - `memory/v1/memory_retrieval.py`
    - `memory/v1/add_forgettable_memory.py`
- group `cea6d22860a3`:
    - `memory/v1/local_vector_memory.py`
    - `memory/v1/conversation_manager.py`
    - `memory/v1/memory_retrieval.py`
    - `memory/v1/add_forgettable_memory.py`
- group `ca9545b7727f`:
    - `memory/v2/benchmarks/benchmark_initial_ack.py`
    - `memory/v2/benchmarks/benchmark_gemma4.py`
- group `ac624300d25e`:
    - `memory/v2/benchmarks/benchmark_initial_ack.py`
    - `memory/v2/benchmarks/benchmark_gemma4.py`

