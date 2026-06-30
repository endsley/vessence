# Vessence Refactor Journal

## 2026-06-30 - V2 Pipeline Helpers And Sanitizer Guard

Goal/scope:
- Finish the next behavior-preserving Vessence refactor slice without changing Jane route contracts, stream event shapes, FIFO markers, or Android client-tool marker semantics.
- Fix small verification bugs found during the pass instead of leaving known broken tests.

Files/modules changed:
- `jane_web/jane_v2/pipeline.py`
- `jane_web/jane_v2/awaiting_markers.py`
- `jane_web/jane_v2/stage2_response.py`
- `jane_web/jane_v2/pending_sms.py`
- `jane/sanitizers.py`
- `jane_web/jane_proxy.py`
- `jane_web/message_readback.py`
- `memory/v1/memory_retrieval.py`
- `agent_skills/doc_drift_auditor.py`
- Focused tests under `tests/`
- `configs/doc_drift_report.md`

Behavior intentionally preserved:
- Stage 3 `[[AWAITING:<topic>]]` markers are still stripped from streamed deltas and only activate when trailing the final response.
- Stage 2 replies still wrap only the spoken prefix in `<spoken>...</spoken>`, leaving client-tool and music markers outside the spoken text.
- SMS pending confirmation/draft markers keep the same structured FIFO records and client-tool marker payloads.
- `jane_web.jane_v2.pipeline` still exposes the private helper aliases imported by v3 compatibility code.
- Client-tool marker openers in untrusted context are still neutralized as `[[CLIENT-TOOL-STRIPPED:`.

