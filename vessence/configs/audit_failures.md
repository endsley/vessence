# Audit Failures

Failed audit attempts — auditor couldn't generate tests, fix bugs, or
ran out of time. These are pointers for human review.
Newest entries appended at bottom by `agent_skills/nightly_code_auditor.py`.

## 2026-05-09 01:00 — jane_web/jane_v2/classes/greeting/handler.py
Test generation failed.

## 2026-05-13 01:00 — jane_web/jane_v2/classes/shopping_list/handler.py
Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for jane_web/jane_v2/classes/shopping_list/handler.py', '--no-verify']' returned non-zero exit status 1.

## 2026-05-17 01:00 — jane_web/jane_v2/stage1_classifier.py
Test generation failed.

## 2026-05-21 01:00 — intent_classifier/v2/classifier.py
Tests failing after 3 fix attempts. Reverted.

Last test output:
```
============================= test session starts ==============================
platform linux -- Python 3.13.7, pytest-9.0.2, pluggy-1.6.0 -- /home/chieh/google-adk-env/adk-venv/bin/python
cachedir: .pytest_cache
rootdir: /home/chieh/ambient/vessence
plugins: asyncio-1.3.0, anyio-4.12.1, typeguard-4.5.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 37 items

test_code/auto_audit_classifier.py::test_spec_file_documents_stage1_algorithm_and_thresholds PASSED [  2%]
test_code/auto_audit_classifier.py::test_classifier_docstring_contract_names_shape_and_no_llm PASSED [  5%]
test_code/auto_audit_classifier.py::test_high_confidence_majority_returns_winning_class PASSED [  8%]
test_code/auto_audit_classifier.py::test_low_vote_fraction_delegates_to_opus PASSED [ 10%]
test_code/auto_audit_classifier.py::test_low_margin_delegates_to_opus PASSED [ 13%]
test_code/auto_audit_classifier.py::test_distance_floor_delegates_before_vote_result PASSED [ 16%]
test_code/auto_audit_classifier.py::test_query_uses_top_k_count_distance_and_metadata_includes PASSED [ 18%]
test_code/auto_audit_classifier.py::test_classifier_retries_once_when_cached_collection_is_stale PASSED [ 21%]
test_code/auto_audit_classifier.py::test_unexpected_collection_query_error_is_not_swallowed PASSED [ 24%]
test_code/auto_audit_classifier.py::test_very_long_input_skips_load_embedding_and_db PASSED [ 27%]
test_code/auto_audit
```

## 2026-05-25 01:00 — jane_web/jane_v2/classes/greeting/handler.py
Tests failing after 3 fix attempts. Reverted.

Last test output:
```
============================= test session starts ==============================
platform linux -- Python 3.13.7, pytest-9.0.2, pluggy-1.6.0 -- /home/chieh/google-adk-env/adk-venv/bin/python
cachedir: .pytest_cache
rootdir: /home/chieh/ambient/vessence
plugins: asyncio-1.3.0, anyio-4.12.1, typeguard-4.5.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 54 items

test_code/auto_audit_handler.py::TestDocumentedBehavior::test_spec_documents_greeting_stage2_contract PASSED [  1%]
test_code/auto_audit_handler.py::TestDocumentedBehavior::test_module_docstring_documents_simple_greeting_and_escalation_contract PASSED [  3%]
test_code/auto_audit_handler.py::TestDocumentedBehavior::test_basic_canned_greeting_returns_text_and_skips_ollama PASSED [  5%]
test_code/auto_audit_handler.py::TestDocumentedBehavior::test_common_greetings_use_documented_fast_path[how's it going?-check_in] PASSED [  7%]
test_code/auto_audit_handler.py::TestDocumentedBehavior::test_common_greetings_use_documented_fast_path[How are you-check_in] PASSED [  9%]
test_code/auto_audit_handler.py::TestDocumentedBehavior::test_common_greetings_use_documented_fast_path[what's up-check_in] PASSED [ 11%]
test_code/auto_audit_handler.py::TestDocumentedBehavior::test_common_greetings_use_documented_fast_path[HELLO!!!-hello] PASSED [ 12%]
test_code/auto_audit_handler.py::TestDocumentedBehavior::test_common_greetings_use_documented
```

## 2026-05-26 01:00 — jane_web/jane_v2/classes/send_message/handler.py
Tests failing after 3 fix attempts. Reverted.

Last test output:
```
============================= test session starts ==============================
platform linux -- Python 3.13.7, pytest-9.0.2, pluggy-1.6.0 -- /home/chieh/google-adk-env/adk-venv/bin/python
cachedir: .pytest_cache
rootdir: /home/chieh/ambient/vessence
plugins: asyncio-1.3.0, anyio-4.12.1, typeguard-4.5.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 26 items

test_code/auto_audit_handler.py::test_is_coherent[Hello there-True] PASSED [  3%]
test_code/auto_audit_handler.py::test_is_coherent[text my wife-True] PASSED [  7%]
test_code/auto_audit_handler.py::test_is_coherent[(none)-True] PASSED    [ 11%]
test_code/auto_audit_handler.py::test_is_coherent[-True] PASSED          [ 15%]
test_code/auto_audit_handler.py::test_is_coherent[I am at the-False] PASSED [ 19%]
test_code/auto_audit_handler.py::test_is_coherent[I want a-False] PASSED [ 23%]
test_code/auto_audit_handler.py::test_is_coherent[um hello-False] PASSED [ 26%]
test_code/auto_audit_handler.py::test_is_coherent[hello uh world-False] PASSED [ 30%]
test_code/auto_audit_handler.py::test_is_coherent[hey siri send a text-False] PASSED [ 34%]
test_code/auto_audit_handler.py::test_is_coherent[alexa what time is it-False] PASSED [ 38%]
test_code/auto_audit_handler.py::test_is_coherent[Alexander is my friend-True] PASSED [ 42%]
test_code/auto_audit_handler.py::test_is_coherent[I love the way you are-False] PASSED [ 46%]
test_code/
```

