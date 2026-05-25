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

