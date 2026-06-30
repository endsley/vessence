# Vessence Refactor Journal

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