## 2026-06-01 01:00 — jane_web/jane_v2/stage2_dispatcher.py
Tests failing after 3 fix attempts. Reverted.

Last test output:
```
============================= test session starts ==============================
platform linux -- Python 3.13.7, pytest-9.0.2, pluggy-1.6.0 -- /home/chieh/google-adk-env/adk-venv/bin/python
cachedir: .pytest_cache
rootdir: /home/chieh/ambient/vessence
plugins: asyncio-1.3.0, anyio-4.12.1, typeguard-4.5.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 65 items

test_code/auto_audit_stage2_dispatcher.py::TestDispatchDocumentedBehavior::test_dispatch_invokes_async_handler_and_returns_dict PASSED [  1%]
test_code/auto_audit_stage2_dispatcher.py::TestDispatchDocumentedBehavior::test_dispatch_offloads_sync_handler_to_thread PASSED [  3%]
test_code/auto_audit_stage2_dispatcher.py::TestDispatchDocumentedBehavior::test_async_handler_is_awaited_directly PASSED [  4%]
test_code/auto_audit_stage2_dispatcher.py::TestDispatchDocumentedBehavior::test_missing_class_returns_none PASSED [  6%]
test_code/auto_audit_stage2_dispatcher.py::TestDispatchDocumentedBehavior::test_class_with_no_handler_returns_none PASSED [  7%]
test_code/auto_audit_stage2_dispatcher.py::TestDispatchDocumentedBehavior::test_declining_handler_returning_none_returns_none PASSED [  9%]
test_code/auto_audit_stage2_dispatcher.py::TestDispatchDocumentedBehavior::test_crashed_handler_returns_none PASSED [ 10%]
test_code/auto_audit_stage2_dispatcher.py::TestDispatchDocumentedBehavior::test_gate_rejection_returns_none_and_does_n
```

## 2026-06-06 01:00 — vault_web/recent_turns.py
Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for vault_web/recent_turns.py', '--no-verify']' returned non-zero exit status 1.

## 2026-06-16 01:00 — jane_web/jane_v2/recent_context.py
Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for jane_web/jane_v2/recent_context.py', '--no-verify']' returned non-zero exit status 1.

## 2026-06-17 01:00 — jane_web/jane_v2/recent_context.py
Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for jane_web/jane_v2/recent_context.py', '--no-verify']' returned non-zero exit status 1.

## 2026-06-18 01:00 — jane_web/jane_v2/recent_context.py
Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for jane_web/jane_v2/recent_context.py', '--no-verify']' returned non-zero exit status 1.

## 2026-06-20 01:00 — intent_classifier/v2/classifier.py
Tests failing after 3 fix attempts. Reverted.

Last test output:
```
============================= test session starts ==============================
platform linux -- Python 3.13.7, pytest-9.0.2, pluggy-1.6.0 -- /home/chieh/google-adk-env/adk-venv/bin/python
cachedir: .pytest_cache
rootdir: /home/chieh/ambient/vessence
plugins: asyncio-1.3.0, anyio-4.12.1, typeguard-4.5.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 46 items

test_code/auto_audit_classifier.py::test_spec_default_thresholds_match_precision_first_stage1_contract PASSED [  2%]
test_code/auto_audit_classifier.py::test_high_confidence_majority_vote_returns_documented_shape PASSED [  4%]
test_code/auto_audit_classifier.py::test_borderline_three_of_five_votes_delegates_per_spec PASSED [  6%]
test_code/auto_audit_classifier.py::test_margin_threshold_demotes_ambiguous_vote_even_when_confidence_floor_passes PASSED [  8%]
test_code/auto_audit_classifier.py::test_nearest_neighbor_distance_gate_overrides_unanimous_vote PASSED [ 10%]
test_code/auto_audit_classifier.py::test_long_prompt_word_gate_skips_embedding_and_chromadb PASSED [ 13%]
test_code/auto_audit_classifier.py::test_empty_input_is_safe_and_delegates_when_not_near_training_data PASSED [ 15%]
test_code/auto_audit_classifier.py::test_malformed_non_string_input_is_rejected_before_db_lookup[None] PASSED [ 17%]
test_code/auto_audit_classifier.py::test_malformed_non_string_input_is_rejected_before_db_lookup[123] PASSED [ 19%]
test_cod
```

## 2026-06-21 01:00 — agent_skills/sms_helpers.py
Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for agent_skills/sms_helpers.py', '--no-verify']' returned non-zero exit status 1.

## 2026-06-22 01:00 — agent_skills/sms_helpers.py
Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for agent_skills/sms_helpers.py', '--no-verify']' returned non-zero exit status 1.

## 2026-06-25 01:00 — vault_web/recent_turns.py
Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for vault_web/recent_turns.py', '--no-verify']' returned non-zero exit status 1.

## 2026-06-26 01:00 — vault_web/recent_turns.py
Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for vault_web/recent_turns.py', '--no-verify']' returned non-zero exit status 1.

## 2026-06-27 01:00 — vault_web/recent_turns.py
Auditor crashed: Command '['git', 'commit', '-m', 'auto-audit: add tests for vault_web/recent_turns.py', '--no-verify']' returned non-zero exit status 1.

