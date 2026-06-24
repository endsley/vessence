# Vessence Refactor Journal

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