Boundary chosen:
- The large v2 pipeline owned several pure helper concerns inline. Extracting awaiting-marker streaming, Stage 2 response formatting, and pending-SMS resolution reduced the pipeline by roughly 400 lines while keeping the orchestration and persistence code in place.
- The sanitizer bug was handled as a tiny shared helper in `jane.sanitizers` so `jane_proxy`, SMS readback, and memory retrieval use the same marker-neutralization behavior without importing from each other.
- The doc drift auditor now parses `_CLASS_MAP` with `ast.literal_eval` and parses the documented class table structurally, so aliases with spaces and class names containing digits do not create false drift warnings.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane/sanitizers.py jane_web/jane_proxy.py memory/v1/memory_retrieval.py jane_web/message_readback.py agent_skills/doc_drift_auditor.py jane_web/jane_v2/pending_sms.py jane_web/jane_v2/stage2_response.py jane_web/jane_v2/awaiting_markers.py jane_web/jane_v2/pipeline.py jane_web/jane_v3/pipeline.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_client_tool_sanitizer.py tests/test_doc_drift_auditor.py tests/test_pending_sms.py tests/test_stage2_response.py tests/test_awaiting_markers.py test_code/test_stage3_awaiting_marker.py -q` passed (`40 passed, 1 warning`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`38 passed`).
- `VESSENCE_HOME=/home/chieh/ambient/vessence /home/chieh/google-adk-env/adk-venv/bin/python agent_skills/doc_drift_auditor.py` passed with `0 fixes, 0 warnings`.

Remaining follow-up slices:
- `jane_web/main.py`, `jane_web/jane_proxy.py`, and `memory/v1/conversation_manager.py` are still the highest-value large-module targets; each needs characterization tests because they own live routes, stream contracts, or memory persistence behavior.
- The v2 pipeline is smaller now, but route orchestration, FIFO persistence, and Stage 3 streaming can still be split once the stream contract has broader tests.
- The deprecation warning in `jane_web/jane_v2/pending_action_resolver.py` still needs a small timezone-aware datetime cleanup.

## 2026-06-30 - Documentation Drift Auditor Cron State

Goal/scope:
- Keep the Vessence documentation drift auditor aligned with the cron registry's active/paused distinction.
- Preserve the existing audit behavior for active cron scripts, removed jobs, non-cron scripts, class-map checks, and skills-registry checks.

Files/modules changed:
- `agent_skills/doc_drift_auditor.py`
- `tests/test_doc_drift_auditor.py`
- `configs/CRON_JOBS.md`
- `configs/v2_3stage_pipeline.md`
- `configs/Jane_architecture.md`
- `configs/memory_manage_architecture.md`
- `configs/doc_drift_report.md`

Behavior intentionally preserved:
- Uncommented scripts from `crontab -l` are still treated as active.
- Removed jobs and non-cron scheduled scripts are still excluded from "claims active" warnings.
- Stage-1 class table drift still compares `configs/v2_3stage_pipeline.md` against `_CLASS_MAP`.

Boundary chosen:
- The bug was in the auditor's section-state parsing: cron jobs documented under a `Paused:` heading were still treated as active documentation claims. Adding `Paused:` to the existing inactive-header check fixes the false-positive path without changing the broader cron parsing algorithm.

Verification:
- `python -m py_compile agent_skills/doc_drift_auditor.py` passed.
- `python -m pytest tests/test_doc_drift_auditor.py -q` passed (`1 passed`).
- `agent_skills/doc_drift_auditor.py` ran after the documentation updates and wrote a clean `configs/doc_drift_report.md` with no warnings.

Remaining follow-up slices:
- The auditor still parses `_CLASS_MAP` with a regex and therefore needs table rows to use underscore aliases for class names containing spaces, such as `NATIONALGRID_BILLS`.
- A future refactor could parse `_CLASS_MAP` with `ast.literal_eval` to remove that documentation constraint.
- Broad Vessence size audit, excluding local virtualenv/build trees, found the largest source modules are `jane_web/main.py` (~6530 lines), `jane_web/jane_proxy.py` (~3847), `memory/v1/conversation_manager.py` (~2134), `jane_web/jane_v2/pipeline.py` (~2064), and `memory/v1/janitor_memory.py` (~1862). These are the right next refactor targets, but each needs characterization tests because they own live routes, stream contracts, persisted memory schemas, or provider/tool orchestration.
- Speed/process finding: repo-wide shell scans must exclude `venv/` (~724 MB) and `omniparser_venv/` (~7.2 GB). A naive `find . -name '*.py' | xargs wc -l` spent time counting vendored packages and produced unusable output; future audits should use `rg --files` with explicit excludes.

## 2026-06-24 - Android/Web Stream Client Helpers

Goal/scope:
- Refactor one behavior-preserving stream-client slice across Android and web.
- Keep Jane route contracts, NDJSON/SSE event names, response shapes, TTS behavior, and Android version metadata unchanged.

Files/modules changed:
- `android/app/src/main/java/com/vessences/android/util/AssistantMarkup.kt`
- `android/app/src/main/java/com/vessences/android/ui/chat/ChatViewModel.kt`
- `vault_web/templates/jane.html`

Behavior intentionally preserved:
- Android still strips `[ACK]...[/ACK]`, client-tool markers, `<spoken>`, `<visual>`, and awaiting markers before display/TTS in the same stream paths.
- Android still limits spoken fallback text to the same sentence/word/character caps and keeps the existing ellipsis behavior.
- Web still handles the same stream event set: `heartbeat`, `offloaded`, `model`, `ack`, `status`, `permission_request`, `thought`, `tool_use`, `tool_result`, `delta`, `done`, `error`, `provider_error`, and `conversation_end`.
- No route, API, persisted-data, APK version, changelog, or deploy behavior was changed.

Boundary chosen:
- Android assistant markup normalization was pure string logic embedded in `ChatViewModel`; extracting it to `AssistantMarkup` keeps the view model focused on stream orchestration, TTS queues, and UI state.
- Web `applyStreamEvent` repeatedly looked up the active Jane bubble and hand-mutated status logs; `_streamActiveMessage`, `_appendStreamStatus`, and `_finishStreamWithText` keep that local to the same Alpine component while reducing branch duplication.

Verification:
- `nice -n 19 ionice -c 3 ./gradlew :app:compileDebugKotlin` from `android/` passed.
- The Android compile also ran `verifyChangelog` for `v0.2.97` and `verifyOnnxModels`; both passed.
- `python -m py_compile jane_web/main.py jane_web/jane_proxy.py jane_web/broadcast.py vault_web/share.py vault_web/playlists.py` passed.
- Extracted JavaScript from `vault_web/templates/jane.html`, replaced the Jinja session placeholder with `null`, stripped `{% raw %}` markers, and ran `node --check`; it passed.

Remaining follow-up slices:
- Extract Android stream-turn processing out of `ChatViewModel` into a small state reducer after adding characterization tests for `delta`/`done`/tool-result flows.
- Split `vault_web/templates/jane.html` into static helper assets or smaller template partials once a template-aware frontend check exists.
- Audit `ShareReceiverActivity.kt`, `ArticleReaderV2Activity.kt`, and `MainActivity.kt` for similar pure helper/service extractions.
