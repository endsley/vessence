# Dead Code Report — 2026-04-17 01:16

## Dead files — review needed (10)

(Candidates for deletion, but failed an auto-delete safety check —
 usually means the file is too new, too large, or outside agent_skills/test_code.)

- `agent_skills/log_activity_cli.py`
- `test_code/test_verify_first.py`
- `test_code/test_awaiting_stripper.py`
- `test_code/test_todo_list.py`
- `test_code/test_stop_thinking_cancel.py`
- `test_code/test_todo_list_classifier_adversarial.py`
- `test_code/verify_empty_install.py`
- `intent_classifier/v2/stage2_benchmark.py`
- `intent_classifier/v1/greeting_handler.py`
- `startup_code/build_logo_options.py`

## Possibly-dead functions (47)

(No references found via grep. May be false positives if called via
 getattr, dynamic dispatch, or HTTP route registration.)

- `agent_skills/gemma_query.py` :: `query_local_llm()`
- `test_code/inspect_librarian_input.py` :: `section_stats()`
- `test_code/test_intelligent_archival.py` :: `run_archival_process()`
- `test_code/test_vault_unit.py` :: `vault_dir()`
- `test_code/test_vault_unit.py` :: `authed_client()`
- `test_code/test_vault_unit.py` :: `totp_secret()`
- `test_code/verify_empty_install.py` :: `active_dockerfiles()`
- `test_code/verify_empty_install.py` :: `assert_no_seeded_memory()`
- `test_code/verify_empty_install.py` :: `assert_compose_uses_host_mounts()`
- `test_code/verify_empty_install.py` :: `assert_dockerfiles_do_not_copy_runtime_data()`
- `jane_web/task_offloader.py` :: `heartbeat_loop()`
- `jane_web/reverse_proxy.py` :: `drain_active()`
- `jane_web/verify_first_policy.py` :: `needs_memory_evidence()`
- `jane_web/main.py` :: `get_trusted_device_cookie_id()`
- `jane_web/main.py` :: `check_share_or_auth()`
- `jane_web/main.py` :: `is_android_webview_request()`
- `jane_web/main.py` :: `queue_device_command()`
- `jane_web/main.py` :: `iter_file()`
- `intent_classifier/v2/stage2_benchmark.py` :: `ollama_call()`
- `intent_classifier/v2/stage2_benchmark.py` :: `parse_fields()`
- `intent_classifier/v2/stage2_benchmark.py` :: `score_response()`
- `intent_classifier/v2/experiment.py` :: `load_registry()`
- `intent_classifier/v2/experiment.py` :: `get_embedding_fn()`
- `intent_classifier/v2/experiment.py` :: `build_chroma_collection()`
- `intent_classifier/v2/experiment.py` :: `classify_by_embedding()`
- `intent_classifier/v2/experiment.py` :: `llm_extract_metadata()`
- `intent_classifier/v2/experiment.py` :: `classify_baseline_llm()`
- `intent_classifier/v2/experiment.py` :: `parse_baseline_class()`
- `intent_classifier/v2/experiment.py` :: `run_experiment()`
- `intent_classifier/v1/gemma_router.py` :: `get_active_model()`
- `intent_classifier/v1/greeting_handler.py` :: `is_pure_greeting()`
- `context_builder/v1/context_builder.py` :: `lookup_contact()`
- `context_builder/v1/context_builder.py` :: `format_contact_info()`
- `memory/v1/janitor_memory.py` :: `refresh_dynamic_query_markers()`
- `memory/v1/janitor_memory.py` :: `verify_code_memories()`
- `memory/v2/benchmarks/generate_mock_trees.py` :: `generate_tree_compact()`
- `memory/v2/benchmarks/generate_mock_trees.py` :: `generate_tree_flat()`
- `memory/v2/benchmarks/benchmark_gemma4.py` :: `call_gemma4()`
- `startup_code/first_run_setup.py` :: `read_env()`
- `startup_code/first_run_setup.py` :: `bootstrap_env_file()`
- `startup_code/first_run_setup.py` :: `detect_cli_provider()`
- `startup_code/first_run_setup.py` :: `prompt_api_keys()`
- `startup_code/first_run_setup.py` :: `guide_google_oauth_setup()`
- `startup_code/bump_android_version.py` :: `ensure_changelog_entry()`
- `startup_code/bump_android_version.py` :: `update_marketing_links()`
- `startup_code/bump_android_version.py` :: `scan_deployed_max_version_code()`
- `startup_code/build_logo_options.py` :: `write_gallery()`

## Duplicate function bodies (21 groups)

(Identical bodies — candidates for extraction into a shared helper.)

- group `681f62da338a`:
    - `agent_skills/llm_summarize.py`
    - `agent_skills/gemma_summarize.py`
- group `a06f6fffc42f`:
    - `agent_skills/llm_summarize.py`
    - `agent_skills/gemma_summarize.py`
- group `e8a455e1797c`:
    - `agent_skills/llm_summarize.py`
    - `agent_skills/gemma_summarize.py`
- group `36e71a17864b`:
    - `agent_skills/llm_summarize.py`
    - `agent_skills/gemma_summarize.py`
- group `8dd258284513`:
    - `agent_skills/llm_summarize.py`
    - `agent_skills/gemma_summarize.py`
- group `ff7537e8f176`:
    - `agent_skills/llm_summarize.py`
    - `agent_skills/gemma_summarize.py`
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
- group `db44ee464c52`:
    - `test_code/test_awaiting_stripper.py`
    - `test_code/test_awaiting_stripper.py`
    - `test_code/test_awaiting_stripper.py`
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
- … and 1 more groups

