# Vessence Refactor Journal

## 2026-07-02 - Fifteen-Hour Refactor Closeout

Goal/scope:
- Close the extended refactor run with the current verified architecture state.
- Document the boundaries that are now stable enough for future passes and the targets intentionally deferred.

Files/modules changed:
- `REFACTORING.md`

Architecture state after this run:
- Context building now has dedicated v1 modules for source readers, managed-user context, tool protocols, prompt profiles, memory planning/summaries, saved articles, recent history, system prompt sections, and user background.
- Jane v2 handler code is split further by domain: timer parsing/responses/tool markers, TODO parsing/categories/responses/cache, shopping-list actions/responses, weather slices/phrasing/responses, calendar formatting/prompts/responses, send-message parsing/prompts/responses, and clinic schedule helpers/prompts/responses.
- v2 client-tool/SMS/timer/music markers now use shared marker builders rather than each handler shaping marker JSON itself.
- v2 Ollama posting now has a shared transport helper, plus a local-model wrapper used by the simple local generation handlers. The remaining direct call sites are intentionally policy-specific.
- Memory and agent-skill modules have many newly extracted helpers from earlier slices in this run; the maintained test suite covers those boundaries.

Behavior intentionally preserved:
- Public route contracts, FIFO marker shapes, Stage 1 class mapping, Stage 2 handler return shapes, Stage 3 delegation semantics, pending-action payload shapes, cache formats, and Android/client-tool marker contracts were kept stable.
- No server restart was performed.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1340 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest test_code/auto_audit_stage1_classifier.py -q` passed (`132 passed`).
- `git diff --check` passed.

Remaining follow-up slices:
- `jane_web/main.py`, `jane_web/jane_proxy.py`, `memory/v1/conversation_manager.py`, and `memory/v1/janitor_memory.py` are still the largest worthwhile structural targets; each needs route, stream, or persistence characterization before further splitting.
- Remaining direct v2 Ollama call sites should stay separate until a future helper explicitly models their custom payload argument shape, fallback policy, and activity-recording behavior.
- Existing dirty generated/self-improvement config files were not reverted.

## 2026-07-02 - Shared Local LLM Post Wrapper

Goal/scope:
- Extract the repeated simple-handler local Ollama wrapper that imports v2 model settings, builds a payload, and posts it.
- Migrate duplicate wrappers in `do_math`, `get_time`, `tell_joke`, `read_calendar`, `greeting`, `weather`, send-message extraction, clinic phrasing, and pending SMS draft edits.

Files/modules changed:
- `jane_web/jane_v2/ollama_client.py`
- `jane_web/jane_v2/classes/do_math/handler.py`
- `jane_web/jane_v2/classes/get_time/handler.py`
- `jane_web/jane_v2/classes/clinic_schedules_info/handler.py`
- `jane_web/jane_v2/classes/greeting/canned.py`
- `jane_web/jane_v2/classes/greeting/handler.py`
- `jane_web/jane_v2/classes/read_calendar/handler.py`
- `jane_web/jane_v2/classes/send_message/extraction_prompt.py`
- `jane_web/jane_v2/classes/send_message/handler.py`
- `jane_web/jane_v2/classes/tell_joke/handler.py`
- `jane_web/jane_v2/classes/weather/handler.py`
- `jane_web/jane_v2/classes/weather/phrasing.py`
- `jane_web/jane_v2/pending_sms.py`
- `tests/test_ollama_client.py`
- `tests/test_clinic_schedule_helpers.py`
- `tests/test_do_math_evaluator.py`
- `tests/test_get_time_helpers.py`
- `tests/test_greeting_canned.py`
- `tests/test_read_calendar_prompts.py`
- `tests/test_send_message_parsing.py`
- `tests/test_tell_joke_helpers.py`
- `tests/test_weather_slices.py`
- `tests/test_pending_sms.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The migrated handlers still use `LOCAL_LLM`, `LOCAL_LLM_NUM_CTX`, `LOCAL_LLM_TIMEOUT`, `OLLAMA_KEEP_ALIVE`, and `OLLAMA_URL` from `jane_web.jane_v2.models`.
- Payload shapes stay owned by each handler's prompt/helper module.
- Calendar's `num_predict` selection remains per call through explicit payload kwargs.
- Greeting, weather, and send-message extraction payload builders now accept keep-alive explicitly while preserving the previous `-1` default.
- Clinic phrasing keeps the same structured-context prompt and fallback strings while sharing the model-settings/post wrapper.
- Pending SMS draft edits keep the same rewrite prompt, payload options, quote cleanup, and fallback-to-concat behavior.
- Ollama activity recording still goes through the existing `post_ollama_response()` default path.
- Handler fallback/escalation behavior on Ollama errors is unchanged.

Boundary chosen:
- These handlers had the same wrapper shape and focused tests around payload builders.
- Other v2 call sites were intentionally left alone because they have different argument shapes, suppress activity recording, or have branch-specific fallback policy.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/ollama_client.py jane_web/jane_v2/classes/do_math/handler.py jane_web/jane_v2/classes/get_time/handler.py jane_web/jane_v2/classes/tell_joke/handler.py tests/test_ollama_client.py tests/test_do_math_evaluator.py tests/test_get_time_helpers.py tests/test_tell_joke_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ollama_client.py tests/test_do_math_evaluator.py tests/test_get_time_helpers.py tests/test_tell_joke_helpers.py -q` passed (`27 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/ollama_client.py jane_web/jane_v2/classes/read_calendar/handler.py tests/test_ollama_client.py tests/test_read_calendar_prompts.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ollama_client.py tests/test_read_calendar_prompts.py tests/test_read_calendar_formatting.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/greeting/handler.py jane_web/jane_v2/classes/greeting/canned.py jane_web/jane_v2/classes/weather/handler.py jane_web/jane_v2/classes/weather/phrasing.py tests/test_greeting_canned.py tests/test_weather_slices.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_greeting_canned.py tests/test_weather_slices.py tests/test_ollama_client.py -q` passed (`15 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/send_message/handler.py jane_web/jane_v2/classes/send_message/extraction_prompt.py tests/test_send_message_parsing.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_send_message_parsing.py tests/test_ollama_client.py -q` passed (`15 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/clinic_schedules_info/handler.py tests/test_clinic_schedule_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_clinic_schedule_helpers.py tests/test_ollama_client.py -q` passed (`13 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/pending_sms.py tests/test_pending_sms.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_pending_sms.py tests/test_ollama_client.py -q` passed (`8 passed`).

Remaining follow-up slices:
- A future helper could support payload builders with extra settings such as `num_predict`, but that should be driven by focused tests for read-calendar and dispatcher policy.
- Send-message, pending SMS, dispatcher, unclear prompt, and delegate-ack call sites should stay separate unless a future helper explicitly models their custom payload arguments and fallback/activity policy.

## 2026-07-02 - TODO List Response Builder Cleanup

Goal/scope:
- Move the remaining generic TODO-list response dictionary construction out of the Stage 2 handler.
- Keep handler control flow, Google Docs edit calls, cache refresh behavior, pending-action payloads, and spoken text unchanged.

Files/modules changed:
- `jane_web/jane_v2/classes/todo_list/handler.py`
- `jane_web/jane_v2/classes/todo_list/responses.py`
- `tests/test_todo_list_responses.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing-cache, empty-list, add/remove success, add/remove failure, add-item follow-up, remove-item follow-up, and ask-category responses keep the same `text` and `structured` shapes.
- Existing `STAGE2_FOLLOWUP` pending-action fields, handler class, awaiting values, question text, and expiration format are unchanged.
- The handler's edit/resume branching and external `agent_skills.docs_tools` calls are unchanged.

Boundary chosen:
- `todo_list/responses.py` already owned most TODO response builders, so moving the remaining shared shapes there reduces handler noise without touching parsing, category matching, cache I/O, or Google Docs integration.
- This is safer than opening another large route/module split near the end of the timebox.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/todo_list/handler.py jane_web/jane_v2/classes/todo_list/responses.py tests/test_todo_list_responses.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_todo_list_responses.py tests/test_todo_list_categories.py tests/test_todo_list_parsing.py tests/test_todo_list_cache.py -q` passed (`23 passed`).

Remaining follow-up slices:
- `todo_list/handler.py` still contains Google Docs edit side effects and resume orchestration; further splitting should wait for handler-level characterization around successful add/remove paths with mocked docs tools.
- Larger targets remain `jane_web/main.py`, `jane_web/jane_proxy.py`, and memory persistence modules, but they need route/stream/persistence characterization before edits.

## 2026-07-02 - Delegate Ack Ollama Client Migration

Goal/scope:
- Route Stage 3 delegate-ack generation through the shared `post_ollama_response()` helper.
- Add a focused test that covers `_generate_delegate_ack()` through prompt construction, helper call, and normalization.

Files/modules changed:
- `jane_web/jane_v2/pipeline.py`
- `tests/test_delegate_ack.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Ack generation still uses the same hardcoded Ollama generate URL.
- Ack payload options, keep-alive logic, and normalization remain unchanged.
- Failures still return the static delegate ack fallback.

Boundary chosen:
- Ollama transport and activity recording now use shared infrastructure.
- Delegate ack prompt construction, duration estimation, and fallback policy remain in the pipeline/delegate-ack helpers.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/pipeline.py tests/test_delegate_ack.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ollama_client.py tests/test_delegate_ack.py tests/test_jane_v2_pipeline_helpers.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1337 passed`).

Remaining follow-up slices:
- Most covered v2 local-Ollama call sites now use the shared helper; remaining direct calls should be audited with branch-specific tests first.

## 2026-07-02 - Unclear Prompt Ollama Client Migration

Goal/scope:
- Route unclear-prompt detection through the shared `post_ollama_response()` helper.
- Add focused tests for UNCLEAR classification and fail-open behavior on helper errors.

Files/modules changed:
- `jane_web/jane_v2/unclear_prompt.py`
- `tests/test_unclear_prompt.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Blank prompts still return clear without calling the LLM.
- Model import failures and Ollama errors still fail open as clear.
- Returned text is still stripped/uppercased before checking for `UNCLEAR`.

Boundary chosen:
- Ollama transport and activity recording use shared infrastructure.
- Prompt construction, fail-open policy, and UNCLEAR interpretation remain in `unclear_prompt.py`.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/unclear_prompt.py tests/test_unclear_prompt.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ollama_client.py tests/test_unclear_prompt.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1336 passed`).

Remaining follow-up slices:
- Pipeline-level LLM checks remain broader and should be migrated only with direct pipeline branch tests.

## 2026-07-02 - Stage 2 Dispatcher Ollama Client Migration

Goal/scope:
- Route Stage 2 continuation and gate-check LLM calls through the shared `post_ollama_response()` helper.
- Preserve the prior difference where continuation checks did not record Ollama activity but gate checks did.

Files/modules changed:
- `jane_web/jane_v2/stage2_dispatcher.py`
- `tests/test_stage2_dispatcher_prompts.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Short continuation replies still skip the LLM call.
- Continuation check failures still fail open as same-topic.
- Gate-check failures still fail open as class-accepted.
- Continuation checks still interpret `CHANGED*` as topic pivot, and gate checks still interpret `NO*` as wrong class.

Boundary chosen:
- Ollama transport and response extraction now use shared infrastructure.
- Dispatcher-specific fail-open policy and answer interpretation remain in the dispatcher.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/stage2_dispatcher.py tests/test_stage2_dispatcher_prompts.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ollama_client.py tests/test_stage2_dispatcher_prompts.py tests/test_stage2_handler_invocation.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1334 passed`).

Remaining follow-up slices:
- Pipeline-level and unclear-prompt LLM calls still have broader routing context; migrate only with focused tests for their exact fail-open/fallback behavior.

## 2026-07-02 - Pending SMS Ollama Client Migration

Goal/scope:
- Route pending SMS draft-edit composition through the shared `post_ollama_response()` helper.
- Add a focused async test for the successful draft-edit path.

Files/modules changed:
- `jane_web/jane_v2/pending_sms.py`
- `tests/test_pending_sms.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Draft-edit prompt and generation options remain unchanged.
- Empty or failed LLM output still falls back to appending the edit instruction to the old draft body.
- Successful output still strips quote wrapping and a leading `New body:` prefix before emitting `sms_draft_update`.

Boundary chosen:
- Ollama HTTP transport and activity recording use the shared helper.
- SMS draft-edit prompt construction and fallback behavior remain in `pending_sms.py`.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/pending_sms.py tests/test_pending_sms.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ollama_client.py tests/test_pending_sms.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1334 passed`).

Remaining follow-up slices:
- Dispatcher and pipeline local-LLM gates can migrate if their prompt/result contracts are covered directly.

## 2026-07-02 - Send Message Ollama Client Migration

Goal/scope:
- Route the send-message Stage 2 extraction LLM call through the shared `post_ollama_response()` helper.
- Keep extraction payload construction, parse fallback, and escalation behavior in the handler.

Files/modules changed:
- `jane_web/jane_v2/classes/send_message/handler.py`
- `tests/test_send_message_parsing.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- LLM extraction failures still return `None` so Stage 3 can handle the turn.
- Successful responses are still parsed through `parse_extraction()`.
- Existing extraction payload options remain unchanged.

Boundary chosen:
- HTTP transport and activity recording use the shared helper.
- Send-message-specific extraction parsing and safety routing stay local.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/send_message/handler.py tests/test_send_message_parsing.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ollama_client.py tests/test_send_message_parsing.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1333 passed`).

Remaining follow-up slices:
- Pending SMS draft-edit LLM composition can migrate next if its fallback concat behavior is explicitly covered.

## 2026-07-02 - Greeting and Calendar Ollama Client Migration

Goal/scope:
- Route greeting and read-calendar Stage 2 Ollama calls through the shared `post_ollama_response()` helper.
- Keep their prompt building, generation options, and fallback behavior unchanged.

Files/modules changed:
- `jane_web/jane_v2/classes/greeting/handler.py`
- `jane_web/jane_v2/classes/read_calendar/handler.py`
- `tests/test_greeting_canned.py`
- `tests/test_read_calendar_prompts.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Greeting still escalates on empty output, wrong-class output, or Ollama failure.
- Read-calendar still returns `None` on empty output or Ollama failure.
- Both handlers still use their existing payload helper functions and model settings.

Boundary chosen:
- HTTP transport and activity recording now live in the shared Ollama helper.
- Handler-specific routing/fallback policy remains local.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/greeting/handler.py jane_web/jane_v2/classes/read_calendar/handler.py tests/test_greeting_canned.py tests/test_read_calendar_prompts.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ollama_client.py tests/test_greeting_canned.py tests/test_read_calendar_prompts.py tests/test_read_calendar_formatting.py -q` passed (`18 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1333 passed`).

Remaining follow-up slices:
- Remaining Ollama call sites include dispatcher/pipeline-specific logic and should migrate only with focused dispatcher tests.

## 2026-07-02 - Shared Stage 2 Ollama Client

Goal/scope:
- Add `jane_web/jane_v2/ollama_client.py` with a shared async Ollama POST helper.
- Route do-math, get-time, tell-joke, weather, and clinic Stage 2 handlers through the helper.
- Keep each handler responsible for building its own payload and fallback behavior.

Files/modules changed:
- `jane_web/jane_v2/ollama_client.py`
- `jane_web/jane_v2/classes/do_math/handler.py`
- `jane_web/jane_v2/classes/get_time/handler.py`
- `jane_web/jane_v2/classes/tell_joke/handler.py`
- `jane_web/jane_v2/classes/weather/handler.py`
- `jane_web/jane_v2/classes/clinic_schedules_info/handler.py`
- `tests/test_ollama_client.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Each handler still posts the same payload it previously built.
- Responses are still stripped from the `response` JSON field.
- `record_ollama_activity()` remains best-effort and non-fatal.
- Handler-specific exception handling and fallback text remain local.

Boundary chosen:
- HTTP transport, status raising, response extraction, and activity recording are shared infrastructure.
- Prompt construction, model options, timeouts, and user-facing fallback policy remain with each handler.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/ollama_client.py jane_web/jane_v2/classes/do_math/handler.py jane_web/jane_v2/classes/get_time/handler.py jane_web/jane_v2/classes/tell_joke/handler.py jane_web/jane_v2/classes/weather/handler.py jane_web/jane_v2/classes/clinic_schedules_info/handler.py tests/test_ollama_client.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ollama_client.py tests/test_do_math_evaluator.py tests/test_tell_joke_helpers.py tests/test_weather_slices.py tests/test_clinic_schedule_helpers.py -q` passed (`39 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1333 passed`).

Remaining follow-up slices:
- Other Ollama call sites can migrate if their fallback behavior is already covered.

## 2026-07-02 - Shopping List Response Builders

Goal/scope:
- Move shopping-list view/add/remove/clear/check response text construction into `jane_web/jane_v2/classes/shopping_list/responses.py`.
- Keep parameter validation, store imports, and list mutation inside the handler.

Files/modules changed:
- `jane_web/jane_v2/classes/shopping_list/responses.py`
- `jane_web/jane_v2/classes/shopping_list/handler.py`
- `tests/test_shopping_list_actions.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Empty and non-empty list views keep the same text.
- Add/remove/clear responses keep the same phrasing and item joining.
- Check responses still use the existing present/missing phrasing helper.

Boundary chosen:
- Response text construction is deterministic Stage 2 response policy.
- Shopping-list persistence and mutation remain in the handler.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/shopping_list/responses.py jane_web/jane_v2/classes/shopping_list/handler.py tests/test_shopping_list_actions.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_shopping_list_actions.py tests/test_shopping_list_data.py -q` passed (`15 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1332 passed`).

Remaining follow-up slices:
- Store access can be abstracted later only if tests cover mutation order and confidence handling.

## 2026-07-02 - Clinic Schedule Response Helpers

Goal/scope:
- Move clinic-schedule pending-action and final response construction into `jane_web/jane_v2/classes/clinic_schedules_info/responses.py`.
- Keep SQLite reads, fact building, and local LLM phrasing inside the handler.

Files/modules changed:
- `jane_web/jane_v2/classes/clinic_schedules_info/responses.py`
- `jane_web/jane_v2/classes/clinic_schedules_info/handler.py`
- `tests/test_clinic_schedule_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Clinic follow-ups still use handler class `clinic schedules info`.
- The routing-only pending question still uses the `(awaiting:<name>)` shape.
- Handler output still returns the phrased text plus a `clinic_followup` pending action.

Boundary chosen:
- Response and pending-action construction is deterministic Stage 2 policy.
- Patient schedule facts, DB access, and LLM phrasing remain in the handler.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/clinic_schedules_info/responses.py jane_web/jane_v2/classes/clinic_schedules_info/handler.py tests/test_clinic_schedule_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_clinic_schedule_helpers.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1331 passed`).

Remaining follow-up slices:
- Clinic fact builders are still DB-bound; split further only around pure row-selection policy with fixture-backed tests.

## 2026-07-02 - Weather Follow-Up Response Helper

Goal/scope:
- Move weather follow-up response construction into `jane_web/jane_v2/classes/weather/responses.py`.
- Keep cache reads, slice selection, Ollama phrasing, and resume routing in `weather/handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/weather/responses.py`
- `jane_web/jane_v2/classes/weather/handler.py`
- `tests/test_weather_slices.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Successful weather answers still append `Want the weather for another day?`.
- The pending action remains a `STAGE2_FOLLOWUP` for handler class `weather`.
- Pending data still carries the requested topic, location fallback, and `awaiting` field through `pending_continuation()`.

Boundary chosen:
- Follow-up response construction is deterministic Stage 2 response policy.
- Weather cache access and LLM phrasing stay in the handler.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/weather/responses.py jane_web/jane_v2/classes/weather/handler.py tests/test_weather_slices.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_weather_slices.py tests/test_weather_payload_helpers.py -q` passed (`12 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1330 passed`).

Remaining follow-up slices:
- Weather resume policy can be extracted later if same-class restart and end-phrase behavior get direct tests.

## 2026-07-02 - Music Play Marker Helper

Goal/scope:
- Add `music_play_marker()` to `jane_web/music_playlists.py`.
- Reuse it from v2 music-play response formatting and generic Stage 2 response assembly.

Files/modules changed:
- `jane_web/music_playlists.py`
- `jane_web/jane_v2/classes/music_play/matching.py`
- `jane_web/jane_v2/stage2_response.py`
- `tests/test_music_playlists.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Playlist IDs still render as `[MUSIC_PLAY:<playlist_id>]`.
- Stage 2 still appends a music marker only when the text does not already contain one.
- Music-play matching still returns the same response payload shape.

Boundary chosen:
- Music marker construction belongs beside existing music marker parsing/replacement helpers.
- Stage 2 response normalization and playlist matching keep their existing responsibilities.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/music_playlists.py jane_web/jane_v2/classes/music_play/matching.py jane_web/jane_v2/stage2_response.py tests/test_music_playlists.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_music_playlists.py tests/test_music_play_matching.py tests/test_stage2_response.py -q` passed (`15 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1330 passed`).

Remaining follow-up slices:
- Other non-client-tool markers can move to dedicated marker helpers as their callers get focused tests.

## 2026-07-02 - Client Tool Marker Builder

Goal/scope:
- Add a shared `build_client_tool_marker()` formatter in `jane_web/client_tool_markers.py`.
- Route SMS marker helpers through the shared builder while preserving their default JSON spacing.
- Move timer marker formatting into `jane_web/jane_v2/classes/timer/tool_markers.py` with compact JSON preserved.

Files/modules changed:
- `jane_web/client_tool_markers.py`
- `jane_web/jane_v2/sms_tool_markers.py`
- `jane_web/jane_v2/classes/timer/tool_markers.py`
- `jane_web/jane_v2/classes/timer/responses.py`
- `tests/test_client_tool_markers.py`
- `tests/test_timer_tool_markers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- SMS client-tool markers still use the same default `json.dumps()` spacing.
- Timer markers still use compact JSON with no spaces.
- Existing timer response builders still return the same visible text and structured payload shapes.

Boundary chosen:
- Marker serialization is shared formatting policy.
- Marker extraction/parsing, timer response semantics, and SMS pending-state behavior remain in their existing modules.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/client_tool_markers.py jane_web/jane_v2/sms_tool_markers.py jane_web/jane_v2/classes/timer/tool_markers.py jane_web/jane_v2/classes/timer/responses.py tests/test_client_tool_markers.py tests/test_timer_tool_markers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_client_tool_markers.py tests/test_sms_tool_markers.py tests/test_timer_tool_markers.py tests/test_timer_parsing.py -q` passed (`25 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1330 passed`).

Remaining follow-up slices:
- Additional client-tool families can migrate to the shared marker builder when their behavior-specific tests are in place.

## 2026-07-02 - Stage 1 Prompt Cleaning Helper

Goal/scope:
- Move Stage 1 prompt cleanup for tool-result prefixes, system marker blocks, subject-change preambles, and weather plural fixups into `jane_web/jane_v2/stage1_prompt_cleaning.py`.
- Keep classifier gates, Chroma lookup, class maps, and logging in `stage1_classifier.py`.

Files/modules changed:
- `jane_web/jane_v2/stage1_prompt_cleaning.py`
- `jane_web/jane_v2/stage1_classifier.py`
- `tests/test_stage1_prompt_cleaning.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Nested `[TOOL_RESULT:{...}]` prefixes are still stripped with the brace-counting parser.
- Complete and truncated SMS/phone system blocks are still removed before classification.
- Subject-change preambles still leave only the requested topic.
- The `weathers` plural fixup still normalizes to `weather`.

Boundary chosen:
- Prompt cleanup is deterministic pre-classification text policy.
- Embedding classification, maturity gates, strict keyword guards, and class routing stay in `stage1_classifier.py`.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/stage1_prompt_cleaning.py jane_web/jane_v2/stage1_classifier.py tests/test_stage1_prompt_cleaning.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_stage1_prompt_cleaning.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1327 passed`).

Remaining follow-up slices:
- Stage 1 still has classifier-gate policy that could be split by class family, but that should be done only with broader routing tests.

## 2026-07-02 - V2 SMS Tool Marker Helpers

Goal/scope:
- Centralize v2 SMS client-tool marker construction, draft-marker regex, and Stage 3 SMS guidance text in `jane_web/jane_v2/sms_tool_markers.py`.
- Keep pending-action resolution, send-message response shaping, and pipeline control flow in their existing modules.

Files/modules changed:
- `jane_web/jane_v2/sms_tool_markers.py`
- `jane_web/jane_v2/pending_sms.py`
- `jane_web/jane_v2/classes/send_message/responses.py`
- `jane_web/jane_v2/pipeline.py`
- `tests/test_sms_tool_markers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Direct-send, draft-send, draft-cancel, and draft-update markers still serialize through `json.dumps()` with the same visible shapes.
- Open draft extraction still recognizes the same `contacts.sms_*` marker actions and JSON payload group.
- Non-streaming and streaming Stage 3 SMS request guidance keeps the same instructions and marker examples.

Boundary chosen:
- Marker string construction and SMS guidance text are shared formatting policy.
- Pending SMS state handling, local LLM draft editing, and pipeline stage transitions remain in their runtime modules.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/sms_tool_markers.py jane_web/jane_v2/pending_sms.py jane_web/jane_v2/classes/send_message/responses.py jane_web/jane_v2/pipeline.py tests/test_sms_tool_markers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_sms_tool_markers.py tests/test_pending_sms.py tests/test_send_message_parsing.py -q` passed (`22 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1322 passed`).

Remaining follow-up slices:
- The broader kernel-hygiene warning still points at a larger phone-tool migration; this slice only removed duplicated marker construction.

## 2026-07-02 - Tool Protocol Prompt Assets

Goal/scope:
- Move static client-tool protocol prompt assets out of `context_builder.py` into `context_builder/v1/tool_protocols.py`.
- Preserve the existing `context_builder` import surface for `PHONE_TOOLS_PROTOCOL`, `TOOL_CTX_*`, and `CLASSIFICATION_TO_INTENT`.
- Remove the stale `jane/context_builder.py` hygiene allowlist entry that referenced this pending cleanup.

Files/modules changed:
- `context_builder/v1/tool_protocols.py`
- `context_builder/v1/context_builder.py`
- `scripts/hooks/check-kernel-hygiene.sh`
- `tests/test_tool_protocols.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Gemma classification labels still map to the same intent levels and tool-context prompt blocks.
- The legacy phone-tools fallback prompt still contains the same Android tool marker guidance.
- Runtime code that imports `CLASSIFICATION_TO_INTENT` from `context_builder.v1.context_builder` continues to work.

Boundary chosen:
- Static prompt assets now live in a prompt-specific module.
- System-prompt assembly, tool-loader fallback behavior, and profile classification remain in `context_builder.py`.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile context_builder/v1/tool_protocols.py context_builder/v1/context_builder.py tests/test_tool_protocols.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_tool_protocols.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1318 passed`).

Non-gate observation:
- `scripts/hooks/check-kernel-hygiene.sh` still reports existing `jane_web` hardcoded phone-tool references outside this slice.

Remaining follow-up slices:
- The remaining context-builder constants are broader standing-brain policy text; split them only when there is a concrete ownership boundary.

## 2026-07-02 - Managed User Context Builder

Goal/scope:
- Move managed-user context block formatting and memory-scope selection into `context_builder/v1/managed_user_context.py`.
- Keep user config loading, existence checks, exception handling, and unmanaged-user fallback in `context_builder.py`.

Files/modules changed:
- `context_builder/v1/managed_user_context.py`
- `context_builder/v1/context_builder.py`
- `tests/test_managed_user_context.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Unmanaged or missing user configs still produce no managed-user block and no managed memory path.
- Managed users only get a private memory path when `memory` is enabled in their capabilities.
- Capability IDs are still rendered through configured labels, with unknown IDs left as-is.
- Display name fallback still uses display name, then email, then the supplied user ID.

Boundary chosen:
- Prompt-block formatting is deterministic and now directly tested.
- Runtime imports from `agent_skills.user_manager` remain isolated in `context_builder.py`.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile context_builder/v1/managed_user_context.py context_builder/v1/context_builder.py tests/test_managed_user_context.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_managed_user_context.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1315 passed`).

Remaining follow-up slices:
- Context-builder orchestration still has sync/async duplication around task state and personal facts; extract only if the boundary can stay behavior-preserving.

## 2026-07-02 - Context Source Readers

Goal/scope:
- Move context-builder text-file and JSON-summary source reading into `context_builder/v1/context_sources.py`.
- Keep the legacy context builder wrapper methods in place for compatibility with existing tests and callers.

Files/modules changed:
- `context_builder/v1/context_sources.py`
- `context_builder/v1/context_builder.py`
- `tests/test_context_sources.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing text and JSON summary files still return an empty string.
- Text sources still truncate before stripping whitespace.
- JSON sources still parse and re-serialize through `json.dumps()` before applying the max-character limit.

Boundary chosen:
- Disk-source read policy is deterministic and now directly tested.
- Context assembly, memory retrieval, and runtime provider wiring remain in `context_builder.py`.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile context_builder/v1/context_sources.py context_builder/v1/context_builder.py tests/test_context_sources.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_context_sources.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1311 passed`).

Remaining follow-up slices:
- The managed-user runtime block may be a reasonable future extraction if it can be split without obscuring provider boundaries.

## 2026-07-02 - Nearest Memory Selection Helper

Goal/scope:
- Move nearest-memory candidate sorting, content-key dedupe, limit enforcement, and final line formatting into `memory/v1/nearest_memory.py`.
- Keep query planning, Chroma lookup, embedding, and candidate construction in `memory_retrieval.py`.

Files/modules changed:
- `memory/v1/nearest_memory.py`
- `memory/v1/memory_retrieval.py`
- `tests/test_nearest_memory.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Promoted recent short-term candidates still sort ahead of ordinary candidates by priority.
- Ordinary candidates still sort by ascending distance.
- Duplicate content keys are still emitted only once.
- Returned lines still use the `source: formatted memory` shape and stop at `limit`.

Boundary chosen:
- Final nearest-memory output selection is deterministic and now directly tested.
- Vector queries, lexical filtering, and embedding fallbacks remain in memory retrieval.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/nearest_memory.py memory/v1/memory_retrieval.py tests/test_nearest_memory.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nearest_memory.py -q` passed (`8 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1308 passed`).

Remaining follow-up slices:
- Candidate construction is already helperized; remaining retrieval work is mostly Chroma query orchestration.

## 2026-07-02 - Short-Term Memory Recency Boost Helper

Goal/scope:
- Move short-term memory recency-boost sorting, filtering, formatting, and dedupe-key policy into `memory/v1/retrieved_memory_facts.py`.
- Keep Chroma client access, collection reads, cache writes, and best-effort exception handling in `memory_retrieval.py`.

Files/modules changed:
- `memory/v1/retrieved_memory_facts.py`
- `memory/v1/memory_retrieval.py`
- `tests/test_retrieved_memory_facts.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The recency boost still considers the top 3 timestamp-sorted short-term rows.
- Expired, stale, `None`, and low-signal protocol rows are still skipped.
- Formatted recent rows are still appended after semantic short-term results.
- The legacy preview-key dedupe behavior is preserved, including the existing distance-suffix nuance.

Boundary chosen:
- Row sorting/filtering/formatting is deterministic retrieval policy.
- Chroma reads and failure containment remain inside the memory retrieval runtime.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/retrieved_memory_facts.py memory/v1/memory_retrieval.py tests/test_retrieved_memory_facts.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_retrieved_memory_facts.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1306 passed`).

Remaining follow-up slices:
- `build_memory_sections()` remains broad Chroma orchestration; extract only around similarly deterministic collection-specific policies.

## 2026-07-02 - National Grid Fetch Totals Helper

Goal/scope:
- Move National Grid fetch total/status aggregation into `agent_skills/nationalgrid_bill_helpers.py`.
- Keep browser orchestration, account iteration, warning collection, and final payload assembly in `nationalgrid_bills.py`.

Files/modules changed:
- `agent_skills/nationalgrid_bill_helpers.py`
- `agent_skills/nationalgrid_bills.py`
- `tests/test_nationalgrid_bill_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Account totals are still summed from each summary's `total_amount_text`.
- Warnings still change status from `ok` to `partial`.
- Runs where all account summaries have `downloaded_count == 0` still report `missing`, overriding warning-derived `partial`.
- `total_amount` and `total_amount_text` retain their existing numeric/text shapes.

Boundary chosen:
- Total/status aggregation is deterministic result policy.
- Playwright, downloads, account loops, and warning generation remain in the runtime fetcher.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/nationalgrid_bill_helpers.py agent_skills/nationalgrid_bills.py tests/test_nationalgrid_bill_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nationalgrid_bill_helpers.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1305 passed`).

Remaining follow-up slices:
- Further National Grid refactors should wait for browser/extractor fakes; the remaining runtime work is mostly Playwright orchestration.

## 2026-07-02 - National Grid Extractor Config Helper

Goal/scope:
- Move National Grid Playwright extractor config construction into `agent_skills/nationalgrid_bill_helpers.py`.
- Keep extractor loading, secret resolution, Playwright browser work, downloads, and result aggregation in `nationalgrid_bills.py`.

Files/modules changed:
- `agent_skills/nationalgrid_bill_helpers.py`
- `agent_skills/nationalgrid_bills.py`
- `tests/test_nationalgrid_bill_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Billing config still uses `NATIONALGRID_EMAIL` and `NATIONALGRID_PASSWORD` env-backed secrets.
- Account labels, account links, target months, cache options, and filename template remain unchanged.
- Runtime `_build_config()` still exists as the local wrapper used by the downloader flow.

Boundary chosen:
- Extractor config shape is deterministic contract data and can be tested without launching Playwright.
- Browser/session/download behavior remains in the National Grid runtime module.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/nationalgrid_bill_helpers.py agent_skills/nationalgrid_bills.py tests/test_nationalgrid_bill_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nationalgrid_bill_helpers.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1304 passed`).

Remaining follow-up slices:
- `fetch_bills()` remains browser orchestration; extract further only around pure result-status aggregation or with Playwright fakes.

## 2026-07-02 - TODO Add Follow-Up Response Helpers

Goal/scope:
- Move repeated TODO-list add-flow follow-up response builders into `jane_web/jane_v2/classes/todo_list/responses.py`.
- Keep Google Docs mutation, cache refresh, category matching, and resume-flow branching in `todo_list/handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/todo_list/responses.py`
- `jane_web/jane_v2/classes/todo_list/handler.py`
- `tests/test_todo_list_responses.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Asking for an item after the category is known still creates `awaiting="add_item_for_category"`.
- Asking for a category with no item yet still creates `awaiting="add_category_then_item"`.
- Asking for a category after capturing item text still creates `awaiting="add_category"` and preserves `item_text`.
- The existing category-list wording replacement still asks, "Which category should I add it to?"

Boundary chosen:
- User-facing follow-up text and pending-action payload shape are deterministic response contracts.
- Store mutations, docs-tool imports, cache refresh, and category/item matching remain in the handler.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/todo_list/responses.py jane_web/jane_v2/classes/todo_list/handler.py tests/test_todo_list_responses.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_todo_list_responses.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1303 passed`).

Remaining follow-up slices:
- `_handle_resume()` still has several mutation branches; extract only around one awaited state at a time with docs-tool fakes.

## 2026-07-02 - Pending Action Resolution Helper

Goal/scope:
- Move deterministic pending-action response routing into `jane_web/jane_v2/pending_action_resolution.py`.
- Keep FIFO/session lookup, blank prompt guards, pending expiry checks, and import failure handling in `pending_action_resolver.py`.

Files/modules changed:
- `jane_web/jane_v2/pending_action_resolution.py`
- `jane_web/jane_v2/pending_action_resolver.py`
- `tests/test_pending_action_resolution.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- High-precision interrupts and topic pivots still clear Stage 2/3 follow-ups with `action="pivot"`.
- Weak cancels like `no` still fall through for Stage 3 follow-ups and open SMS drafts.
- Strong cancels still cancel protected pending types.
- SMS confirmation, SMS draft send/edit, Stage 3 follow-up, and Stage 2 follow-up return the same payload shapes as before.
- The resolver still passes its logger into the routing helper, preserving diagnostic log messages.

Boundary chosen:
- The routing matrix is deterministic and can be tested without patching `vault_web.recent_turns`.
- Runtime state retrieval, expiration policy, and fall-through behavior remain in the resolver wrapper.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/pending_action_resolution.py jane_web/jane_v2/pending_action_resolver.py tests/test_pending_action_resolution.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_pending_action_resolution.py tests/test_pending_action_expiry.py tests/test_pending_action_phrases.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1302 passed`).

Remaining follow-up slices:
- Expiry parsing is already covered; broader resolver tests would need a fake `vault_web.recent_turns` module for end-to-end wrapper behavior.

## 2026-07-02 - Reverse Proxy Header Helpers

Goal/scope:
- Move reverse proxy hop-by-hop header filtering, forwarding metadata, websocket detection, and streaming-response detection into `jane_web/reverse_proxy_helpers.py`.
- Keep aiohttp session management, control endpoints, upstream switching, proxy streaming, and websocket forwarding in `reverse_proxy.py`.

Files/modules changed:
- `jane_web/reverse_proxy_helpers.py`
- `jane_web/reverse_proxy.py`
- `tests/test_reverse_proxy_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Hop-by-hop headers are still removed case-insensitively.
- `X-Forwarded-For` and `X-Forwarded-Proto` are still injected into upstream requests.
- Websocket upgrade detection still preserves the existing exact `Connection: upgrade` behavior.
- Streaming detection still matches chunked transfer encoding or `text/event-stream` content type.

Boundary chosen:
- Header policy is deterministic and now lives outside the aiohttp runtime module.
- Request forwarding, state accounting, upstream connections, and response streaming remain in the reverse proxy.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/reverse_proxy_helpers.py jane_web/reverse_proxy.py tests/test_reverse_proxy_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_reverse_proxy_helpers.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1297 passed`).

Remaining follow-up slices:
- Proxy state persistence/loading remains inline; extract only with temp-path tests around persisted upstream state.

## 2026-07-02 - Task Offloader Context Selection Helper

Goal/scope:
- Move task offloader automation prompt/system-prompt selection into `jane_web/task_offloader_context.py`.
- Keep background threading, session history lookup, context building, automation execution, retry behavior, and announcements in `task_offloader.py`.

Files/modules changed:
- `jane_web/task_offloader_context.py`
- `jane_web/task_offloader.py`
- `tests/test_task_offloader_context.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Offloaded tasks still use the built transcript when context construction supplies one.
- When no transcript is available, the raw user message is still sent to automation.
- Missing/empty system prompts still become an empty string.

Boundary chosen:
- Prompt selection from a built context is deterministic and now covered directly.
- Runtime session lookup, context construction failures, threading, retries, and automation execution remain in the offloader.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/task_offloader_context.py jane_web/task_offloader.py tests/test_task_offloader_context.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_task_offloader_context.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1296 passed`).

Remaining follow-up slices:
- The retry loop still owns automation-specific control flow; extract only with fake `run_automation_prompt` tests.

## 2026-07-02 - Message Readback TalkingPoints Candidate Helpers

Goal/scope:
- Move TalkingPoints URL code extraction, candidate dedupe, and decoded-code expansion into `jane_web/message_readback_helpers.py`.
- Keep redirect fetching, API calls, static page fetches, cache I/O, and resolver orchestration in `message_readback.py`.

Files/modules changed:
- `jane_web/message_readback_helpers.py`
- `jane_web/message_readback.py`
- `tests/test_message_readback_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `/U/<code>` and `/m/<code>` TalkingPoints paths still produce candidate codes.
- Original URL candidates are still considered before redirected URL candidates.
- Duplicate candidates are still suppressed.
- URL-safe base64 values that decode to TalkingPoints separator text are still appended after direct candidates.

Boundary chosen:
- Candidate extraction is deterministic URL policy and now covered without network requests.
- HTTP redirects, TalkingPoints API calls, static HTML parsing, and cache writes remain in the resolver runtime.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/message_readback_helpers.py jane_web/message_readback.py tests/test_message_readback_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_message_readback_helpers.py -q` passed (`8 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1293 passed`).

Remaining follow-up slices:
- Cache path/load/save side effects remain inline; extract only if a temp-file fixture is added for cache migration behavior.

## 2026-07-02 - Job Queue Shared Idle Helpers

Goal/scope:
- Reuse shared queue idle helpers in `agent_skills/job_queue_runner.py`.
- Extend `agent_skills/prompt_queue_idle.py` with prioritized multi-key timestamp readers to preserve the job queue's legacy state-file behavior.

Files/modules changed:
- `agent_skills/prompt_queue_idle.py`
- `agent_skills/job_queue_runner.py`
- `tests/test_prompt_queue_idle.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing activity state files still count as no activity.
- Malformed state files still contribute timestamp `0`.
- Within a single job queue state file, `last_message_ts` still takes priority over `last_active_ts` when both are present.
- The most recent timestamp across user and terminal state files still drives the idle decision.

Boundary chosen:
- JSON timestamp extraction and idle-threshold comparison are shared queue policy.
- Job selection, Jane API calls, job status updates, and memory logging remain in the job queue runner.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/prompt_queue_idle.py agent_skills/job_queue_runner.py tests/test_prompt_queue_idle.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_prompt_queue_idle.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1292 passed`).

Remaining follow-up slices:
- Job queue result-summary formatting is still inline in `main()`, but it is low risk compared with runner/API boundaries.

## 2026-07-02 - Self-Healing Dedupe State Helpers

Goal/scope:
- Move self-healing fingerprint dedupe decision and new-record construction into `agent_skills/self_healing_helpers.py`.
- Keep state locking, incident/job file creation, JSON writes, and auto-repair launch orchestration in `self_healing.py`.

Files/modules changed:
- `agent_skills/self_healing_helpers.py`
- `agent_skills/self_healing.py`
- `tests/test_self_healing_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Repeated incidents inside the rate-limit window still reuse the existing incident/job paths and increment occurrence count.
- New incidents outside the rate-limit window still preserve original `first_seen_at` when present.
- New fingerprint records still store `last_seen_at`, `last_seen_ts`, occurrence count, incident path, job path, source, and category.

Boundary chosen:
- Fingerprint record transitions are deterministic safety policy and now covered by a focused test matrix.
- File creation, state lock lifetime, JSONL logging, and repair subprocess launch remain in the runtime module.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/self_healing_helpers.py agent_skills/self_healing.py tests/test_self_healing_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_self_healing_helpers.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1291 passed`).

Remaining follow-up slices:
- `capture_exception()` and `capture_report()` still build incident dictionaries inline; extract those only if tests need direct incident-shape coverage.

## 2026-07-02 - Self-Healing Incident Path Helpers

Goal/scope:
- Move self-healing incident JSON path and repair-job path formatting into `agent_skills/self_healing_helpers.py`.
- Keep state locking, incident writes, job body writes, and auto-repair launch orchestration in `self_healing.py`.

Files/modules changed:
- `agent_skills/self_healing_helpers.py`
- `agent_skills/self_healing.py`
- `tests/test_self_healing_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Incident filenames still strip `:` and `-` from `created_at` and append the incident id.
- Repair job filenames still use zero-padded job numbers and slugified source/category components.
- Job body rendering and filesystem writes remain unchanged.

Boundary chosen:
- Naming policy is deterministic and now tested directly.
- Mutable state updates, JSONL logging, job creation, and subprocess launch remain in the self-healing runtime module.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/self_healing_helpers.py agent_skills/self_healing.py tests/test_self_healing_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_self_healing_helpers.py -q` passed (`9 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1289 passed`).

Remaining follow-up slices:
- Incident dedupe state transitions are the next meaningful self-healing boundary, but they should be extracted with a dedicated state-transition test matrix rather than folded into this naming slice.

## 2026-07-02 - Audit Auto-Fix Preflight Helpers

Goal/scope:
- Move audit auto-fixer result initialization and preflight validation into `agent_skills/audit_auto_fix_helpers.py`.
- Keep file reads, backups, replacements, syntax checks, rollback, and logging in `audit_auto_fixer.py`.

Files/modules changed:
- `agent_skills/audit_auto_fix_helpers.py`
- `agent_skills/audit_auto_fixer.py`
- `tests/test_audit_auto_fix_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `skip` issues still return a skipped result with the LLM fix description.
- Missing `file`, `search_text`, or `replacement_text` still skips the issue.
- Identical search/replacement text still skips the issue.
- Unsafe paths still skip with the same `File not safe to modify: ...` reason.
- File mutation is still attempted only after the existing safety predicate approves the path.

Boundary chosen:
- Preflight validation is deterministic policy and can be tested without touching target files or backups.
- The mutating half of `apply_fix()` still owns filesystem reads, writes, backup restoration, and Python syntax verification.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/audit_auto_fix_helpers.py agent_skills/audit_auto_fixer.py tests/test_audit_auto_fix_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_audit_auto_fix_helpers.py -q` passed (`9 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1288 passed`).

Remaining follow-up slices:
- `apply_fix()` file mutation could be tested with temporary files in a future slice, but the current safety decision boundary is now covered.

## 2026-07-02 - Prompt Queue Chroma Purge Script Helper

Goal/scope:
- Move prompt queue archive Chroma purge script generation into `agent_skills/prompt_queue_memory.py`.
- Keep prompt archive file mutations and subprocess execution in `prompt_queue_runner.py`.

Files/modules changed:
- `agent_skills/prompt_queue_memory.py`
- `agent_skills/prompt_queue_runner.py`
- `tests/test_prompt_queue_memory.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Archived prompt indices are still matched against `prompt_queue` memory subtopics shaped as `item_<index>`.
- The purge still targets the `short_term_memory` collection and deletes only matching IDs.
- Purge failures are still contained by the runner's existing exception handler.

Bug fixed:
- The generated subprocess script previously called `get_chroma_client(...)` without importing it inside the `python -c` process. The helper now emits `from jane.config import get_chroma_client`.
- Archived index order is now stable in the generated script, which makes tests and logs deterministic.

Boundary chosen:
- Script generation is deterministic memory-cleanup policy and can be tested without touching ChromaDB.
- Archive file writes, subprocess launch, and warning logging stay in the queue runner.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/prompt_queue_memory.py agent_skills/prompt_queue_runner.py tests/test_prompt_queue_memory.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_prompt_queue_memory.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1286 passed`).

Remaining follow-up slices:
- `archive_completed_prompts()` still mixes prompt-list file mutation and subprocess orchestration; deeper extraction should wait for a filesystem fixture around `PROMPT_LIST_PATH` and `ACCOMPLISHED_PATH`.

## 2026-07-02 - Nightly Code Audit Fix Prompt Helpers

Goal/scope:
- Move nightly code-audit fix-attempt prompt assembly and provider stop-marker detection into `agent_skills/nightly_code_audit_helpers.py`.
- Keep module file reads, frontier provider calls, and file-change detection in `nightly_code_auditor.py`.

Files/modules changed:
- `agent_skills/nightly_code_audit_helpers.py`
- `agent_skills/nightly_code_auditor.py`
- `tests/test_nightly_code_audit_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Fix prompts still include the same module path, edit scope instructions, attempt counter, and TEST_WRONG/GIVE_UP policy.
- Module source sent to the provider is still truncated to 6000 characters.
- Test failure output sent to the provider is still truncated to 3000 characters.
- Provider output containing `TEST_WRONG` or `GIVE_UP` still declines the fix attempt.

Boundary chosen:
- Prompt construction and provider stop-marker policy are deterministic and now directly testable.
- Runtime provider invocation and the "did the module file change" check remain in the auditor phase.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/nightly_code_audit_helpers.py agent_skills/nightly_code_auditor.py tests/test_nightly_code_audit_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nightly_code_audit_helpers.py -q` passed (`9 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1285 passed`).

Remaining follow-up slices:
- `nightly_code_auditor.py` is now mostly orchestration; further work there should wait for branch/git orchestration tests or fakes.

## 2026-07-02 - Nightly Code Audit Prompt Helpers

Goal/scope:
- Move nightly code-audit test-generation prompt assembly into `agent_skills/nightly_code_audit_helpers.py`.
- Keep module file reads, integration config reads, frontier provider calls, branch management, and audit orchestration in `nightly_code_auditor.py`.

Files/modules changed:
- `agent_skills/nightly_code_audit_helpers.py`
- `agent_skills/nightly_code_auditor.py`
- `tests/test_nightly_code_audit_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Integration contract text is still included only when the audited module path appears in the integrations file.
- Generated prompts still include the same audit instructions, target test path, and structural invariant requirements.
- Module code is still truncated to 8000 characters before being sent to the frontier provider.

Boundary chosen:
- Prompt assembly is deterministic policy and can be tested without invoking the LLM or touching git state.
- File I/O, provider calls, generated test execution, branch cleanup, and logging remain in the auditor orchestration.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nightly_code_audit_helpers.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1283 passed`).

Remaining follow-up slices:
- Fix-attempt prompt construction in `phase3_attempt_fix()` is another deterministic candidate, but it should be extracted separately with tests around truncation and TEST_WRONG/GIVE_UP policy.

## 2026-07-02 - Google Cloud Receipt Request Validation

Goal/scope:
- Move Google Cloud receipt download argument validation into `agent_skills/google_cloud_receipt_utils.py`.
- Keep profile loading, browser automation, account discovery, candidate selection, downloads, and manifest writes in `google_cloud_receipts.py`.

Files/modules changed:
- `agent_skills/google_cloud_receipt_utils.py`
- `agent_skills/google_cloud_receipts.py`
- `tests/test_google_cloud_receipts.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `count < 1` still raises `ValueError("count must be >= 1")`.
- Missing both `count` and date range still raises `ValueError("Provide either count or a date range.")`.
- `start_date > end_date` still raises `ValueError("start_date must be <= end_date")`.
- Valid count-only or date-range requests still proceed to runtime profile/browser work.

Boundary chosen:
- Argument validation is deterministic request policy and can be tested without launching Playwright or touching Google Cloud.
- Browser/session/download behavior remains in the downloader.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/google_cloud_receipt_utils.py agent_skills/google_cloud_receipts.py tests/test_google_cloud_receipts.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_google_cloud_receipts.py -q` passed (`17 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1281 passed`).

Remaining follow-up slices:
- Browser DOM discovery remains tightly coupled to live Google Cloud pages and should stay in the script until Playwright fixtures exist.

## 2026-07-02 - Audit Auto-Fix Report Discovery Helpers

Goal/scope:
- Move audit auto-fixer report discovery policy into `agent_skills/audit_auto_fix_helpers.py`.
- Keep CLI argument handling, report reading, LLM analysis, fix application, and report writing in `audit_auto_fixer.py`.

Files/modules changed:
- `agent_skills/audit_auto_fix_helpers.py`
- `agent_skills/audit_auto_fixer.py`
- `tests/test_audit_auto_fix_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing audit directories still produce no report.
- `auto_fix_*.md` reports are still ignored.
- Latest report selection still sorts reverse by filename.
- Today's report lookup still matches any `audit_<YYYY-MM-DD>*.md` report and returns the latest one.

Boundary chosen:
- Report discovery is deterministic filesystem selection policy already adjacent to safety/report-rendering helpers.
- Runtime fix orchestration remains in the auto-fixer script.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/audit_auto_fix_helpers.py agent_skills/audit_auto_fixer.py tests/test_audit_auto_fix_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_audit_auto_fix_helpers.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1280 passed`).

Remaining follow-up slices:
- `apply_fix()` still mixes issue validation and file mutation; extract validation first if more auto-fixer coverage is added.

## 2026-07-02 - Prompt Queue Idle Helpers

Goal/scope:
- Move prompt queue activity timestamp reading and idle-threshold decision helpers into `agent_skills/prompt_queue_idle.py`.
- Keep queue-run orchestration, logging messages, prompt mutation, and execution side effects in `prompt_queue_runner.py`.

Files/modules changed:
- `agent_skills/prompt_queue_idle.py`
- `agent_skills/prompt_queue_runner.py`
- `tests/test_prompt_queue_idle.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing activity files still count as no activity.
- Malformed activity files still log warnings and contribute timestamp `0`.
- The latest timestamp across Discord/user and terminal idle sources is still used.
- A missing timestamp still means "assuming idle"; otherwise idleness is `now - last_activity >= IDLE_THRESHOLD`.

Boundary chosen:
- Activity-file parsing and idle math are deterministic queue policy.
- Prompt processing, queue mutation, memory writes, and Jane API calls remain in the runner.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/prompt_queue_idle.py agent_skills/prompt_queue_runner.py tests/test_prompt_queue_idle.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_prompt_queue_idle.py tests/test_prompt_queue_docs.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1279 passed`).

Remaining follow-up slices:
- Prompt queue archive Chroma purge construction still embeds a script string; extract only with tests around the generated purge script.

## 2026-07-02 - Proxy Global Idle Timestamp Helper

Goal/scope:
- Move Jane proxy global idle timestamp file reading into `jane_web/proxy_sessions.py`.
- Keep prune orchestration and session expiration side effects in `jane_proxy.py`.

Files/modules changed:
- `jane_web/proxy_sessions.py`
- `jane_web/jane_proxy.py`
- `tests/test_proxy_sessions.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing, malformed, or unreadable activity files still return `0.0`.
- Future timestamps are still clamped to the current time before pruning decisions.
- `jane_proxy._read_global_idle_ts()` remains as the compatibility wrapper used by prune orchestration.

Boundary chosen:
- Reading and normalizing the global idle timestamp is session-pruning policy and belongs with the other proxy session helpers.
- Ending sessions and logging expirations remain in the proxy module.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/proxy_sessions.py jane_web/jane_proxy.py tests/test_proxy_sessions.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_proxy_sessions.py tests/test_proxy_brain.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1276 passed`).

Remaining follow-up slices:
- `_prune_stale_sessions()` can become more testable if session-ending side effects are injected, but that is a broader seam than this safe helper move.

## 2026-07-02 - Greeting Prompt And Payload Helpers

Goal/scope:
- Move greeting local-LLM prompt construction and payload construction into `jane_web/jane_v2/classes/greeting/canned.py`.
- Keep HTTP transport, activity recording, canned fast path, wrong-class detection, and response cleanup in the handler.

Files/modules changed:
- `jane_web/jane_v2/classes/greeting/canned.py`
- `jane_web/jane_v2/classes/greeting/handler.py`
- `tests/test_greeting_canned.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Recent conversation is still included only when non-empty after stripping.
- User prompt text is still stripped before insertion.
- Ollama request options remain temperature `0.7`, `num_predict` `60`, caller-provided `num_ctx`, `stream: false`, `think: false`, and `keep_alive: -1`.
- The canned fast path and wrong-class/cleanup helpers are unchanged.

Boundary chosen:
- Greeting prompt and payload policy now live next to the existing deterministic greeting helpers.
- Runtime transport and handler branching remain in the handler.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/greeting/canned.py jane_web/jane_v2/classes/greeting/handler.py tests/test_greeting_canned.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_greeting_canned.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1275 passed`).

Remaining follow-up slices:
- No obvious remaining greeting refactor with enough benefit after canned, prompt, payload, and cleanup helper extraction.

## 2026-07-02 - Tell Joke Prompt And Parser Helpers

Goal/scope:
- Move tell-joke prompt construction, local Ollama payload construction, and THOUGHT/REPLY parsing into `jane_web/jane_v2/classes/tell_joke/helpers.py`.
- Keep HTTP transport, activity recording, latency measurement, and handler response shape in the handler.

Files/modules changed:
- `jane_web/jane_v2/classes/tell_joke/helpers.py`
- `jane_web/jane_v2/classes/tell_joke/handler.py`
- `tests/test_tell_joke_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Recent conversation is still included only when non-empty after stripping.
- User prompt text is still stripped before insertion.
- Ollama request options remain temperature `0.9`, `num_predict` `100`, caller-provided `num_ctx`, `stream: false`, `think: false`, and caller-provided `keep_alive`.
- Responses still prefer `REPLY:` and strip quote wrapping; thought-only outputs no longer speak the `THOUGHT:` prefix.

Boundary chosen:
- Prompt/payload/parsing are deterministic policy and now have direct characterization tests.
- Runtime transport and latency logging remain in the handler.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/tell_joke/helpers.py jane_web/jane_v2/classes/tell_joke/handler.py tests/test_tell_joke_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_tell_joke_helpers.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1274 passed`).

Remaining follow-up slices:
- Greeting uses a similar prompt/payload path and can be extracted with the same pattern.

## 2026-07-02 - Read Calendar LLM Payload Helper

Goal/scope:
- Move read-calendar local Ollama payload construction into `jane_web/jane_v2/classes/read_calendar/prompts.py`.
- Keep HTTP transport, activity recording, event fetching, and response routing in the handler.

Files/modules changed:
- `jane_web/jane_v2/classes/read_calendar/prompts.py`
- `jane_web/jane_v2/classes/read_calendar/handler.py`
- `tests/test_read_calendar_prompts.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Calendar LLM requests still use the caller-provided prompt text unchanged.
- Ollama request options remain temperature `0.2`, caller-provided `num_predict`, caller-provided `num_ctx`, `stream: false`, `think: false`, and caller-provided `keep_alive`.

Boundary chosen:
- Calendar prompt templates and local-LLM payload policy now live together.
- Runtime transport and calendar event I/O remain in the handler.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/read_calendar/prompts.py jane_web/jane_v2/classes/read_calendar/handler.py tests/test_read_calendar_prompts.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_read_calendar_prompts.py tests/test_read_calendar_formatting.py -q` passed (`12 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1269 passed`).

Remaining follow-up slices:
- Calendar resume routing could be split into a state-machine helper, but it needs direct async handler tests around pending states first.

## 2026-07-02 - Timer Legacy Intent Rule Helpers

Goal/scope:
- Move timer legacy phrase sets and boolean intent checks into `jane_web/jane_v2/classes/timer/intent_rules.py`.
- Keep duration parsing, pending resume flow, and response marker construction in the existing parsing/response modules and handler.

Files/modules changed:
- `jane_web/jane_v2/classes/timer/intent_rules.py`
- `jane_web/jane_v2/classes/timer/handler.py`
- `tests/test_timer_parsing.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Count, cancel, list, create-without-duration, and set-trigger checks use the same phrase sets as before.
- Bare short durations still count as timer set triggers.
- Non-trigger conversational duration phrases still escalate instead of setting a timer.

Boundary chosen:
- Phrase-level legacy intent checks are deterministic classification policy.
- Parsing durations/labels and building client-tool responses remain in their existing dedicated modules.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/timer/intent_rules.py jane_web/jane_v2/classes/timer/handler.py tests/test_timer_parsing.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_timer_parsing.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1268 passed`).

Remaining follow-up slices:
- Params-driven timer dispatch could be normalized behind a small command object later, but current response coverage is already adequate.

## 2026-07-02 - Time Local LLM Payload Helper

Goal/scope:
- Move get-time local Ollama payload construction into `jane_web/jane_v2/classes/get_time/time_helpers.py`.
- Keep HTTP transport, activity recording, latency measurement, and fallback handling in the handler.

Files/modules changed:
- `jane_web/jane_v2/classes/get_time/time_helpers.py`
- `jane_web/jane_v2/classes/get_time/handler.py`
- `tests/test_get_time_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Time LLM requests still use the caller-provided prompt text unchanged.
- Ollama request options remain temperature `0.3`, `num_predict` `80`, caller-provided `num_ctx`, `stream: false`, `think: false`, and caller-provided `keep_alive`.

Boundary chosen:
- Prompt and local-LLM payload policy now live together in the time helper module.
- Runtime transport and fallback behavior remain in the handler.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/get_time/time_helpers.py jane_web/jane_v2/classes/get_time/handler.py tests/test_get_time_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_get_time_helpers.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1267 passed`).

Remaining follow-up slices:
- No obvious remaining get-time refactor with enough benefit after prompt, parser, fast-path, and payload helper extraction.

## 2026-07-02 - Math Local LLM Payload Helper

Goal/scope:
- Move do-math local Ollama request payload construction into the evaluator helper module.
- Keep HTTP transport, activity recording, parsing, safe evaluation, and response timing in the handler.

Files/modules changed:
- `jane_web/jane_v2/classes/do_math/evaluator.py`
- `jane_web/jane_v2/classes/do_math/handler.py`
- `tests/test_do_math_evaluator.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Math extraction requests still use the caller-provided prompt text unchanged.
- Ollama request options remain temperature `0.0`, `num_predict` `40`, caller-provided `num_ctx`, `stream: false`, `think: false`, and caller-provided `keep_alive`.

Boundary chosen:
- Payload construction is deterministic local-LLM policy and belongs with the existing math prompt/evaluator helpers.
- Transport and telemetry stay in the handler.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/do_math/evaluator.py jane_web/jane_v2/classes/do_math/handler.py tests/test_do_math_evaluator.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_do_math_evaluator.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1266 passed`).

Remaining follow-up slices:
- No obvious remaining math refactor with enough benefit after evaluator and payload extraction.

## 2026-07-02 - Weather Phrasing Payload Helpers

Goal/scope:
- Move weather Stage 2 answer template formatting and Ollama payload construction into `jane_web/jane_v2/classes/weather/phrasing.py`.
- Keep cache reads, slice selection, HTTP transport, and final day-reference enforcement in the handler.

Files/modules changed:
- `jane_web/jane_v2/classes/weather/phrasing.py`
- `jane_web/jane_v2/classes/weather/handler.py`
- `tests/test_weather_slices.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Weather data slices are still JSON-rendered with `indent=2`.
- Day references still come from the shared `day_reference()` helper.
- Ollama request options remain temperature `0.2`, `num_predict` `60`, caller-provided `num_ctx`, `stream: false`, `think: false`, and `keep_alive: -1`.
- The handler still applies `ensure_day_reference()` to the returned text.

Boundary chosen:
- Prompt/payload shape is deterministic phrasing policy.
- Runtime cache and local LLM transport stay in the handler.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/weather/phrasing.py jane_web/jane_v2/classes/weather/handler.py tests/test_weather_slices.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_weather_slices.py -q` passed (`8 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1265 passed`).

Remaining follow-up slices:
- Weather cache loading could be extracted if route-level tests are added around cache miss and malformed cache behavior.

## 2026-07-02 - Clinic Schedule Prompt Helpers

Goal/scope:
- Move clinic schedule Stage 2 system prompt assembly and Ollama payload construction into `jane_web/jane_v2/classes/clinic_schedules_info/prompting.py`.
- Keep SQLite fact loading, loader dispatch, HTTP transport, and response fallback handling in the handler.

Files/modules changed:
- `jane_web/jane_v2/classes/clinic_schedules_info/prompting.py`
- `jane_web/jane_v2/classes/clinic_schedules_info/handler.py`
- `tests/test_clinic_schedule_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Conversation context is included only when non-empty after stripping.
- Facts and pending state are still JSON-rendered with `indent=2` and `default=str`.
- Ollama request options remain temperature `0.2`, `num_predict` `600`, caller-provided `num_ctx`, `stream: false`, `think: false`, and caller-provided `keep_alive`.
- The handler still exposes `_SYSTEM_PROMPT`.

Boundary chosen:
- Prompt/payload construction is deterministic local policy.
- Database reads and the local LLM HTTP call remain in the handler where runtime dependencies are already managed.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/clinic_schedules_info/prompting.py jane_web/jane_v2/classes/clinic_schedules_info/handler.py tests/test_clinic_schedule_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_clinic_schedule_helpers.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1264 passed`).

Remaining follow-up slices:
- Clinic fact builders could move into a data-access module, but that needs SQLite fixture coverage for the loader dispatch path.

## 2026-07-02 - Send Message Extraction Prompt Helpers

Goal/scope:
- Move send-message extraction prompt formatting and Ollama request payload construction into `jane_web/jane_v2/classes/send_message/extraction_prompt.py`.
- Keep HTTP transport, activity recording, and extraction parsing in the handler.

Files/modules changed:
- `jane_web/jane_v2/classes/send_message/extraction_prompt.py`
- `jane_web/jane_v2/classes/send_message/handler.py`
- `tests/test_send_message_parsing.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Recent conversation context is still included only when non-empty after stripping.
- User prompts are still stripped before insertion into the extraction prompt.
- Ollama request options remain temperature `0.0`, `num_predict` `100`, caller-provided `num_ctx`, `stream: false`, `think: false`, and `keep_alive: -1`.
- The handler still exposes `_EXTRACT_PROMPT` for compatibility.

Boundary chosen:
- Prompt and payload shape are deterministic policy; network I/O and response parsing stay in the handler.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/send_message/extraction_prompt.py jane_web/jane_v2/classes/send_message/handler.py tests/test_send_message_parsing.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_send_message_parsing.py -q` passed (`13 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1262 passed`).

Remaining follow-up slices:
- The open-draft safety net still mixes FIFO access with response decisions; extract only with tests that stub current-session and recent-turn state.

## 2026-07-02 - TODO List Cache Helpers

Goal/scope:
- Move TODO-list cache path and JSON loading into `jane_web/jane_v2/classes/todo_list/cache.py`.
- Keep edit, resume, category matching, and response flow in the handler.

Files/modules changed:
- `jane_web/jane_v2/classes/todo_list/cache.py`
- `jane_web/jane_v2/classes/todo_list/handler.py`
- `tests/test_todo_list_cache.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing TODO cache files still return `None`.
- Invalid or unreadable cache content still returns `None` after logging.
- Valid JSON cache payloads are returned unchanged.
- The handler still exposes `_CACHE_PATH` and `_load_cache` aliases for existing callers/tests.

Boundary chosen:
- Cache file location and read failure policy are I/O concerns separate from the TODO read/edit conversation flow.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/todo_list/cache.py jane_web/jane_v2/classes/todo_list/handler.py tests/test_todo_list_cache.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_todo_list_cache.py tests/test_todo_list_parsing.py tests/test_todo_list_categories.py tests/test_todo_list_responses.py -q` passed (`20 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1260 passed`).

Remaining follow-up slices:
- Resume-flow edit actions still duplicate add/remove success/error response shapes; extract only if handler-level async tests are added around docs_tools calls.

## 2026-07-02 - Stage 2 Handler Invocation Helpers

Goal/scope:
- Move Stage 2 handler signature inspection and optional-kwargs construction into `jane_web/jane_v2/stage2_handler_invocation.py`.
- Keep route selection, gate checks, continuation checks, handler execution, and self-correction decisions in `stage2_dispatcher.py`.

Files/modules changed:
- `jane_web/jane_v2/stage2_handler_invocation.py`
- `jane_web/jane_v2/stage2_dispatcher.py`
- `tests/test_stage2_handler_invocation.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Handlers that do not accept optional kwargs are still called with only the prompt.
- Handlers receive only the optional kwargs they declare: `context`, `pending`, and/or `params`.
- Internal pending-action `question` metadata is still stripped before handler invocation without mutating the original pending dict.
- Sync handlers still run in a worker thread and async handlers are still awaited.

Boundary chosen:
- Signature compatibility is deterministic request-shaping policy.
- The dispatcher remains responsible for routing decisions and the actual async/sync invocation path.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/stage2_handler_invocation.py jane_web/jane_v2/stage2_dispatcher.py tests/test_stage2_handler_invocation.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_stage2_handler_invocation.py tests/test_stage2_dispatcher_prompts.py -q` passed (`9 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1257 passed`).

Remaining follow-up slices:
- Gate/continuation LLM request payload construction could be extracted later if tests pin the exact Ollama request body.

## 2026-07-02 - V2 Body Message Update Helpers

Goal/scope:
- Move v2 chat-body message replacement, append, and prepend mechanics into `jane_web/jane_v2/body_message_updates.py`.
- Reuse the shared helpers from the v2 pipeline and Stage 3 body injection path.

Files/modules changed:
- `jane_web/jane_v2/body_message_updates.py`
- `jane_web/jane_v2/pipeline.py`
- `jane_web/jane_v2/stage3_body_injections.py`
- `tests/test_jane_v2_pipeline_helpers.py`
- `tests/test_stage3_escalate_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Pydantic v2 `model_copy` remains preferred over Pydantic v1 `copy`.
- The v2 pipeline still returns the original body for empty append/prepend inputs.
- The pipeline's mutable fallback for bare body objects is preserved.
- Verify-first prepends still insert one blank line unless the injected block already ends with a blank line.

Boundary chosen:
- Message mutation is mechanical request-model compatibility logic used by multiple v2 Stage 3 paths.
- Dispatch, evidence lookup, protocol loading, and voice/class-specific text construction stay in their existing modules.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/body_message_updates.py jane_web/jane_v2/pipeline.py jane_web/jane_v2/stage3_body_injections.py tests/test_jane_v2_pipeline_helpers.py tests/test_stage3_escalate_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_jane_v2_pipeline_helpers.py tests/test_stage3_escalate_helpers.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1252 passed`).

Remaining follow-up slices:
- Consider moving more Stage 3 injection text builders only if a focused test can pin the exact prompt blocks.

## 2026-07-02 - Shared Pending Job Summary Scanner

Goal/scope:
- Move pending job Markdown directory scanning into `agent_skills/job_queue_docs.pending_job_summaries_from_dir()`.
- Reuse it from `agent_skills/run_queue_next.py` and `agent_skills/check_continuation.py`.

Files/modules changed:
- `agent_skills/job_queue_docs.py`
- `agent_skills/run_queue_next.py`
- `agent_skills/check_continuation.py`
- `tests/test_job_queue_docs.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `README.md`, non-Markdown files, non-files, unreadable files, and non-pending jobs are still skipped.
- Missing job titles still fall back to the filename for these summary views.
- Pending job summaries are still sorted by priority and then numeric job prefix.
- `check_continuation.py` still returns only the first job number/title, while `run_queue_next.py` still returns all pending summaries.

Boundary chosen:
- This helper shares read-only queue summary discovery.
- The full job runner keeps its richer parser because it needs full content for execution and status mutation.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/job_queue_docs.py agent_skills/run_queue_next.py agent_skills/check_continuation.py tests/test_job_queue_docs.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_job_queue_docs.py tests/test_continuation_policy.py -q` passed (`12 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1252 passed`).

Remaining follow-up slices:
- Consider unifying full job parsing only if execution-path tests cover status updates, result sections, archive moves, and announcement behavior together.

## 2026-07-02 - Audit Notification Payload Helpers

Goal/scope:
- Move audit notification message, announcement payload, and notification state payload construction into `agent_skills/audit_report_helpers.py`.
- Keep latest-audit discovery, JSONL appends, state-file writes, freshness checks, and logging in `agent_skills/notify_audit_results.py`.

Files/modules changed:
- `agent_skills/audit_report_helpers.py`
- `agent_skills/notify_audit_results.py`
- `tests/test_audit_report_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Audit announcements still use `type: queue_progress`, `final: true`, and the same `audit_result_<date>` ID.
- The visible message still starts with `**Morning audit summary**`, includes the local run timestamp, and appends the extracted brief.
- Notification state still records `last_notified_date`, `last_report_generated_at`, and `announcement_id`.

Boundary chosen:
- Payload/message shape is deterministic report policy.
- Filesystem reads/writes and date/freshness decisions remain in the notifier script.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/audit_report_helpers.py agent_skills/notify_audit_results.py tests/test_audit_report_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_audit_report_helpers.py tests/test_nightly_audit_helpers.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1251 passed`).

Remaining follow-up slices:
- Consider reusing a single queue-progress JSONL writer across audit, queue runners, and task offloader only after reconciling their current timestamp field differences.

## 2026-07-02 - Ambient Task Research Synthesis Prompt Helper

Goal/scope:
- Move Ambient task-research OpenAI synthesis message construction into `agent_skills/ambient_task_research_rules.py`.
- Keep OpenAI API calls, environment checks, response parsing, cache writes, web search, and Discord notification in `ambient_task_research.py`.

Files/modules changed:
- `agent_skills/ambient_task_research_rules.py`
- `agent_skills/ambient_task_research.py`
- `tests/test_ambient_task_research_rules.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The system prompt text and user message shape are unchanged.
- Web search data is still omitted when empty and truncated to 6000 characters when present.
- OpenAI request model, token limit, temperature, timeout, and response extraction are unchanged.

Boundary chosen:
- Prompt construction is deterministic policy already adjacent to task extraction, cache-key, stale-cache, search-query, and Discord-summary rules.
- The script now owns only runtime I/O around the OpenAI request.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ambient_task_research_rules.py agent_skills/ambient_task_research.py tests/test_ambient_task_research_rules.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ambient_task_research_rules.py tests/test_ambient_heartbeat_rules.py -q` passed (`17 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1250 passed`).

Remaining follow-up slices:
- Consider extracting task cache read/write only with temp-file tests and without changing cron paths.

## 2026-07-02 - Gmail Unread Cleanup Shared Policy

Goal/scope:
- Route the Nutricost/Gmail monitor's final old-unread scan through `process_unread_cleanup_message()`.
- Add `count_unread_cleanup_messages()` so live and dry-run scans share the same unread-label and age policy.

Files/modules changed:
- `agent_skills/nutricost_deal_monitor.py`
- `tests/test_gmail_cleanup_monitor.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The Gmail query for old unread messages is still `is:unread older_than:<days>d` with the same Trash/spam handling.
- Successful live cleanup still returns/counts `old_unread_trashed`.
- Dry-run cleanup still does not trash messages.

Behavior intentionally improved:
- Dry-run and live unread cleanup now both evaluate each message with the same policy used by `process_unread_cleanup_message()`.
- If Gmail query results include a read or too-recent false positive, the monitor now reports `old_unread_skipped_read` or `old_unread_too_recent` instead of blindly counting/trashing it.

Boundary chosen:
- This is a small orchestration helper around existing decision logic.
- Gmail service reads, trash calls, query construction, and failure-count policy remain in the monitor.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/nutricost_deal_monitor.py tests/test_gmail_cleanup_monitor.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_gmail_cleanup_monitor.py tests/test_gmail_cleanup_decisions.py tests/test_gmail_cleanup_counts.py tests/test_gmail_cleanup_queries.py -q` passed (`20 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1249 passed`).

Remaining follow-up slices:
- Consider extracting a generic "query, list, process, merge counts" scan helper only if tests cover Nutricost, CrunchLabs, sender cleanup, calendar cleanup, and unread cleanup together.

## 2026-07-02 - Async Context Builder Saved Article Predicate

Goal/scope:
- Fix and test the async context-builder saved-article predicate path.
- Keep saved-article selection, scoring, and context formatting in `context_builder/v1/saved_articles_context.py`.

Files/modules changed:
- `context_builder/v1/context_builder.py`
- `tests/test_context_builder_async_saved_articles.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Async context building still loads saved Daily Briefing article context only when the prompt references articles/news/briefing content.
- Async status callbacks still emit the existing "Checking saved Daily Briefing articles..." and "Saved briefing article context loaded." messages.
- Unrelated prompts still skip the saved-article loader entirely.

Behavior intentionally fixed:
- `build_jane_context_async()` no longer raises `NameError` for saved-article prompts because `_should_include_saved_articles` is now imported from the saved-article helper module.

Boundary chosen:
- This is a narrow wiring fix at the context-builder boundary.
- File reads, article JSON parsing, relevance scoring, and async task cancellation behavior remain unchanged.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile context_builder/v1/context_builder.py tests/test_context_builder_async_saved_articles.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_context_builder_async_saved_articles.py tests/test_saved_articles_context.py tests/test_context_assembly.py tests/test_context_memory_plan.py -q` passed (`15 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1248 passed`).

Remaining follow-up slices:
- Add a higher-level streaming proxy test only if saved-article prompts become a common failure mode in runtime logs.

## 2026-07-02 - Context Builder Memory Plan Helper

Goal/scope:
- Move sync/async memory-summary branch selection into `context_builder/v1/memory_plan.py`.
- Share the policy for short-anaphora memory skips, override handling, retrieval gating, fallback normalization, and async status text.

Files/modules changed:
- `context_builder/v1/memory_plan.py`
- `context_builder/v1/context_builder.py`
- `jane/context_builder.py`
- `tests/test_context_memory_plan.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Short anaphoric messages still skip ChromaDB and force conversation-summary inclusion.
- Explicit memory-summary overrides still take precedence over retrieval.
- Memory retrieval still runs only when enabled and the prompt profile includes memory.
- Disabled/skipped retrieval still uses normalized fallback memory text.
- Async status strings for anaphora skips and memory retrieval are unchanged.

Boundary chosen:
- The new helper decides what should happen but does not perform memory retrieval.
- Daemon/Chroma calls, managed-user memory paths, async task creation, and cancellation remain in `context_builder.py`.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile context_builder/v1/memory_plan.py context_builder/v1/context_builder.py jane/context_builder.py tests/test_context_memory_plan.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_context_memory_plan.py tests/test_context_assembly.py tests/test_context_memory_summary.py tests/test_prompt_profiles.py -q` passed (`18 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1246 passed`).

Remaining follow-up slices:
- If more context-builder work is needed, extract task-state/personal-facts loading only after tests cover managed-user vs owner behavior.

## 2026-07-02 - Context Builder Assembly Helper

Goal/scope:
- Move final Jane context assembly into `context_builder/v1/context_assembly.py`.
- Share system prompt joining, recent-history transcript construction, platform context line generation, TTS instruction injection, and managed-user block injection between sync and async builders.

Files/modules changed:
- `context_builder/v1/context_assembly.py`
- `context_builder/v1/context_builder.py`
- `jane/context_builder.py`
- `tests/test_context_assembly.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- System sections are still joined with blank lines and stripped at the ends.
- Recent conversation history still uses the existing recent-history formatting helpers.
- Async platform context still maps `android`, `web`, and `cli` to the same labels and falls back to the raw platform name.
- TTS and managed-user instructions are still appended after core system sections.

Boundary chosen:
- Final assembly is deterministic and shared by sync/async paths.
- Memory retrieval, research offload, saved-article loading, managed-user config lookup, and async task cancellation behavior remain in the context builder.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile context_builder/v1/context_assembly.py context_builder/v1/context_builder.py jane/context_builder.py tests/test_context_assembly.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_context_assembly.py tests/test_recent_history.py tests/test_context_memory_summary.py -q` passed (`10 passed`).
- `test_code/test_jane_context_builder.py` still has stale monkeypatch targets for `jane.context_builder.get_memory_summary`; that legacy `test_code` file was already outside the maintained `tests/` gate.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1241 passed`).

Remaining follow-up slices:
- Consider extracting memory retrieval planning only after tests pin status callback order and override/fallback behavior for both sync and async builders.

## 2026-07-02 - Session Wrapper Text Helpers

Goal/scope:
- Move Jane wrapper output normalization, prompt splitting, noise filtering, terminal-input filtering, and status-line formatting into `jane/session_wrapper_text.py`.
- Keep PTY lifecycle, Gemini process restart behavior, memory commits, signal handling, and TTS orchestration in `jane/jane_session_wrapper.py`.

Files/modules changed:
- `jane/session_wrapper_text.py`
- `jane/jane_session_wrapper.py`
- `tests/test_session_wrapper_text.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- ANSI escape stripping and CR/LF normalization still produce the same committed assistant text.
- Gemini prompt detection still checks the same prompt patterns in the same order and returns the same assistant/remainder/match tuple.
- Short noise-like Gemini status messages are still excluded from memory commits.
- Terminal escape input and inputs longer than 5000 characters are still ignored.
- `/status` still prints `process=<state> generation=<n> ready=<bool>`.

Boundary chosen:
- Text-policy helpers are deterministic and easy to unit test without launching Gemini, opening PTYs, or touching memory.
- The wrapper class remains the owner of subprocesses, locks, queues, and shutdown ordering.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane/session_wrapper_text.py jane/jane_session_wrapper.py tests/test_session_wrapper_text.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_session_wrapper_text.py -q` passed (`8 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1237 passed`).

Remaining follow-up slices:
- Consider extracting interactive command dispatch only if tests can pin restart, TTS, and status behavior without changing process-control semantics.

## 2026-07-02 - RA Research Shared JSON Scanner

Goal/scope:
- Reuse `jane.json_scanner.find_json_object_end()` in `agent_skills/ra_research_text.py`.
- Keep fence stripping, dict-only validation, and JSON decode behavior in the RA text helper.

Files/modules changed:
- `agent_skills/ra_research_text.py`
- `tests/test_ra_research_text.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Direct JSON objects, fenced JSON blocks, and embedded JSON objects still parse to dictionaries.
- Empty, non-JSON, malformed, and non-object payloads still return `None`.

Behavior intentionally improved:
- RA JSON parsing now accepts a valid first JSON object followed by trailing text.
- Braces inside JSON strings no longer confuse object-boundary detection.

Boundary chosen:
- Balanced JSON scanning is shared text parsing policy already used by client-tool markers and session-summary parsing.
- Reusing it removes another ad hoc first/last-brace parser without touching RA research network, cache, or LLM calls.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_text.py tests/test_ra_research_text.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_text.py tests/test_json_scanner.py tests/test_ra_research_codex_prompt.py -q` passed (`15 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1229 passed`).

Remaining follow-up slices:
- Search for remaining tolerant JSON parsers and migrate only after focused tests cover malformed/trailing-output behavior.

## 2026-07-02 - Nutricost Alert State Helpers

Goal/scope:
- Move Nutricost monitor alert-state defaults and alerted-message ID updates into `agent_skills/nutricost_deal_utils.py`.
- Keep Gmail reads, trash actions, alert email sending, and persistent state file writes in `agent_skills/nutricost_deal_monitor.py`.

Files/modules changed:
- `agent_skills/nutricost_deal_utils.py`
- `agent_skills/nutricost_deal_monitor.py`
- `tests/test_nutricost_deal_utils.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing or unreadable monitor state still falls back to `{"alerted_message_ids": []}`.
- Previously alerted qualifying messages still return `already_alerted`.
- Non-dry-run alerts still add the message ID and store sorted unique IDs.
- Dry-run alerts still do not mutate state.
- Helper names are re-exported from `nutricost_deal_monitor` for compatibility/tests.

Boundary chosen:
- Alert-state shape and sorted-ID updates are deterministic data policy.
- Extracting them keeps `process_message()` focused on Gmail message evaluation and side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/nutricost_deal_utils.py agent_skills/nutricost_deal_monitor.py tests/test_nutricost_deal_utils.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nutricost_deal_utils.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1229 passed`).

Remaining follow-up slices:
- Consider extracting sender-cleanup spec/query orchestration if tests pin `main()` outcome-count behavior.
- Keep Gmail service calls, trashing, and alert email sending in the monitor.

## 2026-07-02 - Google Cloud Receipt Manifest Helpers

Goal/scope:
- Move Google Cloud receipt manifest path and downloaded-receipts JSON serialization into `agent_skills/google_cloud_receipt_utils.py`.
- Reuse the same JSON helper for manifest file writes and CLI download output.

Files/modules changed:
- `agent_skills/google_cloud_receipt_utils.py`
- `agent_skills/google_cloud_receipts.py`
- `tests/test_google_cloud_receipts.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Manifest files are still named `manifest.json` under the chosen output directory.
- Downloaded receipt JSON still serializes dataclass fields with two-space indentation and the same field order.
- CLI `download` output and manifest file contents now use the same serialization helper.
- `google_cloud_receipts._manifest_path` remains available as an alias for the extracted helper.

Boundary chosen:
- Manifest path and JSON formatting are deterministic output-shape policy.
- Extracting them keeps the Playwright runner focused on browser automation and download coordination.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/google_cloud_receipt_utils.py agent_skills/google_cloud_receipts.py tests/test_google_cloud_receipts.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_google_cloud_receipts.py -q` passed (`16 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1228 passed`).

Remaining follow-up slices:
- Consider extracting CLI argument-to-download-options normalization only if tests cover parser defaults and error messages.
- Keep browser/session/download side effects in `google_cloud_receipts.py`.

## 2026-07-02 - Google Cloud Downloaded Receipt Helper

Goal/scope:
- Move `DownloadedReceipt` manifest-record construction into `agent_skills/google_cloud_receipt_utils.py`.
- Keep Playwright navigation, direct-download attempts, locator resolution, and file saving in `agent_skills/google_cloud_receipts.py`.

Files/modules changed:
- `agent_skills/google_cloud_receipt_utils.py`
- `agent_skills/google_cloud_receipts.py`
- `tests/test_google_cloud_receipts.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Document-row, direct-href, and click-download paths still produce the same `DownloadedReceipt` fields.
- Receipt date still comes from the parsed candidate date used for filename generation when available.
- Manifest paths still store `account_id`, `account_name`, `receipt_date`, `amount`, `source_name`, `row_text`, and saved file path as strings.
- `google_cloud_receipts.downloaded_receipt_from_candidate` is re-exported for helper/test compatibility.

Boundary chosen:
- Manifest-record construction is deterministic mapping from a `ReceiptCandidate` plus saved path.
- Extracting it removes three repeated dataclass construction blocks while leaving browser automation unchanged.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/google_cloud_receipt_utils.py agent_skills/google_cloud_receipts.py tests/test_google_cloud_receipts.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_google_cloud_receipts.py -q` passed (`15 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1227 passed`).

Remaining follow-up slices:
- Consider moving manifest JSON serialization/path helpers into the utility module if more report/download scripts need the same convention.
- Keep Playwright page/locator/download behavior in the runner unless mocked browser tests are added.

## 2026-07-02 - Session Summary Path Helper

Goal/scope:
- Move session-summary safe filename/path derivation into `jane/session_summary_helpers.py`.
- Keep configured summary directory ownership in `jane/session_summary.py`.

Files/modules changed:
- `jane/session_summary_helpers.py`
- `jane/session_summary.py`
- `tests/test_session_summary_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Session IDs still allow alphanumeric characters, dot, underscore, and dash.
- Other characters are replaced with `_`, leading/trailing dots and underscores are stripped, and an empty safe ID falls back to `default`.
- Summary files still live under `JANE_SESSION_SUMMARY_DIR` and use the `.json` suffix.

Boundary chosen:
- Path sanitization is deterministic and independent from file reads/writes.
- Injecting the base directory keeps the helper testable without importing runtime config paths.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane/session_summary_helpers.py jane/session_summary.py tests/test_session_summary_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_session_summary_helpers.py tests/test_proxy_text.py -q` passed (`16 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1226 passed`).

Remaining follow-up slices:
- `jane/session_summary.py` is now small enough that further changes should focus on a stubbed subprocess/write characterization test rather than more extraction.

## 2026-07-02 - Session Summary Prompt Helpers

Goal/scope:
- Move deterministic session-summary prompt construction and raw Qwen-output coercion into `jane/session_summary_helpers.py`.
- Keep subprocess execution, exception handling, parsed-vs-fallback choice, and JSON file writes in `jane/session_summary.py`.

Files/modules changed:
- `jane/session_summary_helpers.py`
- `jane/session_summary.py`
- `tests/test_session_summary_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The Qwen prompt still includes the current JSON summary, cleaned user message, cleaned Jane response, max-three-topic instruction, field rules, no-explanation instruction, and the partial JSON suffix `````json\n{"topics":[``.
- Raw model output still gets prefixed with `{"topics":[` only when the stripped output does not start with `{`.
- Private helper aliases remain available from `jane.session_summary`.

Boundary chosen:
- Prompt assembly and raw-output coercion are deterministic string policy and can be tested without invoking Qwen or touching session-summary files.
- `session_summary.py` now reads as orchestration around pure helper calls, which makes a later stubbed subprocess/write test smaller.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane/session_summary_helpers.py jane/session_summary.py tests/test_session_summary_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_session_summary_helpers.py tests/test_json_scanner.py tests/test_proxy_text.py -q` passed (`20 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1225 passed`).

Remaining follow-up slices:
- Add a stubbed subprocess/write test for `_update_session_summary()` before changing fallback selection or file persistence.

## 2026-07-02 - Session Summary Helper Extraction

Goal/scope:
- Move pure session-summary behavior into `jane/session_summary_helpers.py`.
- Keep summary-path resolution, async dispatch, subprocess execution, and file writes in `jane/session_summary.py`.

Files/modules changed:
- `jane/session_summary_helpers.py`
- `jane/session_summary.py`
- `tests/test_session_summary_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `format_session_summary()` keeps the numbered topic/state/open-loop output shape and three-topic cap.
- Trivial-turn gating keeps the same greeting/time-query/short-turn skip policy.
- System metadata stripping keeps the copied regex behavior and output spacing.
- Summary sanitization still drops empty topics, dedupes by topic/state key, truncates fields to the same limits, and keeps at most three topics.
- Fallback summary generation still prepends the current-turn candidate, skips duplicate topic labels, infers open loops from "next"/"need to", and uses the same keyword topic guesses.
- Private helper names remain available from `jane.session_summary` as aliases for compatibility.

Behavior intentionally improved:
- Session-summary JSON extraction now uses the shared balanced scanner, so braces inside JSON strings no longer break parsing.

Boundary chosen:
- The extracted helpers are deterministic string/dict policy and do not need subprocess, filesystem, locks, or config paths.
- `session_summary.py` now focuses on orchestration: loading current summary, building the prompt, calling Qwen, choosing parsed vs fallback summary, and writing the JSON file.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane/session_summary_helpers.py jane/session_summary.py tests/test_session_summary_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_session_summary_helpers.py tests/test_json_scanner.py tests/test_proxy_text.py -q` passed (`18 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1223 passed`).

Remaining follow-up slices:
- Add a focused test around `_update_session_summary()` with a stubbed subprocess before changing prompt assembly or write behavior.
- Legacy `test_code/test_jane_proxy_persistence.py` has stale stubs that do not accept the current `cls` writeback argument and should be repaired separately if `test_code/` is brought back as a gate.

## 2026-07-02 - Shared JSON Object Scanner

Goal/scope:
- Move the balanced JSON-object scanner into `jane/json_scanner.py`.
- Keep `jane_web/client_tool_json.py` as a compatibility re-export and reuse the shared scanner in structured short-term memory JSON parsing.

Files/modules changed:
- `jane/json_scanner.py`
- `jane_web/client_tool_json.py`
- `memory/v1/short_term_structured.py`
- `tests/test_json_scanner.py`
- `tests/test_short_term_structured.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Client-tool marker parsing still handles nested objects, escaped strings, marker-like substrings inside JSON strings, and start offsets through the same public helper name.
- `jane_web.client_tool_json.find_json_object_end` remains import-compatible for existing callers/tests.
- Structured short-term JSON parsing still strips code fences, finds the first JSON object, normalizes configured extraction keys, and rejects missing/unbalanced/non-object payloads.

Behavior intentionally improved:
- Structured short-term JSON parsing now ignores braces inside JSON strings instead of counting them as object delimiters.

Boundary chosen:
- Balanced JSON scanning is domain-agnostic string parsing and was already needed by both web client-tool marker parsing and memory extraction.
- Keeping a web compatibility wrapper avoids caller churn while moving the implementation to a shared Jane module.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane/json_scanner.py jane_web/client_tool_json.py jane_web/client_tool_markers.py memory/v1/short_term_structured.py tests/test_json_scanner.py tests/test_client_tool_json.py tests/test_short_term_structured.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_json_scanner.py tests/test_client_tool_json.py tests/test_client_tool_markers.py tests/test_short_term_structured.py test_code/test_short_term_extractor.py -q` passed (`53 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1216 passed`).

Remaining follow-up slices:
- `jane/session_summary.py` has a separate first-brace/last-brace parser; leave it unchanged until fallback behavior is characterized.
- Look for other tolerant JSON parsers that can reuse `jane.json_scanner` only when focused tests pin their current malformed-output behavior.

## 2026-07-02 - Structured Short-term Memory Metadata Helper

Goal/scope:
- Move the structured short-term Chroma metadata dictionary shape into `memory/v1/short_term_structured.py`.
- Keep UUID creation, timestamp calculation, embedding generation, and Chroma writes in `ConversationManager.update_short_term_memory()`.

Files/modules changed:
- `memory/v1/short_term_structured.py`
- `memory/v1/conversation_manager.py`
- `tests/test_short_term_structured.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Structured short-term writes still include the same `session_id`, `timestamp`, `expires_at`, `memory_type`, `author`, `topic`, `role`, `raw_chars`, `summary_chars`, and extracted metadata fields.
- `summary_style`, turn-kind flags, artifact/person/time metadata, and count fields still come from the extractor unchanged.
- Chroma add/update behavior, custom embedding fallback, skip gates, and writeback logging remain in `conversation_manager.py`.

Boundary chosen:
- Metadata shape is deterministic and had no dependency on Chroma, locks, UUID generation, or embedding calls.
- Extracting it keeps the persistence method focused on deciding whether and how to write, while tests pin the exact row metadata contract.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/short_term_structured.py memory/v1/conversation_manager.py tests/test_short_term_structured.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_short_term_structured.py test_code/test_short_term_extractor.py -q` passed (`37 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1211 passed`).

Remaining follow-up slices:
- Consider extracting theme-slot metadata builders from `_do_thematic_update()` and `_fallback_raw_theme()` once tests cover create/update/evict fallback paths.
- Keep Chroma collection calls and embedding fallback in `conversation_manager.py` until a collection fake covers the write path.

## 2026-07-02 - Client Tool Marker JSON Scanner Helper

Goal/scope:
- Extract the balanced JSON-object scanner used by client-tool markers into `jane_web/client_tool_json.py`.
- Reuse the scanner in both outgoing `[[CLIENT_TOOL:...]]` marker parsing and incoming `[TOOL_RESULT:...]` feedback parsing.

Files/modules changed:
- `jane_web/client_tool_json.py`
- `jane_web/client_tool_markers.py`
- `tests/test_client_tool_json.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `[[CLIENT_TOOL:<name>:{json}]]` parsing still handles nested JSON, escaped strings, marker-like text inside strings, whitespace before the close token, malformed names, and incomplete stream chunks the same way.
- `[TOOL_RESULT:{json}]` extraction still strips only leading well-formed dict payloads and leaves malformed markers visible.
- Tool-result brain-context formatting and delimiter neutralization are unchanged.

Boundary chosen:
- The marker parser had two copies of the same balanced-brace/string/escape scanner.
- Extracting this pure scanner reduces parser duplication while avoiding changes to stream buffering, code-fence handling, UUID generation, or phone-tool result formatting.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/client_tool_json.py jane_web/client_tool_markers.py tests/test_client_tool_json.py tests/test_client_tool_markers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_client_tool_json.py tests/test_client_tool_markers.py tests/test_proxy_text.py -q` passed (`17 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1210 passed`).

Remaining follow-up slices:
- Keep streaming buffer and code-fence state inside `ToolMarkerExtractor` unless a dedicated stream-contract test suite is expanded.
- Consider extracting phone-tool result block rendering separately if more tools add result metadata fields.

## 2026-07-02 - Web Offloader Announcement Payload Helper

Goal/scope:
- Move web task-offloader queue-progress payload construction and JSONL append behavior into `jane_web/task_offloader_announcements.py`.
- Keep background threading, heartbeat timing, context loading, automation retries, and message wording in `jane_web/task_offloader.py`.

Files/modules changed:
- `jane_web/task_offloader_announcements.py`
- `jane_web/task_offloader.py`
- `tests/test_task_offloader_announcements.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Offloader announcements still use `created_at`, `id`, `type`, and `message` keys.
- Non-final progress announcements still omit the `final` key.
- Final success and error announcements still include `"final": true`.
- JSONL writes still create the parent directory, append one UTF-8 line per announcement, and keep Unicode unescaped.
- Start, heartbeat, empty-response retry, final-result, automation-error, and unexpected-error text remains owned by the existing message helpers.

Boundary chosen:
- Announcement payload shape was repeated throughout the task runner, but it is deterministic and independent from thread scheduling or automation execution.
- Extracting only payload/write formatting reduces repeated event-shape literals while leaving runtime control flow in the offloader.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/task_offloader_announcements.py jane_web/task_offloader.py tests/test_task_offloader_announcements.py tests/test_task_offloader_messages.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_task_offloader_announcements.py tests/test_task_offloader_messages.py tests/test_announcements.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1206 passed`).

Remaining follow-up slices:
- Consider extracting offloader context/session-history loading only after adding fakes for `jane_proxy`, auth, and the context builder.
- Keep automation retry timing and heartbeat thread behavior in `task_offloader.py` unless a thread-level characterization test is added.

## 2026-07-02 - Self-healing Auto-repair Launch Policy

Goal/scope:
- Move self-healing auto-repair daily-cap/cooldown state policy into `agent_skills/self_healing_helpers.py`.
- Keep incident-path existence checks, state locking, logging, subprocess environment construction, and repair process launch in `self_healing.py`.

Files/modules changed:
- `agent_skills/self_healing_helpers.py`
- `agent_skills/self_healing.py`
- `tests/test_self_healing_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Auto-repair state still resets count when the calendar day changes.
- Daily cap still blocks launch once `auto_repair_count` reaches the configured max.
- Cooldown still blocks launch when the last repair timestamp is within the configured window.
- Successful launch decisions still update `last_auto_repair_ts`, `last_auto_repair_at`, and increment `auto_repair_count`.

Boundary chosen:
- Cap/cooldown decisions are deterministic state policy.
- Extracting them makes throttling behavior directly testable while leaving file locking and subprocess launch side effects in the runtime module.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/self_healing_helpers.py agent_skills/self_healing.py tests/test_self_healing_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_self_healing_helpers.py -q` passed (`8 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1201 passed`).

Remaining follow-up slices:
- Keep incident recording, job-file writes, JSONL logging, and auto-repair subprocess launch in `self_healing.py` until filesystem/process fakes cover the full incident lifecycle.

## 2026-07-02 - Doc Drift Vocal Summary Helper

Goal/scope:
- Move Doc Drift Audit vocal-summary payload selection into `agent_skills/doc_drift_helpers.py`.
- Keep importing and calling `log_vocal_summary()` in `doc_drift_auditor.py`.

Files/modules changed:
- `agent_skills/doc_drift_helpers.py`
- `agent_skills/doc_drift_auditor.py`
- `tests/test_doc_drift_auditor.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- No-drift runs still log the same info summary text.
- Warning runs still use medium severity and the same "docs drifted from the code" wording.
- Fix-only runs still use info severity and the same "small fixes" wording.
- The auditor's private `_drift_vocal_summary_kwargs` alias is available for tests/debugging.

Boundary chosen:
- Vocal-summary kwargs are deterministic from the change/warning lists.
- Extracting them keeps `_log_vocal()` focused on optional import and side-effect execution while making message-branch behavior testable.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/doc_drift_helpers.py agent_skills/doc_drift_auditor.py tests/test_doc_drift_auditor.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_doc_drift_auditor.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1200 passed`).

Remaining follow-up slices:
- Keep cron reads, filesystem edits, report writes, git commits, and vocal logging side effects in `doc_drift_auditor.py`.

## 2026-07-02 - Pipeline Audit Judge Prompt Helper

Goal/scope:
- Move pipeline-audit LLM judge prompt construction into `agent_skills/pipeline_audit_helpers.py`.
- Keep live pipeline HTTP calls, classify-only fallback, Ollama judge execution, Chroma exemplar logic, and report writes in `pipeline_audit_100.py`.

Files/modules changed:
- `agent_skills/pipeline_audit_helpers.py`
- `agent_skills/pipeline_audit_100.py`
- `tests/test_pipeline_audit_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Judge prompts keep the same user prompt, classification, stage, ack fallback, tool-call fallback, 300-character response truncation, known-class list, and exact three-line output contract.
- Judge response parsing and report generation remain unchanged.
- The audit script's private `_build_judge_prompt` alias is available for tests/debugging.

Boundary chosen:
- The judge prompt is deterministic audit policy, while `pipeline_audit_100.py` owns live network/model orchestration.
- Extracting it extends the existing helper module and makes the audit contract directly testable.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/pipeline_audit_helpers.py agent_skills/pipeline_audit_100.py tests/test_pipeline_audit_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_pipeline_audit_helpers.py -q` passed (`8 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1199 passed`).

Remaining follow-up slices:
- Keep live pipeline streaming, classifier calls, judge model calls, and disabled Chroma self-correction in `pipeline_audit_100.py` until integration tests can fake those services together.

## 2026-07-02 - Do Math Prompt Builder

Goal/scope:
- Move the do-math local-LLM arithmetic expression prompt template and prompt construction into `jane_web/jane_v2/classes/do_math/evaluator.py`.
- Keep the local LLM call, timing, safe evaluation, error handling, and response assembly in `handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/do_math/evaluator.py`
- `jane_web/jane_v2/classes/do_math/handler.py`
- `tests/test_do_math_evaluator.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The expression prompt still lists the same allowed operators/functions, non-math `NONE` contract, examples, stripped user prompt insertion, and final `EXPRESSION:` marker.
- Safe evaluator rules, formatting, rejection paths, and handler escalation behavior are unchanged.
- The handler's private `_PROMPT_TEMPLATE` alias remains available.

Boundary chosen:
- The prompt is part of the deterministic parser/evaluator contract, while the handler owns I/O and orchestration.
- Extracting the prompt builder makes the LLM contract testable without touching Ollama or the safe AST evaluator.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/do_math/evaluator.py jane_web/jane_v2/classes/do_math/handler.py tests/test_do_math_evaluator.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_do_math_evaluator.py -q` passed (`13 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1198 passed`).

Remaining follow-up slices:
- Keep `_call_local_llm()` and handler orchestration together until tests can fake Ollama responses around timing/logging behavior.

## 2026-07-02 - Timer Follow-up Duration Parser

Goal/scope:
- Move timer follow-up duration parsing, including bare number/word replies interpreted as minutes, into `jane_web/jane_v2/classes/timer/parsing.py`.
- Keep timer resume state transitions and client-tool response construction in `handler.py` and `responses.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/timer/parsing.py`
- `jane_web/jane_v2/classes/timer/handler.py`
- `tests/test_timer_parsing.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Full duration phrases like `30 seconds` still parse through the normal duration parser.
- Follow-up replies like `five` and `2.5` still mean minutes.
- Invalid follow-up replies still return `0`, causing the handler to re-ask for duration.

Boundary chosen:
- Bare follow-up duration interpretation is parsing logic, not timer state-machine logic.
- Extracting it removes regex/number-word details from `_handle_resume()` without changing pending-action handling or timer client-tool markers.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/timer/parsing.py jane_web/jane_v2/classes/timer/handler.py tests/test_timer_parsing.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_timer_parsing.py tests/test_private_handler_utils.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1197 passed`).

Remaining follow-up slices:
- Leave the timer action state machine in `handler.py`; extracting more would require broader characterization around params-driven and legacy regex dispatch together.

## 2026-07-02 - Shopping List Action Param Guard

Goal/scope:
- Move shopping-list classifier param validation, action normalization, item splitting, and destructive-action confidence gating into `jane_web/jane_v2/classes/shopping_list/actions.py`.
- Keep mutable shopping-list store imports and add/remove/view/clear/check execution in `handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/shopping_list/actions.py`
- `jane_web/jane_v2/classes/shopping_list/handler.py`
- `tests/test_shopping_list_actions.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing params, malformed actions, unknown actions, missing add/remove/check items, and low-confidence destructive actions still escalate by returning `None`.
- Destructive confidence still rejects booleans, non-numeric values, non-finite numbers, and values below `0.80`.
- Valid add/check/view params still ignore confidence, while valid remove/clear params carry confidence through to the backing store functions.

Boundary chosen:
- Validation and confidence gating are deterministic and must happen before any shopping-list mutation.
- Extracting them makes the safety gate directly testable while leaving the store side effects in the handler.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/shopping_list/actions.py jane_web/jane_v2/classes/shopping_list/handler.py tests/test_shopping_list_actions.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_shopping_list_actions.py tests/test_shopping_list_data.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1196 passed`).

Remaining follow-up slices:
- Keep the actual list-store calls in `handler.py` unless a future test seam fakes `agent_skills.shopping_list` end to end.

## 2026-07-02 - Read Calendar Prompt Helpers

Goal/scope:
- Move read-calendar Stage 2 answer/detail prompt templates, prompt construction, forced edit/create escalation phrase checks, and `ESCALATE` marker parsing into `jane_web/jane_v2/classes/read_calendar/prompts.py`.
- Keep Google Calendar fetching, event simplification, Ollama calls, resume routing, and response payload construction in their existing modules.
- Preserve the handler's private prompt constants and helper names as imported aliases.

Files/modules changed:
- `jane_web/jane_v2/classes/read_calendar/prompts.py`
- `jane_web/jane_v2/classes/read_calendar/handler.py`
- `tests/test_read_calendar_prompts.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Calendar answer prompts keep the same spoken-style instructions, no-event guidance, `ESCALATE` instruction, current-day formatting, event summary insertion, and user-question insertion.
- Event-detail prompts keep the same detail instructions and event-info insertion.
- Edit/create/delete/reschedule calendar requests still escalate before local event listing.
- Any model response containing the word `ESCALATE` still escalates.

Boundary chosen:
- Prompt assembly and escalation text predicates are deterministic and independent of calendar I/O or local LLM execution.
- Extracting them keeps the handler focused on fetch/phrase/resume orchestration while making the LLM prompt contract directly testable.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/read_calendar/handler.py jane_web/jane_v2/classes/read_calendar/prompts.py tests/test_read_calendar_prompts.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_read_calendar_formatting.py tests/test_read_calendar_prompts.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1195 passed`).

Remaining follow-up slices:
- Keep calendar event fetching and `_ask_qwen()` in `handler.py` until tests can safely fake `calendar_tools` and Ollama together.

## 2026-07-02 - Shared Stage 2 Pending Continuation Helpers

Goal/scope:
- Make `agent_skills/private_handler_utils._expires_at()` timezone-aware while preserving the `YYYY-MM-DDTHH:MM:SSZ` string contract.
- Route weather follow-up pending actions and clinic schedule follow-up pending actions through the shared `pending_continuation()` helper.
- Remove duplicated handler-local pending-action/expiry construction.

Files/modules changed:
- `agent_skills/private_handler_utils.py`
- `jane_web/jane_v2/classes/weather/handler.py`
- `jane_web/jane_v2/classes/clinic_schedules_info/handler.py`
- `tests/test_private_handler_utils.py`
- `tests/test_weather_slices.py`
- `tests/test_clinic_schedule_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- STAGE2_FOLLOWUP payloads keep the same type, handler class, status, awaiting tag, nested data, question text, and expiry format.
- Weather still asks "Want the weather for another day?" and carries topic/location state.
- Clinic schedule follow-ups still use the `(awaiting:clinic_followup)` routing question and `clinic schedules info` handler class.

Boundary chosen:
- Pending-action construction is shared Stage 2 infrastructure, and the timestamp format is independent of handler-specific business logic.
- Centralizing the duplicated weather/clinic payload construction reduces drift and removed the full-suite `datetime.utcnow()` warning source without touching LLM calls or database/cache reads.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/private_handler_utils.py jane_web/jane_v2/classes/weather/handler.py jane_web/jane_v2/classes/clinic_schedules_info/handler.py tests/test_private_handler_utils.py tests/test_weather_slices.py tests/test_clinic_schedule_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_private_handler_utils.py tests/test_weather_slices.py tests/test_clinic_schedule_helpers.py tests/test_read_calendar_formatting.py tests/test_send_message_parsing.py tests/test_timer_parsing.py -q` passed (`44 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1192 passed`, no warning summary).

Remaining follow-up slices:
- Leave handler-specific follow-up semantics in each Stage 2 handler unless more duplicated pending-action shapes appear with direct test coverage.

## 2026-07-02 - Send Message Params Metadata Helper

Goal/scope:
- Move classifier-param normalization for the send-message Stage 2 handler into `jane_web/jane_v2/classes/send_message/parsing.py`.
- Keep LLM extraction, open-draft safety net checks, contact resolution, alias writes, confirmation handling, and client-tool response construction in their existing modules.

Files/modules changed:
- `jane_web/jane_v2/classes/send_message/parsing.py`
- `jane_web/jane_v2/classes/send_message/handler.py`
- `tests/test_send_message_parsing.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `intent_kind=ask` still escalates to Stage 3 so Opus can phrase and confirm the draft.
- Missing recipient params still escalate.
- Valid params still trim recipient/body text, convert blank bodies to `(none)`, compute the same rule-based coherence flag, and preserve the classifier confidence value.

Boundary chosen:
- Params normalization is a deterministic counterpart to the existing LLM extraction parser.
- Extracting it shrinks the live handler while leaving SMS side effects, contact lookup, alias persistence, and send/draft response markers untouched.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/send_message/handler.py jane_web/jane_v2/classes/send_message/parsing.py tests/test_send_message_parsing.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_send_message_parsing.py tests/test_pending_sms.py -q` passed (`16 passed`, 2 existing `datetime.utcnow()` warnings).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1189 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep recipient resolution and auto-alias persistence in `handler.py` until tests can fake `sms_helpers` and `vault_web.database` together without risking send behavior.

## 2026-07-02 - Todo List Response Helpers

Goal/scope:
- Move TODO-list pending-action construction and read/continue response assembly into `jane_web/jane_v2/classes/todo_list/responses.py`.
- Keep cache loading, Google Docs add/remove execution, shopping-list delegation, category matching, and resume routing in `handler.py`.
- Preserve the handler's private `_pending`, `_expires_at`, and `_read_and_ask_another` names as aliases for existing debug/import compatibility.

Files/modules changed:
- `jane_web/jane_v2/classes/todo_list/responses.py`
- `jane_web/jane_v2/classes/todo_list/handler.py`
- `tests/test_todo_list_responses.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- STAGE2_FOLLOWUP pending actions keep the same handler class, status, awaiting field, nested data shape, literal question field, and `YYYY-MM-DDTHH:MM:SSZ` expiry format.
- Reading a category still appends the spoken category to `already_read`, asks "Want to hear another category?" only when another visible category has items, and ends the conversation when nothing useful remains.
- Hidden/internal TODO categories are still filtered through the existing category helper.

Boundary chosen:
- Response payload construction is deterministic once the category list and already-read state are known.
- Extracting it reduces the large handler without touching Google Docs mutations, subprocess cache refreshes, or Stage 2 routing side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/todo_list/handler.py jane_web/jane_v2/classes/todo_list/responses.py tests/test_todo_list_responses.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_todo_list_categories.py tests/test_todo_list_parsing.py tests/test_todo_list_responses.py -q` passed (`17 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1188 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep edit execution and resume add/remove branches in `handler.py` until tests can safely fake `docs_tools`, cache refresh, and end-phrase behavior together.

## 2026-07-02 - Context Builder Memory and Transcript Helpers

Goal/scope:
- Move context-builder memory summary normalization into `context_builder/v1/memory_summary.py`.
- Add `build_user_transcript()` to `context_builder/v1/recent_history.py` and use it in both sync and async Jane context builders.
- Remove the now-unused local `MAX_MEMORY_CHARS` constant from `context_builder.py`.

Files/modules changed:
- `context_builder/v1/memory_summary.py`
- `context_builder/v1/recent_history.py`
- `context_builder/v1/context_builder.py`
- `tests/test_context_memory_summary.py`
- `tests/test_recent_history.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Real retrieved memory still wins over fallback memory and is stripped/truncated.
- `"No relevant context found."`, blank primary summaries, and blank/no-context fallbacks still produce no memory section.
- User transcripts still prepend `Recent Conversation:` only when recent history exists, then append `User: ...` and `Jane:` with the same blank-line separation.

Boundary chosen:
- Memory normalization and transcript assembly are deterministic and shared by sync/async context construction.
- Extracting them reduces duplicated context-builder assembly code without touching Chroma, research offload, user management, or tool-prompt loading.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile context_builder/v1/memory_summary.py context_builder/v1/recent_history.py context_builder/v1/context_builder.py tests/test_context_memory_summary.py tests/test_recent_history.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_context_memory_summary.py tests/test_recent_history.py tests/test_prompt_profiles.py tests/test_user_background.py -q` passed (`17 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1184 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep system-section composition, memory daemon fallback, research offload, saved-article loading, and tool-loader imports in `context_builder.py` until tests can fake those runtime sources together.

## 2026-07-02 - Ambient Heartbeat Prompt Builders

Goal/scope:
- Move Ambient heartbeat research synthesis prompt construction and implementation-task prompt construction into `agent_skills/ambient_heartbeat_rules.py`.
- Keep web search, automation runner calls, spec file reads/writes, cache updates, task completion marking, and Discord notifications in `ambient_heartbeat.py`.

Files/modules changed:
- `agent_skills/ambient_heartbeat_rules.py`
- `agent_skills/ambient_heartbeat.py`
- `tests/test_ambient_heartbeat_rules.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Research synthesis prompts keep the same Project Ambient system context and still truncate web-search data to 8000 characters.
- Implementation prompts keep the same task line, spec context block, and instruction to report completion in 2-3 sentences.
- Automation timeouts and failure handling are unchanged.

Boundary chosen:
- Prompt construction is deterministic once the topic prompt, web data, task, and spec excerpt are known.
- Extracting it keeps the heartbeat runner focused on external search, automation, and spec mutation while making prompt contracts directly testable.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ambient_heartbeat_rules.py agent_skills/ambient_heartbeat.py tests/test_ambient_heartbeat_rules.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ambient_heartbeat_rules.py tests/test_ambient_task_research_rules.py -q` passed (`16 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1181 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep live web search, automation execution, and spec/cache file writes in `ambient_heartbeat.py` until tests can fake those side effects together.

## 2026-07-02 - Dead Code Dynamic Import Helpers

Goal/scope:
- Move dynamic import prefix regex parsing, Python relative-path dotted directory normalization, and dynamic-prefix path matching into `agent_skills/dead_code_dynamic_imports.py`.
- Keep filesystem traversal, real directory validation, grep/crontab checks, dead-file scanning, auto-delete, report writing, and git commit behavior in `dead_code_auditor.py`.

Files/modules changed:
- `agent_skills/dead_code_dynamic_imports.py`
- `agent_skills/dead_code_auditor.py`
- `tests/test_dead_code_dynamic_imports.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The auditor still recognizes `importlib.import_module(f"pkg.sub.{name}")`, string-concat `import_module("pkg.sub." + name)`, and `__import__(f"pkg.sub.{name}")` patterns.
- Dynamic import prefixes are still trusted only after the auditor confirms they map to real directories in the Vessence tree.
- Files under an exact dynamic-prefix directory or nested beneath one still count as dynamically imported.

Boundary chosen:
- Regex parsing and relative path matching are deterministic and easy to test without walking the repo.
- Extracting them keeps the auditor's scan loop focused on filesystem and fail-safe reference checks.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/dead_code_dynamic_imports.py agent_skills/dead_code_auditor.py tests/test_dead_code_dynamic_imports.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_dead_code_dynamic_imports.py tests/test_dead_code_policy.py tests/test_dead_code_report.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1179 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep repo traversal, grep reference counting, crontab checks, unlinking, and git commit behavior in `dead_code_auditor.py` until tests can fake those external systems together.

## 2026-07-02 - Nightly Summary Log Rendering Helpers

Goal/scope:
- Move nightly self-improvement append-log preamble and per-job summary line rendering into `agent_skills/nightly_report_rendering.py`.
- Keep orchestrator logging, job subprocess execution, report file I/O, readable report writes, and vocal rollup behavior in `nightly_self_improve.py`.

Files/modules changed:
- `agent_skills/nightly_report_rendering.py`
- `agent_skills/nightly_self_improve.py`
- `tests/test_nightly_report_rendering.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- New `configs/self_improve_log.md` files still start with the same title and column explanation.
- Per-run headings still use `YYYY-MM-DD HH:MM`.
- Job rows still use the same ok/timeout/failure markers, status text, duration seconds, and log basename rendering.

Boundary chosen:
- Summary log Markdown is deterministic once the run start time and job result dicts are known.
- Extracting it keeps the orchestrator focused on job execution and file appending while extending the existing report-rendering test surface.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/nightly_report_rendering.py agent_skills/nightly_self_improve.py tests/test_nightly_report_rendering.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nightly_report_rendering.py tests/test_nightly_report_summaries.py tests/test_nightly_log_reader.py -q` passed (`22 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1175 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep actual summary file creation/appending in `nightly_self_improve.py` until filesystem tests cover missing log files, append failures, and report archive writes together.

## 2026-07-02 - Essence Builder Interview Helpers

Goal/scope:
- Move essence builder section display names, question formatting, section intro rendering, essence-name extraction, progress summary, and spec markdown rendering into `agent_skills/essence_builder_interview.py`.
- Keep interview state persistence, answer processing, manifest generation, folder copying, output file writes, and build orchestration in `essence_builder.py`.

Files/modules changed:
- `agent_skills/essence_builder_interview.py`
- `agent_skills/essence_builder.py`
- `tests/test_essence_builder_interview.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Section names and out-of-range fallback labels are unchanged.
- Required and optional interview question numbering keeps the same Markdown layout.
- Essence-name extraction still prefers quoted names, then colon suffixes, then a 60-character fallback.
- Public progress and generated spec markdown keep the same section order and skip `review_approve`.

Boundary chosen:
- Interview text rendering and progress/spec formatting are pure transformations over section definitions and recorded answers.
- Extracting them makes the builder's user-facing text contract directly testable while leaving filesystem generation untouched.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/essence_builder_interview.py agent_skills/essence_builder.py tests/test_essence_builder_interview.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_essence_builder_interview.py tests/test_essence_builder_parsing.py tests/test_essence_builder_outputs.py -q` passed (`20 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1174 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep state save/load and `build_essence_from_spec()` file operations in `essence_builder.py` until tests can fake template copy, generated files, and state path behavior together.

## 2026-07-02 - Education Audit Rule Helpers

Goal/scope:
- Move homework audit mode validation, local-base-url guard, unsupported-answer issue payload, grader/canonical mismatch issue payload, and unreliable-verdict issue payload into `agent_skills/edu_homework_audit_rules.py`.
- Keep DB access, HTTP/dev-login workflow, attempt reuse/start/delete behavior, answer submission, LLM review, report writing, and CLI parsing in `edu_homework_audit.py`.

Files/modules changed:
- `agent_skills/edu_homework_audit_rules.py`
- `agent_skills/edu_homework_audit.py`
- `tests/test_edu_homework_audit_rules.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `run_audit()` still accepts only `full-grade` and `audit-only`, and `--reuse-attempt` still requires audit-only mode.
- Non-local base URLs are still refused with the same localhost DB-port warning.
- Unsupported auto-answer, canonical-solution mismatch, and stale/locked/unknown verdict findings keep the same severities, kinds, and message text.

Boundary chosen:
- Validation and issue-payload construction are deterministic policy independent of MySQL, HTTP, grader responses, and report output.
- Extracting them makes the high-risk audit loop smaller without changing attempt ownership or submission semantics.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/edu_homework_audit_rules.py agent_skills/edu_homework_audit.py tests/test_edu_homework_audit_rules.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_edu_homework_audit_rules.py tests/test_edu_homework_report.py tests/test_edu_homework_llm_review.py tests/test_edu_homework_parsers.py -q` passed (`17 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1168 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep the live audit attempt lifecycle in `edu_homework_audit.py` until tests can fake DB rows, `EduClient`, grader fragments, cleanup failures, and report sidecar writes together.

## 2026-07-02 - Google Cloud Billing Account Helpers

Goal/scope:
- Move Google Cloud billing account row normalization and open-account selection into `agent_skills/google_cloud_receipt_utils.py`.
- Keep `gcloud` subprocess execution, browser profile checks, Playwright navigation, receipt discovery, and downloads in `google_cloud_receipts.py`.

Files/modules changed:
- `agent_skills/google_cloud_receipt_utils.py`
- `agent_skills/google_cloud_receipts.py`
- `tests/test_google_cloud_receipts.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `billingAccounts/{id}` names still normalize to bare account ids, display names still fall back to the account id, and missing ids are skipped.
- Only open billing accounts are considered selectable.
- Requested account ids are still whitespace-trimmed, closed or absent accounts are reported as missing, and `_select_accounts()` still raises the same error shape.

Boundary chosen:
- Account row normalization and requested-id filtering are deterministic transformations over `gcloud` JSON output.
- Extracting them leaves the downloader responsible for I/O while giving account-selection behavior direct coverage.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/google_cloud_receipt_utils.py agent_skills/google_cloud_receipts.py tests/test_google_cloud_receipts.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_google_cloud_receipts.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1163 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep `gcloud` execution, profile validation, Playwright discovery, and file downloads in `google_cloud_receipts.py` until tests can fake subprocess JSON, browser locators, popups, cookies, and download failures together.

## 2026-07-02 - Conversation Archival Scheduling Helpers

Goal/scope:
- Move smart-Archivist wait policy and Archivist model-selection policy into `memory/v1/conversation_archival.py`.
- Keep wall-clock lookup, idle timer calculation, archival triggering, model invocation, and persistence in `conversation_manager.py`.

Files/modules changed:
- `memory/v1/conversation_archival.py`
- `memory/v1/conversation_manager.py`
- `tests/test_conversation_archival.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- After `ARCHIVIST_SMART_AFTER_HOUR`, archival still waits when idle time is below `ARCHIVIST_SMART_IDLE_SECS`.
- The smart model is selected only when the current hour is at or after the smart threshold and idle time is at least the smart idle threshold.
- The default Archivist model is still used before the smart window or while idle time is below the threshold.

Boundary chosen:
- The hour/idle comparison is deterministic once the current hour and thresholds are supplied.
- Extracting it makes the time policy directly testable while leaving runtime scheduling in `ConversationManager`.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/conversation_archival.py memory/v1/conversation_manager.py tests/test_conversation_archival.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_conversation_archival.py tests/test_conversation_text.py tests/test_conversation_themes.py -q` passed (`25 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1161 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep actual idle-time computation, background archival triggers, and model execution in `conversation_manager.py` until scheduler tests can fake the active write lock and collection state together.

## 2026-07-02 - Conversation Archival Prompt Helpers

Goal/scope:
- Move conversation archival triage noise filtering, Archivist triage prompt construction, triage decision normalization, conversation summary prompt construction, and bad-summary rejection into `memory/v1/conversation_archival.py`.
- Keep LLM calls, exception handling, logging, Chroma writes, SQLite reads/writes, and archival orchestration in `conversation_manager.py`.

Files/modules changed:
- `memory/v1/conversation_archival.py`
- `memory/v1/conversation_manager.py`
- `tests/test_conversation_archival.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Known low-signal archival inputs still short-circuit to `Discard` with case-insensitive regex matching.
- Archivist triage still accepts only `Keep`, `Forgettable`, or `Discard`; all other model outputs still become `Retry`.
- Conversation summaries still use the same neutral third-person summary prompt and reject summaries containing configured bad-pattern substrings case-insensitively.

Boundary chosen:
- Prompt text, prefilter policy, and decision normalization are deterministic and do not require Chroma or LLM calls to test.
- Extracting them leaves `ConversationManager` focused on persistence and model invocation while making archival prompt contracts directly visible.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/conversation_archival.py memory/v1/conversation_manager.py tests/test_conversation_archival.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_conversation_archival.py tests/test_conversation_text.py tests/test_conversation_themes.py -q` passed (`24 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1160 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep archival model calls, Chroma collection mutation, and SQLite ledger interactions in `conversation_manager.py` until fake collection/database tests cover triage failures and archival write paths together.

## 2026-07-02 - RA Research NCBI Request Helpers

Goal/scope:
- Move NCBI parameter assembly, PubMed esearch parameters, esearch cache JSON shape, PMID extraction, efetch parameters, and efetch cache text rendering into `agent_skills/ra_research_ncbi.py`.
- Keep HTTP requests, response parsing, cache file writes, XML parsing, retry/throttle behavior, and candidate selection in `ra_research_cron.py`.

Files/modules changed:
- `agent_skills/ra_research_ncbi.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_ncbi.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- NCBI params still include `tool` and `email`, include stripped `NCBI_API_KEY` only when present, and let caller extras override earlier keys.
- PubMed search requests still use `db=pubmed`, `retmode=json`, the same term/retmax/retstart/sort fields, and return IDs as strings.
- PubMed search cache JSON and efetch cache text keep the same timestamp, URL, query/PMID, and raw response fields.

Boundary chosen:
- Request parameter and cache payload construction is deterministic once the query, PMID list, timestamps, URL, and response data are known.
- Extracting it makes PubMed network functions read as I/O wrappers around explicit request/cache contracts.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_ncbi.py agent_skills/ra_research_cron.py tests/test_ra_research_ncbi.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_ncbi.py tests/test_ra_research_pubmed.py tests/test_ra_research_candidates.py -q` passed (`18 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1154 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep live PubMed HTTP calls and XML parse loops in `ra_research_cron.py` until tests can fake successful esearch/efetch responses, cache write paths, malformed XML, and NCBI failures together.

## 2026-07-02 - RA Research Artifact Helpers

Goal/scope:
- Move RA research artifact slugging, HTML/XML text extraction, JATS article detection, source folder naming, PubMed abstract text rendering, web source metadata construction, and raw source suffix selection into `agent_skills/ra_research_artifacts.py`.
- Keep HTTP fetching, artifact file writes, PDF/XML retrieval, throttling sleeps, summary generation, and cron orchestration in `ra_research_cron.py`.

Files/modules changed:
- `agent_skills/ra_research_artifacts.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_artifacts.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Slugs still allow letters, numbers, underscores, dots, and hyphens, fall back to `source`, and truncate at the caller-provided length.
- HTML extraction still removes script/style/nav/footer/header/aside content; PMC XML extraction still strips references, tables, figures, and permissions.
- PubMed abstract artifacts keep the same saved metadata text format.
- Web source artifacts keep the same `web_{id}` source id, folder naming, metadata fields, and `.xml` versus `.html` suffix rule.

Boundary chosen:
- Artifact naming and text extraction are pure transformations over source metadata or response bodies.
- Extracting them reduces the cron module's direct parsing/rendering responsibilities while leaving online fetch behavior unchanged.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_artifacts.py agent_skills/ra_research_cron.py tests/test_ra_research_artifacts.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_artifacts.py tests/test_ra_research_source_utils.py tests/test_ra_research_state.py -q` passed (`18 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1149 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep `save_pubmed_artifacts()` and `save_web_source_artifacts()` in `ra_research_cron.py` until fake HTTP/file tests cover full-text XML, PDF detection, web HTML/XML handling, and failure logging together.

## 2026-07-02 - RA Research State Payload Helpers

Goal/scope:
- Move RA research cron default-state construction, run-start mutation, run-artifact state stamping, delivery-result flags, and returned run payload shaping into `agent_skills/ra_research_state.py`.
- Keep directory creation, state file I/O, PubMed/web fetching, LLM/Codex calls, report writing, notification delivery, and cron orchestration in `ra_research_cron.py`.

Files/modules changed:
- `agent_skills/ra_research_state.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_state.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing or unreadable state files still produce the same active RA research state shape.
- Run start still refreshes mission/status, increments `run_count` with the same `int()` conversion, and stores the start timestamp.
- Run artifact paths, smart-provider metadata, delivery flags, codex-path fallback, and the public `run_once()` return payload keep the same keys and string conversions.

Boundary chosen:
- State/result shaping is deterministic once timestamps, paths, counts, and delivery channel are known.
- Extracting it leaves the large cron module focused on online research orchestration and side effects while giving the state contract direct tests.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_state.py agent_skills/ra_research_cron.py tests/test_ra_research_state.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_state.py tests/test_ra_research_delivery.py tests/test_ra_research_report_markdown.py -q` passed (`20 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1141 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep source fetching, summary retry, Codex synthesis, report file writes, and notification delivery in `ra_research_cron.py` until fake filesystem/network tests cover those side effects together.

## 2026-07-02 - Janitor Theme Dedupe Helpers

Goal/scope:
- Move short-term theme row extraction and per-neighbor cross-session deletion decisions into `memory/v1/janitor_theme_dedupe.py`.
- Keep Chroma reads, nearest-neighbor queries, random scan limiting, delete calls, and logging in `janitor_memory.py`.

Files/modules changed:
- `memory/v1/janitor_theme_dedupe.py`
- `memory/v1/janitor_memory.py`
- `tests/test_janitor_theme_dedupe.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Only rows with `memory_type == "short_term_theme"` are considered for cross-session dedupe.
- Same-theme, same-session, already-deleted, already-seen, and over-threshold neighbors still do not delete anything.
- Cross-session near-duplicates still keep the more recently updated theme and delete the older one.

Boundary chosen:
- Chroma querying is runtime I/O, but row shaping and neighbor deletion policy are deterministic.
- Extracting them makes `dedup_cross_session_themes()` easier to audit without changing delete behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/janitor_theme_dedupe.py memory/v1/janitor_memory.py tests/test_janitor_theme_dedupe.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_janitor_theme_dedupe.py tests/test_janitor_report.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1136 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep cross-session theme query loops and Chroma deletes in `janitor_memory.py` until tests can fake nearest-neighbor results, random scan limiting, and delete failures.

## 2026-07-02 - Janitor Normalization Prompt Builders

Goal/scope:
- Move long-term memory split/rewrite normalization prompt construction into `memory/v1/janitor_normalization.py`.
- Keep candidate selection, LLM calls, Chroma add/update/delete, quarantine logging, and result counters in `janitor_memory.py`.

Files/modules changed:
- `memory/v1/janitor_normalization.py`
- `memory/v1/janitor_memory.py`
- `tests/test_janitor_normalization.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Oversized split prompts still request 2-6 atomic durable memories as JSON and include the same topic/memory fields.
- Rewrite prompts still request one compact durable memory, use the same max-character value, and keep the same durable-facts/filler-removal instructions.
- Normalization thresholds, result accounting, metadata shape, and Chroma writes are unchanged.

Boundary chosen:
- Prompt construction is deterministic policy already adjacent to normalization metadata helpers.
- Extracting it leaves the janitor normalization loop focused on orchestration and collection mutation.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/janitor_normalization.py memory/v1/janitor_memory.py tests/test_janitor_normalization.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_janitor_normalization.py tests/test_janitor_report.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1133 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep normalization LLM parsing and Chroma add/update/delete behavior in `janitor_memory.py` until fake collection tests cover split success, rewrite success, unchanged rows, and quarantine failures.

## 2026-07-02 - Janitor Code Verification Prompts

Goal/scope:
- Move code-memory detection plus Codex and frontier verification prompt builders into `memory/v1/janitor_code_verification.py`.
- Keep subprocess execution, frontier invocation, JSON extraction, metadata stamping, quarantine/delete behavior, and collection updates in `janitor_memory.py`.

Files/modules changed:
- `memory/v1/janitor_code_verification.py`
- `memory/v1/janitor_memory.py`
- `tests/test_janitor_code_verification.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Code-memory detection keeps the same Vessence-internals regex coverage.
- Codex prompts keep the same audit checklist, memory id/topic rendering, and JSON verdict contract.
- Frontier prompts keep the same Codex finding fields, actual-code confirmation instruction, and JSON update/delete/keep contract.
- `janitor_memory._is_code_memory` remains available as an alias to the extracted helper.

Boundary chosen:
- Verification prompt construction and code-memory classification are deterministic policy.
- Extracting them leaves the janitor verifier focused on process execution, parsing, and Chroma mutation.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/janitor_code_verification.py memory/v1/janitor_memory.py tests/test_janitor_code_verification.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_janitor_code_verification.py tests/test_janitor_report.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1132 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep code-memory verification execution and fix application in `janitor_memory.py` until tests can fake Codex output, frontier output, collection updates, deletes, and quarantine writes.

## 2026-07-02 - Janitor Report Payload Builders

Goal/scope:
- Move memory janitor JSON report and append-only history entry construction into `memory/v1/janitor_report.py`.
- Keep load gating, Chroma reads/writes, purge/consolidation/normalization work, file writes, code-memory verification, and dynamic marker refresh in `janitor_memory.py`.

Files/modules changed:
- `memory/v1/janitor_report.py`
- `memory/v1/janitor_memory.py`
- `tests/test_janitor_report.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Report payload keeps the same timestamps, reduction counts, forgettable purge breakdown, permanent count, processed topics, deletion summaries, normalization result, quarantine path, log purge counts, image clustering placeholder, and merge details.
- History entries keep the same append-only shape and derive unique `collection::topic` merge labels from the merge log.
- `run_janitor()` still writes `JANITOR_LOG` and `janitor_consolidation_history.jsonl` in the same places.

Boundary chosen:
- Report/history payload construction is deterministic after the janitor stages finish.
- Extracting it makes `run_janitor()` more focused on orchestration and side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/janitor_report.py memory/v1/janitor_memory.py tests/test_janitor_report.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_janitor_report.py tests/test_janitor_consolidation.py tests/test_janitor_duplicates.py tests/test_janitor_expiry.py tests/test_janitor_log_retention.py tests/test_janitor_normalization.py tests/test_janitor_query_markers.py tests/test_janitor_rules.py -q` passed (`26 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1129 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep janitor stage orchestration and report file writes in `janitor_memory.py` until fake Chroma and filesystem tests cover purge, consolidation, normalization, and history write failures together.

## 2026-07-02 - TalkingPoints Cache Entry Helper

Goal/scope:
- Move TalkingPoints readback cache entry TTL/value interpretation into `message_readback_helpers.cache_entry_readback_value()`.
- Keep cache file loading/saving, current-time lookup, cache sentinel ownership, and network resolution in `message_readback.py`.

Files/modules changed:
- `jane_web/message_readback_helpers.py`
- `jane_web/message_readback.py`
- `tests/test_message_readback_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Non-dict entries still count as cache misses.
- Resolved entries use the success TTL and return the cached string.
- Empty failed-resolution entries use the shorter failed-cache TTL and return `None` while fresh.
- Expired entries return the caller-provided cache-miss sentinel.

Boundary chosen:
- Cache entry interpretation is deterministic once the entry, current time, TTLs, and sentinel are known.
- Extracting it leaves the readback module focused on file I/O and TalkingPoints network resolution.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/message_readback_helpers.py jane_web/message_readback.py tests/test_message_readback_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_message_readback_helpers.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1127 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep TalkingPoints HTTP resolution and cache file writes in `message_readback.py` until tests can fake `requests`, HTML parsing, cache path selection, and write failures.

## 2026-07-02 - V3 Privacy Gate Decision Helpers

Goal/scope:
- Move Jane v3 privacy-gate neighbor filtering and closest/majority refusal decision logic into `jane_web/jane_v3/privacy_gate.py`.
- Keep v2 classifier loading, embedding, Chroma querying, `privacy_for()` import, logging, and fail-open exception behavior in `jane_web/jane_v3/pipeline.py`.

Files/modules changed:
- `jane_web/jane_v3/privacy_gate.py`
- `jane_web/jane_v3/pipeline.py`
- `tests/test_v3_privacy_gate.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Neighbors still enter the gate only when distance is non-`None` and within `_PRIVACY_GATE_DISTANCE`.
- The gate still refuses when the closest in-range neighbor is `local_only`.
- The gate still refuses when at least 3 in-range neighbors are private and private neighbors form a strict majority.
- Empty/non-majority neighbor sets still allow Stage 3.

Boundary chosen:
- Chroma lookup is runtime I/O, but the privacy decision over neighbors is deterministic.
- Extracting it makes the fail-open query wrapper easier to audit while adding direct coverage for the refusal rules.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v3/privacy_gate.py jane_web/jane_v3/pipeline.py tests/test_v3_privacy_gate.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_v3_privacy_gate.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1126 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep `_stage3_privacy_check()` embedding and Chroma access in the v3 pipeline until tests can fake classifier state, collection counts, query results, and privacy lookup failures.

## 2026-07-02 - Evidence Context Composition Helpers

Goal/scope:
- Move verify-first evidence metadata defaults plus architecture and memory evidence block composition into `jane_web/evidence_context.py`.
- Keep evidence requirement classification, async Chroma lookup, memory dedup, body prepending, and logging in `jane_web/jane_v2/pipeline.py`.

Files/modules changed:
- `jane_web/evidence_context.py`
- `jane_web/jane_v2/pipeline.py`
- `tests/test_evidence_context.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Evidence metadata starts with the same required/code/memory flags and char counts.
- Jane architecture context keeps the same XML wrapper and guidance text.
- Required Chroma memory evidence keeps the same bracketed section markers and skips blank deduped memory.
- `_apply_evidence_policy()` still loads architecture only for code-required turns and fetches/dedupes memory only for memory-required turns.

Boundary chosen:
- Verify-block text composition is deterministic once evidence requirements and fetched context are known.
- Extracting it leaves `_apply_evidence_policy()` focused on async retrieval, import boundaries, and body mutation.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/evidence_context.py jane_web/jane_v2/pipeline.py tests/test_evidence_context.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_evidence_context.py tests/test_verify_first_policy.py tests/test_jane_v2_pipeline_helpers.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1122 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep `_apply_evidence_policy()` async memory lookup and body-prepend behavior in `pipeline.py` until tests can fake `classify_evidence_requirements`, Chroma evidence, dedup, and architecture file reads together.

## 2026-07-02 - FIFO Turn Record Builder

Goal/scope:
- Move structured FIFO turn record assembly into `jane_web/jane_v2/fifo_records.py`.
- Keep privacy lookup, compact summary formatting, `add_structured()`, conversation-end FIFO clearing, and error logging in `jane_web/jane_v2/pipeline.py`.

Files/modules changed:
- `jane_web/jane_v2/fifo_records.py`
- `jane_web/jane_v2/pipeline.py`
- `tests/test_fifo_records.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Base FIFO records still include `user_text`, `assistant_text`, `summary`, `stage`, and `intent`.
- Privacy and confidence are still omitted when empty.
- Handler structured fields still skip `None` values.
- Client tools still normalize to `{"name", "args"}` entries, with `tool` as a fallback name and `{}` as default args.
- Conversation-end and evidence extras still live under `metadata`.

Boundary chosen:
- FIFO record assembly is deterministic once privacy and summary are computed.
- Extracting it keeps `_persist_turn_to_fifo()` focused on imports, runtime privacy lookup, FIFO writes, and clear-on-end side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/fifo_records.py jane_web/jane_v2/pipeline.py tests/test_fifo_records.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_fifo_records.py tests/test_jane_v2_pipeline_helpers.py -q` passed (`8 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1119 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep FIFO persistence and clear-on-conversation-end behavior in `pipeline.py` until tests can fake `vault_web.recent_turns` writes and failures.

## 2026-07-02 - Self-Improvement Context Renderer

Goal/scope:
- Move Stage 3 self-improvement context block rendering into `jane_web/self_improvement_context.py`.
- Keep recent summary loading, import failure handling, logging, and body injection in `jane_web/jane_v2/pipeline.py`.

Files/modules changed:
- `jane_web/self_improvement_context.py`
- `jane_web/jane_v2/pipeline.py`
- `tests/test_self_improvement_context.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Empty logs still produce the same `[SELF IMPROVEMENT CONTEXT]` block with latest-report/log paths and the 14-day no-entry guidance.
- Populated logs still group entries by job, keep newest-first numbering, preserve severity fallback to `info`, and include the same voice-response style instructions.
- `_inject_self_improvement_context()` still reads 14 days / 20 entries and appends the rendered block to the body.

Boundary chosen:
- Rendering the self-improvement block is deterministic once `read_recent_summaries()` returns entries.
- Extracting it removes a large text-formatting branch from the v2 pipeline without changing log I/O or Stage 3 injection order.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/self_improvement_context.py jane_web/jane_v2/pipeline.py tests/test_self_improvement_context.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_self_improvement_context.py tests/test_jane_v2_pipeline_helpers.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1116 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep self-improvement log reading in `agent_skills.self_improve_log` and pipeline import handling unchanged unless storage-level tests cover missing files, malformed JSON, and cutoff behavior.

## 2026-07-02 - Delegate Ack Policy Helpers

Goal/scope:
- Move Stage 3 delegate-ack duration heuristics, `Got it` rewrite policy, prompt construction, and model-response cleanup into `jane_web/jane_v2/delegate_ack.py`.
- Keep recent FIFO lookup, Ollama model selection, keep-alive policy, async HTTP call, activity recording, and fallback logging in `jane_web/jane_v2/pipeline.py`.

Files/modules changed:
- `jane_web/jane_v2/delegate_ack.py`
- `jane_web/jane_v2/pipeline.py`
- `tests/test_delegate_ack.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Duration buckets still use the same signal phrases and word-count thresholds.
- Flow-aware ack prompts keep the same requirements, examples, bad examples, class line, and 400-character user-message cap.
- Model responses still strip labels/quotes, cap long text at the first period or 120 characters, and rewrite repeated `Got it` starts by route class.
- `_estimate_duration`, `_avoid_got_it_default`, and `_ACK_FALLBACK` remain available in `pipeline.py` as imported private aliases.

Boundary chosen:
- Ack policy is deterministic prompt/response text handling around the async Ollama call.
- Extracting it keeps `_generate_delegate_ack()` focused on runtime model invocation and error fallback.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/delegate_ack.py jane_web/jane_v2/pipeline.py tests/test_delegate_ack.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_delegate_ack.py tests/test_jane_v2_pipeline_helpers.py -q` passed (`9 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1114 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep `_generate_delegate_ack()` transport, timeout, keep-alive, and activity-recording behavior in `pipeline.py` until an async HTTP fake covers Ollama failures and response parsing end to end.

## 2026-07-02 - Conversation Transcript Rendering Helpers

Goal/scope:
- Move ledger transcript line cleanup and full-session transcript rendering into `conversation_windows.py`.
- Keep SQLite reads, session filtering, and archival scheduling in `ConversationManager`.

Files/modules changed:
- `memory/v1/conversation_windows.py`
- `memory/v1/conversation_manager.py`
- `tests/test_conversation_windows.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Transcript rendering still strips injected metadata blocks, collapses whitespace, skips empty/protocol-chatter turns, uppercases roles, and joins retained lines with blank lines.
- Window archival transcripts and full-session archival transcripts now share the same line cleanup policy.

Boundary chosen:
- Ledger row rendering is deterministic text transformation.
- Extracting it keeps `_fetch_session_transcript()` focused on SQL access and makes session/window archival cleanup consistent.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/conversation_windows.py memory/v1/conversation_manager.py tests/test_conversation_windows.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_conversation_windows.py tests/test_conversation_text.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1110 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep SQLite ledger fetching and window-watermark updates in `ConversationManager` until database-backed tests cover failed transcript fetches and archival retry state.

## 2026-07-02 - Long-Term Promotion Helpers

Goal/scope:
- Move long-term promotion merge-candidate shaping, Memory Architect merge prompt construction, and archivist metadata construction into `long_term_promotion.py`.
- Keep target collection selection, Chroma query/add/update, `completion_json()`, UUID generation, timestamps, and error handling in `ConversationManager`.

Files/modules changed:
- `memory/v1/long_term_promotion.py`
- `memory/v1/conversation_manager.py`
- `tests/test_long_term_promotion.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Empty nearest-neighbor query results still skip the merge prompt and add a fresh entry.
- Missing distance entries still default to `1.0`.
- Merge prompts keep the same category/content header, match formatting, decision criteria, and JSON response contract.
- Archivist metadata keeps the same source/session/topic/timestamp fields, optional `updated_thematic` status, and user-memory `user_id` / `memory_type` / `author` fields.

Boundary chosen:
- Query result shaping and prompt/metadata construction are deterministic around the Chroma and LLM side effects.
- Extracting them reduces `_promote_to_long_term()` while preserving the collection write path.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/long_term_promotion.py memory/v1/conversation_manager.py tests/test_long_term_promotion.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_long_term_promotion.py tests/test_conversation_themes.py -q` passed (`13 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1109 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep `_promote_to_long_term()` collection writes in `ConversationManager` until fake Chroma collections cover query failures, merge updates, new adds, user-memory routing, and partial archivist failures.

## 2026-07-02 - Archivist Prompt Builder

Goal/scope:
- Move the Thematic Archivist JSON prompt construction into `conversation_themes.archivist_prompt()`.
- Keep `completion_json()`, theme registry fetches, archival topic resolution, user-identity reclassification, long-term promotion, and partial-failure behavior in `ConversationManager`.

Files/modules changed:
- `memory/v1/conversation_themes.py`
- `memory/v1/conversation_manager.py`
- `tests/test_conversation_themes.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The archivist prompt keeps the same worth-remembering rubric, drop rules, heuristics, output schema, theme rules, atomic rules, and 20,000-character transcript tail.
- Registered theme text still comes from `_format_theme_registry_for_prompt()`.
- Atomic topic names still come from `ConversationManager._ATOMIC_MEMORY_TOPICS`.

Boundary chosen:
- Prompt construction is deterministic text policy and easy to unit-test.
- Extracting it removes a large prompt literal from `_archive_transcript()` while preserving the archival execution and persistence path.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/conversation_themes.py memory/v1/conversation_manager.py tests/test_conversation_themes.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_conversation_themes.py tests/test_conversation_text.py -q` passed (`18 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1106 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep archival promotion, registry resolution, and window watermark changes in `ConversationManager` until fake long-term collection tests can prove retry and partial-failure behavior.

## 2026-07-02 - Session Theme Result Helpers

Goal/scope:
- Move Chroma theme-result fallback filtering and sorted entry construction into `conversation_themes.py`.
- Keep Chroma `get()` calls, compound-query fallback, session scoping, and collection ownership in `ConversationManager`.

Files/modules changed:
- `memory/v1/conversation_themes.py`
- `memory/v1/conversation_manager.py`
- `tests/test_conversation_themes.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Compound-query fallback still filters only rows whose metadata has `memory_type == "short_term_theme"`.
- Theme entries still contain `id`, `document`, and `metadata`, with missing metadata defaulting to `{}`.
- Theme entries still sort by `metadata.theme_index`, defaulting missing indexes to `0`.

Boundary chosen:
- Chroma result shaping is deterministic data transformation.
- Extracting it keeps `_fetch_session_themes()` focused on database lookup and fallback selection.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/conversation_themes.py memory/v1/conversation_manager.py tests/test_conversation_themes.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_conversation_themes.py tests/test_conversation_text.py -q` passed (`17 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1105 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep actual theme create/update/delete collection calls in `ConversationManager` until a fake collection fixture covers IDs, metadata timestamps, and duplicate theme indexes.

## 2026-07-02 - Conversation Theme Prompt Helpers

Goal/scope:
- Move thematic-memory title prompt, classification prompt, classification parser, title cleanup, and summary prompt construction into `conversation_themes.py`.
- Keep LLM calls, fallback decisions, logging, theme Chroma records, and session theme fetch/update behavior in `ConversationManager`.

Files/modules changed:
- `memory/v1/conversation_themes.py`
- `memory/v1/conversation_manager.py`
- `tests/test_conversation_themes.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Empty theme lists still ask for a short title and fall back to the first 50 characters of the turn.
- Existing-theme prompts keep the same indexed list format, 100-character theme summary slice, 800-character turn slice, and response instructions.
- `EXISTING:` responses still clamp out-of-range indexes to the last theme.
- `NEW:` responses still strip surrounding quotes and default to `General discussion` when empty.
- Theme summary prompts keep the same update-vs-new wording and truncation.

Boundary chosen:
- Theme prompt construction and response parsing are deterministic text policy.
- Extracting them leaves `ConversationManager` focused on persistence, model invocation, fallback logging, and Chroma updates.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/conversation_themes.py memory/v1/conversation_manager.py tests/test_conversation_themes.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_conversation_themes.py tests/test_conversation_text.py -q` passed (`15 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1103 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep thematic Chroma fetch/update and raw fallback storage in `ConversationManager` until fake collection tests cover compound-query fallback, theme ordering, and add/update metadata.

## 2026-07-02 - Short-Term Summary Planning Helper

Goal/scope:
- Move short-term memory summary planning into `conversation_text.build_short_term_summary_plan()`.
- Keep the utility LLM call, failure fallback, summary normalization, Chroma writes, and ledger behavior in `ConversationManager`.

Files/modules changed:
- `memory/v1/conversation_text.py`
- `memory/v1/conversation_manager.py`
- `tests/test_conversation_text.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Empty turns still return an empty `concise_turn_memory_v1` summary.
- Short non-code turns still use the rule-based `rule_based_turn_memory_v1` path.
- Assistant code-edit turns still use the code-change prompt and bullet-preserving normalization.
- Long non-code turns still use the concise-turn prompt and collapse whitespace.
- LLM failures still fall back to the cleaned original content capped at 280 characters.

Boundary chosen:
- Summary style selection and prompt construction are deterministic text policy.
- Extracting that policy keeps `ConversationManager._summarize_for_short_term()` focused on model invocation, fallback, and return compatibility.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/conversation_text.py memory/v1/conversation_manager.py tests/test_conversation_text.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_conversation_text.py tests/test_context_compaction.py tests/test_conversation_windows.py tests/test_conversation_themes.py -q` passed (`20 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1099 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep short-term Chroma writeback and thematic memory updates in `ConversationManager` until tests can fake collections, ledger rows, and utility-model outputs together.

## 2026-07-02 - Retrieved Memory Fact Filters

Goal/scope:
- Move Chroma result row filtering and formatted fact-line construction into `retrieved_memory_facts.py`.
- Keep query planning, embedding, Chroma collection access, parallel futures, recency boost I/O, cache writes, and section assembly in `memory_retrieval.py`.

Files/modules changed:
- `memory/v1/retrieved_memory_facts.py`
- `memory/v1/memory_retrieval.py`
- `tests/test_retrieved_memory_facts.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Distance checks still fail open for missing or non-numeric distances.
- User-memory tier splitting, prompt-queue suppression, file-index suppression, DS3000 anchor de-dupe, low-signal filters, and expiry checks keep the same rules.
- Jane long-term, file-index, essence, and semantic short-term facts keep the same formatted memory line policy.
- `memory_retrieval.py` still exposes the existing private helper aliases used by side scripts and tests.

Boundary chosen:
- Retrieved rows are deterministic data once Chroma returns `docs`, `metas`, and `distances`.
- Extracting the row filters makes `build_memory_sections()` easier to read while leaving vector DB access and best-effort recency boost behavior in place.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/retrieved_memory_facts.py memory/v1/memory_retrieval.py tests/test_retrieved_memory_facts.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_retrieved_memory_facts.py tests/test_memory_sections.py tests/test_nearest_memory.py tests/test_nearest_query_specs.py -q` passed (`18 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1096 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep the recency boost and Chroma/futures orchestration in `memory_retrieval.py` until a fake collection fixture covers best-effort database failures and recent-entry de-dupe.

## 2026-07-02 - Stage 2 Dispatcher Prompt Builders

Goal/scope:
- Move Stage 2 continuation/gate LLM prompt construction and class descriptions into `stage2_dispatcher_prompts.py`.
- Keep HTTP calls, handler dispatch, self-correction, gate skip logic, and routing in `stage2_dispatcher.py`.

Files/modules changed:
- `jane_web/jane_v2/stage2_dispatcher_prompts.py`
- `jane_web/jane_v2/stage2_dispatcher.py`
- `tests/test_stage2_dispatcher_prompts.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Class descriptions are unchanged.
- Continuation checks still prefer literal pending questions and fall back to class descriptions.
- Gate prompts keep the same examples and one-word YES/NO instruction.
- Unknown classes still fail open with no gate prompt.

Boundary chosen:
- Dispatcher gate prompts are deterministic text policy.
- Extracting them leaves Stage 2 dispatch focused on async LLM calls, handler invocation, and routing decisions.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/stage2_dispatcher_prompts.py jane_web/jane_v2/stage2_dispatcher.py tests/test_stage2_dispatcher_prompts.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_stage2_dispatcher_prompts.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1092 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep dispatch routing order and self-correction side effects in `stage2_dispatcher.py` until fake handler/LLM fixtures cover gate rejection, follow-up abandon, sync/async handlers, and `wrong_class`.

## 2026-07-02 - Pending Action Phrase Policy Helpers

Goal/scope:
- Move pending-action confirm/cancel/edit phrase policy, topic-pivot detection, high-precision interrupt detection, and reply normalization into `pending_action_phrases.py`.
- Keep pending state lookup, expiry handling, FIFO turn IDs, and routing result construction in `pending_action_resolver.py`.

Files/modules changed:
- `jane_web/jane_v2/pending_action_phrases.py`
- `jane_web/jane_v2/pending_action_resolver.py`
- `tests/test_pending_action_phrases.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Confirm, cancel, edit, strong Stage 3 cancel, topic pivot, and high-precision interrupt phrase sets are unchanged.
- Reply normalization still lowercases, strips, and removes trailing punctuation/whitespace.
- Soft cancels like `no` still do not cancel `STAGE3_FOLLOWUP` / `SEND_MESSAGE_DRAFT_OPEN`.
- `pending_action_resolver` still exposes `_normalize`, `_is_confirm`, `_is_cancel`, `_is_edit_intent`, `_is_topic_pivot`, `_is_high_precision_interrupt`, and `_STAGE3_CANCEL_STRONG` for existing callers.

Boundary chosen:
- Phrase classification is deterministic text policy shared by the resolver and send-message safety net.
- Extracting it makes resolver routing easier to read while preserving all pending-state side effects in the resolver.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/pending_action_phrases.py jane_web/jane_v2/pending_action_resolver.py tests/test_pending_action_phrases.py tests/test_pending_action_expiry.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_pending_action_phrases.py tests/test_pending_action_expiry.py tests/test_send_message_parsing.py tests/test_pending_sms.py -q` passed (`21 passed`, 2 existing `datetime.utcnow()` warnings).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1088 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep the resolver's main `resolve()` routing order intact until fake FIFO state tests cover each pending type and pivot/cancel branch.

## 2026-07-02 - Stage 3 Body Injection Helpers

Goal/scope:
- Move Stage 3 body message copy, voice hint wrapping, extracted-param injection, and class-protocol injection into `stage3_body_injections.py`.
- Keep structured FIFO-state injection, NDJSON streaming, v1 stream delegation, auth/session lookup, and tool marker handling in `stage3_escalate.py`.

Files/modules changed:
- `jane_web/jane_v2/stage3_body_injections.py`
- `jane_web/jane_v2/stage3_escalate.py`
- `tests/test_stage3_escalate_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `model_copy()` remains preferred over `copy()` when replacing body messages.
- Voice requests still prepend the same short spoken-response hint.
- Extracted params still filter `None`, empty strings, empty dicts, and empty lists before rendering.
- Class protocol blocks keep the same XML-ish wrapper and priority wording.
- `stage3_escalate` still exposes the old private helper names as aliases.

Boundary chosen:
- Body-message injections are deterministic transformations before the stream begins.
- Extracting them leaves `stage3_escalate.py` focused on runtime state injection, v1 streaming, event filtering, and error handling.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/stage3_body_injections.py jane_web/jane_v2/stage3_escalate.py tests/test_stage3_escalate_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_stage3_escalate_helpers.py tests/test_stage3_protocols.py tests/test_stage3_injections.py -q` passed (`16 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1085 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Stage 3 stream event filtering and error handling should stay in `stage3_escalate.py` until fake v1 stream fixtures cover ack suppression, tool marker extraction, and crash events.

## 2026-07-02 - Local Vector Memory Tier Helpers

Goal/scope:
- Move local vector memory result expiry, fact formatting, tier bucketing, section rendering, and librarian prompt text into `local_vector_memory_helpers.py`.
- Keep Chroma collection access, embedding/query behavior, Ollama synthesis, and ADK `MemoryEntry` construction in `local_vector_memory.py`.

Files/modules changed:
- `memory/v1/local_vector_memory_helpers.py`
- `memory/v1/local_vector_memory.py`
- `tests/test_local_vector_memory_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Forgettable memory expiry still uses lexicographic ISO timestamp comparison.
- Memory facts still render timestamp, topic, optional expiry date, and document text in the same shape.
- Permanent, long-term, and recent/forgettable section headings are unchanged.
- The librarian system instruction and user prompt keep the same rules and query/facts format.

Boundary chosen:
- Tier bucketing and librarian prompt construction are deterministic transformations of Chroma result payloads.
- Extracting them makes memory result policy testable without loading ChromaDB, embedding models, Ollama, or ADK memory objects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/local_vector_memory_helpers.py memory/v1/local_vector_memory.py tests/test_local_vector_memory_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_local_vector_memory_helpers.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1084 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep Chroma query execution and Ollama synthesis in the service until fake collection and fake librarian tests cover error and empty-result paths.

## 2026-07-02 - Task Offloader Announcement Message Helpers

Goal/scope:
- Move background task offloader announcement text, truncation, retry text, final-result fallback, and automation-error categorization into `task_offloader_messages.py`.
- Keep thread spawning, heartbeat timing, context building, automation execution, retries, and JSONL writes in `task_offloader.py`.

Files/modules changed:
- `jane_web/task_offloader_messages.py`
- `jane_web/task_offloader.py`
- `tests/test_task_offloader_messages.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Start, heartbeat, retry, final empty-result, automation-error, and unexpected-error user-facing messages are unchanged.
- Heartbeats still use only the last 300 characters of progress output and emit nothing when no output exists.
- Automation error precedence remains timed-out, empty-response, not-found, exit-code, then generic failure.
- `task_offloader._truncate` remains available as an alias to the extracted truncation helper.

Boundary chosen:
- Announcement text and error categorization are deterministic presentation rules.
- Extracting them reduces the background runner to orchestration and side effects while giving the user-visible status policy direct tests.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/task_offloader_messages.py jane_web/task_offloader.py tests/test_task_offloader_messages.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_task_offloader_messages.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1080 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Session-history loading and context construction should stay in the offloader until fake session/context fixtures cover pronoun-resolution behavior.

## 2026-07-02 - Identity Essay Prompt Helpers

Goal/scope:
- Move identity-essay memory truncation and user/Jane/Amber prompt construction out of `generate_identity_essay.update_essay()`.
- Keep Chroma memory loading, essay file reads/writes, Gemini calls, and console output in the generator script.

Files/modules changed:
- `agent_skills/identity_essay_prompts.py`
- `agent_skills/generate_identity_essay.py`
- `tests/test_identity_essay_prompts.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Memory documents are still joined with newlines and capped at 150,000 characters.
- Missing user essays still use `(No existing essay yet.)`.
- Missing Jane/Amber essays still use the existing first-self-reflection placeholder.
- Jane and Amber prompt role descriptions and first-person instructions remain distinct.

Boundary chosen:
- Prompt construction is deterministic text assembly and does not need Chroma, vault files, or Gemini credentials.
- Extracting it makes the generator's orchestration steps easier to scan while giving prompt policy focused tests.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/identity_essay_prompts.py agent_skills/generate_identity_essay.py tests/test_identity_essay_prompts.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_identity_essay_prompts.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1075 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- File read/write repetition could move into a small essay-store helper, but only if paired with temp-directory tests and without changing vault paths.

## 2026-07-02 - Reverse Proxy Header Protocol Helpers

Goal/scope:
- Extract reverse-proxy header filtering, forwarded-header construction, websocket upgrade detection, and streaming-response detection from `proxy_handler()`.
- Keep rate limiting, upstream session use, request/response streaming, websocket proxying, and error handling unchanged.

Files/modules changed:
- `jane_web/reverse_proxy.py`
- `tests/test_reverse_proxy_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Hop-by-hop headers are still filtered case-insensitively.
- `X-Forwarded-For` and `X-Forwarded-Proto` are still overwritten with the detected client IP and request scheme.
- Websocket detection still matches `Upgrade: websocket` or exactly `Connection: upgrade`.
- Streaming detection still matches chunked transfer encoding or `text/event-stream` content types.

Boundary chosen:
- Header/protocol classification is deterministic request metadata logic and can be tested without sockets or an upstream app.
- Extracting it shortens the async proxy body while avoiding changes to live proxy I/O behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/reverse_proxy.py tests/test_reverse_proxy_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_reverse_proxy_helpers.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1072 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Consider an integration-style proxy handler test only with a fake upstream/session fixture; avoid changing websocket forwarding or drain counters without async coverage.

## 2026-07-02 - Server Email Result Formatting Helpers

Goal/scope:
- Move server-side email client-tool visible result formatting and send-argument normalization into `jane_web.email_tool_results`.
- Keep `server_email_tools.execute_email_tool_serverside()` responsible for adapter dispatch, Gmail side effects, and logging.

Files/modules changed:
- `jane_web/email_tool_results.py`
- `jane_web/server_email_tools.py`
- `tests/test_server_email_tools.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Inbox, read, search, send, delete, credential-error, generic-error, and unknown-tool visible strings are unchanged.
- Send validation still rejects missing recipients before empty bodies.
- `from_email`, `from`, and `sender` aliases still resolve in the same order.
- Successful send logging still records the resulting message ID, sender, and recipient.

Boundary chosen:
- Email result rendering is deterministic formatting over Gmail adapter payloads and tool args.
- Extracting it keeps the server dispatcher focused on dynamic imports and side effects while making future visible-string edits easier to audit.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/email_tool_results.py jane_web/server_email_tools.py tests/test_server_email_tools.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_server_email_tools.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1068 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep live Gmail API behavior in `agent_skills.email_tools`; deeper server adapter abstractions only pay off if more client-tool email operations are added.

## 2026-07-02 - Proxy Acknowledgement Rule Table

Goal/scope:
- Convert `jane_web.proxy_ack.pick_ack()` from a long ordered branch chain into explicit acknowledgement rule data plus a small matcher.
- Keep the public `pick_ack()` API and deterministic chooser hook unchanged.

Files/modules changed:
- `jane_web/proxy_ack.py`
- `tests/test_proxy_ack.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Question-prefix matching still has priority over status/opinion/explanation keywords.
- Each category keeps the same first acknowledgement string and option ordering.
- Matching still lowercases and strips the user message before evaluating rules.
- Uncategorized messages still return `None`.

Boundary chosen:
- Acknowledgement selection is a pure rule table over normalized prompt text.
- Extracting the matcher from the category data makes future category audits less error-prone without touching proxy orchestration.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/proxy_ack.py tests/test_proxy_ack.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_proxy_ack.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1067 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Keep proxy acknowledgement text changes separate from refactoring; the extracted table makes copy edits straightforward but no product text was changed in this slice.

## 2026-07-02 - Ambient Heartbeat Discord Summary Helper

Goal/scope:
- Move ambient heartbeat Discord summary formatting into `ambient_heartbeat_rules.heartbeat_discord_summary()`.
- Keep idle gating, cache checks, web search, automation synthesis, spec writes, implementation calls, and Discord sending in `ambient_heartbeat.py`.

Files/modules changed:
- `agent_skills/ambient_heartbeat_rules.py`
- `agent_skills/ambient_heartbeat.py`
- `tests/test_ambient_heartbeat_rules.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Summary heading still includes the generated timestamp label.
- Researched topic names still replace underscores with spaces.
- Implemented task lines are still emitted exactly as stored by the caller.
- The footer still points at `ambient_app.md`.

Boundary chosen:
- Heartbeat notification text is pure presentation over researched topic IDs and completed task labels.
- Extracting it keeps the main heartbeat loop focused on scheduling, research, spec mutation, implementation, and delivery.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ambient_heartbeat_rules.py agent_skills/ambient_heartbeat.py tests/test_ambient_heartbeat_rules.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ambient_heartbeat_rules.py tests/test_ambient_task_research_rules.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1067 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `ambient_heartbeat.main()` still mixes idle checks, stale-cache research, spec mutation, implementation calls, and notification delivery; split only with fake cache/spec/search/automation tests.

## 2026-07-02 - Ambient Task Research Discord Summary Helper

Goal/scope:
- Move ambient task research Discord summary formatting into `ambient_task_research_rules.task_research_discord_summary()`.
- Keep idle checks, task extraction, cache writes, web search, OpenAI synthesis, and Discord sending in `ambient_task_research.py`.

Files/modules changed:
- `agent_skills/ambient_task_research_rules.py`
- `agent_skills/ambient_task_research.py`
- `tests/test_ambient_task_research_rules.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Summary heading still includes the generated timestamp label.
- The researched/total task count line is unchanged.
- Each researched task still shows phase, task text, and a teaser from the first three note lines.
- Note teasers are still capped at 200 characters.
- The footer still points at the research cache path.

Boundary chosen:
- Discord summary formatting is pure presentation over researched task records.
- Extracting it keeps the main loop focused on scheduling, research, cache mutation, and notification delivery.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ambient_task_research_rules.py agent_skills/ambient_task_research.py tests/test_ambient_task_research_rules.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ambient_task_research_rules.py tests/test_ambient_heartbeat_rules.py -q` passed (`13 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1066 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `ambient_task_research.main()` still mixes idle gating, cache mutation, web search, synthesis, and delivery; split only with fake search/synthesis/cache tests.

## 2026-07-02 - Marketplace Title Filter Rule Helper

Goal/scope:
- Move Facebook Marketplace clean-title/bad-title policy from the Playwright harvester loop into `listing_rules.title_filter_result()`.
- Keep browser navigation, detail extraction, photo downloads, listing JSON writes, and logging in `harvester.py`.

Files/modules changed:
- `agent_skills/marketplace/listing_rules.py`
- `agent_skills/marketplace/harvester.py`
- `tests/test_marketplace_listing_rules.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `require_clean_title=True` still requires `clean title` and rejects bad title phrases.
- `require_clean_title=False` still allows listings without clean-title text but rejects bad title phrases.
- Bad title phrases still include salvage, rebuilt, reconstructed, branded, lemon, and rebuilt/salvage variants.
- Harvester log paths still distinguish failed clean-title checks from bad-title-only flags.

Boundary chosen:
- Title policy is pure text classification.
- Extracting it keeps listing filtering rules together and reduces inline policy inside the browser scraping loop.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/marketplace/listing_rules.py agent_skills/marketplace/harvester.py tests/test_marketplace_listing_rules.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_marketplace_listing_rules.py tests/test_marketplace_helpers.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1065 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `_run_query()` still mixes Playwright navigation, detail extraction, filtering, photo downloads, and JSON writes; split only with fake page/download fixtures for pass, miles-drop, suspicious, and title-drop cases.

## 2026-07-02 - Chat Error Audit Job Rendering Helpers

Goal/scope:
- Move Android chat-error stack-frame parsing, slug/filename generation, and audit-job markdown rendering into `chat_error_audit_helpers.py`.
- Keep job numbering, source-file lookup, directory creation, file writes, and logging in `chat_error_audit.py`.

Files/modules changed:
- `agent_skills/chat_error_audit_helpers.py`
- `agent_skills/chat_error_audit.py`
- `tests/test_chat_error_audit_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The first `com.vessences.android.*` stack frame is still selected.
- Job filenames still use `job_NNN_chat_error_<exception>.md`.
- Missing exception classes still fall back to `UnknownException`.
- Job markdown still truncates messages at 400 characters and stack traces at 1800 characters.
- The generated job keeps the same frontmatter, incident, scope, verification, and notes sections.

Boundary chosen:
- Stack parsing and job-spec rendering are deterministic transformations of the diagnostic payload.
- Extracting them gives `chat_error_audit` direct unit coverage without touching live queue numbering or filesystem behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/chat_error_audit_helpers.py agent_skills/chat_error_audit.py tests/test_chat_error_audit_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_chat_error_audit_helpers.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1064 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `create_audit_job()` still performs live queue-number discovery and writes files; add temp-directory tests before changing numbering or write behavior.

## 2026-07-02 - Pipeline Audit Report Markdown Helper

Goal/scope:
- Move pipeline audit markdown report assembly from `pipeline_audit_100.main()` into `pipeline_audit_helpers.build_pipeline_audit_report_markdown()`.
- Keep prompt loading, live pipeline calls, judge calls, optional exemplar handling, and report file writing in `pipeline_audit_100.py`.

Files/modules changed:
- `agent_skills/pipeline_audit_helpers.py`
- `agent_skills/pipeline_audit_100.py`
- `tests/test_pipeline_audit_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Report heading, audited prompt count, elapsed seconds, failure counts, and auto-fix count are unchanged.
- Stage and classification breakdowns still use `most_common()` ordering.
- Fixes-by-class still render only when non-empty.
- Classification failures are still capped at 30 and pipe-escaped.
- Response failures are still capped at 20, pipe-escaped, and response text is capped at 150 characters.

Boundary chosen:
- Report markdown assembly is pure formatting over counters and failure lists.
- Extracting it keeps the live audit loop focused on collecting evidence and leaves report formatting independently testable.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/pipeline_audit_helpers.py agent_skills/pipeline_audit_100.py tests/test_pipeline_audit_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_pipeline_audit_helpers.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1060 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `pipeline_audit_100.main()` still owns live HTTP pipeline execution and judge orchestration; split only with fake runner/judge tests so audit failure accounting stays observable.

## 2026-07-02 - National Grid Monthly Summary Row Helpers

Goal/scope:
- Move National Grid monthly row construction, current-bill row handling, inferred missing-PDF rows, missing-month rows, and total aggregation into small helpers inside `nationalgrid_bill_helpers.py`.
- Keep account resolution, prompt/year parsing, and the public `summarize_account()` shape unchanged.

Files/modules changed:
- `agent_skills/nationalgrid_bill_helpers.py`
- `tests/test_nationalgrid_bill_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Downloaded bill rows keep amount, amount text, path, file URL, cached flag, billing period, issue date, and SHA fields.
- Current downloaded bill rows still add `source: current_bill` and carry the first current row text when available.
- If a current row implies the next month after the latest discovered historical month, the summary still adds `amount_found_pdf_missing`.
- Target months without a row still render as `missing`.
- Totals are still computed from displayed `amount_text` values.

Boundary chosen:
- Monthly amount row construction is deterministic data shaping from extractor records.
- Extracting it makes the current-bill inference path explicit and directly testable while leaving `summarize_account()` responsible for assembling account-level metadata.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/nationalgrid_bill_helpers.py agent_skills/nationalgrid_bills.py tests/test_nationalgrid_bill_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nationalgrid_bill_helpers.py -q` passed (`9 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1059 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `nationalgrid_bills.fetch_bills()` still mixes Playwright navigation, download retries, account state, and summary assembly; split only with fake page/download fixtures for login, cached bill, and current-bill paths.

## 2026-07-02 - Homework Audit Report Part Helpers

Goal/scope:
- Move homework audit markdown counting, per-question row formatting, flagged finding selection, and flagged-question block formatting into `edu_homework_report_parts.py`.
- Keep the public `build_homework_audit_markdown()` report shape and section ordering in `edu_homework_report.py`.

Files/modules changed:
- `agent_skills/edu_homework_report_parts.py`
- `agent_skills/edu_homework_report.py`
- `tests/test_edu_homework_report.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Full-grade score lines still show score plus correct/total counts.
- Issue totals and high-severity counts are unchanged.
- Correct answers still render as `OK`; incorrect answers still render as `**WRONG**`.
- Empty issue cells still render as `—`; issue counts with any high-severity issue remain bold.
- Flagged-question blocks keep prompt, solution, submitted answer, verdict, feedback, error, and issue formatting unchanged.

Boundary chosen:
- Report-part formatting is pure transformation from finding dictionaries to markdown lines.
- Extracting it makes table and flagged-question formatting testable independently while leaving the public report builder as the composition layer.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/edu_homework_report_parts.py agent_skills/edu_homework_report.py tests/test_edu_homework_report.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_edu_homework_report.py tests/test_edu_homework_llm_review.py tests/test_edu_homework_parsers.py tests/test_edu_homework_answers.py tests/test_edu_homework_lint.py -q` passed (`19 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1057 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `build_homework_audit_markdown()` is now mostly composition; avoid further splitting until a snapshot-style test covers the complete markdown document for multiple modes.

## 2026-07-02 - RA Report Channel Normalizer

Goal/scope:
- Move RA report-channel alias/default handling into `ra_research_delivery.normalize_report_channel()`.
- Use the shared normalizer in both report dispatch and final `run_once()` result/state shaping.

Files/modules changed:
- `agent_skills/ra_research_delivery.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_delivery.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `email` and `gmail` still route to email delivery.
- `none`, `off`, and `disabled` still suppress delivery.
- Blank, missing, and unknown channels still default to app delivery.
- `last_report_channel`, `email_sent`, and `report_channel` still use canonical values: `email`, `disabled`, or `app`.

Boundary chosen:
- Channel normalization is pure string policy.
- Extracting it removes duplicated conditionals from the cron orchestration while leaving send/email/app side effects unchanged.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_delivery.py agent_skills/ra_research_cron.py tests/test_ra_research_delivery.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_delivery.py tests/test_ra_reports.py tests/test_ra_research_codex_outputs.py tests/test_ra_research_report_markdown.py -q` passed (`23 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1055 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `run_once()` still owns a large state mutation/result payload block; split only with fake I/O tests that cover report paths, Codex/no-Codex branches, and notification-channel combinations.

## 2026-07-02 - Context Builder Recent History Formatter

Goal/scope:
- Move recent conversation transcript formatting from `context_builder.py` into `recent_history.py`.
- Keep sync/async context assembly, memory retrieval, research offload, platform handling, and system-section assembly unchanged.

Files/modules changed:
- `context_builder/v1/recent_history.py`
- `context_builder/v1/context_builder.py`
- `tests/test_recent_history.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Only the last `max_turns` history entries are considered.
- Assistant turns are labeled `Jane`; all other roles are labeled `User`.
- Whitespace is collapsed before formatting.
- Empty content is skipped.
- Long lines are truncated with `...` using the existing remaining-character logic.
- `context_builder._format_recent_history` remains available as an imported alias.

Boundary chosen:
- Recent-history formatting is pure transcript shaping.
- Extracting it lets both sync and async builders share tested formatting without carrying that detail in the main context builder.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile context_builder/v1/recent_history.py context_builder/v1/context_builder.py tests/test_recent_history.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_recent_history.py tests/test_prompt_profiles.py tests/test_user_background.py tests/test_system_prompt_sections.py tests/test_saved_articles_context.py tests/test_essence_context.py -q` passed (`25 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1054 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `build_jane_context()` and `build_jane_context_async()` still duplicate several context assembly steps; split only after adding coverage for memory override, anaphora skip, TTS, managed-user, and platform branches.

## 2026-07-02 - Janitor Log Retention Policy Helper

Goal/scope:
- Move janitor log-retention filename and age decisions into `janitor_log_retention.py`.
- Keep directory walking, mtime reads, file deletion, logging, and report-directory discovery in `janitor_memory.py`.

Files/modules changed:
- `memory/v1/janitor_log_retention.py`
- `memory/v1/janitor_memory.py`
- `tests/test_janitor_log_retention.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Ordinary `.log` and `.jsonl` files still use the 21-day default retention.
- Protected audit/history logs still use 90-day retention.
- Non-log extensions are still ignored by log purging.
- Self-improvement archive reports still match `self_improvement_*.md` and use 14-day retention.
- Missing log/report directories still return zero deletions.

Boundary chosen:
- Retention eligibility is pure filename and timestamp policy.
- Extracting it makes deletion decisions testable without creating or deleting files.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/janitor_log_retention.py memory/v1/janitor_memory.py tests/test_janitor_log_retention.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_janitor_log_retention.py tests/test_janitor_query_markers.py tests/test_janitor_rules.py tests/test_janitor_normalization.py tests/test_janitor_duplicates.py -q` passed (`17 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1051 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `purge_old_log_files()` and `purge_old_self_improve_reports()` still perform live filesystem deletion; add temp-directory integration tests before changing traversal or delete behavior.

## 2026-07-02 - Janitor Dynamic Query Marker Helpers

Goal/scope:
- Move dynamic query marker label extraction and personal/project/file classification from `janitor_memory.refresh_dynamic_query_markers()` into `janitor_query_markers.py`.
- Keep ChromaDB collection reads, warning logs, timestamp generation, JSON writes, and janitor orchestration in `janitor_memory.py`.

Files/modules changed:
- `memory/v1/janitor_query_markers.py`
- `memory/v1/janitor_memory.py`
- `tests/test_janitor_query_markers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Topic and subtopic metadata are still lower-cased and stripped.
- `general`, `unknown`, and empty labels are still ignored.
- User-memory labels in the personal allowlist still become `personal_markers`.
- Other user-memory labels plus long-term and short-term labels still become `project_markers`.
- File-index labels still become sorted `file_markers`.

Boundary chosen:
- Marker payload shaping is pure set manipulation over metadata labels.
- Extracting it makes the intent-classification marker policy testable without ChromaDB clients or filesystem writes.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/janitor_query_markers.py memory/v1/janitor_memory.py tests/test_janitor_query_markers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_janitor_query_markers.py tests/test_query_markers.py tests/test_query_intent.py tests/test_janitor_rules.py tests/test_janitor_normalization.py tests/test_janitor_duplicates.py -q` passed (`23 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1048 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `refresh_dynamic_query_markers()` still directly owns Chroma collection access and JSON writing; split only with fake Chroma client tests for collection-missing and partial-failure behavior.

## 2026-07-02 - Gmail Cleanup Outcome Counting Helper

Goal/scope:
- Move repeated Gmail cleanup outcome counting and exception-to-failure mapping into `gmail_cleanup_counts.py`.
- Keep Gmail queries, message reads, trash calls, alert sending, cleanup decisions, and monitor logging in `nutricost_deal_monitor.py`.

Files/modules changed:
- `agent_skills/gmail_cleanup_counts.py`
- `agent_skills/nutricost_deal_monitor.py`
- `tests/test_gmail_cleanup_counts.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Nutricost scan failures still count as `failed`.
- CrunchLabs failures still count as `crunchlabs_failed`.
- Sender cleanup failures still use each sender's cleanup prefix plus `_failed`.
- Google Calendar failures still count as `google_calendar_failed`.
- Unread cleanup dry runs still count all queried unread messages as `old_unread_would_trash`.
- Non-dry unread cleanup still directly trashes queried message IDs and counts `old_unread_trashed` or `old_unread_failed`.

Boundary chosen:
- Counting outcomes is deterministic and independent of Gmail service state.
- Extracting it removes repeated try/count loops while leaving all side effects in the monitor's existing processors.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/gmail_cleanup_counts.py agent_skills/nutricost_deal_monitor.py tests/test_gmail_cleanup_counts.py tests/test_gmail_cleanup_monitor.py tests/test_nutricost_deal_utils.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_gmail_cleanup_counts.py tests/test_gmail_cleanup_monitor.py tests/test_nutricost_deal_utils.py tests/test_gmail_cleanup_queries.py -q` passed (`25 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1046 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `nutricost_deal_monitor.main()` still owns scan ordering and state persistence; split only if adding an integration test around a fake service and fake state file.

## 2026-07-02 - RA Research Evidence Table Rows

Goal/scope:
- Move deterministic evidence-table row construction from `ra_research_report_markdown.py` into `ra_research_report_tables.py`.
- Keep report section ordering, prose, source ranking, summary selection, and public markdown builders unchanged.

Files/modules changed:
- `agent_skills/ra_research_report_tables.py`
- `agent_skills/ra_research_report_markdown.py`
- `tests/test_ra_research_report_markdown.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Action-plan evidence rows still include at most 40 summaries.
- Recommendation-scheme evidence rows still include at most 30 summaries.
- Empty evidence tables still use `| No sources processed yet | | | |`.
- Action-plan source titles still truncate the title portion to 90 characters without counting the source ID prefix.
- Existing pipe-escaping behavior is preserved, including the recommendation-scheme scope cell remaining unescaped.

Boundary chosen:
- Evidence rows are pure markdown table formatting from summary dictionaries.
- Extracting them reduces duplication in long report builders while keeping higher-level report assembly in the existing module.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_report_tables.py agent_skills/ra_research_report_markdown.py tests/test_ra_research_report_markdown.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_report_markdown.py -q` passed (`8 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1044 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `build_useful_report_markdown()` still has a long section-assembly flow; split only with snapshot-style tests for high-signal, low-signal, no-signal, and Codex-discovery branches.

## 2026-07-02 - Homework LLM Review Batch Helper

Goal/scope:
- Move the batched LLM conceptual-review loop from `edu_homework_audit.llm_conceptual_review()` into `edu_homework_llm_review.run_batched_llm_review()`.
- Keep real LLM availability checks, imports, audit orchestration, database state, and Classroom/Docs side effects in `edu_homework_audit.py`.

Files/modules changed:
- `agent_skills/edu_homework_llm_review.py`
- `agent_skills/edu_homework_audit.py`
- `tests/test_edu_homework_llm_review.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Invalid `batch_size` still raises `ValueError`.
- Findings are still reviewed in batches with prompts from `build_llm_review_prompt()`.
- Model tier and timeout are still passed through to the completion function.
- LLM responses are still normalized and merged across batches.
- All-failed batches still raise `RuntimeError`.
- Partial batch failures still surface as a low-severity `llm_partial_failure` issue.

Boundary chosen:
- Batch orchestration is deterministic aside from the injected completion function.
- Extracting it makes batching, merge, and failure behavior testable without importing the live Claude client or running the full homework audit flow.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/edu_homework_llm_review.py agent_skills/edu_homework_audit.py tests/test_edu_homework_llm_review.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_edu_homework_llm_review.py tests/test_edu_homework_report.py tests/test_edu_homework_parsers.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1042 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `run_audit()` still mixes DB attempt lifecycle, HTTP client operations, grading, and report shaping; split only after fake DB/client tests cover start/reuse/cleanup/full-grade paths.

## 2026-07-02 - Essence Builder Manifest Assembly Helper

Goal/scope:
- Move essence manifest assembly from `essence_builder.generate_manifest()` into `essence_builder_manifest.py`.
- Keep interview state management, state persistence, spec/personality generation, folder creation, template copying, and file writes in `essence_builder.py`.

Files/modules changed:
- `agent_skills/essence_builder_manifest.py`
- `agent_skills/essence_builder.py`
- `tests/test_essence_builder_parsing.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `generate_manifest(state)` remains the public wrapper and returns the same manifest shape.
- Role title, shared skills, UI type, permissions, capabilities, preferred model, credentials, starters, and proactive triggers still use the existing parsing helpers.
- Description is still capped at 200 characters and model reasoning at 300 characters.
- Legacy private parser aliases remain available from `essence_builder.py`.

Boundary chosen:
- Manifest assembly is deterministic transformation of `essence_name` plus interview answers.
- Extracting it makes defaulting and truncation behavior testable without constructing or mutating interview state.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/essence_builder_manifest.py agent_skills/essence_builder.py tests/test_essence_builder_parsing.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_essence_builder_parsing.py tests/test_essence_builder_outputs.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1040 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `build_essence_from_spec()` still calls `generate_manifest()` twice and mixes filesystem writes with payload generation; split only after adding temp-directory integration tests for template/no-template builds.

## 2026-07-02 - Google Cloud Receipt Candidate Builders

Goal/scope:
- Move Google Cloud transaction/document row parsing into pure candidate-builder helpers in `google_cloud_receipt_utils.py`.
- Keep Playwright page navigation, locators, frame handling, clicking, direct downloads, and manifest writes in `google_cloud_receipts.py`.

Files/modules changed:
- `agent_skills/google_cloud_receipt_utils.py`
- `agent_skills/google_cloud_receipts.py`
- `tests/test_google_cloud_receipts.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Transaction receipt controls still derive receipt date from row text or source name, parse amount from row text, keep hrefs for link controls, and preserve discovery order.
- Document rows still accept only statement/invoice/receipt rows with a Google Payments token.
- Document candidate source names still title-case the matched document kind, such as `Invoice`.
- Date-range filtering, sorting, destination naming, and actual browser downloads are unchanged.

Boundary chosen:
- Candidate construction is deterministic data shaping from account metadata, row text, href/token, and index.
- Extracting it makes parsing and rejection rules testable without Playwright or a live Google Cloud Billing session.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/google_cloud_receipt_utils.py agent_skills/google_cloud_receipts.py tests/test_google_cloud_receipts.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_google_cloud_receipts.py -q` passed (`12 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1039 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `_save_receipt_page()` still mixes direct cookie download, embedded PDF detection, download-button handling, and print-to-PDF fallback; split only after adding async fake-page/context tests for each fallback path.

## 2026-07-02 - Shared Queue Jane API Request Helper

Goal/scope:
- Move duplicated prompt/job queue Jane API request flow into `queue_jane_api.run_queue_chat_request()`.
- Preserve runner-owned progress announcements, work-log writes, connection-error handling, queue state mutation, and memory logging.

Files/modules changed:
- `agent_skills/queue_jane_api.py`
- `agent_skills/prompt_queue_runner.py`
- `agent_skills/job_queue_runner.py`
- `tests/test_queue_jane_api.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Queue requests still hit `/api/jane/chat/stream` first with `(10, None)` timeout and fall back to `/api/jane/chat` on HTTP 401 with `(10, 600)` timeout.
- Sync fallback still reads the `text` field and returns success based on `bool(text)`.
- HTTP fallback failures still return `Error: HTTP <status>` and announce `HTTP <status>`.
- Stream errors still return `Error: <error>` while empty stream completions remain unsuccessful without an error string.
- Work-log writes remain stream-only, matching the old early return on sync fallback.

Boundary chosen:
- Prompt and job queue runners duplicated the HTTP stream/sync fallback and stream parsing flow.
- Extracting the request helper makes queue API behavior testable with fake `post` responses while keeping runner-specific side effects outside the shared helper.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/queue_jane_api.py agent_skills/prompt_queue_runner.py agent_skills/job_queue_runner.py tests/test_queue_jane_api.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_queue_jane_api.py tests/test_queue_progress_announcements.py tests/test_prompt_queue_docs.py tests/test_job_queue_docs.py -q` passed (`29 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1037 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- Prompt and job runners still duplicate outer connection-error and final announcement handling; extract only after tests cover `requests.ConnectionError` and generic exception paths at the runner level.

## 2026-07-02 - Queue Progress Announcement Appender

Goal/scope:
- Move the queue-progress JSONL append operation into `queue_progress_announcements.py`.
- Update both prompt and job queue runners to use the shared append helper while preserving their existing failure-swallowing behavior.

Files/modules changed:
- `agent_skills/queue_progress_announcements.py`
- `agent_skills/prompt_queue_runner.py`
- `agent_skills/job_queue_runner.py`
- `tests/test_queue_progress_announcements.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Queue progress lines still use the same `json.dumps` formatting and receive one trailing newline per announcement.
- Prompt queue progress IDs still use the `queue_<timestamp>` shape.
- Job queue progress IDs still use the `job_<timestamp>` shape.
- Both runners still ignore announcement write failures so queue execution is not blocked by notification file problems.

Boundary chosen:
- Prompt and job queue runners duplicated the same JSONL construction and append logic.
- Extracting the append operation keeps API calls and runner control flow untouched while making the announcement file contract directly testable.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/queue_progress_announcements.py agent_skills/prompt_queue_runner.py agent_skills/job_queue_runner.py tests/test_queue_progress_announcements.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_queue_progress_announcements.py tests/test_queue_jane_api.py tests/test_prompt_queue_docs.py tests/test_job_queue_docs.py -q` passed (`25 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1033 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `run_prompt()` and `run_job()` still duplicate HTTP fallback and stream handling structure; split only after adding tests with fake `requests.post` responses for stream, sync fallback, HTTP error, and connection error paths.

## 2026-07-02 - Nightly TLDR Item Condenser

Goal/scope:
- Move the nested TL;DR bullet condensation logic from `nightly_self_improve._job_details()` into `nightly_report_summaries.py`.
- Keep job log reading, artifact selection, per-job report summarization, and readable-report file writes in `nightly_self_improve.py`.

Files/modules changed:
- `agent_skills/nightly_report_summaries.py`
- `agent_skills/nightly_self_improve.py`
- `tests/test_nightly_report_summaries.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- TL;DR items still strip leading Markdown bullets, collapse whitespace, skip configured placeholder prefixes, truncate at roughly 160 characters, and cap each list at three entries.
- Job status placeholder problems and "No concrete improvement" placeholders still stay out of the top compact summary.
- The nightly report renderer still receives the same `problems_tldr_list` and `fixes_tldr_list` fields.

Boundary chosen:
- TL;DR condensation is deterministic string normalization and filtering.
- Extracting it makes report-summary truncation and skip-prefix behavior testable without running nightly jobs or reading log/artifact files.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/nightly_report_summaries.py agent_skills/nightly_self_improve.py tests/test_nightly_report_summaries.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nightly_report_summaries.py tests/test_nightly_report_rendering.py tests/test_nightly_log_reader.py -q` passed (`21 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1032 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `_job_details()` still combines artifact presence checks, log-tail reading, and summary selection; split only after adding tests that provide fake artifacts/logs for each named nightly stage.

## 2026-07-02 - Read Calendar Follow-Up Response Builders

Goal/scope:
- Move read-calendar pending-action, event serialization, detail follow-up, another-day follow-up, event-choice, and day-choice response construction into `read_calendar/responses.py`.
- Keep Google Calendar fetching, Qwen summarization/detail phrasing, range resolution, event matching, and resume state transitions in `handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/read_calendar/responses.py`
- `jane_web/jane_v2/classes/read_calendar/handler.py`
- `tests/test_read_calendar_formatting.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Event-list answers still ask whether Chieh wants details and store only `id`, `summary`, `description`, `start`, `end`, and `html_link` in pending state.
- No-event answers and event-detail answers still transition to the `another_day_or_stop` follow-up.
- Multi-event yes replies still ask `Which one?` and preserve the event list in pending state.
- Another-day yes replies still ask `Which day?` with an `awaiting_day_choice` pending action.

Boundary chosen:
- Follow-up response construction was deterministic and independent of live calendar reads or local LLM calls.
- Extracting it makes the repeating-read contract testable while leaving external calendar and Qwen side effects in the handler.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/read_calendar/responses.py jane_web/jane_v2/classes/read_calendar/handler.py tests/test_read_calendar_formatting.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_read_calendar_formatting.py -q` passed (`8 passed`, 6 existing `datetime.utcnow()` warnings).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1031 passed`, 11 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `_handle_resume()` still owns several state branches; split only after handler-level async tests cover yes/no, explicit event match, range pivot, and day-choice escalation paths.

## 2026-07-02 - Timer Response Builders

Goal/scope:
- Move timer marker, spoken confirmation, pending follow-up, set/list/count/cancel/delete response construction into `timer/responses.py`.
- Keep action detection, duration parsing fallbacks, same-class restart detection, params handling, and follow-up state transitions in `handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/timer/responses.py`
- `jane_web/jane_v2/classes/timer/handler.py`
- `tests/test_timer_parsing.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Timer set responses still emit compact `timer.set` JSON markers and end the conversation.
- Labeled timer spoken text still handles already-terminal labels such as `ready`, `done`, and `up`.
- Duration and label follow-ups still create `STAGE2_FOLLOWUP` pending actions with the same awaiting/data/question shape.
- Count/list/cancel/delete responses still emit the same client-tool markers and structured entity payloads.

Boundary chosen:
- Timer response construction was deterministic and repeated across params-driven and legacy regex dispatch.
- Extracting it makes marker, spoken-text, and pending-action contracts testable without touching the handler's intent-detection state machine.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/timer/responses.py jane_web/jane_v2/classes/timer/handler.py tests/test_timer_parsing.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_timer_parsing.py -q` passed (`9 passed`, 3 existing `datetime.utcnow()` warnings).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1028 passed`, 5 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- The timer handler still mixes params-driven and legacy regex dispatch for action selection; split only after adding handler-level tests that cover equivalent params/legacy paths for set, delete, list, cancel, and count.

## 2026-07-02 - Send Message Response Builders

Goal/scope:
- Move send-message marker, direct-send response, confirmation prompt, revision prompt, and open-draft send/cancel response construction into `send_message/responses.py`.
- Keep LLM extraction, pending FIFO lookup, contact resolution, alias writes, confidence checks, and Stage 3 escalation decisions in `handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/send_message/responses.py`
- `jane_web/jane_v2/classes/send_message/handler.py`
- `tests/test_send_message_parsing.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Confirmed sends still end the conversation with `Done.` plus the `contacts.sms_send_direct` marker.
- Fast-path sends still answer `Done, message sent.` plus the direct-send marker.
- Garbled-message and revised-body paths still create `STAGE2_FOLLOWUP` pending actions with the same `send_confirmation` and `revised_body` data shapes.
- Open SMS draft confirm/cancel still emit `contacts.sms_send` / `contacts.sms_cancel` markers and resolve `SEND_MESSAGE_DRAFT_OPEN`.

Boundary chosen:
- Response construction was duplicated across resume, direct-send, and open-draft safety-net paths.
- Extracting pure builders makes marker and pending-action shapes testable without LLM calls, contact lookup, session state, or SQLite alias writes.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/send_message/responses.py jane_web/jane_v2/classes/send_message/handler.py tests/test_send_message_parsing.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_send_message_parsing.py -q` passed (`10 passed`, 2 existing `datetime.utcnow()` warnings).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_pending_sms.py tests/test_client_tool_sanitizer.py tests/test_stage2_response.py -q` passed (`15 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1024 passed`, 2 existing `datetime.utcnow()` warnings).

Remaining follow-up slices:
- `_check_open_draft()` still reads session/FIFO state and prompt intent in one function; split only after adding tests that can fake active session state without coupling to live recent-turn storage.

## 2026-07-02 - Clinic Schedule Patient Brief Helper

Goal/scope:
- Move repeated active-patient brief shaping into `clinic_schedules_info/schedule_helpers.py`.
- Keep SQLite reads, loader dispatch, patient-detail lookups, local LLM calls, and handler routing in `handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/clinic_schedules_info/schedule_helpers.py`
- `jane_web/jane_v2/classes/clinic_schedules_info/handler.py`
- `tests/test_clinic_schedule_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Active patient briefs still include only `index`, `name`, and `time`.
- Today overview, day facts, next-patient facts, and no-patient-detail fallback still expose the same brief shape.
- Full patient detail rows still keep health concerns, recommendations, and visit summary where needed.

Boundary chosen:
- Brief shaping was duplicated across fact builders and is deterministic.
- Extracting it prevents shape drift while keeping database and LLM side effects in the handler.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/clinic_schedules_info/schedule_helpers.py jane_web/jane_v2/classes/clinic_schedules_info/handler.py tests/test_clinic_schedule_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_clinic_schedule_helpers.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1021 passed`).

Remaining follow-up slices:
- `_facts_patient_detail()` still mixes name lookup, index lookup, and fallback roster shaping; split only after handler-level fixture tests cover those loader cases.

## 2026-07-02 - Todo Category Resolver Helper

Goal/scope:
- Move exact-name and alias-based Todo category lookup into `todo_list/categories.py`.
- Keep Google Docs edits, cache refreshes, pending-action construction, readback flow, and shopping-list delegation in the handler.

Files/modules changed:
- `jane_web/jane_v2/classes/todo_list/categories.py`
- `jane_web/jane_v2/classes/todo_list/handler.py`
- `tests/test_todo_list_categories.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Exact category names still match after the same normalization.
- Short aliases such as `clinic` and `urgent` still resolve through `CATEGORY_ALIASES`.
- Read-path parameter category matching still runs against visible categories only.
- Edit-path category matching can still resolve against the full category list.

Boundary chosen:
- Category lookup by exact name or alias was duplicated in the edit and read paths.
- Extracting it removes drift while preserving the handler as the side-effect owner for docs edits and follow-up routing.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/todo_list/categories.py jane_web/jane_v2/classes/todo_list/handler.py tests/test_todo_list_categories.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_todo_list_categories.py tests/test_todo_list_parsing.py -q` passed (`13 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1020 passed`).

Remaining follow-up slices:
- The Todo resume flow still mixes pending-action states with docs edit side effects; split only after adding handler-level async tests around each awaiting state.

## 2026-07-02 - Self-Healing Job Markdown Helper

Goal/scope:
- Move self-healing repair job Markdown construction out of `self_healing.py`.
- Keep incident capture, state locking, deduplication, incident JSON writes, job numbering, JSONL logging, and auto-repair subprocess launching in `self_healing.py`.

Files/modules changed:
- `agent_skills/self_healing_helpers.py`
- `agent_skills/self_healing.py`
- `tests/test_self_healing_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Job titles still use `Self-heal <source>: <incident title>`.
- Job metadata still includes pending/high status, created date, auto-generated flag, source, and incident path.
- Context lines still include source, category, project root, fingerprint, and request path.
- Steps and verification instructions keep the same wording and order.

Boundary chosen:
- Job Markdown is deterministic text derived from an incident and date.
- Extracting it makes the repair-job contract testable while leaving durable state and queue-file side effects in the self-healing module.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/self_healing_helpers.py agent_skills/self_healing.py tests/test_self_healing_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_self_healing_helpers.py tests/test_self_healing_reports.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1019 passed`).

Remaining follow-up slices:
- `_record_incident()` still mixes rate-limit state updates, file writes, and launch decisions; split only after tests characterize dedupe and cooldown behavior with temporary state files.

## 2026-07-02 - National Grid Account Summary Helper

Goal/scope:
- Move extractor-record to account-summary shaping out of `nationalgrid_bills.py`.
- Keep account resolution, extractor loading, secret resolution, Playwright execution, browser/cache/download directories, and CLI behavior in `nationalgrid_bills.py`.

Files/modules changed:
- `agent_skills/nationalgrid_bill_helpers.py`
- `agent_skills/nationalgrid_bills.py`
- `tests/test_nationalgrid_bill_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Downloaded bill rows still retain amount, amount text, path, file URL, cache flag, billing period, issue date, and hash fields.
- Current-bill downloads still add `source="current_bill"` and current row text when available.
- Current bill rows still infer the next month after latest history and produce `amount_found_pdf_missing` when the PDF is not available.
- Missing months, downloaded/missing/amount-found counts, record status/error, and totals keep the same shape.

Boundary chosen:
- Account summary construction is deterministic transformation of extractor records and target months.
- Extracting it makes bill summary edge cases testable without Playwright, credentials, or live National Grid data.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/nationalgrid_bill_helpers.py agent_skills/nationalgrid_bills.py tests/test_nationalgrid_bill_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nationalgrid_bill_helpers.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1018 passed`).

Remaining follow-up slices:
- `fetch_bills()` still assembles final metadata/status and combined totals inline; split that only after adding characterization tests for partial/missing status precedence.

## 2026-07-02 - Facebook Marketplace Candidate Helpers

Goal/scope:
- Move visible-row parsing and batch delete-candidate selection into `facebook_marketplace_rules.py`.
- Keep Playwright navigation, scrolling, delete UI interaction, audit-log appends, and CLI argument parsing in `facebook_marketplace_message_cleanup.py`.

Files/modules changed:
- `agent_skills/facebook_marketplace_rules.py`
- `agent_skills/facebook_marketplace_message_cleanup.py`
- `tests/test_facebook_marketplace_message_cleanup.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Conversation rows still clean label/text, strip `Group chat:`, parse href/title, and derive relative age from raw text.
- Scan audit records are still written for every classified conversation before max-delete limiting.
- Delete candidates still include only `Decision(action="delete")` entries, preserve scan order, and return none when `max_delete <= 0`.
- Playwright deletion fallbacks remain unchanged.

Boundary chosen:
- Row parsing and candidate selection are deterministic Marketplace policy rules and can be tested without browser automation.
- The cleanup script remains responsible for live Facebook UI side effects and audit file writes.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/facebook_marketplace_rules.py agent_skills/facebook_marketplace_message_cleanup.py tests/test_facebook_marketplace_message_cleanup.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_facebook_marketplace_message_cleanup.py -q` passed (`8 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1016 passed`).

Remaining follow-up slices:
- Audit record payload construction could be extracted next, but only if preserving timestamp placement and mode/status fields is characterized.

## 2026-07-02 - Audit Auto-Fix Prompt Helper

Goal/scope:
- Move the audit-auto-fixer LLM analysis prompt out of `audit_auto_fixer.py`.
- Keep report discovery, provider invocation, JSON parsing, backup creation, file modification, syntax verification, and report writing in the fixer.

Files/modules changed:
- `agent_skills/audit_auto_fix_prompt.py`
- `agent_skills/audit_auto_fixer.py`
- `tests/test_audit_auto_fix_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The prompt still requires exact absolute file paths under `VESSENCE_HOME`.
- The prompt still forbids crontab modifications and file deletions.
- The allowed categories and skip rules remain unchanged.
- Example paths still use the configured Vessence root, and the audit report text is inserted in the same section.

Boundary chosen:
- Prompt construction is a pure contract that should be testable without invoking the configured frontier provider.
- The fixer remains responsible for all side effects and safety checks.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/audit_auto_fix_prompt.py agent_skills/audit_auto_fixer.py tests/test_audit_auto_fix_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_audit_auto_fix_helpers.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1014 passed`).

Remaining follow-up slices:
- `apply_fix()` still mixes validation, backup, replacement, syntax verification, and rollback; split only after adding focused tests around every failure status.

## 2026-07-02 - Dead Code Report Renderer

Goal/scope:
- Move dead-code Markdown report construction out of `dead_code_auditor.py`.
- Keep tree scanning, grep checks, dynamic-import detection, auto-delete actions, file writes, and git commit attempts in the auditor.

Files/modules changed:
- `agent_skills/dead_code_report.py`
- `agent_skills/dead_code_auditor.py`
- `tests/test_dead_code_report.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Report headings, counts, relative path formatting, duplicate-group formatting, and clean-code message remain the same.
- Dead function output is still capped at 50 entries and duplicate groups at 20 entries.
- `write_report()` still writes to the same report path and logs the same relative-path message.

Boundary chosen:
- Report rendering is deterministic and only depends on the collected candidate lists plus timestamp.
- Extracting it keeps destructive filesystem behavior isolated in the auditor while making report shape directly testable.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/dead_code_report.py agent_skills/dead_code_auditor.py tests/test_dead_code_report.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_dead_code_report.py tests/test_dead_code_policy.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1013 passed`).

Remaining follow-up slices:
- Duplicate body normalization and dynamic-import prefix detection are possible future pure boundaries, but dynamic import detection should be characterized with temporary source trees before moving.

## 2026-07-02 - Transcript Review Source Loaders

Goal/scope:
- Move transcript prompt dump, Jane web log, and Android diagnostics source parsing out of `transcript_quality_review.py`.
- Keep runtime log directory selection, missing prompt-dump warning, review orchestration, Codex execution, and report writing in the runner.

Files/modules changed:
- `agent_skills/transcript_review_sources.py`
- `agent_skills/transcript_quality_review.py`
- `tests/test_transcript_review_sources.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing source files still return empty lists.
- Malformed JSONL rows in prompt dumps and Android diagnostics are still skipped.
- Prompt dump rows are still filtered through the same date/session/message formatter.
- Pipeline and Android event rows still use the same relevance filters and output line formatting.

Boundary chosen:
- Source parsing is deterministic file I/O with small filtering rules and does not need to live in the review orchestration module.
- Path-parameterized loaders make malformed-line and missing-file behavior directly testable without touching runtime logs.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/transcript_review_sources.py agent_skills/transcript_quality_review.py tests/test_transcript_review_sources.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_transcript_review_sources.py tests/test_transcript_review_vocal.py tests/test_transcript_review_prompts.py tests/test_transcript_review_format.py -q` passed (`18 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1010 passed`).

Remaining follow-up slices:
- `transcript_quality_review.py` is now mostly orchestration; further extraction should move only if provider invocation or report-writing behavior needs stronger seams.

## 2026-07-02 - Transcript Review Vocal Summary Helpers

Goal/scope:
- Move transcript-review vocal-summary payload construction out of `transcript_quality_review.py`.
- Keep importing and calling `agent_skills.self_improve_log.log_vocal_summary()` in the runner.

Files/modules changed:
- `agent_skills/transcript_review_vocal.py`
- `agent_skills/transcript_quality_review.py`
- `tests/test_transcript_review_vocal.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Empty reviews still log the same `summary` field with `severity="info"`.
- Non-empty reviews still count `CRITICAL`, `MEDIUM`, and `LOW` severities the same way.
- The spoken severity still prioritizes critical over medium over low.
- The most urgent issue still prefers the first critical issue, then the first medium issue, then the first issue.
- Existing odd fallback wording for unrecognized severities is preserved.

Boundary chosen:
- Vocal-summary payload construction is deterministic and testable without importing the logging side-effect module.
- The runner remains responsible for runtime import failure handling and the actual log write.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/transcript_review_vocal.py agent_skills/transcript_quality_review.py tests/test_transcript_review_vocal.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_transcript_review_vocal.py tests/test_transcript_review_prompts.py tests/test_transcript_review_format.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1006 passed`).

Remaining follow-up slices:
- `transcript_quality_review.py` still has three similar JSONL/log loading functions; a file-reader adapter could be extracted if the malformed-line and missing-file cases are characterized first.

## 2026-07-02 - Transcript Review Prompt Helpers

Goal/scope:
- Move Codex transcript-review and frontier-fix prompt templates out of `transcript_quality_review.py`.
- Keep log loading, subprocess/provider invocation, report writing, vocal summary logging, and CLI flow in the runner.

Files/modules changed:
- `agent_skills/transcript_review_prompts.py`
- `agent_skills/transcript_quality_review.py`
- `tests/test_transcript_review_prompts.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Codex review prompts keep the same transcript/log insertion point, JSON-only output contract, severity labels, and stage-review instructions.
- Frontier fix prompts keep the same report path/content insertion, code-lock instructions, no-restart rule, pipeline architecture guardrails, and exemplar specificity policy.
- `transcript_quality_review.py` still exposes `CODEX_PROMPT_TEMPLATE` and `CLAUDE_FIX_PROMPT_TEMPLATE` through imports for compatibility.

Boundary chosen:
- Prompt construction is a pure text contract and was obscuring the subprocess/provider execution paths.
- Extracting it allows direct tests for prompt policy without invoking Codex or the frontier provider.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/transcript_review_prompts.py agent_skills/transcript_quality_review.py tests/test_transcript_review_prompts.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_transcript_review_prompts.py tests/test_transcript_review_format.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`1002 passed`).

Remaining follow-up slices:
- `_log_vocal_summary_for_review()` still mixes severity summarization with the vocal-summary side effect; extract the pure summary payload next if continuing in this module.

## 2026-07-02 - Context Builder User Background Helpers

Goal/scope:
- Move personal-facts file loading, fact snippet formatting, and user-background selection out of `context_builder.py`.
- Keep runtime context assembly, memory retrieval, managed-user handling, research offload, and system prompt assembly in `context_builder.py`.

Files/modules changed:
- `context_builder/v1/user_background.py`
- `context_builder/v1/context_builder.py`
- `tests/test_user_background.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing, malformed, and non-dict personal facts still load as an empty dict.
- Always-on facts still render before topic-map facts.
- AI/coding, music, and teaching topic groups still use the same keyword triggers.
- Duplicate rendered snippets from topic-map facts are still suppressed.
- `context_builder.py` still re-exports `_load_personal_facts` and `_select_user_background` for `jane.context_builder` and `claude_smart_context`.

Boundary chosen:
- User-background selection is deterministic data shaping around a small JSON file and does not need to live inside the context assembly flow.
- Extracting it isolates personal-fact policy from memory/research/system-section side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile context_builder/v1/user_background.py context_builder/v1/context_builder.py tests/test_user_background.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_user_background.py tests/test_prompt_profiles.py tests/test_system_prompt_sections.py tests/test_essence_context.py tests/test_saved_articles_context.py -q` passed (`22 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`999 passed`).

Remaining follow-up slices:
- `_build_system_sections()` is now the main pure-ish boundary left in `context_builder.py`, but it calls cached essence/tool loaders and should be split only after those side-effect seams are characterized.

## 2026-07-02 - Context Builder Prompt Profile Helpers

Goal/scope:
- Move prompt profile dataclass, keyword groups, anaphora detection, conversation-summary gating, and prompt-profile classification out of `context_builder.py`.
- Keep context assembly, memory retrieval, research offload execution, file-context injection, and system prompt section assembly in `context_builder.py`.

Files/modules changed:
- `context_builder/v1/prompt_profiles.py`
- `context_builder/v1/context_builder.py`
- `tests/test_prompt_profiles.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Explicit intent levels still win before message-category classification.
- Tool/data/greeting/simple/file/project/factual/casual profiles keep the same names and include flags.
- Project-work profiles still use the same injected/default research decider behavior.
- `context_builder.py` still re-exports the private prompt-profile helper names used by existing tests and callers.

Boundary chosen:
- Prompt profile selection is deterministic policy logic and was a clear pure boundary inside the core context assembler.
- Extracting it reduces `context_builder.py` without changing the memory, research, saved-article, or system-section side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile context_builder/v1/prompt_profiles.py context_builder/v1/context_builder.py tests/test_prompt_profiles.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_prompt_profiles.py tests/test_system_prompt_sections.py tests/test_essence_context.py tests/test_saved_articles_context.py -q` passed (`18 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`995 passed`).

Remaining follow-up slices:
- `_select_user_background()` and `_build_system_sections()` remain in `context_builder.py`; user-background selection is the next pure candidate if tests characterize topic-map inclusion and duplicate suppression.

## 2026-07-02 - Gmail Cleanup Decision Helpers

Goal/scope:
- Move sender cleanup, Google Calendar cleanup, and old-unread cleanup classification rules out of `nutricost_deal_monitor.py`.
- Keep Gmail reads, trash mutations, logging, query construction, state handling, and cron orchestration in the monitor.

Files/modules changed:
- `agent_skills/gmail_cleanup_decisions.py`
- `agent_skills/nutricost_deal_monitor.py`
- `tests/test_gmail_cleanup_decisions.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Sender cleanup outcomes still use the same label-derived prefixes and `_skipped`, `_skipped_labels`, `_skipped_subject`, `_too_recent`, `_trashed`, and `_would_trash` suffixes.
- Google Calendar cleanup still returns the same skipped/no-date/future/trash outcomes.
- Old unread cleanup still requires the `UNREAD` label, preserves the age gate, and returns the same dry-run and live outcomes.
- Gmail trashing remains in the monitor and only runs when the decision says the message should be trashed.

Boundary chosen:
- Cleanup classification is deterministic and depends only on message metadata, configured fragments/labels, age, and the dry-run flag.
- Extracting it gives direct tests for the cron status contract without fake Gmail service objects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/gmail_cleanup_decisions.py agent_skills/nutricost_deal_monitor.py tests/test_gmail_cleanup_decisions.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_gmail_cleanup_decisions.py tests/test_gmail_cleanup_monitor.py tests/test_gmail_cleanup_queries.py tests/test_gmail_message_utils.py -q` passed (`22 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`994 passed`).

Remaining follow-up slices:
- `nutricost_deal_monitor.main()` still contains repeated scan/process/count loops for each cleanup family; extract the loop orchestration only if a small helper can preserve exception-to-outcome behavior exactly.

## 2026-07-02 - Nutricost Deal Alert Helpers

Goal/scope:
- Move Nutricost message text assembly, best-discount selection, and deal-alert subject/body formatting out of `nutricost_deal_monitor.py`.
- Keep Gmail reads, trashing, send-email side effects, state persistence, and cron orchestration in the monitor.

Files/modules changed:
- `agent_skills/nutricost_deal_utils.py`
- `agent_skills/nutricost_deal_monitor.py`
- `tests/test_nutricost_deal_utils.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Deal alert subjects remain `Nutricost <discount>% deal`.
- Alert bodies keep the same discount, original subject/date, Gmail message ID, link list, and no-link fallback text.
- Low-threshold marketing messages are still trashed, and qualifying dry-run messages still return `would_alert` without mutating state or trashing.
- Existing helper re-exports from `nutricost_deal_monitor.py` remain available.

Boundary chosen:
- Nutricost parsing and alert rendering are deterministic domain rules that can be tested without Gmail API calls.
- The monitor remains responsible for live Gmail service mutation and cron-level control flow.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/nutricost_deal_utils.py agent_skills/nutricost_deal_monitor.py tests/test_nutricost_deal_utils.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nutricost_deal_utils.py tests/test_gmail_cleanup_monitor.py -q` passed (`18 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`991 passed`).

Remaining follow-up slices:
- The generic cleanup decision branches in `process_sender_cleanup_message()`, `process_google_calendar_message()`, and `process_unread_cleanup_message()` are candidates for a separate pure decision-helper extraction.

## 2026-07-02 - EDU Homework LLM Review Helpers

Goal/scope:
- Move conceptual-review prompt construction and LLM review JSON normalization out of `edu_homework_audit.py`.
- Keep batching, model invocation, timeout handling, partial-failure notes, and full-failure errors in the audit driver.

Files/modules changed:
- `agent_skills/edu_homework_llm_review.py`
- `agent_skills/edu_homework_audit.py`
- `tests/test_edu_homework_llm_review.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Empty prompt text is still represented as `<EMPTY PROMPT>`.
- Prompt chunks still render question number, key, answer type with `default` fallback, and stripped prompt text.
- LLM issues still default severity to `low`, kind to `llm_review`, prefix kinds with `llm_`, and skip empty messages.
- Review entries without an `n` are still ignored.

Boundary chosen:
- The LLM review path had pure prompt/normalization rules mixed with model calls and failure handling.
- Extracting those rules makes the review contract testable without invoking the LLM.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/edu_homework_llm_review.py agent_skills/edu_homework_audit.py tests/test_edu_homework_llm_review.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_edu_homework_llm_review.py tests/test_edu_homework_parsers.py tests/test_edu_homework_answers.py tests/test_edu_homework_lint.py tests/test_edu_homework_report.py -q` passed (`15 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`987 passed`).

Remaining follow-up slices:
- The homework audit driver still mixes DB lookup, HTTP navigation, answer submission, and issue aggregation; further refactors should start with characterization around `run_audit()` before moving side effects.

## 2026-07-02 - Essence Builder Output Helpers

Goal/scope:
- Move generated essence custom-tool stub text, UI layout payload, onboarding payload, and custom-functions write gate out of `essence_builder.py`.
- Keep interview state flow, manifest/personality/spec generation, directory creation, file writes, and state clearing in `essence_builder.py`.

Files/modules changed:
- `agent_skills/essence_builder_outputs.py`
- `agent_skills/essence_builder.py`
- `tests/test_essence_builder_outputs.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Custom tool stubs keep the same triple-quoted text, essence name, source spec text, TODO line, and trailing newline.
- Custom tool files are still skipped for blank, `none`, `n/a`, and `no` answers.
- UI layout payloads still use one `main` component named `<ui_type>_panel` and truncate notes at 500 characters.
- Onboarding payloads still include conversation starters, empty steps, and 500-character notes.

Boundary chosen:
- Generated file payloads are deterministic and easy to test without creating essence folders.
- The builder remains responsible for filesystem side effects and interview-state lifecycle.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/essence_builder_outputs.py agent_skills/essence_builder.py tests/test_essence_builder_outputs.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_essence_builder_outputs.py tests/test_essence_builder_parsing.py tests/test_essence_validation.py -q` passed (`18 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`984 passed`).

Remaining follow-up slices:
- `generate_manifest()` still mixes several extraction calls and manifest assembly; extract a manifest-builder helper only if a full manifest characterization test is added.

## 2026-07-02 - Google Cloud Receipt Destination Helpers

Goal/scope:
- Move Google Cloud receipt destination collision handling and final download suffix selection out of `google_cloud_receipts.py`.
- Keep browser automation, direct cookie download, Playwright download handling, manifest writes, and CLI behavior in the downloader.

Files/modules changed:
- `agent_skills/google_cloud_receipt_utils.py`
- `agent_skills/google_cloud_receipts.py`
- `tests/test_google_cloud_receipts.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Existing destination filenames still receive `_2`, `_3`, etc. before the suffix.
- Suggested download filenames still override the destination suffix when they contain an extension.
- Suggested suffixes are still lowercased.
- The downloader still exposes `_unique_dest_path` and `_final_download_path` as compatibility aliases.

Boundary chosen:
- Destination filename selection is deterministic and belongs with the existing Google Cloud receipt parsing/filename utilities.
- The downloader remains responsible for browser/network/file side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/google_cloud_receipt_utils.py agent_skills/google_cloud_receipts.py tests/test_google_cloud_receipts.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_google_cloud_receipts.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`979 passed`).

Remaining follow-up slices:
- Google Cloud receipt manifest construction and download-result rows are possible pure boundaries, but the browser interaction paths should remain unchanged unless fixture tests are added.

## 2026-07-02 - RA Research Recommendation Prompt Helpers

Goal/scope:
- Move RA recommendation-scheme system prompt text, user prompt payload construction, and safety-note insertion rule out of `ra_research_cron.py`.
- Keep local LLM execution, generated-length fallback, deterministic fallback generation, timestamp selection, and final newline formatting in the cron module.

Files/modules changed:
- `agent_skills/ra_research_recommendation_prompt.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_recommendation_prompt.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Recommendation prompts still require the same sections and state that the loop continues until Kathia is asymptomatic or Chieh stops the cron.
- Prompt payloads still include generated timestamp, mission, new source IDs, and compact summaries limited to 80.
- JSON prompt serialization still uses `ensure_ascii=False`.
- The safety note is still prepended only when generated text contains neither `medical advice` nor `rheumatologist`.

Boundary chosen:
- Recommendation prompt construction and safety-note enforcement are deterministic rules embedded in an LLM orchestration function.
- Extracting them makes the medical-safety wording and prompt payload contract directly testable.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_recommendation_prompt.py agent_skills/ra_research_cron.py tests/test_ra_research_recommendation_prompt.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_recommendation_prompt.py tests/test_ra_research_discoveries.py tests/test_ra_research_codex_outputs.py tests/test_ra_research_codex_prompt.py tests/test_ra_research_ollama.py tests/test_ra_research_summary_prompt.py tests/test_ra_research_source_utils.py tests/test_ra_research_pubmed.py tests/test_ra_research_text.py tests/test_ra_research_summary_cache.py tests/test_ra_research_report_markdown.py tests/test_ra_research_candidates.py tests/test_ra_research_delivery.py tests/test_ra_research_html.py -q` passed (`67 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`977 passed`).

Remaining follow-up slices:
- `write_run_report()` and `send_report_update()` are now the main remaining RA cron side-effect aggregators; further extraction should focus on pure payload construction around those paths.

## 2026-07-02 - RA Research Discovery Block Helper

Goal/scope:
- Move RA discovery-log block Markdown rendering out of `ra_research_cron.py`.
- Keep timestamp selection, missing-file initialization, and append behavior in the cron module.

Files/modules changed:
- `agent_skills/ra_research_discoveries.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_discoveries.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Discovery blocks still start with a blank line and `## Run <id> — <timestamp>`.
- The mission line and Discoveries, Safety Flags, and Open Questions sections keep the same ordering and Markdown list rendering.
- `append_discoveries()` still creates `# RA Research Discoveries` when the file does not exist and then appends the block.

Boundary chosen:
- The discovery log block is deterministic user-facing Markdown.
- Extracting it leaves file lifecycle behavior in the cron while making the block shape directly testable.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_discoveries.py agent_skills/ra_research_cron.py tests/test_ra_research_discoveries.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_discoveries.py tests/test_ra_research_codex_outputs.py tests/test_ra_research_codex_prompt.py tests/test_ra_research_ollama.py tests/test_ra_research_summary_prompt.py tests/test_ra_research_source_utils.py tests/test_ra_research_pubmed.py tests/test_ra_research_text.py tests/test_ra_research_summary_cache.py tests/test_ra_research_report_markdown.py tests/test_ra_research_candidates.py tests/test_ra_research_delivery.py tests/test_ra_research_html.py -q` passed (`64 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`974 passed`).

Remaining follow-up slices:
- `build_recommendation_scheme()` still has inline prompt construction and safety-note enforcement; extract those pure rules if continuing in the RA cron.

## 2026-07-02 - RA Research Codex Output Helpers

Goal/scope:
- Move Codex synthesis Markdown rendering, compressed-context document rendering, and generated-vs-fallback Markdown selection out of `ra_research_cron.py`.
- Keep file write sequencing, latest-file updates, discovery appends, deterministic fallback generation, and return values in the cron module.

Files/modules changed:
- `agent_skills/ra_research_codex_outputs.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_codex_outputs.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Codex synthesis Markdown still uses the same headings, list rendering, mission fallback, compressed context section, and trailing newline.
- Compressed context files still use `# RA Research Compressed Context`, an `Updated:` line, the context body, and a final newline.
- Recommendation scheme and action plan text still fall back when generated Markdown is shorter than 800 characters.
- Accepted generated Markdown is still stripped and then written with one trailing newline.

Boundary chosen:
- `write_codex_outputs()` mixed pure Markdown decisions with durable file writes.
- Extracting the pure decisions makes the report contract testable while preserving write order and fallback behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_codex_outputs.py agent_skills/ra_research_cron.py tests/test_ra_research_codex_outputs.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_codex_outputs.py tests/test_ra_research_codex_prompt.py tests/test_ra_research_ollama.py tests/test_ra_research_summary_prompt.py tests/test_ra_research_source_utils.py tests/test_ra_research_pubmed.py tests/test_ra_research_text.py tests/test_ra_research_summary_cache.py tests/test_ra_research_report_markdown.py tests/test_ra_research_candidates.py tests/test_ra_research_delivery.py tests/test_ra_research_html.py -q` passed (`62 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`972 passed`).

Remaining follow-up slices:
- `append_discoveries()` still builds Markdown inline; extract discovery block rendering if the RA cron remains the active refactor target.

## 2026-07-02 - RA Research Codex Prompt Helpers

Goal/scope:
- Move Codex synthesis prompt payload construction, prompt serialization, automation system prompt text, and non-JSON fallback result shaping out of `ra_research_cron.py`.
- Keep prompt payload cache writes, automation runner invocation, raw response cache writes, JSON parsing, and failure logging in the cron module.

Files/modules changed:
- `agent_skills/ra_research_codex_prompt.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_codex_prompt.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The Codex prompt still includes mission, safety boundary, model policy, previous compressed context, new source IDs, compact cached summaries, and the same required output keys.
- The prompt still starts with the same highest-judgment RA synthesis prefix and serializes JSON with `ensure_ascii=False`.
- The automation system prompt still states that the assistant builds a traceable research dossier and does not provide medical advice.
- Non-JSON Codex output still becomes a fallback result with the raw response truncated to 12,000 characters and the same discovery warning.

Boundary chosen:
- Codex prompt construction is pure and large enough to obscure the subprocess orchestration path.
- Extracting it makes the prompt contract testable while leaving live automation behavior unchanged.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_codex_prompt.py agent_skills/ra_research_cron.py tests/test_ra_research_codex_prompt.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_codex_prompt.py tests/test_ra_research_ollama.py tests/test_ra_research_summary_prompt.py tests/test_ra_research_source_utils.py tests/test_ra_research_pubmed.py tests/test_ra_research_text.py tests/test_ra_research_summary_cache.py tests/test_ra_research_report_markdown.py tests/test_ra_research_candidates.py tests/test_ra_research_delivery.py tests/test_ra_research_html.py -q` passed (`57 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`967 passed`).

Remaining follow-up slices:
- `write_codex_outputs()` still mixes Markdown rendering and file writes; extract Codex synthesis Markdown and fallback selection helpers before touching the write sequence.

## 2026-07-02 - RA Research Ollama Request Helpers

Goal/scope:
- Move duplicated Ollama base URL normalization and chat request payload construction out of `ra_research_cron.py`.
- Keep environment model selection, `requests.post`, response parsing, text stripping, warning logs, and timeout behavior in the cron module.

Files/modules changed:
- `agent_skills/ra_research_ollama.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_ollama.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Trailing slashes are still stripped from Ollama base URLs.
- Base URLs ending in `/api/generate` or `/api/chat` are still normalized to the server root.
- Chat payloads still send model, system/user messages, `stream: False`, `keep_alive: -1`, and options with `num_ctx` plus `temperature: 0.1`.
- JSON and text calls still use the same endpoint, timeout, and response handling.

Boundary chosen:
- `ollama_chat_json()` and `ollama_chat_text()` duplicated request construction but differ in response parsing.
- Extracting the shared request contract removes drift without touching live model behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_ollama.py agent_skills/ra_research_cron.py tests/test_ra_research_ollama.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_ollama.py tests/test_ra_research_summary_prompt.py tests/test_ra_research_source_utils.py tests/test_ra_research_pubmed.py tests/test_ra_research_text.py tests/test_ra_research_summary_cache.py tests/test_ra_research_report_markdown.py tests/test_ra_research_candidates.py tests/test_ra_research_delivery.py tests/test_ra_research_html.py -q` passed (`53 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`963 passed`).

Remaining follow-up slices:
- `run_codex_synthesis()` still has prompt construction, subprocess execution, and output parsing in one function; split prompt/output helpers before touching subprocess behavior.

## 2026-07-02 - RA Research Summary Prompt Helpers

Goal/scope:
- Move RA source-summary system prompt text, required JSON schema, payload construction, and JSON prompt serialization out of `ra_research_cron.py`.
- Keep cache lookup, LLM execution, fallback behavior, summary finalization, and summary file writes in the cron module.

Files/modules changed:
- `agent_skills/ra_research_summary_prompt.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_summary_prompt.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The system prompt still identifies the model as an evidence reviewer, says Jane is not providing medical care, requires source-supported extraction, and demands one JSON object.
- The required summary schema still includes the same source, evidence, intervention, safety, monitoring, diet, lifestyle, technology, limitation, and clinician discussion fields.
- The evidence scope is still written into the required schema for each source.
- Source text is still capped at 24,000 characters.
- JSON serialization still uses `ensure_ascii=False`.

Boundary chosen:
- The summary prompt schema is an evidence-cache contract and should be directly testable.
- The cron now composes prompt helpers with LLM/cache side effects instead of embedding the schema inline.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_summary_prompt.py agent_skills/ra_research_cron.py tests/test_ra_research_summary_prompt.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_summary_prompt.py tests/test_ra_research_source_utils.py tests/test_ra_research_pubmed.py tests/test_ra_research_text.py tests/test_ra_research_summary_cache.py tests/test_ra_research_report_markdown.py tests/test_ra_research_candidates.py tests/test_ra_research_delivery.py tests/test_ra_research_html.py -q` passed (`49 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`959 passed`).

Remaining follow-up slices:
- The Ollama chat request construction in `ollama_chat_json()` and `ollama_chat_text()` is duplicated; extract base URL/model/payload helpers before changing any local LLM behavior.

## 2026-07-02 - RA Research Source Utility Helpers

Goal/scope:
- Move RA research source cache-key selection, citation formatting, and fallback summary payload construction out of `ra_research_cron.py`.
- Keep current timestamp selection, summary cache writes, LLM calls, and cron orchestration in the cron module.

Files/modules changed:
- `agent_skills/ra_research_source_utils.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_source_utils.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Source cache keys still prefer `pmid`, then `pmcid`, `doi`, `source_id`, and `url`.
- Citations still include up to three authors plus `et al.`, optional publication date, title, journal, PMID, and DOI.
- Fallback summaries still use the first cleaned sentence fragment, capped at 500 characters, and preserve the existing missing-period behavior from splitting on `. `.
- Fallback summaries still emit the same default fields, limitation text, artifact path, `needs_llm_review=True`, and study type fallback.

Boundary chosen:
- Source identity and fallback payloads are deterministic evidence-cache contracts, but they were mixed into the cron's LLM/cache side effects.
- The cron wrapper now injects `iso_now()` while the helper owns the payload shape under direct tests.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_source_utils.py agent_skills/ra_research_cron.py tests/test_ra_research_source_utils.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_source_utils.py tests/test_ra_research_pubmed.py tests/test_ra_research_text.py tests/test_ra_research_summary_cache.py tests/test_ra_research_report_markdown.py tests/test_ra_research_candidates.py tests/test_ra_research_delivery.py tests/test_ra_research_html.py -q` passed (`45 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`955 passed`).

Remaining follow-up slices:
- The RA summary prompt schema in `summarize_source()` is a good next pure boundary, but it should be extracted with a test that locks the exact required-schema keys.

## 2026-07-02 - RA Research PubMed Parser Helpers

Goal/scope:
- Move PubMed XML text extraction, publication date parsing, author parsing, article ID parsing, and PubMed record shaping out of `ra_research_cron.py`.
- Keep PubMed HTTP fetches, NCBI parameter construction, response cache writes, XML root parsing, and candidate processing in the cron module.

Files/modules changed:
- `agent_skills/ra_research_pubmed.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_pubmed.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Article dates still take priority over journal issue publication dates and default missing month/day to `01`.
- Month names still map by their first three characters, with unknown text falling back to January.
- Author parsing still prefers collective names and otherwise joins fore name plus last name, capped by the caller's limit.
- Article IDs still lowercase `IdType` and skip empty values.
- Parsed PubMed records still produce the same source fields, abstract label formatting, publication-type filtering, MeSH filtering, and PubMed URL shape.

Boundary chosen:
- PubMed XML parsing is pure and central to the RA evidence cache, but it was embedded in the large cron orchestrator.
- Extracting it lets the cron own network/cache side effects while the parser contract is directly characterized with fixture XML.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_pubmed.py agent_skills/ra_research_cron.py tests/test_ra_research_pubmed.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_pubmed.py tests/test_ra_research_text.py tests/test_ra_research_summary_cache.py tests/test_ra_research_report_markdown.py tests/test_ra_research_candidates.py tests/test_ra_research_delivery.py tests/test_ra_research_html.py -q` passed (`40 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`950 passed`).

Remaining follow-up slices:
- `ra_research_cron.py` still owns artifact save paths, LLM prompt construction, Codex synthesis orchestration, and report delivery orchestration; the next safest pure boundary is source artifact path/content metadata helpers.

## 2026-07-02 - Job Queue Memory Text Helpers

Goal/scope:
- Move job queue memory fact text and job-number extraction out of `job_queue_runner.py`.
- Keep success gating, timestamp creation, `add_fact` subprocess persistence, and warning logs in the runner.

Files/modules changed:
- `agent_skills/job_queue_memory.py`
- `agent_skills/job_queue_runner.py`
- `tests/test_job_queue_memory.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Job numbers are still parsed from the job filename stem before the first underscore.
- Successful job facts still include job number, UTC date string, title, and a 300-character result snippet with `...` only when longer.
- Failed jobs still do not write job queue facts.

Boundary chosen:
- Job memory fact text is deterministic and mirrors the prompt queue memory helper pattern.
- The runner now owns only the persistence side effect and delegates the text contract to tests.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/job_queue_memory.py agent_skills/job_queue_runner.py tests/test_job_queue_memory.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_job_queue_memory.py tests/test_queue_jane_api.py tests/test_queue_progress_announcements.py tests/test_prompt_queue_memory.py tests/test_job_queue_creation.py tests/test_job_queue_docs.py -q` passed (`29 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`942 passed`).

Remaining follow-up slices:
- Job queue add/create output still has small inline display text; extract only if that area is changed for queue UX.

## 2026-07-02 - Shared Queue Jane API Helpers

Goal/scope:
- Move shared queue chat request payload construction and Jane stream event parsing out of `prompt_queue_runner.py` and `job_queue_runner.py`.
- Keep HTTP calls, 401 sync fallback handling, queue-specific session IDs, announcements, work-log writes, and connection-error handling in the runners.

Files/modules changed:
- `agent_skills/queue_jane_api.py`
- `agent_skills/prompt_queue_runner.py`
- `agent_skills/job_queue_runner.py`
- `tests/test_queue_jane_api.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Queue chat payloads still send `message`, queue-specific `session_id`, and `platform: queue`.
- Stream parsing still ignores blank and invalid JSON lines.
- `delta` events still append response text.
- `done` events still provide fallback text only when no delta text has arrived.
- `error` events still produce `Error: <message>` with `success=False`.
- Empty or whitespace-only stream text still returns an unsuccessful result.

Boundary chosen:
- Prompt and job queues had duplicated stream parsing for the same Jane API contract.
- Extracting the parser gives direct coverage for the event contract while leaving network behavior untouched.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/queue_jane_api.py agent_skills/prompt_queue_runner.py agent_skills/job_queue_runner.py tests/test_queue_jane_api.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_queue_jane_api.py tests/test_queue_progress_announcements.py tests/test_prompt_queue_memory.py tests/test_prompt_queue_docs.py tests/test_job_queue_creation.py tests/test_job_queue_docs.py -q` passed (`33 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`939 passed`).

Remaining follow-up slices:
- The two queue runners still duplicate HTTP request/fallback orchestration; extract that only if fake response tests are added for 401 sync fallback, stream errors, and connection failures.

## 2026-07-02 - Shared Queue Progress Announcement Helpers

Goal/scope:
- Move duplicated queue-progress announcement path, progress ID, payload, and JSONL line construction out of `prompt_queue_runner.py` and `job_queue_runner.py`.
- Keep queue-specific message text, timestamp creation, file append behavior, API streaming, work-log writes, and failure swallowing in the runners.

Files/modules changed:
- `agent_skills/queue_progress_announcements.py`
- `agent_skills/prompt_queue_runner.py`
- `agent_skills/job_queue_runner.py`
- `tests/test_queue_progress_announcements.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Prompt queue progress IDs still use `queue_<milliseconds>`.
- Job queue progress IDs still use `job_<milliseconds>`.
- Announcements still write to `$VESSENCE_DATA_HOME/data/jane_announcements.jsonl`.
- JSON payloads still include `timestamp`, `type: queue_progress`, `id`, `message`, and `final` with the same `json.dumps` formatting.
- Both runners still ignore announcement write failures.

Boundary chosen:
- Queue progress announcement payloads are a shared client contract duplicated across two runners.
- Extracting the payload/path contract reduces drift while leaving runtime network and file-write behavior in place.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/queue_progress_announcements.py agent_skills/prompt_queue_runner.py agent_skills/job_queue_runner.py tests/test_queue_progress_announcements.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_queue_progress_announcements.py tests/test_prompt_queue_memory.py tests/test_prompt_queue_docs.py tests/test_job_queue_creation.py tests/test_job_queue_docs.py -q` passed (`27 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`933 passed`).

Remaining follow-up slices:
- The two queue runners still duplicate Jane API streaming/fallback handling; extract only after adding characterization tests for `delta`, `done`, `error`, and 401 sync fallback paths.

## 2026-07-02 - Prompt Queue Memory Text Helpers

Goal/scope:
- Move prompt queue mutation summaries, shared truncation, and successful completion fact text out of `prompt_queue_runner.py`.
- Keep timestamp creation, subprocess calls to memory/fact scripts, failure skip behavior, and logger calls in the runner.

Files/modules changed:
- `agent_skills/prompt_queue_memory.py`
- `agent_skills/prompt_queue_runner.py`
- `tests/test_prompt_queue_memory.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Queue mutation log summaries still truncate prompt text to 80 characters and append `...` only when longer.
- Successful completion facts still include the same prompt index, UTC date string, success status, 100-character prompt snippet, and 300-character result snippet.
- The existing long-prompt punctuation shape is preserved, including the extra period after an ellipsis in the `Prompt:` sentence.
- Failed/incomplete prompts are still not persisted to Chroma memory.

Boundary chosen:
- Memory fact text is deterministic and easy to regress accidentally while editing the runner.
- The runner now keeps the side effects while the text contract has focused tests.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/prompt_queue_memory.py agent_skills/prompt_queue_runner.py tests/test_prompt_queue_memory.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_prompt_queue_memory.py tests/test_prompt_queue_docs.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`928 passed`).

Remaining follow-up slices:
- Queue progress announcement JSON construction inside `run_prompt()` is another pure text/payload boundary before touching the Jane API streaming logic.

## 2026-07-02 - Prompt Queue Archive Helpers

Goal/scope:
- Move prompt queue archive-section rendering and completed-entry removal/renumbering out of `prompt_queue_runner.py`.
- Keep archive threshold checks, queue/accomplished file I/O, Chroma purge script construction/execution, user notification, and logging in the runner.

Files/modules changed:
- `agent_skills/prompt_queue_docs.py`
- `agent_skills/prompt_queue_runner.py`
- `tests/test_prompt_queue_docs.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Completed prompt archive sections still use the same date heading, prompt headings, prompt text placement, and `---` separators.
- Completed entries are still removed by prompt index and remaining prompt entries are renumbered sequentially.
- The existing header spacing produced by the archive-removal join is characterized rather than cleaned up.
- Chroma memory deletion and Discord/work-log notification behavior are unchanged.

Boundary chosen:
- The archive Markdown transformation is deterministic document logic and belongs with the existing prompt queue document helpers.
- The runner remains responsible for side effects and operational decisions.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/prompt_queue_docs.py agent_skills/prompt_queue_runner.py tests/test_prompt_queue_docs.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_prompt_queue_docs.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`924 passed`).

Remaining follow-up slices:
- `prompt_queue_runner.py` still mixes Jane API streaming, announcements, memory logging, idle checks, and main-loop orchestration; the next low-risk boundary is extracting queue announcement payload construction from `run_prompt()`.

## 2026-07-02 - Nightly Report Body Helpers

Goal/scope:
- Move nightly self-improvement executive-summary line generation and per-stage markdown body generation out of `nightly_self_improve.py`.
- Keep top-level report header assembly, TL;DR insertion, latest/archive atomic writes, and report logging in the orchestrator.

Files/modules changed:
- `agent_skills/nightly_report_rendering.py`
- `agent_skills/nightly_self_improve.py`
- `tests/test_nightly_report_rendering.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Executive summaries still distinguish clean runs from timeout/non-zero runs with the same text.
- Concrete improvement counts still use the existing placeholder-filtering rule.
- Stage bodies still keep the same heading order, blank-line layout, duration formatting, purpose bullet normalization, follow-up section, and missing-artifact fallback text.
- Evidence artifact paths are still rendered through the same bullet formatting.

Boundary chosen:
- Stage body rendering is user-facing but deterministic; extracting it gives direct coverage for report structure without exercising the nightly cron runner.
- `write_readable_report()` now composes tested report helpers and retains ownership of final report assembly and atomic file replacement.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/nightly_report_rendering.py agent_skills/nightly_self_improve.py tests/test_nightly_report_rendering.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nightly_report_rendering.py tests/test_nightly_log_reader.py tests/test_nightly_report_summaries.py -q` passed (`20 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`922 passed`).

Remaining follow-up slices:
- A full `write_readable_report()` golden-output test with monkeypatched paths would cover final header assembly and atomic write behavior, but the pure rendering decisions are now independently characterized.

## 2026-07-02 - Nightly Report Rendering Helpers

Goal/scope:
- Move nightly self-improvement report status counting, archive filename selection, TL;DR stage lines, top-followup aggregation, and concrete-improvement filtering out of `nightly_self_improve.py`.
- Keep job-detail construction, markdown report assembly, atomic latest/archive writes, and report logging in the orchestrator.

Files/modules changed:
- `agent_skills/nightly_report_rendering.py`
- `agent_skills/nightly_self_improve.py`
- `tests/test_nightly_report_rendering.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Report status counts still classify only exact `ok` and `timeout`; every other status counts as failed.
- Archive paths still use `self_improvement_YYYYMMDD_HHMMSS.md` and append `_2`, `_3`, etc. when collisions exist.
- TL;DR stage lines still use the existing ok/timeout/failure markers, minutes formatting, nested problem/fix labels, and empty-state text.
- Top followups still strip leading bullet markers and preserve the prior rollup shape before the caller caps output to three lines.
- Placeholder "No concrete improvement" bullets are still excluded from the executive-summary count.

Boundary chosen:
- These rendering decisions are pure, deterministic, and important to the human-readable nightly report.
- Extracting them leaves `write_readable_report()` responsible for orchestration and file writes while making formatting rules directly testable.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/nightly_report_rendering.py agent_skills/nightly_self_improve.py tests/test_nightly_report_rendering.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nightly_report_rendering.py tests/test_nightly_log_reader.py tests/test_nightly_report_summaries.py -q` passed (`17 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`919 passed`).

Remaining follow-up slices:
- The per-stage markdown body inside `write_readable_report()` can be extracted next, but it should be paired with a whole-report characterization test because it controls user-facing report structure.

## 2026-07-02 - Nightly Log Reader Helpers

Goal/scope:
- Move nightly self-improvement log file reading, timestamp-window extraction, run-marker fallback, and tail truncation out of `nightly_self_improve.py`.
- Keep job execution, report detail aggregation, markdown report rendering, summary-log writes, and vocal rollup behavior in the orchestrator.

Files/modules changed:
- `agent_skills/nightly_log_reader.py`
- `agent_skills/nightly_self_improve.py`
- `tests/test_nightly_log_reader.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing or unreadable log files still return empty text.
- Timestamp windows still include the run start through elapsed seconds plus the existing 5-second allowance.
- Run-marker fallback still searches first for the full ISO marker and then the seconds-precision marker.
- Log windows and fallback log bodies still tail-truncate to the caller's character budget.

Boundary chosen:
- Log-window extraction is deterministic and important to the latest self-improvement report, but it was buried inside the cron orchestrator.
- The orchestrator now composes tested log-reader helpers with the already-extracted report summarizers while retaining the same private aliases for local callers/tests.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/nightly_log_reader.py agent_skills/nightly_self_improve.py tests/test_nightly_log_reader.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nightly_log_reader.py tests/test_nightly_report_summaries.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`913 passed`).

Remaining follow-up slices:
- `write_readable_report()` is still a large markdown-rendering function; split TL;DR line generation and archive-path selection after adding direct report-output characterization tests.

## 2026-07-02 - OmniParser Output Helpers

Goal/scope:
- Move OmniParser subprocess stdout JSON extraction, parsed-element text formatting, and service-result shaping out of `omniparser_skill.py`.
- Keep singleton management, screenshot image encoding, subprocess invocation, timeout handling, debug file writes, and public `parse_screenshot()` behavior in `omniparser_skill.py`.

Files/modules changed:
- `agent_skills/omniparser_output.py`
- `agent_skills/omniparser_skill.py`
- `tests/test_omniparser_output.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- JSON is still found by preferring the last `{"elements":` object and falling back to the last `{`.
- OmniParser API error payloads still raise `OmniParser API Error: ...` with the traceback fallback.
- Parsed content lines still use `Element N: <type> at <bbox> - Content: <content>`.
- The service result still returns `labeled_image`, `parsed_content`, and `elements` with the same fallback values.

Boundary chosen:
- Output parsing is deterministic and testable without launching the OmniParser subprocess or requiring image fixtures.
- `omniparser_skill.py` remains responsible for the runtime integration with screenshots, temporary files, subprocess execution, and debug artifacts.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/omniparser_output.py agent_skills/omniparser_skill.py tests/test_omniparser_output.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_omniparser_output.py -q` passed (`5 passed`).
- `test_code/test_omniparser.py` did not reach repo code because `/home/chieh/ambient/logs/System_log/omni_test_input.png` could not be created; the parent directory was missing in this environment.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`908 passed`).

Remaining follow-up slices:
- The screenshot save path in `test_code/test_omniparser.py` can create its parent directory or use a temp directory so the optional integration check exercises the actual OmniParser service path.

## 2026-07-02 - Safe Docker Command Helpers

Goal/scope:
- Move safe Docker container-name construction and `docker run` command assembly out of `safe_docker.py`.
- Keep allowed mount base resolution, mount safety checks, GPU availability probing, global Docker lock, subprocess execution, timeout handling, force-kill cleanup, and public `run_docker()` API in `safe_docker.py`.

Files/modules changed:
- `agent_skills/safe_docker_command.py`
- `agent_skills/safe_docker.py`
- `tests/test_safe_docker_command.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Container names still use `safe_` plus the first eight UUID hex characters.
- Docker command option order is unchanged: base limits, optional GPU flag, env vars, volume mounts, image, then args.
- GPU flag is still included only when the caller asks for GPU and `/usr/bin/nvidia-smi` exists.
- Unsafe mounts are still rejected before command construction/subprocess execution.

Boundary chosen:
- Command construction is deterministic and testable without Docker.
- `safe_docker.py` remains responsible for safety gates and process lifecycle.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/safe_docker_command.py agent_skills/safe_docker.py tests/test_safe_docker_command.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_safe_docker_command.py tests/test_docker_safety.py -q` passed (`8 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`903 passed`).

Remaining follow-up slices:
- `run_docker()` could accept an injectable subprocess runner for timeout/cleanup tests, but command and mount policy are now covered.

## 2026-07-02 - Vault Tunnel URL Helpers

Goal/scope:
- Move Cloudflare quick-tunnel URL extraction, env/fixed URL selection, and CLI output formatting out of `vault_tunnel_url.py`.
- Keep environment reads, configured log paths, log file reads, fixed-domain constants, and CLI behavior in `vault_tunnel_url.py`.

Files/modules changed:
- `agent_skills/vault_tunnel_helpers.py`
- `agent_skills/vault_tunnel_url.py`
- `tests/test_vault_tunnel_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `VAULT_URL` still overrides everything when set.
- The fixed Vault domain still wins before legacy log parsing.
- Legacy log parsing still scans from newest line to oldest and extracts `https://*.trycloudflare.com`.
- CLI output still prints Vault URL and Jane URL on separate lines, preserving the double space after `Jane URL:`.
- Missing URLs still print the same unavailable message.

Boundary chosen:
- URL selection, log-line parsing, and output text are deterministic and testable without live tunnel logs.
- `vault_tunnel_url.py` remains the runtime script for reading environment and log files.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/vault_tunnel_helpers.py agent_skills/vault_tunnel_url.py tests/test_vault_tunnel_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_vault_tunnel_helpers.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`899 passed`).

Remaining follow-up slices:
- Because a fixed Vault domain is configured, quick-tunnel log fallback is currently legacy-only; remove it only after confirming no deployment path still needs it.

## 2026-07-02 - Shared Phrase Matcher

Goal/scope:
- Move shared phrase punctuation stripping, lowercasing, and phrase-set membership logic out of `confirmation.py` and `end_phrase.py`.
- Keep yes/no phrase sets, end phrase sets, public `is_yes()`, `is_no()`, and `is_end()` APIs in their original modules.

Files/modules changed:
- `agent_skills/phrase_matcher.py`
- `agent_skills/confirmation.py`
- `agent_skills/end_phrase.py`
- `tests/test_phrase_matcher.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Normalization still strips non-word/non-space punctuation while preserving apostrophes.
- Empty or `None` input still returns `False`.
- Yes, no/revise, and end phrase memberships are unchanged.
- Bare `no` remains both a revise phrase and an end phrase; handlers must preserve their existing check order.
- `confirmation._normalize` and `end_phrase._normalize` remain available as private aliases.

Boundary chosen:
- Phrase normalization is duplicated deterministic logic that benefits from one tested implementation.
- Phrase ownership remains in the intent-specific modules so behavior remains easy to audit.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/phrase_matcher.py agent_skills/confirmation.py agent_skills/end_phrase.py tests/test_phrase_matcher.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_phrase_matcher.py tests/test_pending_sms.py -q` passed (`9 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`895 passed`).

Remaining follow-up slices:
- Other handlers still carry local normalization helpers for domain-specific matching; consolidate only after confirming their punctuation rules match this shared matcher.

## 2026-07-02 - Qwen Query Message Helpers

Goal/scope:
- Move local-Qwen response header, Ollama-unreachable refusal text, system instruction construction, and CLI usage text out of `qwen_query.py`.
- Keep Ollama reachability checks, Ollama chat calls, response printing, CLI argument parsing, and exit behavior in `qwen_query.py`.

Files/modules changed:
- `agent_skills/qwen_query_helpers.py`
- `agent_skills/qwen_query.py`
- `tests/test_qwen_query_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The script still refuses to fall back to Gemini when Ollama is unreachable.
- The local Qwen system instruction still identifies Jane as the user's technical expert and local Qwen specialist.
- Successful responses still print the same local-Qwen transparency header.
- Missing CLI prompt still prints `Usage: qwen_query.py <prompt>`.

Boundary chosen:
- User-facing Qwen script text is deterministic and testable without contacting Ollama.
- `qwen_query.py` remains responsible for local model availability and execution.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/qwen_query_helpers.py agent_skills/qwen_query.py tests/test_qwen_query_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_qwen_query_helpers.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`891 passed`).

Remaining follow-up slices:
- `qwen_query.py` still imports unused local-LLM config names; clean only if the script is otherwise touched for runtime behavior.

## 2026-07-02 - Web Search Formatting Helpers

Goal/scope:
- Move Tavily request payload construction, Tavily quota-status detection, Tavily result formatting, and DuckDuckGo result formatting out of `web_search_utils.py`.
- Keep dotenv loading, Tavily API calls, DuckDuckGo calls, fallback orchestration, logging, and public `web_search()` API in `web_search_utils.py`.

Files/modules changed:
- `agent_skills/web_search_format.py`
- `agent_skills/web_search_utils.py`
- `tests/test_web_search_format.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Tavily requests still send `api_key`, `query`, `max_results`, and `search_depth: basic`.
- Tavily HTTP 402 and 429 still indicate quota/payment exhaustion and trigger fallback.
- Empty result lists still format as an empty string.
- Tavily result formatting still uses title/url/content fields; DuckDuckGo formatting still uses title/href/body fields.
- Missing result fields still default to empty strings in the same Markdown shape.

Boundary chosen:
- Request and result formatting are deterministic and testable without network calls or API keys.
- `web_search_utils.py` remains responsible for external search integrations and fallback order.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/web_search_format.py agent_skills/web_search_utils.py tests/test_web_search_format.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_web_search_format.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`888 passed`).

Remaining follow-up slices:
- Network clients remain hard-coded; introduce injectable clients only if adding integration-style fallback tests.

## 2026-07-02 - Cron Notification Helpers

Goal/scope:
- Move Discord webhook payload truncation, work-log notification cleanup/truncation, and shared cron environment payload construction out of `cron_utils.py`.
- Keep dotenv loading, optional Discord webhook POST, work-log import/call fallback, exception handling, and public cron utility APIs in `cron_utils.py`.

Files/modules changed:
- `agent_skills/cron_notification_helpers.py`
- `agent_skills/cron_utils.py`
- `tests/test_cron_notification_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Discord webhook content is still truncated to 2000 characters.
- Work-log fallback still strips `**` and triple backticks, trims whitespace, and truncates to 300 characters.
- Empty cleaned notifications still do not call the work log.
- Cron environment payload still exposes Discord token/channel defaults plus configured Vessence paths.

Boundary chosen:
- Notification text shaping and env payload construction are deterministic and testable without HTTP, dotenv, or work-log side effects.
- `cron_utils.py` remains the integration point for cron scripts.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/cron_notification_helpers.py agent_skills/cron_utils.py tests/test_cron_notification_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_cron_notification_helpers.py tests/test_model_update_helpers.py -q` passed (`8 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`883 passed`).

Remaining follow-up slices:
- Some cron scripts still implement local notification helpers; consolidate only after confirming their Discord/work-log behavior should match `cron_utils.py`.

## 2026-07-02 - Job Queue Utility Helpers

Goal/scope:
- Move job queue utility metadata parsing and completed-job archive threshold selection out of `job_queue_utils.py`.
- Keep job directory scanning, file reads, completed-directory creation, file moves, logging, and CLI behavior in `job_queue_utils.py`.

Files/modules changed:
- `agent_skills/job_queue_utils_helpers.py`
- `agent_skills/job_queue_utils.py`
- `tests/test_job_queue_utils_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Job listing title still falls back to the filename.
- Status still uses the first token after `Status:` lowercased.
- Priority still defaults to `5` and ignores non-integer priority values.
- Completed jobs still match any status starting with `complete`.
- Archiving still happens only when completed count exceeds the threshold, not when equal to it.

Boundary chosen:
- Metadata parsing and threshold selection are deterministic and testable without moving files.
- `job_queue_utils.py` remains responsible for filesystem side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/job_queue_utils_helpers.py agent_skills/job_queue_utils.py tests/test_job_queue_utils_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_job_queue_utils_helpers.py tests/test_job_queue_view.py tests/test_job_queue_docs.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`879 passed`).

Remaining follow-up slices:
- Job metadata parsing now exists in several queue modules with slightly different behavior; consolidate only after deciding which semantics should win.
- Archive file moves still use `shutil.move` directly; add collision handling only with filesystem fixtures.

## 2026-07-02 - Idle State Helpers

Goal/scope:
- Move idle-state payload construction, UTC ISO timestamp formatting, atomic temp path derivation, and Claude Code activity-file path derivation out of `update_idle_state.py`.
- Keep JSON writing, parent directory creation, atomic `os.replace`, two-file update behavior, and CLI behavior in `update_idle_state.py`.

Files/modules changed:
- `agent_skills/idle_state_helpers.py`
- `agent_skills/update_idle_state.py`
- `tests/test_idle_state_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Idle payloads still contain `last_active_ts` and `last_active_iso`.
- ISO timestamps still use UTC `YYYY-MM-DDTHH:MM:SSZ` format.
- Temp paths still append `.tmp` to the original suffix, producing `idle_state.json.tmp`.
- `claude_code_activity.json` is still written next to `idle_state.json`.

Boundary chosen:
- Timestamp and path policy is deterministic and testable without writing runtime state files.
- `update_idle_state.py` remains responsible for atomic file writes.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/idle_state_helpers.py agent_skills/update_idle_state.py tests/test_idle_state_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_idle_state_helpers.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`875 passed`).

Remaining follow-up slices:
- Jane web has a parallel idle-state payload writer; consolidate only with route-level tests because Jane web must not touch the Claude Code-only activity file.

## 2026-07-02 - Fallback Persona Helpers

Goal/scope:
- Move Amber fallback persona construction, Jane fallback persona construction, Amber basic fallback text, capability rendering, identity-rule rendering, visual references, and optional essay section rendering out of `fallback_query.py`.
- Keep dotenv loading, config path resolution, file reads, manifest JSON reads, runtime `PERSONAS` initialization, provider API calls, CLI parsing, and fallback provider ordering in `fallback_query.py`.

Files/modules changed:
- `agent_skills/fallback_personas.py`
- `agent_skills/fallback_query.py`
- `tests/test_fallback_personas.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Amber personas still render capabilities with tool lists and optional fallback-tag instructions.
- Identity rules, visuals, and "never say you cannot perform" text remain in the same order.
- Amber and Jane persona builders still append optional identity essays only when non-empty.
- The original distinction between runtime user label default (`the user`) and essay-heading fallback (`user`) is preserved through a separate `essay_user_name`.
- Manifest read/build failures still fall back to the same basic Amber fallback text.
- Model query functions and provider fallback ordering are unchanged.

Boundary chosen:
- Persona text construction is deterministic and testable without reading real essay files or calling LLM providers.
- `fallback_query.py` remains the integration script for environment setup, file reads, and API/model calls.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/fallback_personas.py agent_skills/fallback_query.py tests/test_fallback_personas.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_fallback_personas.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`871 passed`).

Remaining follow-up slices:
- Provider request payload construction is still inline in `query_deepseek()` and `query_openai()`; extract only with mocked HTTP tests.
- Import-time `PERSONAS` construction still reads files; changing that would affect CLI startup behavior.

## 2026-07-02 - Nightly Audit Helper Rules

Goal/scope:
- Move nightly-audit text truncation, first-script-lines extraction, latest-summary payload construction, and sleep-window hour policy out of `nightly_audit.py`.
- Keep file reads, crontab/process subprocess checks, audit prompt construction, automation-runner calls, report writes, Discord notifications, and logging in `nightly_audit.py`.

Files/modules changed:
- `agent_skills/nightly_audit_helpers.py`
- `agent_skills/nightly_audit.py`
- `tests/test_nightly_audit_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Long file excerpts still truncate with the same `... [truncated at N chars]` marker only when over the limit.
- Script body reads still use `splitlines()` and join the first `max_lines` with newlines.
- Latest-summary JSON still contains `generated_at`, `report_path`, `health_summary`, and stripped `report`.
- Sleep-window override still applies for hours `1 <= hour < 7`, matching code behavior even though the nearby comment says 2-6 AM.
- `nightly_audit.py` keeps private helper aliases for test visibility.

Boundary chosen:
- Small formatting and time-window rules are deterministic and testable without touching logs, crontab, subprocesses, or the automation runner.
- `nightly_audit.py` remains the integration script for system-state gathering and report generation.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/nightly_audit_helpers.py agent_skills/nightly_audit.py tests/test_nightly_audit_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nightly_audit_helpers.py tests/test_audit_report_helpers.py -q` passed (`9 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`866 passed`).

Remaining follow-up slices:
- The sleep-window comment should be reconciled with the actual 1-6 AM behavior in a documentation pass.
- Audit prompt construction is still inline and large; extract only with golden prompt tests.

## 2026-07-02 - Daily Code Review Helpers

Goal/scope:
- Move daily-code-review file eligibility checks, individual diff truncation, truncation notice text, review prompt construction, and markdown report construction out of `daily_code_review.py`.
- Keep git subprocess calls, changed-file existence checks, diff collection, consult-panel invocation, report file writes, logging, and CLI behavior in `daily_code_review.py`.

Files/modules changed:
- `agent_skills/daily_code_review_helpers.py`
- `agent_skills/daily_code_review.py`
- `tests/test_daily_code_review_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Reviewable files are still selected only by configured extension and skip-pattern exclusion.
- Individual diffs still truncate only when longer than 2000 characters and append the same marker.
- Overall diff truncation notices still use the legacy `total_files - emitted_diff_count` formula.
- Review prompts still include only the first 20 changed files and keep the same review focus instructions.
- Markdown reports keep the same title, file count, file list, separator, and trailing newline.

Boundary chosen:
- Path filtering and prompt/report text are deterministic and testable without running git or invoking peer CLIs.
- `daily_code_review.py` remains responsible for repository subprocesses and consult-panel orchestration.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/daily_code_review_helpers.py agent_skills/daily_code_review.py tests/test_daily_code_review_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_daily_code_review_helpers.py tests/test_consult_panel_helpers.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`861 passed`).

Remaining follow-up slices:
- `get_diff_summary()` still mixes git subprocesses with total character accounting; split only with fake subprocess results.
- Import-time logging setup still creates the review directory; leave it unless CLI initialization is refactored more broadly.

## 2026-07-02 - Self-Improve Log Helpers

Goal/scope:
- Move self-improvement vocal-log severity normalization, structured summary composition, record construction, JSONL line parsing, timestamp filtering, newest-first ordering, and limit handling out of `self_improve_log.py`.
- Keep log path resolution, file append, JSON serialization, file existence checks, file reads, and logging in `self_improve_log.py`.

Files/modules changed:
- `agent_skills/self_improve_log_helpers.py`
- `agent_skills/self_improve_log.py`
- `tests/test_self_improve_log_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Unknown, empty, or missing severities still normalize to `info`.
- Explicit summaries still take precedence over structured fields.
- Structured fields still only strip trailing periods before appending a period, so other punctuation behavior is unchanged.
- Empty composed summaries still skip logging.
- Records keep the same timestamp, job, severity, summary, and optional structured-field keys.
- Recent-summary reads still skip blank, invalid JSON, invalid timestamp, and older-than-cutoff lines.
- Results still return newest-first, and `limit=0` still means no cap because the prior code only capped truthy limits.

Boundary chosen:
- Vocal-summary record policy is deterministic and testable without touching the JSONL log file.
- `self_improve_log.py` remains the storage adapter for appending and reading records.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/self_improve_log_helpers.py agent_skills/self_improve_log.py tests/test_self_improve_log_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_self_improve_log_helpers.py tests/test_nightly_report_summaries.py -q` passed (`12 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`855 passed`).

Remaining follow-up slices:
- `read_recent_summaries()` still computes cutoff with `datetime.utcnow()` internally; inject a clock only if adding storage-level tests.
- The punctuation behavior in structured summaries is now characterized but could be improved in a deliberate wording pass.

## 2026-07-02 - Essence Validation Schema Helpers

Goal/scope:
- Move essence manifest required-field constants and schema validation out of `validate_essence.py`.
- Keep folder structure checks, manifest file reads, JSON parse error handling, CLI printing, and full `validate_essence()` orchestration in `validate_essence.py`.

Files/modules changed:
- `agent_skills/essence_validation.py`
- `agent_skills/validate_essence.py`
- `tests/test_essence_validation.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Top-level required manifest fields are reported in the same order.
- Nested `preferred_model`, `capabilities`, and `ui` checks still run only when those values are objects.
- `capabilities.provides` and `capabilities.consumes` still must be arrays.
- `permissions` and `shared_skills` still must be arrays when present.
- `validate_essence.py` still reexports the schema constants and `validate_manifest()`.

Boundary chosen:
- Manifest schema validation is deterministic and testable without creating essence folders or reading JSON files.
- `validate_essence.py` remains responsible for filesystem validation and CLI behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/essence_validation.py agent_skills/validate_essence.py tests/test_essence_validation.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_essence_validation.py tests/test_essence_loader_helpers.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`849 passed`).

Remaining follow-up slices:
- Folder structure validation can be split with temp-directory tests if essence packaging work resumes.
- CLI output formatting is still inline but low-risk and small.

## 2026-07-02 - Continuation Policy Helpers

Goal/scope:
- Move active-queue emptiness checks, idle-state threshold evaluation, continuation prompt text, and continuation JSON result shapes out of `check_continuation.py`.
- Keep active queue file reads, idle state file reads, pending job discovery, short-circuit order, JSON printing, and CLI behavior in `check_continuation.py`.

Files/modules changed:
- `agent_skills/continuation_policy.py`
- `agent_skills/check_continuation.py`
- `tests/test_continuation_policy.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Active queues still block when `items` has at least one entry; missing `items` still counts as empty.
- Non-dict active queue payloads still raise `AttributeError` if already decoded, matching the prior `q.get(...)` behavior.
- Missing or zero `last_active_ts` still counts as idle by using the legacy large elapsed fallback.
- Idle threshold remains inclusive at the exact boundary.
- Continuation responses keep the same keys, reasons, `prompt_index` values, and `[new]\nrun job queue:` prompt text.
- `check_continuation.py` still checks active queue, then pending jobs, then idle state.

Boundary chosen:
- The continuation decision fragments are deterministic and testable without touching live queue, idle-state, or job files.
- `check_continuation.py` remains responsible for filesystem reads and command-line output.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/continuation_policy.py agent_skills/check_continuation.py tests/test_continuation_policy.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_continuation_policy.py tests/test_job_queue_docs.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`844 passed`).

Remaining follow-up slices:
- Pending job directory scanning is duplicated with `run_queue_next.py`; consolidate only with temp job-directory fixtures.
- The output still omits job title on continuation; changing prompt text would be behavior-facing and should be separate.

## 2026-07-02 - Consult Panel Helpers

Goal/scope:
- Move consult-panel mode prompt construction, prompt/context joining, stdin threshold policy, CLI command argument construction, CLI skip policy, and result synthesis out of `consult_panel.py`.
- Keep CLI discovery via `shutil.which`, subprocess execution, timeout/error handling, thread-pool orchestration, CLI argument parsing, and public `consult_panel()` entry point in `consult_panel.py`.

Files/modules changed:
- `agent_skills/consult_panel_helpers.py`
- `agent_skills/consult_panel.py`
- `tests/test_consult_panel_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Caller and skipped CLIs are still excluded from peer detection.
- Context still appends after the exact `---\nContext:` separator.
- Prompts still switch to stdin only when length is greater than 4000 characters.
- Gemini, Codex, and Claude command shapes are unchanged for both argv and stdin modes.
- Unknown CLI names still return the same error path from `query_cli()`.
- Public `synthesize()` still returns the same no-peer message, model sections, unavailable section, and synthesis section.

Boundary chosen:
- Prompt and command construction are deterministic and testable without installed CLIs or subprocess calls.
- `consult_panel.py` remains responsible for process execution and parallel orchestration.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/consult_panel_helpers.py agent_skills/consult_panel.py tests/test_consult_panel_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_consult_panel_helpers.py -q` passed (`8 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`839 passed`).

Remaining follow-up slices:
- CLI file-context assembly in the script footer remains inline; extract only if the CLI path needs tests.
- `query_cli()` could accept an injectable runner for subprocess tests, but the current helper boundary covers the risky command-shape policy.

## 2026-07-02 - Code Map Output Helpers

Goal/scope:
- Move generated map header construction, hand-written header preservation, merged output rendering, rendered line counting, Android path shortening, and combined `CODE_MAP.md` pointer text out of `generate_code_map.py`.
- Keep priority/secondary file lists, filesystem scanning, static indexing, map target selection, file writes, and CLI behavior in `generate_code_map.py`.

Files/modules changed:
- `agent_skills/code_map_output.py`
- `agent_skills/generate_code_map.py`
- `tests/test_code_map_output.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Generated map headers still use the same title line and `_Auto-generated on ... by generate_code_map.py_` text.
- Existing output files still preserve only text through the auto-generated marker plus two newlines.
- Output line counts still use the legacy `text.count("\n") + 1` rule.
- Android source paths still shorten only the known `android/app/src/main/java/com/vessences/android/` prefix.
- The backward-compatible combined `CODE_MAP.md` text remains unchanged.
- `generate_code_map.py` keeps private helper aliases for the extracted output helpers.

Boundary chosen:
- Output formatting and marker preservation are deterministic and testable without scanning the repository or writing files.
- `generate_code_map.py` remains the orchestration module for walking files and writing code maps.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/code_map_output.py agent_skills/generate_code_map.py tests/test_code_map_output.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_code_map_output.py tests/test_code_map_indexers.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`831 passed`).

Remaining follow-up slices:
- Core/web/android file enumeration still has duplicated scan loops; extract only with temp repo fixtures to avoid changing map coverage.
- `_write_map()` still performs direct file writes; atomic replace is a separate output-safety improvement.

## 2026-07-02 - SMS Helper Rules

Goal/scope:
- Move SMS recipient normalization, SQL LIKE escaping, alias/contact match shaping, duplicate contact collapse, draft TTL checks, draft payload shaping, and cleanup cutoff formatting out of `sms_helpers.py`.
- Keep vault-web path setup, database imports, SQL statements, draft inserts/deletes, logging, and public SMS helper APIs in `sms_helpers.py`.

Files/modules changed:
- `agent_skills/sms_helper_rules.py`
- `agent_skills/sms_helpers.py`
- `tests/test_sms_helper_rules.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `_normalize_name` and `_STOP_PREFIXES` remain importable from `sms_helpers.py`.
- Recipient names still strip only one documented stop prefix, lowercase, trim, and collapse whitespace.
- SQL LIKE search terms still escape backslash, `%`, and `_` in the same order.
- Alias matches still use the normalized alias as display fallback when the alias row has no display name.
- Contact matches still collapse duplicate rows by display name and use the first phone row returned by SQL ordering.
- Ambiguous multi-contact matches still return `None` after logging the number of distinct display names.
- Draft expiry still uses a strict `now - created_epoch > DRAFT_TTL_SECONDS` boundary.
- Draft payloads keep the same `draft_id`, `phone_number`, `display_name`, and `body` keys.

Boundary chosen:
- Recipient/draft policy is deterministic and testable without a SQLite database.
- `sms_helpers.py` remains the database adapter, preserving the source-visible SQL safety checks in the auto-audit suite.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/sms_helper_rules.py agent_skills/sms_helpers.py tests/test_sms_helper_rules.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_sms_helper_rules.py -q` passed (`8 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest test_code/auto_audit_sms_helpers.py -q` passed (`76 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`825 passed`).

Remaining follow-up slices:
- SMS draft ID generation and insert payload construction still live in `create_draft()`; extract only if adding deterministic UUID injection tests.
- Database import fallback behavior should remain in `sms_helpers.py` because callers rely on graceful degradation when `vault_web` is unavailable.

## 2026-07-02 - Weather Payload Helpers

Goal/scope:
- Move Tomorrow.io pollen value mapping and Open-Meteo/weather-cache payload construction out of `fetch_weather.py`.
- Keep environment configuration, HTTP requests, logging, cache directory writes, and CLI behavior in `fetch_weather.py`.

Files/modules changed:
- `agent_skills/weather_payload_helpers.py`
- `agent_skills/fetch_weather.py`
- `tests/test_weather_payload_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing pollen indices still default to `0`/`None`; unknown numeric pollen indices still label as `Unknown`.
- Invalid pollen values still raise during integer conversion and are caught by `fetch_pollen()` as a failed pollen fetch.
- Current weather, air-quality, and forecast fields keep the same keys, unit suffixes, weekday derivation, and `Unknown` weather-code fallback.
- Empty pollen payloads are still omitted from the weather cache.
- `fetch_weather._POLLEN_LABELS` remains available as a private compatibility alias.

Boundary chosen:
- Weather cache JSON shaping is deterministic and testable without live weather APIs.
- `fetch_weather.py` remains responsible for API requests and writing `weather.json`.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/weather_payload_helpers.py agent_skills/fetch_weather.py tests/test_weather_payload_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_weather_payload_helpers.py tests/test_weather_slices.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`817 passed`).

Remaining follow-up slices:
- HTTP request parameter construction is still inline; extract only if adding tests for API parameter shape.
- Cache writes are still direct `write_text`; atomic cache replacement can be added separately if needed.

## 2026-07-02 - Email OAuth Token Helpers

Goal/scope:
- Move Gmail OAuth user normalization, account-token slug/path construction, token payload construction, legacy default-token write policy, refresh timing policy, and refresh-response application out of `email_oauth.py`.
- Keep credential directory setup, JSON file reads/writes, default-account fallback scanning, dotenv/SecretStore bootstrap, HTTP refresh calls, logging, and public token APIs in `email_oauth.py`.

Files/modules changed:
- `agent_skills/email_oauth_helpers.py`
- `agent_skills/email_oauth.py`
- `tests/test_email_oauth_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- User IDs still strip whitespace and lowercase; token slugs still replace `@` with `_at_`, dots with underscores, and other unsupported characters with underscores.
- Blank account-specific token users still raise the same `ValueError` path.
- Stored token payloads keep the same user/access/refresh/type/expires/scope/stored fields and defaults.
- Legacy `gmail_token.json` is still written only when no legacy user exists or it matches the account being stored.
- Refresh checks still use a five-minute leeway before `expires_at`.
- Refresh responses still update access token, expiry, and refresh token in place when Google returns one.
- `email_oauth._normalized_user_id` and `_token_slug` remain available as private compatibility aliases.

Boundary chosen:
- Token naming, payload shaping, and refresh timing are deterministic and testable without credentials, disk I/O, or HTTP calls.
- `email_oauth.py` remains the integration module for local credential files and Google token refresh.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/email_oauth_helpers.py agent_skills/email_oauth.py tests/test_email_oauth_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_email_oauth_helpers.py tests/test_email_message_helpers.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest test_code/test_gmail_multi_account_tokens.py -q` passed (`2 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`813 passed`).

Remaining follow-up slices:
- `load_gmail_token()` still owns several filesystem fallback paths; extracting that should use temp credential directories and malformed-token fixtures.
- SecretStore/dotenv bootstrap remains side-effecting and should stay in `email_oauth.py`.

## 2026-07-02 - Shopping List Data Helpers

Goal/scope:
- Move shopping-list payload validation, confidence checks, list-name key policy, in-memory add/remove/clear mutations, and context formatting out of `shopping_list.py`.
- Keep JSON file path resolution, disk reads/writes, public shopping-list APIs, and explicit function signatures in `shopping_list.py`.

Files/modules changed:
- `agent_skills/shopping_list_data.py`
- `agent_skills/shopping_list.py`
- `tests/test_shopping_list_data.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Invalid or malformed shopping-list JSON still loads as an empty dict.
- List names still lowercase without trimming whitespace, while all-whitespace list names still raise `ValueError`.
- Add-item still creates missing lists, trims item text, dedupes case-insensitively, preserves original item casing, and saves even for empty item requests.
- Remove-item still requires confidence, rejects empty item text, removes case-insensitively, and saves only when the target list exists.
- Clear-list still requires confidence, creates/empties the lowercase list key, and saves.
- Context formatting keeps the same empty-store text, title-cased list headings, bullet indentation, and empty-list marker.

Boundary chosen:
- Shopping-list data policy is deterministic and testable without touching `VESSENCE_DATA_HOME`.
- The wrapper module remains responsible for storage and compatibility with existing Jane web handlers.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/shopping_list_data.py agent_skills/shopping_list.py tests/test_shopping_list_data.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_shopping_list_data.py tests/test_shopping_list_actions.py -q` passed (`13 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest test_code/auto_audit_shopping_list.py -q` passed (`104 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`806 passed`).

Remaining follow-up slices:
- If whitespace-preserving list keys are undesirable, normalize with `.strip().lower()` in a deliberate behavior-changing pass and migrate existing stored keys.
- Disk write atomicity is still simple `write_text`; add atomic replace only with storage-focused tests.

## 2026-07-02 - Docs Editing Helpers

Goal/scope:
- Move Google Docs body text extraction, Docs batch-update request payload construction, section-end detection, TODO add/remove edit planning, and TODO category placeholder construction out of `docs_tools.py`.
- Keep Google OAuth/token refresh, Docs service construction, document reads, batchUpdate execution, replace/delete wrappers, and public TODO tool functions in `docs_tools.py`.

Files/modules changed:
- `agent_skills/docs_editing_helpers.py`
- `agent_skills/docs_tools.py`
- `tests/test_docs_editing_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `docs_tools._extract_text` and `docs_tools._find_end_of_section` remain importable private helper aliases.
- Docs text extraction still concatenates paragraph text runs and ignores non-paragraph/non-text-run content.
- Insert and replace requests keep the same Google Docs API body shapes and case-sensitive replacement behavior.
- TODO add-item behavior still appends after the last numbered item when any numbered item is present, otherwise after the last observed line in the section.
- TODO remove-item behavior still strips list markers only for matching/messages and replaces the exact original line plus trailing newline with empty text.
- Category matching still uses stripped case-insensitive whole-line matching, and new categories still append `1. Nothing`.

Boundary chosen:
- Docs JSON walking, request body construction, and TODO line planning are deterministic and testable without Google credentials or network access.
- `docs_tools.py` remains the integration adapter responsible for OAuth and actual Docs API mutations.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/docs_editing_helpers.py agent_skills/docs_tools.py tests/test_docs_editing_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_docs_editing_helpers.py tests/test_todo_doc_helpers.py -q` passed (`16 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`798 passed`).

Remaining follow-up slices:
- The existing TODO add-item logic can treat an empty target section followed by another header/list as part of the target section; this is now characterized but should only be changed deliberately.
- Live Docs API behavior for repeated replacement text still depends on Google `replaceAllText`; preserve or redesign with explicit index-based edits in a separate behavior-changing pass.

## 2026-07-02 - User Manager Config Helpers

Goal/scope:
- Move non-email user ID normalization, capability validation, default config construction, existing config default backfill, initial seed fact construction, and personality description extraction out of `user_manager.py`.
- Keep email-based user ID conversion, filesystem path resolution, config reads/writes, ChromaDB memory seeding, user deletion, personality file reads, and user-space creation in `user_manager.py`.

Files/modules changed:
- `agent_skills/user_manager_helpers.py`
- `agent_skills/user_manager.py`
- `tests/test_user_manager_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Empty local user IDs still normalize to `user`; whitespace-separated and dotted IDs still normalize to lowercase underscore IDs.
- Email user IDs still use `vault_web.auth.user_id_from_email` in `user_manager.py`.
- Capability validation still filters unknown IDs, dedupes in request order, and falls back to the default capability list.
- Missing config fields still get the same default user ID, personality, memory namespace, capabilities, vault path, and managed flag.
- Initial seed facts and personality descriptions keep the same text/first-line rules.

Boundary chosen:
- Config shaping and validation are deterministic and testable without creating user directories or writing ChromaDB records.
- The manager module remains responsible for user-space side effects and external auth integration.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/user_manager_helpers.py agent_skills/user_manager.py tests/test_user_manager_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_user_manager_helpers.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`788 passed`).

Remaining follow-up slices:
- `create_user_space()` still mixes directory creation, memory seeding, and config writes; split only with filesystem and Chroma fakes.
- `delete_user_space()` should stay guarded in `user_manager.py` because it performs destructive filesystem deletion.

## 2026-07-02 - National Grid Bill Helpers

Goal/scope:
- Move National Grid slugging, money parsing/formatting, target-month generation, target-month splitting, account resolution, and year inference out of `nationalgrid_bills.py`.
- Keep extractor module loading, National Grid Playwright login/download flow, cache/download directory setup, account summary aggregation, JSON output, and CLI flow in `nationalgrid_bills.py`.

Files/modules changed:
- `agent_skills/nationalgrid_bill_helpers.py`
- `agent_skills/nationalgrid_bills.py`
- `tests/test_nationalgrid_bill_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Slugs still replace non-alphanumeric runs with underscores and fall back to `account`.
- Money parsing still strips `$`, commas, and spaces, quantizes to cents, and returns `None` for invalid values.
- Current-year month generation still stops at the current month unless future months are requested; future years still return empty unless future months are included.
- Target months still accept comma-separated `YYYY-MM` values, dedupe while preserving order, and reject invalid formats.
- Account resolution still handles explicit account keys, Air Temple electric/gas expansion, Earth Kingdom gas aliases, utility filtering, and utility-only fallback.
- Year inference still prefers explicit `20xx` years and otherwise recognizes YTD/so-far phrasing.

Boundary chosen:
- Account/month/money/year policy is deterministic and testable without National Grid credentials, Playwright, or file downloads.
- The bill module remains responsible for browser automation and result aggregation side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/nationalgrid_bill_helpers.py agent_skills/nationalgrid_bills.py tests/test_nationalgrid_bill_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nationalgrid_bill_helpers.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`783 passed`).

Remaining follow-up slices:
- `_summarize_account()` still contains non-trivial current-bill inference and total aggregation; extract only with representative extractor records as fixtures.
- Browser automation and SecretStore credential resolution must stay in `nationalgrid_bills.py`.

## 2026-07-02 - Email Message Payload Helpers

Goal/scope:
- Move Gmail message header parsing, base64 body decoding, HTML tag stripping, recursive body extraction, and attachment metadata extraction out of `email_tools.py`.
- Keep Gmail OAuth/token refresh, service construction, inbox/search reads, full-message reads, send/trash API calls, MIME message construction, and CLI behavior in `email_tools.py`.

Files/modules changed:
- `agent_skills/email_message_helpers.py`
- `agent_skills/email_tools.py`
- `tests/test_email_message_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Header parsing still keeps only from/to/cc/bcc/subject/date keys and lowercases header names.
- Body decoding still uses URL-safe base64 and UTF-8 replacement on decode errors.
- Recursive body extraction still returns the first body-bearing part in part order, including stripped HTML if that part appears before plain text.
- HTML stripping remains the same crude tag removal used for LLM-readable fallback.
- Attachment extraction still recurses through nested parts and returns filename, MIME type, size, and attachment ID metadata only.

Boundary chosen:
- Gmail payload parsing is deterministic and testable without OAuth credentials or Gmail API calls.
- `email_tools.py` remains responsible for auth, network calls, and send/delete side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/email_message_helpers.py agent_skills/email_tools.py tests/test_email_message_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_email_message_helpers.py tests/test_server_email_tools.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`778 passed`).

Remaining follow-up slices:
- MIME send-message construction is still in `send_email()`; extract only with raw-message tests because header casing/order can matter.
- Gmail service construction should stay in `email_tools.py` because it depends on OAuth token refresh behavior.

## 2026-07-02 - Calendar Time Helpers

Goal/scope:
- Move calendar range resolution, local-day range construction, UTC ISO serialization, local naive ISO normalization, and reminder override validation out of `calendar_tools.py`.
- Keep timezone detection, Google credential checks, Calendar API service construction, event CRUD calls, quick-add, event slimming, and logging in `calendar_tools.py`.

Files/modules changed:
- `agent_skills/calendar_time_helpers.py`
- `agent_skills/calendar_tools.py`
- `tests/test_calendar_time_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Date ranges remain half-open local ranges from midnight to next midnight.
- `today`, `tomorrow`, `weekend`, `this_week`, `next_week`, `next`, next-N-day hints, weekday hints, explicit `YYYY-MM-DD`, and unknown fallback behavior are unchanged.
- Weekday hints still resolve to the upcoming occurrence, including today when it matches.
- UTC serialization still emits RFC-3339 strings ending in `Z`.
- Caller-supplied ISO datetimes still strip offsets and preserve wall-clock digits for Google local-time interpretation.
- Reminder overrides still reject more than five reminders and non-int/out-of-range minute values.

Boundary chosen:
- Time/range/reminder policy is deterministic and testable without Google credentials or Calendar API calls.
- The calendar tool remains responsible for auth, service calls, and API response shaping.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/calendar_time_helpers.py agent_skills/calendar_tools.py tests/test_calendar_time_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_calendar_time_helpers.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`774 passed`).

Remaining follow-up slices:
- Event body construction is still inside `create_event()` and `update_event()`; extract only if API request-body tests are added.
- Timezone detection remains in `calendar_tools.py` because it probes host runtime state.

## 2026-07-02 - Transcript Review Filtering Helpers

Goal/scope:
- Move transcript review prompt-dump context stripping, prompt record filtering, pipeline log filtering, Android diagnostic event summarization, and Codex JSON-array extraction/parsing into `transcript_review_format.py`.
- Keep log file reads, Codex CLI subprocess calls, report writes, vocal summary logging, frontier-provider fix calls, and CLI flow in `transcript_quality_review.py`.

Files/modules changed:
- `agent_skills/transcript_review_format.py`
- `agent_skills/transcript_quality_review.py`
- `tests/test_transcript_review_format.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Prompt dump rows still match by date prefix, strip `[END CURRENT CONVERSATION STATE]` content, cap user messages at 500 characters, and truncate session IDs to 12 characters.
- Pipeline log filtering still requires the date prefix and one of the same relevant markers, then caps lines at 300 characters.
- Android diagnostics still require the ISO date prefix and selected categories, with the same `tool_handler` detail and `voice_flow` extra fields.
- Codex output parsing still extracts the first JSON-array-shaped span and the runner still logs parse errors with the raw output prefix.
- Existing condensed context and report markdown formatting remain in the same helper module.

Boundary chosen:
- Record filtering and output extraction are deterministic and testable without reading live logs or invoking Codex.
- The runner remains responsible for all file and subprocess side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/transcript_review_format.py agent_skills/transcript_quality_review.py tests/test_transcript_review_format.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_transcript_review_format.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`769 passed`).

Remaining follow-up slices:
- Vocal summary wording is still in `transcript_quality_review.py`; extract only if summary generation needs more tests.
- Frontier-provider fix prompting remains runner-owned because prompt wording changes can affect autonomous code edits.

## 2026-07-02 - Job Queue Creation Helpers

Goal/scope:
- Move minimal job queue filename slugging, next-job-number selection, creation draft assembly, and minimal job markdown rendering out of `job_queue_runner.py`.
- Keep job directory scanning, file writes, queue execution, web API calls, status mutation, memory logging, and run-lock behavior in `job_queue_runner.py`.

Files/modules changed:
- `agent_skills/job_queue_creation.py`
- `agent_skills/job_queue_runner.py`
- `tests/test_job_queue_creation.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Job titles still use the stripped first line capped at 60 characters.
- Safe filenames still lowercase, replace non-alphanumeric/underscore/hyphen characters with underscores, cap at 40 characters, trim underscores, and fall back to `task`.
- Next job numbers still parse only filenames that start with digits.
- Minimal job markdown keeps the same status, priority, created date, context, steps, and verification template.
- `add_job_from_text()` still returns the generated filename and writes the same file content shape.

Bug fixed:
- `add_job_from_text()` previously referenced `re` without importing it. Moving the regex logic into `job_queue_creation.py` removes that runtime failure path.

Boundary chosen:
- Job creation string policy is deterministic and testable without writing queue files or invoking the Jane web API.
- The runner remains responsible for filesystem and execution side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/job_queue_creation.py agent_skills/job_queue_runner.py tests/test_job_queue_creation.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_job_queue_creation.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`766 passed`).

Remaining follow-up slices:
- Queue web API streaming and announcement writes are still duplicated with the prompt queue runner; extracting that needs request/response fakes.
- Job memory logging remains side-effecting and should stay runner-owned.

## 2026-07-02 - Gmail Cleanup Query Helpers

Goal/scope:
- Move Gmail cleanup local-day date handling, Gmail date formatting, sender cleanup outcome prefixes, daily sender query construction, older sender query construction, Google Calendar query construction, and unread cleanup query construction out of `nutricost_deal_monitor.py`.
- Keep Gmail API reads, message parsing, trash/send actions, state persistence, CLI parsing, and monitor orchestration in `nutricost_deal_monitor.py`.

Files/modules changed:
- `agent_skills/gmail_cleanup_queries.py`
- `agent_skills/nutricost_deal_monitor.py`
- `tests/test_gmail_cleanup_queries.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Previous local day still uses America/New_York and treats naive datetimes as New York local time.
- Gmail dates still format as `YYYY/MM/DD`.
- Daily sender queries still search from one day before through two days after the local day, then rely on message processing for precise local-date filtering.
- Query builders still include the same recipient, sender, spam/trash, category/subject, older-than, calendar, and unread terms.
- Sender cleanup outcome prefixes still slug labels to lowercase underscore text with `sender_cleanup` fallback.

Boundary chosen:
- Query/date/string rules are deterministic and testable without Gmail credentials or destructive trash/send operations.
- The monitor script remains responsible for all Gmail service calls and side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/gmail_cleanup_queries.py agent_skills/nutricost_deal_monitor.py tests/test_gmail_cleanup_queries.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_gmail_cleanup_queries.py tests/test_gmail_cleanup_monitor.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`761 passed`).

Remaining follow-up slices:
- Message-processing branches still mix Gmail reads, header parsing, cleanup decisions, trashing, and logging; split only with service/message fixtures for each branch.
- The monitor should not be run during refactor verification because it can trash messages and send email outside dry-run.

## 2026-07-02 - Self-Healing Utility Helpers

Goal/scope:
- Move self-healing env flag parsing, auto-repair policy, request header redaction, first-stack-frame extraction, fingerprinting, slug/id generation, incident title formatting, and JSON-safe conversion out of `self_healing.py`.
- Keep incident capture, state file locking, dedupe/rate-limit mutation, incident JSON writes, job file creation, JSONL logging, auto-repair launch, and smoke-test entry point in `self_healing.py`.

Files/modules changed:
- `agent_skills/self_healing_helpers.py`
- `agent_skills/self_healing.py`
- `tests/test_self_healing_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Sensitive headers are still redacted, visible `x-*` and selected standard headers are still capped at 500 characters, and other headers are omitted.
- Env flags still treat `0`, `false`, `no`, and `off` as disabled.
- Explicit `auto_repair` arguments still override the env default.
- Stack-frame extraction still returns the first trimmed line starting with `at ` or `File `, capped at 240 characters.
- Fingerprints are still SHA-256 based and truncated to 24 hex characters.
- Slugs still use lowercase alphanumeric/underscore text, max length, and `incident` fallback.
- Existing private helper names in `self_healing.py` remain direct aliases to the extracted helpers.

Boundary chosen:
- Utility policy is deterministic and testable without writing incident state, creating job files, or launching repair subprocesses.
- `self_healing.py` remains responsible for persistence, locks, rate limits, and repair orchestration.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/self_healing_helpers.py agent_skills/self_healing.py tests/test_self_healing_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_self_healing_helpers.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`756 passed`).

Remaining follow-up slices:
- Job markdown generation is still embedded in `_create_job_for_incident()`; extract only with golden job-file tests.
- State mutation and auto-repair throttling remain coupled to the lock file and should stay script-owned until filesystem fixtures are added.

## 2026-07-02 - Pipeline Audit Helpers

Goal/scope:
- Move pipeline-audit system-context stripping, prompt JSONL filtering/deduping, stream event summarization, and judge-response parsing out of `pipeline_audit_100.py`.
- Keep prompt file reads, live classifier calls, streaming HTTP calls, Ollama judge calls, Chroma exemplar writes, report file writes, and CLI flow in `pipeline_audit_100.py`.

Files/modules changed:
- `agent_skills/pipeline_audit_helpers.py`
- `agent_skills/pipeline_audit_100.py`
- `tests/test_pipeline_audit_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Stage 3 system XML blocks and current-conversation-state blocks are stripped before replaying prompt dump messages.
- Prompt loading still drops invalid JSON, empty messages, messages shorter than three characters, and remaining bracketed/parenthesized system-looking prompts.
- Prompt dedupe still keeps the first occurrence and returns the last `n` unique prompts.
- Stream summaries still preserve ack text, parsed client tool names, final/delta response text capped at 500 characters, classification/stage fields, and stage2/stage3 fallback heuristics.
- Judge parsing still accepts case-insensitive `CORRECT_CLASS`, `CLASSIFICATION_OK`, and `RESPONSE_OK` lines.

Boundary chosen:
- Prompt cleanup, event summarization, and judge text parsing are deterministic and testable without the live Jane server or local LLM.
- The audit script remains responsible for all network/model and ChromaDB side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/pipeline_audit_helpers.py agent_skills/pipeline_audit_100.py tests/test_pipeline_audit_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_pipeline_audit_helpers.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`750 passed`).

Remaining follow-up slices:
- Report rendering is still in `pipeline_audit_100.py`; extract only with golden markdown tests because report wording is operational evidence.
- `add_exemplar()` remains disabled and should not be refactored into active behavior during cleanup.

## 2026-07-02 - Code Keyword Evolution Helpers

Goal/scope:
- Move code-map keyword tuple parsing, code-map name extraction, code-related message detection, candidate keyword selection, keyword insert-block formatting, and source insertion out of `evolve_code_map_keywords.py`.
- Keep SQLite ledger reads, source/config file reads, keyword file writes, logging, service restart, and cron flow in `evolve_code_map_keywords.py`.

Files/modules changed:
- `agent_skills/code_keyword_evolution.py`
- `agent_skills/evolve_code_map_keywords.py`
- `tests/test_code_keyword_evolution.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Tuple parsing still reads only double-quoted string values inside the requested assignment.
- Missing tuple assignments still trigger the script warning path; empty but present tuples simply parse as empty.
- Code-map names still include file basenames, stems, function names from `name() -> L...` entries, and class names longer than two characters.
- Messages are still code-related when they contain an existing keyword or a code-map name longer than three characters.
- Candidate keywords still require at least two code-related messages, exclude existing keywords and stopwords, require at least three characters, reject digit-only tokens, and skip leading-underscore tokens.
- Keyword insertion keeps the same auto-evolved comment block and line indentation.

Boundary chosen:
- Text parsing and insertion policy is deterministic and testable without reading the ledger, modifying `jane_proxy.py`, or restarting `jane-web.service`.
- The nightly script remains responsible for I/O and process side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/code_keyword_evolution.py agent_skills/evolve_code_map_keywords.py tests/test_code_keyword_evolution.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_code_keyword_evolution.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`744 passed`).

Remaining follow-up slices:
- Candidate ordering still inherits Python set iteration for equal-count words, matching existing behavior but not ideal for stable diffs.
- The service restart remains in the script; do not run this cron helper during refactor verification.

## 2026-07-02 - Essence Loader Metadata Helpers

Goal/scope:
- Move essence loader directory resolution, tools/essences search-dir construction, manifest type defaults, type-filter checks, available-essence record construction, and list sort policy out of `essence_loader.py`.
- Keep validation, manifest/personality file reads, ChromaDB initialization, in-memory loaded registry, delete/unload behavior, filesystem scanning, and CLI output in `essence_loader.py`.

Files/modules changed:
- `agent_skills/essence_loader_helpers.py`
- `agent_skills/essence_loader.py`
- `tests/test_essence_loader_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Tool directory resolution still prefers `TOOLS_DIR`, then legacy `ESSENCES_DIR`, then `$AMBIENT_BASE/skills`.
- True essence directory resolution still uses `$AMBIENT_BASE/essences`.
- Available essence records still default missing `type` to `tool` and missing `has_brain` to `False`.
- Type filtering still includes all records for `all` and exact type matches otherwise.
- Listing sort order still puts Jane first, Work Log last, and all other entries alphabetically between them.

Boundary chosen:
- Path/manifest/listing policy is deterministic and testable without loading essences, initializing ChromaDB, or deleting folders.
- The loader module remains responsible for filesystem and runtime state behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/essence_loader_helpers.py agent_skills/essence_loader.py tests/test_essence_loader_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_essence_loader_helpers.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`738 passed`).

Remaining follow-up slices:
- Essence deletion still searches and mutates filesystem state directly; split only with temporary-directory fixtures.
- `load_essence()` still mixes validation, manifest/personality reads, ChromaDB setup, and registry mutation; split only with integration-style tests around valid fixture essences.

## 2026-07-02 - Transcript Display Helpers

Goal/scope:
- Move transcript speaker labels, context-prefix stripping, first-user preview formatting, and `--turns` argument parsing out of `show_transcript.py`.
- Keep SQLite connection/query logic, session resolution, printing, CLI command routing, and `sys.exit()` behavior in `show_transcript.py`.

Files/modules changed:
- `agent_skills/transcript_display_helpers.py`
- `agent_skills/show_transcript.py`
- `tests/test_transcript_display_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- User turns still display as `YOU`; all other roles display as `JANE`.
- First-user previews still collapse whitespace, strip known injected context prefixes, and truncate with the same ellipsis character.
- `_parse_turns_flag()` still exits with the same stderr messages for missing or non-integer `--turns` values.
- Valid `--turns N` still removes the flag/value pair and returns the remaining CLI args unchanged.

Boundary chosen:
- Display and CLI parsing policy is deterministic and testable without opening the transcript SQLite database.
- The script remains responsible for database reads, stdout/stderr output, and process exits.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/transcript_display_helpers.py agent_skills/show_transcript.py tests/test_transcript_display_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_transcript_display_helpers.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`733 passed`).

Remaining follow-up slices:
- SQL query construction is still in `show_transcript.py`; split only if transcript commands grow or need DB-level fixtures.
- Session ambiguity/error printing remains script-owned because it is coupled to CLI exits.

## 2026-07-02 - Nightly Code Audit Helpers

Goal/scope:
- Move nightly code auditor whitelist parsing, default rotation state, next-module rotation, porcelain status filtering, stash/branch naming, and generated test-path construction out of `nightly_code_auditor.py`.
- Keep git commands, stashing, branch checkout/reset, LLM calls, pytest subprocess execution, state file reads/writes, and log file writes in `nightly_code_auditor.py`.

Files/modules changed:
- `agent_skills/nightly_code_audit_helpers.py`
- `agent_skills/nightly_code_auditor.py`
- `tests/test_nightly_code_audit_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Whitelist parsing still accepts only `safe` and `careful` table rows.
- Missing or unreadable state still falls back to `last_index: -1` with an empty history.
- Module rotation still mutates `state["last_index"]` and wraps with modulo.
- Working-tree filtering still ignores expected self-improvement report outputs and `.git.backup` paths while treating every other porcelain line as unexpected.
- Audit branch names, pre-report stash names, and generated test filenames keep the same timestamp/path formats.

Boundary chosen:
- Whitelist/rotation/status-name policy is deterministic and can be tested without running git, pytest, or a frontier model.
- The auditor script remains responsible for all subprocess, branch, stash, LLM, and file persistence behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/nightly_code_audit_helpers.py agent_skills/nightly_code_auditor.py tests/test_nightly_code_audit_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nightly_code_audit_helpers.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`728 passed`).

Remaining follow-up slices:
- Prompt construction for generated tests and attempted fixes is still embedded in `nightly_code_auditor.py`; extract only with golden prompt tests because wording changes can affect LLM behavior.
- Git branch/revert behavior should stay in the script unless subprocess fakes are added.

## 2026-07-02 - Doc Drift Parsing Helpers

Goal/scope:
- Move doc-drift class-map parsing, pipeline doc table parsing, crontab script extraction, documented cron script extraction, inactive cron section detection, and drift report rendering out of `doc_drift_auditor.py`.
- Keep crontab subprocess reads, config file reads/writes, registry cleanup, warning/change accumulation, git commits, vocal logging, and main audit orchestration in `doc_drift_auditor.py`.

Files/modules changed:
- `agent_skills/doc_drift_helpers.py`
- `agent_skills/doc_drift_auditor.py`
- `tests/test_doc_drift_auditor.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `_CLASS_MAP` parsing still normalizes string keys to uppercase underscore form and returns an empty set on syntax/literal-eval failures.
- Documented class parsing still starts from the class table header, reads only the first column, allows digits/underscores, and stops at the next blank line.
- Cron parsing still ignores comments and env assignments, then collects `.py` and `.sh` token basenames from active crontab lines.
- Documentation parsing still reads only `**Script Path:**` entries and treats `Removed Jobs`, `Non-Cron Scheduled Scripts`, `DISABLED`, `COMMENTED OUT`, and `Paused:` sections as inactive.
- Drift report markdown keeps the same headings, spacing, empty-state text, and warning/change formatting.

Boundary chosen:
- Parsing and markdown rendering are deterministic and testable without reading the live crontab, editing config docs, or running git.
- The auditor module remains responsible for all filesystem and subprocess behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/doc_drift_helpers.py agent_skills/doc_drift_auditor.py tests/test_doc_drift_auditor.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_doc_drift_auditor.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`723 passed`).

Remaining follow-up slices:
- `audit_skills_registry()` still mixes registry parsing and auto-editing; split only with text fixtures for full block-removal behavior.
- The git commit path should stay in `doc_drift_auditor.py` unless subprocess fakes are added.

## 2026-07-02 - Audit Auto-Fix Helpers

Goal/scope:
- Move audit auto-fixer safety policy, LLM JSON-array extraction, result partitioning/counting, and markdown fix-report rendering out of `audit_auto_fixer.py`.
- Keep audit-report discovery, LLM calls, backup creation, file reads/writes, syntax verification, restore behavior, CLI parsing, and report file writes in `audit_auto_fixer.py`.

Files/modules changed:
- `agent_skills/audit_auto_fix_helpers.py`
- `agent_skills/audit_auto_fixer.py`
- `tests/test_audit_auto_fix_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Safe extensions and forbidden path patterns are unchanged and still exposed from `audit_auto_fixer.py`.
- File safety still rejects forbidden patterns, unsafe extensions, and non-existent paths.
- LLM response parsing still unwraps JSON code fences and falls back to the first bracketed JSON array inside preamble/trailing text.
- Fix reports keep the same headings, dry-run/live labels, result partitions, basename rendering, and truncation limits.
- Summary counts still treat both `fixed` and `would_fix` as fixed-equivalent.

Boundary chosen:
- Safety checks and markdown rendering are deterministic and testable without invoking the LLM or modifying files.
- The script remains responsible for destructive operations, backups, restore paths, and logging.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/audit_auto_fix_helpers.py agent_skills/audit_auto_fixer.py tests/test_audit_auto_fix_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_audit_auto_fix_helpers.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`720 passed`).

Remaining follow-up slices:
- `apply_fix()` still mixes validation, backup, write, syntax verification, and restore flow; splitting it safely would need filesystem fixtures.
- The LLM prompt body remains in the script because changing it can alter auto-fixer behavior.

## 2026-07-02 - Essence Builder Parsing Helpers

Goal/scope:
- Move essence-builder free-text parsing rules for role titles, list extraction, quoted starters, section fragments, shared skills, UI type, permissions, model selection, triggers, credentials, and folder-name sanitization out of `essence_builder.py`.
- Keep interview state persistence, section flow, spec generation orchestration, manifest assembly, template copying, file writes, and build cleanup in `essence_builder.py`.

Files/modules changed:
- `agent_skills/essence_builder_parsing.py`
- `agent_skills/essence_builder.py`
- `tests/test_essence_builder_parsing.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Existing private parser names in `essence_builder.py` still resolve via imported aliases.
- Role-title extraction still honors `role title:`, `role:`, and `title:` markers, then falls back to the first `the <word>` phrase, then `the specialist`.
- Capability/list extraction still reads matching keyword lines and all short bullet items.
- Conversation starters still prefer quoted strings and otherwise use bullet/numbered lines.
- Shared-skill, UI, permission, model, trigger, credential, and folder-name parsing keep the same matching order and defaults.
- `generate_manifest()` keeps the same manifest shape while delegating parser decisions to the helper.

Boundary chosen:
- Free-text parsing is deterministic and testable without writing essence folders or touching the persisted interview state.
- The builder module remains responsible for stateful interview and filesystem behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/essence_builder_parsing.py agent_skills/essence_builder.py tests/test_essence_builder_parsing.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_essence_builder_parsing.py -q` passed (`8 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`715 passed`).

Remaining follow-up slices:
- `build_essence_from_spec()` still recomputes the manifest more than once; caching that within the function would be safe but should be verified against generated file outputs.
- Interview section text and state transitions are still in `essence_builder.py`; split them only if the builder gets more active use or broader tests.

## 2026-07-02 - Essence Routing Helpers

Goal/scope:
- Move multi-essence route scoring, capability word normalization, request-overlap detection, best-route selection, and capability plan-step construction out of `essence_runtime.py`.
- Keep essence loading/unloading, ChromaDB clients, active-essence persistence, memory porting, runtime state, and orchestration class ownership in `essence_runtime.py`.

Files/modules changed:
- `agent_skills/essence_routing.py`
- `agent_skills/essence_runtime.py`
- `tests/test_essence_routing.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Capability names are still lowercased and split after replacing underscores with spaces.
- Route scoring still uses substring checks against the full lowercased query.
- Query words longer than two characters still score against role title and description.
- Best-route selection still returns the first positive-scoring essence and preserves first-match tie behavior.
- Orchestration plan steps still use the first provider for a matched capability and keep the same subtask text.

Boundary chosen:
- Routing and planning rules are deterministic and testable without ChromaDB, filesystem state, or the runtime singleton.
- Runtime classes remain responsible for stateful lifecycle and persistence work.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/essence_routing.py agent_skills/essence_runtime.py tests/test_essence_routing.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_essence_routing.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`707 passed`).

Remaining follow-up slices:
- Better routing semantics, such as token-boundary matching or tie-break scoring, would be behavior changes and should be handled separately.
- `EssenceRuntime` still mixes lifecycle, persistence, and memory porting; those should be split only with stronger integration tests or fakes.

## 2026-07-02 - TODO Doc Parser Helpers

Goal/scope:
- Move Google Doc TODO export URL construction, UTF-8 body decoding, login-wall detection, category parsing, item counting, and cache payload construction out of `fetch_todo_list.py`.
- Keep environment resolution, HTTP requests, logging, empty-cache guard behavior, atomic file writes, and CLI flow in `fetch_todo_list.py`.

Files/modules changed:
- `agent_skills/todo_doc_helpers.py`
- `agent_skills/fetch_todo_list.py`
- `tests/test_todo_doc_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The export URL format is unchanged.
- Invalid UTF-8 still decodes with replacement characters after a strict UTF-8 attempt fails.
- Login-wall detection still checks the initial response body for the same markers.
- Parser behavior is unchanged for BOM stripping, top-of-doc TODO title skipping, category headers, numbered/dash/star/bullet list markers, orphan item handling, and prose/footer dropping.
- Cache JSON keeps the same `fetched_at`, `doc_id`, `source_url`, `categories`, and `raw_text` fields.

Boundary chosen:
- Doc parsing and cache payload shape are deterministic and can be tested without Google Docs, cron, or filesystem writes.
- The fetcher script remains responsible for network I/O and atomic cache replacement.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/todo_doc_helpers.py agent_skills/fetch_todo_list.py tests/test_todo_doc_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_todo_doc_helpers.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`702 passed`).

Remaining follow-up slices:
- Multi-line TODO items are still intentionally unsupported because the current doc style is single-line items.
- Cache file write behavior should stay in `fetch_todo_list.py` unless filesystem fakes are added.

## 2026-07-02 - Git Backup Commit Summary Helpers

Goal/scope:
- Move automated backup commit prompt construction, summary normalization, default backup summary, and timestamped fallback summary out of `git_backup.py`.
- Keep git diff/add/commit/push subprocess calls, Ollama model calls, timestamp generation, and repository side effects in `git_backup.py`.

Files/modules changed:
- `agent_skills/git_backup_helpers.py`
- `agent_skills/git_backup.py`
- `tests/test_git_backup_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Empty diffs still produce `Regular automated backup`.
- Non-empty diffs are still capped before being embedded in the commit-summary prompt.
- The prompt text sent to the model is unchanged.
- Model-generated summaries still strip wrapping quotes and collapse newlines into spaces.
- Model failures still fall back to `Automated backup: <timestamp>`.

Boundary chosen:
- Commit-message shaping is deterministic and testable without invoking Ollama or mutating git state.
- The backup script remains responsible for all subprocess and remote-push behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/git_backup_helpers.py agent_skills/git_backup.py tests/test_git_backup_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_git_backup_helpers.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`696 passed`).

Remaining follow-up slices:
- Keep git add/commit/push and Ollama calls in the script unless subprocess/model fakes are added.
- Do not run `git_backup.py` during refactor verification because it can commit and push.

## 2026-07-02 - Model Update Notification Helpers

Goal/scope:
- Move Gemini model-update prompt construction, update-persistence gating, Discord message formatting, Discord channel URL construction, and bot headers into a shared helper.
- Keep Gemini API calls, pending-update file writes, pending-update file reads/deletes, Discord HTTP calls, and cron env loading in `check_for_updates.py` and `notify_updates.py`.

Files/modules changed:
- `agent_skills/model_update_helpers.py`
- `agent_skills/check_for_updates.py`
- `agent_skills/notify_updates.py`
- `tests/test_model_update_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The search query string is unchanged.
- The model-update prompt still embeds `CURRENT_MODEL` and requests the same JSON schema.
- Pending updates are still persisted on any truthy `new_model_found` value.
- Discord notification text and bot request headers keep the same shape.

Boundary chosen:
- Prompt/message/request-shape policy is deterministic and can be tested without Gemini, files, or Discord.
- The original scripts remain responsible for network and pending-file side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/model_update_helpers.py agent_skills/check_for_updates.py agent_skills/notify_updates.py tests/test_model_update_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_model_update_helpers.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`692 passed`).

Remaining follow-up slices:
- Updating `CURRENT_MODEL` or provider/model policy should be a separate current-docs task, not bundled into this helper extraction.
- Consider deferring cron env loading in `notify_updates.py` if import-time side effects become a test/runtime issue.

## 2026-07-02 - Iterative Refactor Scheduler Helpers

Goal/scope:
- Move scheduler default-state creation, loaded-state normalization, job-number parsing/allocation, job filename construction, and cron self-disable text rewriting out of `iterative_refactor_scheduler.py`.
- Keep state file reads/writes, job file writes, file locking, subprocess crontab calls, logging, and CLI flow in `iterative_refactor_scheduler.py`.

Files/modules changed:
- `agent_skills/iterative_refactor_helpers.py`
- `agent_skills/iterative_refactor_scheduler.py`
- `tests/test_iterative_refactor_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing state still initializes version, creation time, max iteration count, zero enqueued iterations, and per-project job lists.
- Loaded state still gets missing project/job fields backfilled.
- Job numbers still parse both `job_007...` and `42...` filename prefixes.
- Next job number still mutates the used-number set.
- Cron self-disable still comments active marker lines and leaves already-commented lines unchanged.

Boundary chosen:
- State normalization and cron text rewriting are deterministic and can be tested without queue writes or crontab mutation.
- The scheduler remains responsible for filesystem, lock, and subprocess side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/iterative_refactor_helpers.py agent_skills/iterative_refactor_scheduler.py tests/test_iterative_refactor_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_iterative_refactor_helpers.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`688 passed`).

Remaining follow-up slices:
- Job content wording is still in the scheduler; changing it affects queued instructions and should be handled intentionally.
- Keep crontab subprocess behavior in the scheduler unless command fakes are added.

## 2026-07-02 - Auto Commit WIP Helpers

Goal/scope:
- Move git status filtering, self-improve phase naming, and automatic commit-message formatting out of `auto_commit_wip.py`.
- Keep git status/add/commit/push subprocess calls, CLI argument parsing, and logging in `auto_commit_wip.py`.

Files/modules changed:
- `agent_skills/auto_commit_helpers.py`
- `agent_skills/auto_commit_wip.py`
- `tests/test_auto_commit_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Blank git status lines are ignored.
- `.git.backup` status entries are still filtered out.
- `--push` still uses `post-self-improve`; non-push commits still use `pre-self-improve WIP`.
- The auto-commit message keeps the same subject/body shape.

Boundary chosen:
- Commit eligibility text filtering and message construction are deterministic and can be tested without running git.
- The original script remains responsible for repository mutation.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/auto_commit_helpers.py agent_skills/auto_commit_wip.py tests/test_auto_commit_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_auto_commit_helpers.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`684 passed`).
- Did not run `auto_commit_wip.py` itself because it can create commits.

Remaining follow-up slices:
- Any change to what gets committed should stay in `auto_commit_helpers.py` and be covered before running the script.
- Push behavior and git failure handling should remain in the script unless git subprocess fakes are added.

## 2026-07-02 - Research Result Helpers

Goal/scope:
- Move research-analyzer result shapes, no-solution handling, analysis-error shaping, and research-assistant JSON/code-fence parsing into a shared helper module.
- Keep raw file reads, Ollama calls, output file writes, and CLI entrypoints in `research_analyzer.py` and `research_assistant.py`.

Files/modules changed:
- `agent_skills/research_result_helpers.py`
- `agent_skills/research_analyzer.py`
- `agent_skills/research_assistant.py`
- `tests/test_research_result_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing analyzer input still returns low confidence with `cause: File not found`.
- `NO_SOLUTION_FOUND` still maps to the same low-confidence no-solution result.
- Successful analyzer JSON still gets `found: True`.
- Research assistant still strips ```json and generic code fences before `json.loads`.
- Exceptions still return the existing low-confidence/error payloads in the analyzer and `{"error": ...}` in the assistant.

Boundary chosen:
- Model output normalization and result shaping are deterministic and can be tested without Ollama or filesystem writes.
- The original scripts remain responsible for local model calls and persistence.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/research_result_helpers.py agent_skills/research_analyzer.py agent_skills/research_assistant.py tests/test_research_result_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_research_result_helpers.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`681 passed`).

Remaining follow-up slices:
- Keep Ollama invocation and vault output writes in the scripts unless model and filesystem fakes are added.
- The same JSON extraction helper may be reused by other model-output parsers after focused characterization.

## 2026-07-02 - LLM Config Librarian Shim

Goal/scope:
- Restore the missing `LIBRARIAN_MODEL` compatibility export in `jane.config`.
- Add import-level coverage for `jane.llm_config`, `llm_brain.v1.llm_config`, and the qwen orchestrator helper wiring.

Files/modules changed:
- `jane/config.py`
- `tests/test_llm_config_shim.py`
- `tests/test_qwen_orchestrator_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Existing local LLM aliases still flow from `jane.config` through both LLM config shims.
- `LIBRARIAN_MODEL` is env-driven via `LIBRARIAN_MODEL` or `JANE_LIBRARIAN_MODEL`, falling back to the resolved `LOCAL_LLM_MODEL` instead of hardcoding a separate model tag.

Behavior intentionally fixed:
- Importing `agent_skills.qwen_orchestrator` no longer fails through `jane.llm_config` because `LIBRARIAN_MODEL` is now defined.

Boundary chosen:
- This is a compatibility-shim repair discovered while extracting qwen helper logic.
- It keeps model selection centralized in `jane.config` without changing live Ollama invocation behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane/config.py tests/test_llm_config_shim.py tests/test_qwen_orchestrator_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_llm_config_shim.py tests/test_qwen_orchestrator_helpers.py -q` passed (`7 passed`).
- Direct import check for `agent_skills.qwen_orchestrator` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`677 passed`).

Remaining follow-up slices:
- Model default policy and documentation still need a separate intentional pass if Chieh wants to standardize local librarian defaults.
- Keep provider/model upgrades separate from refactor-only helper extractions.

## 2026-07-02 - Qwen Orchestrator Text Helpers

Goal/scope:
- Move requirement-line package parsing, package import-name normalization, grep harvest section formatting, and empty-harvest fallback text out of `qwen_orchestrator.py`.
- Keep Ollama calls, stage state writes, requirement file reads, `importlib` dependency checks, subprocess grep calls, and CLI orchestration in `qwen_orchestrator.py`.

Files/modules changed:
- `agent_skills/qwen_orchestrator_helpers.py`
- `agent_skills/qwen_orchestrator.py`
- `tests/test_qwen_orchestrator_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Requirement lines still strip comments and split on `==`, `>=`, `<=`, and extras brackets.
- Package import probes still convert dashes to underscores before falling back to the package name.
- Harvested context still keeps at most five grep lines per pattern with the same section header.
- Empty harvests still return `No idiomatic context harvested.`

Boundary chosen:
- Requirement parsing and harvest text formatting are deterministic and can be tested without Ollama, filesystem state writes, import probes, or subprocess grep execution.
- The orchestrator remains responsible for live staged execution.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/qwen_orchestrator_helpers.py agent_skills/qwen_orchestrator.py tests/test_qwen_orchestrator_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_qwen_orchestrator_helpers.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`674 passed`).

Known issue observed:
- Importing `agent_skills.qwen_orchestrator` currently fails before this refactor path because `jane.llm_config` expects `LIBRARIAN_MODEL` from `jane.config`; focused tests therefore cover the extracted helper directly and do not import the live orchestrator module.

Remaining follow-up slices:
- Fix the `jane.llm_config`/`jane.config` model-setting mismatch separately before adding import-level qwen orchestrator tests.
- Keep staged Ollama execution and subprocess harvesting in the orchestrator unless fakes are added.

## 2026-07-02 - CLI LLM Policy Helpers

Goal/scope:
- Move CLI prompt truncation, fallback-worthy error classification, fallback provider ordering, tier-to-model selection, and JSON fence stripping out of `claude_cli_llm.py`.
- Keep command construction, subprocess execution, environment handling, tier wrappers, and JSON parsing in `claude_cli_llm.py`.

Files/modules changed:
- `agent_skills/cli_llm_policy.py`
- `agent_skills/claude_cli_llm.py`
- `tests/test_cli_llm_policy.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Prompts longer than 32,000 characters still keep the first 1,000 chars, the same truncation marker, and the last 31,000 chars.
- Fallback still triggers for limit, quota, timeout, and generic failed CLI errors, but not missing CLI binaries.
- Fallback provider order remains OpenAI, Gemini, Claude with the current provider removed.
- Agent and orchestrator tiers still use provider `smart`; utility still uses `cheap`.
- JSON completion still strips ```json and generic code fences before `json.loads`.

Boundary chosen:
- Fallback/truncation/fence policy is deterministic and can be tested without invoking any LLM CLI.
- The wrapper remains responsible for actual provider subprocess behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/cli_llm_policy.py agent_skills/claude_cli_llm.py tests/test_cli_llm_policy.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_cli_llm_policy.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`670 passed`).

Remaining follow-up slices:
- `_build_command` is already pure but is still provider-coupled; test it before changing command shapes.
- Any provider/model updates should be separate from this behavior-preserving extraction.

## 2026-07-02 - Work Log Data Helpers

Goal/scope:
- Move activity-log path resolution, activity entry shaping, JSON list coercion, bounded append, and recent-entry ordering out of `work_log_tools.py`.
- Keep directory creation, JSON file reads/writes, and public tool functions in `work_log_tools.py`.

Files/modules changed:
- `agent_skills/work_log_helpers.py`
- `agent_skills/work_log_tools.py`
- `tests/test_work_log_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `TOOLS_DIR` still takes precedence over `ESSENCES_DIR`, which takes precedence over `$AMBIENT_BASE/skills`.
- Activity entries still include `timestamp`, `timestamp_epoch`, `description`, and `category`.
- Malformed/non-list log data still behaves like an empty log.
- The log still keeps only the most recent 200 entries and returns recent entries newest-first.

Boundary chosen:
- Work Log data shaping is deterministic and can be tested without creating directories or touching the user data file.
- The original tool module remains responsible for filesystem side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/work_log_helpers.py agent_skills/work_log_tools.py tests/test_work_log_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_work_log_helpers.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`664 passed`).

Remaining follow-up slices:
- Keep file locking or atomic-write changes out of this slice; those would be behavior changes and should be handled separately if Work Log corruption is observed.
- Other small essence tools can follow this pattern when they mix path resolution with JSON shaping.

## 2026-07-02 - Context Summary Hook Helpers

Goal/scope:
- Move Stop-hook payload parsing, response-text extraction, summary length gating, Qwen stdout cleanup, context fact formatting, and last-summary record formatting out of `save_context_summary.py`.
- Keep Qwen subprocess calls, Chroma memory writes, context-log file writes, stdin reading, and exit behavior in `save_context_summary.py`.

Files/modules changed:
- `agent_skills/context_summary_helpers.py`
- `agent_skills/save_context_summary.py`
- `tests/test_context_summary_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Invalid or non-object hook JSON still behaves as an empty payload.
- Only `message` is used as the response text.
- Responses shorter than 50 stripped characters still skip summarization.
- Qwen output still drops lines beginning with `---` and joins the rest with spaces.
- Context snapshot facts and debug records keep the same shapes.

Boundary chosen:
- Hook text parsing and summary shaping are deterministic and can be tested without spawning Qwen or writing ChromaDB memory.
- The original script remains responsible for subprocess and filesystem side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/context_summary_helpers.py agent_skills/save_context_summary.py tests/test_context_summary_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_context_summary_helpers.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`660 passed`).

Remaining follow-up slices:
- Keep model invocation and memory writes in `save_context_summary.py` unless subprocess fakes are added.
- Similar hook scripts should extract payload parsing before touching external calls.

## 2026-07-02 - Dead Code Auditor Safety Policy

Goal/scope:
- Move hard-skip prefix checks, pytest-discovery test-file detection, and auto-delete eligibility policy out of `dead_code_auditor.py`.
- Keep filesystem scanning, dynamic-import detection, grep/reference checks, duplicate-body scanning, unlink operations, report writes, and git commits in `dead_code_auditor.py`.

Files/modules changed:
- `agent_skills/dead_code_policy.py`
- `agent_skills/dead_code_auditor.py`
- `tests/test_dead_code_policy.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Hard-skip matching is still prefix-based.
- `test_code/test_*.py` files are still treated as pytest-discovered.
- Auto-delete still rejects hard-kept filenames, dynamically imported files, large files, files over the line cap, and files younger than the age threshold.
- Age eligibility still uses a strict lower-than comparison, so exactly `AUTO_DELETE_AGE_DAYS` remains eligible.

Behavior intentionally fixed:
- Auto-delete eligibility now enforces the documented `agent_skills/` and `test_code/` root restriction instead of allowing any scanned non-`jane_web` Python file to be auto-deleted.

Boundary chosen:
- Deletion eligibility is pure safety policy over path/stat facts.
- The auditor remains responsible for reference discovery and actual deletion/reporting side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/dead_code_policy.py agent_skills/dead_code_auditor.py tests/test_dead_code_policy.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_dead_code_policy.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`655 passed`).
- Did not run `dead_code_auditor.py` itself because it can unlink files by design.

Remaining follow-up slices:
- Dynamic-import prefix discovery and report rendering can be considered separately, but should stay behavior-preserving and avoid running the destructive auditor during refactor verification.
- Any future auto-delete policy changes should go through `dead_code_policy.py` with focused tests first.

## 2026-07-02 - System Janitor Cleanup Rules

Goal/scope:
- Move log rotation thresholds, stale-file detection, log cleanup action selection, and tail-truncation payload shaping out of `janitor_system.py`.
- Keep temp-file deletion, log filesystem scans, file unlink/truncate operations, transcript cleanup scans, turn-dedupe pruning, job archiving, and CLI flow in `janitor_system.py`.

Files/modules changed:
- `agent_skills/janitor_system_rules.py`
- `agent_skills/janitor_system.py`
- `tests/test_janitor_system_rules.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Log rotation still uses a strict `>` comparison against `MAX_LOG_SIZE_MB`.
- Stale logs and transcript artifacts still delete only when `mtime < cutoff`.
- Active logs still truncate only when larger than 1 MB.
- Tail truncation still drops the first partial line and writes the same header shape.

Boundary chosen:
- Cleanup policy is deterministic over file stat values and byte windows.
- The janitor script remains responsible for destructive filesystem operations and external cleanup calls.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/janitor_system_rules.py agent_skills/janitor_system.py tests/test_janitor_system_rules.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_janitor_system_rules.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`651 passed`).

Remaining follow-up slices:
- Keep actual deletes/truncates in `janitor_system.py` unless filesystem fixtures are added.
- `dead_code_auditor.py` has larger policy boundaries, but it should be handled in smaller audited slices because it can auto-delete files.

## 2026-07-02 - Screen Dimmer Rule Helpers

Goal/scope:
- Move xrandr output parsing, preferred-output selection, sunrise-sunset payload parsing, and brightness time-window decisions out of `screen_dimmer.py`.
- Keep HTTP requests, subprocess calls, printing, and the CLI entrypoint in `screen_dimmer.py`.

Files/modules changed:
- `agent_skills/screen_dimmer_rules.py`
- `agent_skills/screen_dimmer.py`
- `tests/test_screen_dimmer_rules.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Connected outputs are still detected by lines containing ` connected`.
- `DP-1` is still preferred when connected; otherwise brightness applies to all connected outputs.
- After-sunset dimming, after-07:00 brightening, and pre-07:00 no-op behavior keep the same thresholds and messages.
- Sunset API responses still require status `OK` and parse the returned ISO timestamp into local time.

Boundary chosen:
- Time-window decisions and xrandr response parsing are deterministic and can be tested without network calls or monitor brightness changes.
- The script remains responsible for external API access and `xrandr` execution.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/screen_dimmer_rules.py agent_skills/screen_dimmer.py tests/test_screen_dimmer_rules.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_screen_dimmer_rules.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`646 passed`).

Remaining follow-up slices:
- Keep monitor mutation and HTTP retry behavior in `screen_dimmer.py` unless subprocess/request fakes are added.
- If multiple location support is added later, the helper can absorb location-independent brightness rules.

## 2026-07-02 - Job Queue Pending Summary Helpers

Goal/scope:
- Move pending-job number/title/priority summary extraction and priority+number sorting into `job_queue_docs.py`.
- Wire `run_queue_next.py` and `check_continuation.py` through the shared helper while leaving directory scans, idle checks, active-queue checks, and JSON outputs in place.

Files/modules changed:
- `agent_skills/job_queue_docs.py`
- `agent_skills/run_queue_next.py`
- `agent_skills/check_continuation.py`
- `tests/test_job_queue_docs.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Both small queue scripts still skip non-Markdown files and `README.md`.
- Pending status detection still uses the first status word.
- Priority values still map through `PRIORITY_MAP`, defaulting to low priority.
- Jobs missing `# Job:` in `run_queue_next.py` and `check_continuation.py` still use the filename, including the `.md` suffix, as their legacy title fallback.
- Queue ordering remains priority first, then filename job number.

Boundary chosen:
- Job Markdown parsing and queue-display summary selection are pure transforms over file text and names.
- The scripts remain responsible for filesystem traversal, idle/queue-state policy, and command output.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/job_queue_docs.py agent_skills/run_queue_next.py agent_skills/check_continuation.py tests/test_job_queue_docs.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_job_queue_docs.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`641 passed`).

Remaining follow-up slices:
- `job_queue_runner.py` intentionally keeps its simpler priority-only sort; changing that would be behavior, not just extraction.
- Further queue refactors should target side-effect seams only after adding filesystem fixtures.

## 2026-07-02 - Ambient Heartbeat Spec Rules

Goal/scope:
- Move heartbeat cache freshness, research-note block/insertion rules, unanswered-open-question detection, and Phase 1 task readiness parsing out of `ambient_heartbeat.py`.
- Keep idle detection, web search, automation synthesis, spec file reads/writes, task implementation calls, completion marking, sleep pacing, load gates, and Discord notification in `ambient_heartbeat.py`.

Files/modules changed:
- `agent_skills/ambient_heartbeat_rules.py`
- `agent_skills/ambient_heartbeat.py`
- `tests/test_ambient_heartbeat_rules.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Research notes are still inserted immediately after the matched heading, with the same dated block shape and duplicate-date guard.
- Missing headings still append a `### Research: ...` section to the end of the spec.
- Cache staleness still uses day-based age comparison against `last_researched`.
- Phase 1 readiness still returns unchecked Phase 1 tasks only when no unanswered open questions remain.

Behavior intentionally fixed:
- Open Questions detection now accepts numbered headings such as the current `## 10. Open Questions (Must Answer Before Coding)` instead of only `## 8. Open Questions`.
- Real-spec check now finds 47 unanswered questions and returns 0 ready implementation tasks, preventing premature automation runs.

Boundary chosen:
- Spec text transforms and readiness gates are deterministic and can be tested without web search, model calls, file mutation, or Discord notifications.
- The heartbeat script remains responsible for live orchestration and side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ambient_heartbeat_rules.py agent_skills/ambient_heartbeat.py tests/test_ambient_heartbeat_rules.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ambient_heartbeat_rules.py -q` passed (`6 passed`).
- Real spec check found `47` unanswered open questions, `0` Phase 1 unchecked tasks, and `0` ready implementation tasks.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`639 passed`).

Remaining follow-up slices:
- `ambient_heartbeat.py` still has live automation and spec mutation responsibilities; avoid moving those without file/runner fakes.
- If Ambient spec sections are renumbered again, the helper tests cover heading-number independence.

## 2026-07-02 - Ambient Task Research Rules

Goal/scope:
- Move Progress Tracker parsing, task cache key generation, cache staleness checks, and search-query context classification out of `ambient_task_research.py`.
- Keep spec file reads, cache file reads/writes, web search, OpenAI synthesis, Discord notification, sleep pacing, load gates, idle checks, and cron flow in `ambient_task_research.py`.

Files/modules changed:
- `agent_skills/ambient_task_research_rules.py`
- `agent_skills/ambient_task_research.py`
- `tests/test_ambient_task_research_rules.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Task rows are still returned as `{"phase": ..., "task": ...}` dictionaries.
- Phase labels still come from `###` headings, and tasks before a phase still use `Unknown Phase`.
- Cache keys, seven-day stale behavior, invalid-cache fallback, and search-query context ordering preserve the existing script semantics.

Behavior intentionally fixed:
- Progress Tracker detection now accepts numbered headings such as the current `## 11. Progress Tracker`; the script was still looking specifically for `## 9. Progress Tracker`.
- Current real-spec extraction now finds 37 unchecked tasks.

Boundary chosen:
- Spec parsing and cache/query policy are deterministic transforms that can be tested without reading project files, touching the cache, searching the web, or calling OpenAI.
- The original script remains responsible for all live I/O, model calls, notifications, and pacing.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ambient_task_research_rules.py agent_skills/ambient_task_research.py tests/test_ambient_task_research_rules.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ambient_task_research_rules.py -q` passed (`6 passed`).
- Real spec check via `extract_unchecked_tasks()` found `37` unchecked tasks.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`633 passed`).

Remaining follow-up slices:
- Similar rules in `ambient_heartbeat.py` are candidates, especially implementation-readiness parsing, but spec writes and automation prompts should stay in that script.
- Any future Ambient research behavior changes should land in the helper first with text-level tests.

## 2026-07-02 - Process Watchdog Policy Helpers

Goal/scope:
- Move Docker runtime parsing, old-container checks, Docker ps row parsing, and protected-command matching out of `process_watchdog.py`.
- Keep Docker process listing, Docker kill/remove calls, `pgrep`/`ps` calls, `os.kill`, sleep/retry behavior, logging, and cron entrypoint flow in `process_watchdog.py`.

Files/modules changed:
- `agent_skills/process_watchdog_policy.py`
- `agent_skills/process_watchdog.py`
- `tests/test_process_watchdog_policy.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `process_watchdog.py` still exposes `_parse_minutes` as a compatibility alias.
- Minute/hour/second Docker duration strings still map to the same cleanup decisions.
- Process protection still uses case-insensitive substring matching against `PROTECTED_NAMES`.

Behavior intentionally tightened:
- Docker TTS containers reported as running for days, weeks, months, or years now count as older than the max-age threshold instead of being ignored.
- Docker `About a minute` and `Less than a second` strings are handled explicitly.

Boundary chosen:
- Runtime age parsing and protection checks are deterministic policy decisions that can be tested without invoking Docker or sending process signals.
- The watchdog module remains responsible for destructive cleanup actions and live process inspection.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/process_watchdog_policy.py agent_skills/process_watchdog.py tests/test_process_watchdog_policy.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_process_watchdog_policy.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`627 passed`).

Remaining follow-up slices:
- Parsing `ps aux` rows could be extracted later, but the payoff is smaller unless malformed process rows are observed in logs.
- Keep kill/escalation behavior in `process_watchdog.py` unless process and Docker subprocess fakes are added.

## 2026-07-02 - System Load Policy Helpers

Goal/scope:
- Move system-load policy decisions and one-line formatting out of `system_load.py`.
- Keep live CPU/memory/GPU sampling, psutil fallback handling, subprocess calls, cache I/O, waiting, CLI behavior, and logging in `system_load.py`.

Files/modules changed:
- `agent_skills/system_load_policy.py`
- `agent_skills/system_load.py`
- `tests/test_system_load_policy.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `system_load.py` still exposes the private helper aliases used by existing callers/tests.
- Nighttime-window calculation, recommended parallelism, defer reason priority, ample-resource checks, load summary text, and cached hook oneline text keep the existing shapes.
- Runtime sampling still happens through `get_system_load()` and the public functions still make their own fresh readings as before.

Boundary chosen:
- Resource policy over an already-collected load dictionary is deterministic and testable without sleeping, calling `psutil`, or shelling out to `nvidia-smi`.
- The original module remains responsible for live system inspection, cache reads/writes, sleep/retry behavior, and CLI output.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/system_load_policy.py agent_skills/system_load.py tests/test_system_load_policy.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_system_load_policy.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`622 passed`).

Remaining follow-up slices:
- Keep live load sampling and hook cache logic in `system_load.py`; further extraction there is low payoff unless callers need injectable sampling.
- Similar daemon scripts are worth refactoring only when their decision rules can be tested apart from subprocess and filesystem side effects.

## 2026-07-02 - Docker Mount Safety Helpers

Goal/scope:
- Move Docker allowed-mount base calculation and host-path containment checks out of `safe_docker.py`.
- Keep Docker command construction, resource flags, concurrency lock, timeout handling, and force-kill cleanup in `safe_docker.py`.

Files/modules changed:
- `agent_skills/docker_safety.py`
- `agent_skills/safe_docker.py`
- `tests/test_docker_safety.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `safe_docker.py` still exposes `_ALLOWED_MOUNT_BASES`, `_allowed_mount_bases`, `_is_safe_mount_path`, and `_is_safe_mount`.
- Default allowed bases still come from `VESSENCE_HOME`, `VESSENCE_DATA_HOME`, and `VAULT_HOME`, with the same fallback paths.
- A mount is still allowed only when its real path equals an allowed base or is inside one.

Boundary chosen:
- Mount containment is pure security policy and is best tested without invoking Docker.
- The runner remains responsible for subprocess execution and cleanup behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/docker_safety.py agent_skills/safe_docker.py tests/test_docker_safety.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_docker_safety.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`615 passed`).

Remaining follow-up slices:
- Docker command execution and timeout cleanup should stay in `safe_docker.py` unless subprocess fakes are added.
- Other resource scripts should prioritize pure policy checks over subprocess-heavy cleanup paths.

## 2026-07-02 - Audit Report Summary Helpers

Goal/scope:
- Move audit notification brief extraction and nightly audit health-summary extraction into a shared helper module.
- Keep audit report loading, latest-summary writes, announcement writes, state tracking, and automation-runner orchestration in the original scripts.

Files/modules changed:
- `agent_skills/audit_report_helpers.py`
- `agent_skills/nightly_audit.py`
- `agent_skills/notify_audit_results.py`
- `tests/test_audit_report_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `nightly_audit.py` and `notify_audit_results.py` still expose the same private helper names via imports.
- Notification briefs still strip Markdown heading lines, collapse excessive blank lines, and cap at 2200 characters with an ellipsis.
- Health summaries still prefer the `Health Summary` section, stop at the next heading/table heading, cap at 280 characters, and fall back to the first non-empty line.

Boundary chosen:
- Report text shaping is pure and shared by audit notification workflows.
- The scripts remain responsible for filesystem state, recency checks, and announcement side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/audit_report_helpers.py agent_skills/nightly_audit.py agent_skills/notify_audit_results.py tests/test_audit_report_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_audit_report_helpers.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`611 passed`).

Remaining follow-up slices:
- Audit file discovery and announcement writes should stay in the scripts unless filesystem fixtures are added.
- The shared helper can absorb future audit summary formatting rules without touching notifier/orchestrator code.

## 2026-07-02 - Job Queue View Helpers

Goal/scope:
- Move job queue display-row parsing, priority/status labels, priority sorting constants, and Markdown table rendering out of `show_job_queue.py`.
- Keep defaults-file reads, queue directory scans, completed-job loading, CLI argument handling, and JSON output in `show_job_queue.py`.

Files/modules changed:
- `agent_skills/job_queue_view.py`
- `agent_skills/show_job_queue.py`
- `tests/test_job_queue_view.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `show_job_queue.py` still exposes the same label/sort/icon constants and helper aliases via imports.
- Display parsing still reads `# Job:`, `Status:`, `Priority:`, first Objective line, first Result line, and filename number prefixes.
- Pending jobs still show `Awaiting execution`; completed jobs still show the result text.
- Markdown output still respects configured columns and uses the same job count/plural wording.

Boundary chosen:
- Job queue display parsing and table rendering are pure view transforms over Markdown text and loaded queue data.
- The script remains responsible for filesystem reads and CLI output mode.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/job_queue_view.py agent_skills/show_job_queue.py tests/test_job_queue_view.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_job_queue_view.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`607 passed`).

Remaining follow-up slices:
- Queue directory scans and defaults-file reads are low payoff to extract without filesystem fixtures.
- Job queue display and runner now share tested document/view helpers.

## 2026-07-02 - Essence Scheduler Cron Matcher

Goal/scope:
- Move the essence scheduler's five-field cron matcher out of `essence_scheduler.py`.
- Keep state-file I/O, user-idle checks, resource gates, job loading, subprocess execution, and lock-file behavior in the scheduler.

Files/modules changed:
- `agent_skills/cron_schedule.py`
- `agent_skills/essence_scheduler.py`
- `tests/test_cron_schedule.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The scheduler still exposes `_matches_schedule` via import.
- Wildcards, exact fields, comma lists, ranges, step syntax, and cron weekday conversion still match the existing semantics.
- Invalid field counts still return `False`.

Behavior intentionally tightened:
- Invalid numeric fields and zero/negative step values now return `False` instead of being able to raise out of the scheduler loop.

Boundary chosen:
- Cron field matching is deterministic scheduling policy and can be tested with fixed datetimes.
- The scheduler remains responsible for filesystem, resource, idle, and subprocess side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/cron_schedule.py agent_skills/essence_scheduler.py tests/test_cron_schedule.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_cron_schedule.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`603 passed`).

Remaining follow-up slices:
- Scheduler job execution should stay in `essence_scheduler.py` unless subprocess/filesystem fixtures are added.
- Small daemon scripts are worth refactoring only where parsing rules can be isolated and tested.

## 2026-07-02 - Marketplace Listing Rules

Goal/scope:
- Move Marketplace query slugging, vehicle year parsing, mileage parsing, and implausibly-low-mileage suspicion checks out of the Playwright harvester.
- Keep browser scraping, listing detail navigation, photo downloads, filesystem writes, and saved-search orchestration in `harvester.py`.

Files/modules changed:
- `agent_skills/marketplace/listing_rules.py`
- `agent_skills/marketplace/harvester.py`
- `tests/test_marketplace_listing_rules.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The harvester still exposes the same private helper names via imports.
- Year parsing still accepts 1900s and 2000-2029 vehicle years.
- Mileage parsing still handles comma-separated miles, `k` mileage, plain 4-6 digit miles, `mileage` labels, and `driven` labels.
- Mileage values outside `100..600000` are still ignored.
- Suspicion filtering still flags cars older than five years with average mileage below 3000 miles/year.

Boundary chosen:
- Listing parsing and suspicion scoring are deterministic filter rules that decide which Marketplace results survive.
- The harvester remains responsible for Playwright, network, and output directory side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/marketplace/listing_rules.py agent_skills/marketplace/harvester.py tests/test_marketplace_listing_rules.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_marketplace_listing_rules.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`600 passed`).

Remaining follow-up slices:
- Harvester browser flow should stay intact unless Playwright fixtures are introduced.
- Similar marketplace rules should be extracted only when they can be characterized without live Facebook pages.

## 2026-07-02 - Job Queue Document Helpers

Goal/scope:
- Move job Markdown parsing, status/result section rendering, prompt section extraction, and self-continuation instruction rendering out of `job_queue_runner.py`.
- Keep idle checks, job directory scanning, file writes, Jane API calls, announcements, archive calls, and memory logging in the runner.

Files/modules changed:
- `agent_skills/job_queue_docs.py`
- `agent_skills/job_queue_runner.py`
- `tests/test_job_queue_docs.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The runner still exposes `PRIORITY_MAP`, `SELF_CONTINUATION_INSTRUCTION`, and helper aliases via imports.
- Job parsing still reads `# Job:`, first status word, and mapped priority values, falling back to filename/unknown/low priority.
- Status updates still replace the first `Status:` line and add or replace `## Result`.
- Prompt construction still includes Objective, Context, Steps, Verification, Files Involved, and Notes sections when present, then appends the same self-continuation instructions.

Boundary chosen:
- Job Markdown transforms are pure and easy to verify without touching the queue directory or Jane API.
- The runner remains responsible for runtime state, network calls, announcements, and archival side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/job_queue_docs.py agent_skills/job_queue_runner.py tests/test_job_queue_docs.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_job_queue_docs.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`596 passed`).

Remaining follow-up slices:
- Queue execution and announcement writes should stay in `job_queue_runner.py` unless service/API fakes are added.
- Other queue-like scripts should use document-transform helpers before touching side-effectful runners.

## 2026-07-02 - Message Readback Helper Module

Goal/scope:
- Move TalkingPoints URL detection, wrapper detection, untrusted readback sanitization/truncation, URL-safe base64 deeplink decoding, recursive TalkingPoints message extraction, text cleanup, and error-message detection out of `message_readback.py`.
- Keep TalkingPoints network resolution, requests headers, cache I/O, and SMS enrichment orchestration in `message_readback.py`.

Files/modules changed:
- `jane_web/message_readback_helpers.py`
- `jane_web/message_readback.py`
- `tests/test_message_readback_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `message_readback.py` still exposes the same private helper names via imports.
- TalkingPoints wrapper URLs and notification wrapper text use the same regexes.
- Readback sanitization still strips client-tool markers and neutralizes `[MUSIC_PLAY:` markers.
- Base64 deeplink decoding still accepts only decoded values containing `_$_`.
- Recursive TalkingPoints extraction still returns `Teacher: message` from nested dict/list structures and ignores known error messages.

Boundary chosen:
- Parsing and sanitizing untrusted message readback text are pure safety-critical transformations.
- The original module remains responsible for network calls, static page scraping, cache TTLs, and enrichment flow.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/message_readback_helpers.py jane_web/message_readback.py tests/test_message_readback_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_message_readback_helpers.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`592 passed`).

Remaining follow-up slices:
- TalkingPoints network resolution should stay in `message_readback.py` unless HTTP fixtures are added.
- Similar untrusted-text sanitizer helpers should be preferred over broad route-level rewrites.

## 2026-07-02 - Short-Term Turn-Kind Classifier

Goal/scope:
- Move the short-term memory turn-kind regex table and classifier out of `short_term_extractor.py`.
- Keep extraction prompts, LLM invocation, structured parsing, and `build_short_term_note()` orchestration in the extractor.

Files/modules changed:
- `memory/v1/turn_kind.py`
- `memory/v1/short_term_extractor.py`
- `tests/test_turn_kind.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The extractor still exposes `_TURN_KIND_PATTERNS` and `classify_turn_kind` via imports.
- The classifier still scores only the first 4000 characters.
- Calendar, messages, todo, debugging, and code patterns keep the same order and tie behavior.
- Empty or unmatched turns still classify as `general`.

Boundary chosen:
- Turn-kind classification is deterministic memory-routing logic and can be tested without LLM calls.
- The extractor remains responsible for prompt construction and structured note orchestration.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/turn_kind.py memory/v1/short_term_extractor.py tests/test_turn_kind.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_turn_kind.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`586 passed`).

Remaining follow-up slices:
- Extraction prompt templates can stay in `short_term_extractor.py` because they are tightly coupled to the LLM task.
- Additional memory refactors should focus on deterministic retrieval/ranking helpers rather than Chroma orchestration.

## 2026-07-02 - Short-Term Memory Structured Helpers

Goal/scope:
- Move structured short-term memory extraction keys, tolerant JSON parsing, empty extraction construction, skip gating, labeled note rendering, search-text rendering, and Chroma metadata flattening out of `short_term_extractor.py`.
- Keep turn-kind classification, extraction prompt construction, LLM invocation, and top-level `build_short_term_note()` orchestration in `short_term_extractor.py`.

Files/modules changed:
- `memory/v1/short_term_structured.py`
- `memory/v1/short_term_extractor.py`
- `tests/test_short_term_structured.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The extractor still exposes the same helper names via imports.
- JSON parsing still strips Markdown fences, finds the first object, tolerates single-string fields, stringifies list items, and drops unsupported values.
- Notes are still kept only when decisions, open loops, or artifacts exist.
- Note/search text flattening still follows the same category order.
- Metadata still stores primitive flags, counts, and first-eight joined artifact/person/time strings.

Boundary chosen:
- JSON normalization and Chroma-facing flattening are deterministic and central to memory quality.
- The extractor remains responsible for classification, prompt text, LLM failure handling, and final write/skip orchestration.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/short_term_structured.py memory/v1/short_term_extractor.py tests/test_short_term_structured.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_short_term_structured.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`582 passed`).

Remaining follow-up slices:
- Turn-kind classification could be tested separately, but extraction prompt and LLM orchestration should stay in the extractor.
- Memory manager stateful Chroma paths should only be changed with integration fixtures.

## 2026-07-02 - Greeting Canned Reply Helpers

Goal/scope:
- Move canned greeting reply tables, canned greeting regexes, deterministic canned-reply selection, `WRONG_CLASS` detection, and `Jane:` prefix cleanup out of the Stage 2 greeting handler.
- Keep local qwen prompting, Ollama calls, and handler escalation in `handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/greeting/canned.py`
- `jane_web/jane_v2/classes/greeting/handler.py`
- `tests/test_greeting_canned.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The handler still exposes the same private helper names via imports.
- Common check-ins, bare hellos, time-of-day greetings, and thanks still use canned replies.
- Non-greeting prompts that include a task still fall through to the LLM path.
- `WRONG_CLASS` still escalates, and leading `Jane:` self-attribution is still stripped.

Boundary chosen:
- Greeting fast-path matching and text cleanup are pure and testable with an injected chooser.
- The handler remains responsible for local LLM confirmation and response generation.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/greeting/canned.py jane_web/jane_v2/classes/greeting/handler.py tests/test_greeting_canned.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_greeting_canned.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`576 passed`).

Remaining follow-up slices:
- Greeting's qwen fallback should stay in the handler unless LLM response fixtures are added.
- Most remaining small Stage 2 handlers are now low payoff unless they contain rule-heavy fast paths.

## 2026-07-02 - Shopping List Action Helpers

Goal/scope:
- Move shopping-list action constants, comma-separated item splitting, destructive-action confidence validation, present/missing checks, and check-response formatting out of the Stage 2 shopping-list handler.
- Keep `agent_skills.shopping_list` imports, JSON-store mutations, and action dispatch in `handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/shopping_list/actions.py`
- `jane_web/jane_v2/classes/shopping_list/handler.py`
- `tests/test_shopping_list_actions.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The handler still exposes the same private helper names via imports.
- Add/remove/check item parsing still accepts comma-separated strings only and ignores blanks.
- Remove/clear still reject bool, non-numeric, non-finite, and `< 0.80` confidence values.
- Check responses keep the existing yes/no/mixed wording.

Boundary chosen:
- Item parsing, confidence thresholding, and check-response formatting are pure and security-adjacent.
- The handler remains responsible for shopping-list storage calls and mutation ordering.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/shopping_list/actions.py jane_web/jane_v2/classes/shopping_list/handler.py tests/test_shopping_list_actions.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_shopping_list_actions.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`572 passed`).

Remaining follow-up slices:
- Further shopping-list extraction is not worthwhile without storage fakes.
- Small Stage 2 handlers should now be skipped unless they carry deterministic rules worth testing.

## 2026-07-02 - Music Playlist Matching Helpers

Goal/scope:
- Move music-play actionable kind constants, playlist-name normalization, exact/substring/fuzzy playlist candidate selection, and play-response marker formatting out of the Stage 2 music handler.
- Keep vault playlist reads, playlist ID lookup, v1 library scanning, and handler escalation policy in `handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/music_play/matching.py`
- `jane_web/jane_v2/classes/music_play/handler.py`
- `tests/test_music_play_matching.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The handler still exposes the same private helper names via imports.
- Existing playlist matching still tries exact normalized name first, substring containment second, then optional RapidFuzz `token_set_ratio` at score `>= 80`.
- Empty queries and empty candidate lists still produce no match.
- Play responses still include `Playing <name> (<n> tracks).` and append `[MUSIC_PLAY:<id>]` only when a playlist ID exists.

Boundary chosen:
- Matching and response formatting are pure transformations over playlist dictionaries.
- The handler remains responsible for imports from `vault_web`, database/filesystem-backed playlist reads, and v1 ephemeral playlist generation.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/music_play/matching.py jane_web/jane_v2/classes/music_play/handler.py tests/test_music_play_matching.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_music_play_matching.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`567 passed`).

Remaining follow-up slices:
- Vault-backed playlist reads should stay in the handler unless playlist-store fakes are added.
- Very small handlers now need stricter payoff checks before extraction.

## 2026-07-02 - Get Time Helper Module

Goal/scope:
- Move direct time/date fast-path regexes, local time/date reply formatting, LLM prompt construction, time-info formatting, and THOUGHT/REPLY parsing out of the Stage 2 get-time handler.
- Keep local qwen invocation, latency logging, fallback on LLM failure, and response object construction in `handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/get_time/time_helpers.py`
- `jane_web/jane_v2/classes/get_time/handler.py`
- `tests/test_get_time_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The handler still exposes the same private helper names via imports.
- Plain time/date prompts still bypass qwen and return direct local-clock answers.
- Contextual prompts such as `is it late?` still fall through to the LLM path.
- Prompt construction still includes the current time block, recent FIFO context or an empty marker, and the same THOUGHT/REPLY instructions.
- LLM response parsing still prefers the `REPLY:` field and falls back to the raw response or time-info fallback.

Behavior intentionally tightened:
- The fast date regex now matches `what day of the week is it`, which the handler comment already claimed but the old pattern missed.

Boundary chosen:
- Fast-path intent matching, time formatting, prompt text construction, and model-output parsing are pure with injected clocks/test strings.
- The handler remains responsible for the external LLM call and final Stage 2 response shape.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/get_time/time_helpers.py jane_web/jane_v2/classes/get_time/handler.py tests/test_get_time_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_get_time_helpers.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`562 passed`).

Remaining follow-up slices:
- The LLM call wrapper should stay in the handler unless shared Ollama-client fixtures are introduced.
- Smaller Stage 2 handlers should only be split further if they contain meaningful pure logic, not just route orchestration.

## 2026-07-02 - Do Math Evaluator Module

Goal/scope:
- Move restricted AST evaluation, expression-line extraction, and numeric result formatting out of the Stage 2 math handler.
- Keep local qwen expression translation, latency logging, and Stage 2 escalation decisions in `handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/do_math/evaluator.py`
- `jane_web/jane_v2/classes/do_math/handler.py`
- `tests/test_do_math_evaluator.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The handler still exposes the same private helper names and `safe_eval` via imports.
- Arithmetic still allows numeric constants, basic binary operators, unary plus/minus, and the existing safe calls: `sqrt`, `pow`, `abs`, `round`, `floor`, and `ceil`.
- Expression extraction still accepts `EXPRESSION:` lines, whole-reply fallback, fenced one-liners, `NONE`, and trailing comments.
- Number formatting still keeps ints comma-formatted, trims floats to four decimals, and preserves very small non-zero values with compact precision.

Behavior intentionally tightened:
- Boolean literals are now rejected as non-numeric constants. Python treats `bool` as an `int` subclass, but `True` and `False` are not arithmetic literals for this handler.

Boundary chosen:
- The evaluator is deterministic and security-sensitive, so it belongs in a small directly tested module.
- The handler remains responsible for the LLM parse call and user-facing reply construction.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/do_math/evaluator.py jane_web/jane_v2/classes/do_math/handler.py tests/test_do_math_evaluator.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_do_math_evaluator.py -q` passed (`12 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`557 passed`).

Remaining follow-up slices:
- The LLM expression prompt should stay in the handler unless mocked qwen extraction fixtures are added.
- `get_time` has a similar pure fast-path parser worth evaluating next.

## 2026-07-02 - Weather Slice Helpers

Goal/scope:
- Move weather follow-up day parsing, forecast-day normalization, debug-field stripping, topic/day slice construction, day-reference derivation, and day-reference safety prepending out of the Stage 2 weather handler.
- Keep weather cache reads, local qwen phrasing, follow-up pending-action construction, and escalation policy in `handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/weather/slices.py`
- `jane_web/jane_v2/classes/weather/handler.py`
- `tests/test_weather_slices.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The handler still exposes the same private helper names via imports.
- Follow-up replies still map `day after tomorrow`, `tomorrow`, `today`, `tonight`, week/weekend phrases, and weekdays the same way.
- Forecast-day matching still accepts today, tomorrow, weekdays, ISO dates, and treats week/weekend specs as multi-day.
- Weather slices still slim forecast, precipitation, wind, current, overview, air-quality, and pollen payloads before qwen phrasing.
- Non-neutral day references are still prepended when qwen omits them.

Boundary chosen:
- Day parsing and slice construction are deterministic transformations over cached weather JSON.
- The handler remains responsible for cache I/O, qwen calls, and conversation follow-up state.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/weather/slices.py jane_web/jane_v2/classes/weather/handler.py tests/test_weather_slices.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_weather_slices.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`545 passed`).

Remaining follow-up slices:
- Weather qwen prompt/response behavior should stay in the handler unless response fixtures are added.
- Cache freshness and non-Medford escalation are route-policy concerns, not helper logic.

## 2026-07-02 - Read Calendar Formatting Helpers

Goal/scope:
- Move read-calendar range resolution, event time formatting, event-list simplification, event matching, and event-detail block rendering out of the Stage 2 calendar handler.
- Keep Google Calendar fetching, local qwen phrasing, pending-action loops, and escalation decisions in `handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/read_calendar/formatting.py`
- `jane_web/jane_v2/classes/read_calendar/handler.py`
- `tests/test_read_calendar_formatting.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The handler still exposes the same private helper names via imports.
- Stage 2 still only accepts explicit day/week prompts such as `today`, `tonight`, weekdays, `this week`, and `next week`.
- Event summaries still include the deterministic count, day labels, natural times, and all-day fallback.
- Event detail matching still prefers numeric choices, then summary-keyword overlap.
- Detail blocks still include event name, day, time/end time, and a 300-character description cap.

Boundary chosen:
- Calendar range and event formatting are pure transformations over event dictionaries.
- The handler remains responsible for external calendar access, local LLM calls, and multi-turn pending state.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/read_calendar/formatting.py jane_web/jane_v2/classes/read_calendar/handler.py tests/test_read_calendar_formatting.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_read_calendar_formatting.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`539 passed`).

Remaining follow-up slices:
- Calendar API fetching and qwen phrasing should stay in the handler unless test doubles are added.
- Pending follow-up transitions may be testable later, but they require confirmation/end-phrase fixtures.

## 2026-07-02 - Clinic Schedule Helper Module

Goal/scope:
- Move clinic schedule time parsing/formatting, weekday normalization, current-time metadata, active/cancelled splitting, next-patient selection, and loader normalization out of the Stage 2 clinic schedule handler.
- Keep SQLite access, per-loader fact builders, patient lookup, pending-action routing, and local qwen reply phrasing in `handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/clinic_schedules_info/schedule_helpers.py`
- `jane_web/jane_v2/classes/clinic_schedules_info/handler.py`
- `tests/test_clinic_schedule_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The handler still exposes the same private helper names via imports.
- `today` and `tomorrow` still resolve against the current local day by default.
- Active patient indexes still skip cancelled rows and keep one-based visible numbering.
- The next-patient calculation still includes appointments up to 15 minutes late.
- Unknown loaders still fall back to `today_overview`, while patient name/index parameters force `patient_detail`.

Behavior intentionally tightened:
- `parse_time()` now accepts both scraped compact suffixes like `9:15a` and the handler-formatted values like `9:15am`, so next-patient selection can parse the times produced by `_fetch_day_rows()`.

Boundary chosen:
- The extracted helpers are deterministic transformations with optional clock injection for tests.
- The handler remains the owner of local-only schedule database reads and local LLM phrasing.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/clinic_schedules_info/schedule_helpers.py jane_web/jane_v2/classes/clinic_schedules_info/handler.py tests/test_clinic_schedule_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_clinic_schedule_helpers.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`534 passed`).

Remaining follow-up slices:
- Clinic SQL loaders can stay in the handler unless database fixtures are added.
- Local qwen prompt/reply phrasing is side-effectful and should not be split without response fixtures.

## 2026-07-02 - Send Message Parsing Helpers

Goal/scope:
- Move SMS body coherence checks, direct-send confidence validation, and LLM extraction-output parsing out of the Stage 2 send-message handler.
- Keep draft safety-net handling, contact resolution, alias writes, pending-action loops, and client-tool marker emission in `handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/send_message/parsing.py`
- `jane_web/jane_v2/classes/send_message/handler.py`
- `tests/test_send_message_parsing.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The handler still exposes the same private helper names via imports.
- Missing SMS bodies still count as coherent intent and use `(none)`.
- Dangling ending words, filler words, and background device commands still make extracted bodies incoherent.
- `WRONG_CLASS` extraction output still returns the shared sentinel.
- Direct send still requires non-bool numeric confidence of at least `0.80`.

Boundary chosen:
- Parsing qwen output and judging text coherence are pure and deterministic.
- The handler now focuses more clearly on state transitions, contact lookup, alias persistence, and SMS side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/send_message/parsing.py jane_web/jane_v2/classes/send_message/handler.py tests/test_send_message_parsing.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_send_message_parsing.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`528 passed`).

Remaining follow-up slices:
- Send-message draft safety-net logic is side-effectful and should stay in the handler unless recent-turn FIFO state is faked.
- Contact resolution and alias writes should stay behind the existing helper boundary.

## 2026-07-02 - TODO List Category Helpers

Goal/scope:
- Move TODO-list category normalization, visible-category filtering, fuzzy category matching, friendly names, item speech, and category-list speech out of the Stage 2 TODO handler.
- Keep edit execution, Google Docs mutations, cache refresh, pending-action state, and response construction in `handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/todo_list/categories.py`
- `jane_web/jane_v2/classes/todo_list/handler.py`
- `tests/test_todo_list_categories.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The handler still exposes the same private helper names via imports.
- Category aliases, short-reply alias matching, numeric and word ordinal matching, hidden internal categories, friendly category names, and spoken list formats stay centralized behind the same call sites.
- Internal `Ambient project goals` and `Jane` categories remain hidden from this Stage 2 handler.

Behavior intentionally tightened:
- `normalize()` now trims whitespace after removing a leading BOM, so copied category text like `\ufeff Clinic!!` normalizes to `clinic` instead of leaving a leading space.

Boundary chosen:
- Category matching and speech formatting are deterministic and independent of Google Docs edits or pending-action follow-up state.
- The TODO handler now separates category interpretation from request parsing and side-effect execution.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/todo_list/categories.py jane_web/jane_v2/classes/todo_list/handler.py tests/test_todo_list_categories.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_todo_list_categories.py tests/test_todo_list_parsing.py -q` passed (`12 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`521 passed`).

Remaining follow-up slices:
- TODO pending-action response builders are still in the handler because they are tightly coupled to structured payloads.
- Google Docs edit execution should stay in the handler unless docs_tools is faked in tests.

## 2026-07-02 - TODO List Edit Parsing Helpers

Goal/scope:
- Move TODO-list edit intent detection, placeholder item detection, and add/remove item text extraction out of the Stage 2 TODO handler.
- Keep category matching, Google Docs edits, cache refresh, follow-up state, and response construction in `handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/todo_list/parsing.py`
- `jane_web/jane_v2/classes/todo_list/handler.py`
- `tests/test_todo_list_parsing.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The handler still exposes the same private helper names via imports.
- Add/remove intent patterns still detect the same request forms.
- Quoted item extraction, `item is ...` extraction, colon extraction, `add X to my ...`, and remove-item extraction keep their current behavior.
- Placeholder filtering remains a caller-level step after extraction, matching the existing handler flow.

Boundary chosen:
- Edit parsing is deterministic and independent of Google Docs mutations or pending-action state.
- The TODO handler now separates request text parsing from category matching and side-effect execution.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/todo_list/parsing.py jane_web/jane_v2/classes/todo_list/handler.py tests/test_todo_list_parsing.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_todo_list_parsing.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`514 passed`).

Remaining follow-up slices:
- TODO category matching and spoken-list formatting are still pure enough to extract separately.
- Google Docs edit execution should stay in the handler unless docs_tools is faked in tests.

## 2026-07-02 - Timer Handler Parsing Helpers

Goal/scope:
- Move timer duration parsing, label extraction, pretty-duration formatting, delete-target parsing, label-reply parsing, and new-timer restart detection out of the Stage 2 timer handler.
- Keep pending-action construction, follow-up state flow, CLIENT_TOOL marker emission, and handler dispatch in `handler.py`.

Files/modules changed:
- `jane_web/jane_v2/classes/timer/parsing.py`
- `jane_web/jane_v2/classes/timer/handler.py`
- `tests/test_timer_parsing.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The handler still exposes the same private helper names via imports.
- Duration parsing still handles half-hour phrases, `and a half` hours, compound hour/minute values, bare `an hour`/`a minute`, and non-matches.
- Label extraction, delete target parsing, label follow-up cleanup, and same-class new-timer restart detection keep their existing heuristics.
- No changes were made to timer pending actions, structured payloads, conversation-end behavior, or CLIENT_TOOL marker formats.

Boundary chosen:
- Natural-language timer parsing is pure and directly testable.
- The handler now reads as state/response orchestration over parser helpers.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/classes/timer/parsing.py jane_web/jane_v2/classes/timer/handler.py tests/test_timer_parsing.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_timer_parsing.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`509 passed`).

Remaining follow-up slices:
- Timer response builders could be tested later, but they are closely tied to pending-action payload shape and client-tool marker contracts.
- Other Stage 2 handlers with local parsers should be evaluated similarly before touching dispatch logic.

## 2026-07-02 - Code Map Static Indexers

Goal/scope:
- Move Python/HTML/Kotlin file indexers, skip rules, line counting, dispatch, and priority-entry capping out of `generate_code_map.py`.
- Keep repository walking, map section assembly, output-file writing, marker preservation, and CLI target selection in the generator.

Files/modules changed:
- `agent_skills/code_map_indexers.py`
- `agent_skills/generate_code_map.py`
- `tests/test_code_map_indexers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Existing indexer names remain available through `agent_skills.generate_code_map`.
- Python indexing still reports uppercase constants, route-decorated functions, async/sync functions, classes, and class methods.
- HTML indexing still detects Alpine-style methods and `event.type` checks.
- Kotlin indexing still detects classes, composables, functions, override/suspend prefixes, and uppercase constants.
- Skip rules and priority entry caps are unchanged.

Boundary chosen:
- Static file indexing is deterministic and testable with temporary files.
- The map generator now separates parsing rules from repo traversal and file-output concerns.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/code_map_indexers.py agent_skills/generate_code_map.py tests/test_code_map_indexers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_code_map_indexers.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`504 passed`).

Remaining follow-up slices:
- Map section assembly could be extracted later if generator output needs golden tests.
- Current traversal/output behavior should stay in the script because it depends on repo layout and generated config paths.

## 2026-07-02 - Transcript Review Formatting Helpers

Goal/scope:
- Move transcript-review condensed context construction and Codex report Markdown rendering out of `transcript_quality_review.py`.
- Keep log loading, Codex CLI invocation, vocal summary, report file writing, and frontier-provider fix execution in the script.

Files/modules changed:
- `agent_skills/transcript_review_format.py`
- `agent_skills/transcript_quality_review.py`
- `tests/test_transcript_review_format.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The script still exposes `_build_condensed_context` via import.
- User turns are still truncated to 300 chars, pipeline events to the most recent 500 lines, and Android events to the most recent 300 lines.
- Condensed context still appends `[TRUNCATED]` when the max character budget is exceeded.
- Empty and issue-bearing Codex reports keep the same headings, generated timestamp format, issue fields, and fenced log evidence.

Boundary chosen:
- Context/report formatting is pure and independent of log files, Codex execution, or code-fix side effects.
- The review script now separates collection/execution from formatting contracts that can be tested directly.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/transcript_review_format.py agent_skills/transcript_quality_review.py tests/test_transcript_review_format.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_transcript_review_format.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`499 passed`).

Remaining follow-up slices:
- Codex output JSON extraction could be extracted if more malformed-output tests are needed.
- The fixer stage should stay in the script because it is an external frontier-provider workflow.

## 2026-07-02 - Prompt Queue Document Helpers

Goal/scope:
- Move prompt-list Markdown parsing, status update rendering, delete/renumber transforms, and prompt summary truncation out of `prompt_queue_runner.py`.
- Keep idle checks, file I/O wrappers, Jane API calls, announcements, memory logging, Chroma cleanup, and process locking in the runner.

Files/modules changed:
- `agent_skills/prompt_queue_docs.py`
- `agent_skills/prompt_queue_runner.py`
- `tests/test_prompt_queue_docs.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `[new]` entries still parse as `pending`, legacy `[COMPLETE]`/`[INCOMPLETE]` tags still parse correctly, and body parsing still stops at old sub-bullets or `---`.
- Status updates still preserve prompt body text, drop old sub-bullets, and append the same completion/attempt note format.
- Delete plus renumber still removes an entry block and closes index gaps.
- Prompt summaries still cut on late sentence/line boundaries when possible and use the existing ellipsis markers.

Boundary chosen:
- Prompt-list document transforms are pure and easy to characterize.
- The runner now separates fragile Markdown manipulation from queue execution and external side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/prompt_queue_docs.py agent_skills/prompt_queue_runner.py tests/test_prompt_queue_docs.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_prompt_queue_docs.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`495 passed`).

Remaining follow-up slices:
- Archive rendering in `archive_completed_prompts()` could be extracted later, but it is coupled to Chroma cleanup and file writes.
- The queue runner's Jane API execution path should stay intact unless request/stream fixtures are added.

## 2026-07-02 - Facebook Marketplace Classification Rules

Goal/scope:
- Move Marketplace conversation dataclasses, title normalization, age parsing, sold/gone detection, and delete/keep classification out of the Playwright cleanup script.
- Keep Facebook navigation, scanning, deletion clicks, audit logging, and CLI options in `facebook_marketplace_message_cleanup.py`.

Files/modules changed:
- `agent_skills/facebook_marketplace_rules.py`
- `agent_skills/facebook_marketplace_message_cleanup.py`
- `tests/test_facebook_marketplace_message_cleanup.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Existing rule names remain available through `agent_skills.facebook_marketplace_message_cleanup`.
- Protected Honda Fit title matching still handles colon, middle-dot, and group-chat variants.
- Relative age parsing still handles minute/hour/day/week/month/year labels, month-day labels, and weekday labels.
- Sold/gone signals still delete completed conversations while `Is this sold?` questions stay kept.
- Protected titles still win over sold/stale delete signals.

Boundary chosen:
- Conversation classification is pure and independent of browser automation.
- The cleanup script now separates live Facebook UI operations from the rules deciding which conversations are safe delete candidates.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/facebook_marketplace_rules.py agent_skills/facebook_marketplace_message_cleanup.py tests/test_facebook_marketplace_message_cleanup.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_facebook_marketplace_message_cleanup.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`490 passed`).

Remaining follow-up slices:
- The remaining Marketplace cleanup code is mostly Playwright UI automation and should not be split further without browser fixtures.
- Similar browser scripts should first expose pure row parsing/classification boundaries before touching UI actions.

## 2026-07-02 - Nightly Report Summary Helpers

Goal/scope:
- Move pure Markdown/log summarizers out of `nightly_self_improve.py`.
- Keep job execution, subprocess timeouts, log reading, readable report file writes, archival copies, and vocal rollup in the orchestrator.

Files/modules changed:
- `agent_skills/nightly_report_summaries.py`
- `agent_skills/nightly_self_improve.py`
- `tests/test_nightly_report_summaries.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The orchestrator still uses the same private helper names via imports.
- Bullet normalization, Markdown section bullet extraction, field extraction, pipeline summaries, transcript-review severity summaries, and generic log summaries keep the same text output.
- No changes were made to nightly job order, timeout budgets, subprocess environment, report paths, or summary write behavior.

Boundary chosen:
- Summary extraction is deterministic text parsing and independent of subprocess execution or filesystem writes.
- The orchestrator is now closer to job scheduling/report assembly while the parsing rules are directly testable.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/nightly_report_summaries.py agent_skills/nightly_self_improve.py tests/test_nightly_report_summaries.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nightly_report_summaries.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`489 passed`).

Remaining follow-up slices:
- `nightly_self_improve.py` still has report file assembly and job detail wiring; those are lower payoff unless a pure report-builder boundary is introduced.
- Standalone Playwright/browser scripts may have better next refactor opportunities than the orchestrator.

## 2026-07-02 - Nutricost Deal Utility Module

Goal/scope:
- Move Nutricost-specific marketing detection, discount extraction, URL cleanup, and deal-link filtering out of `nutricost_deal_monitor.py`.
- Keep Gmail API reads, trashing, alert sending, daily cleanup policy, state persistence, and CLI flow in the monitor.

Files/modules changed:
- `agent_skills/nutricost_deal_utils.py`
- `agent_skills/nutricost_deal_monitor.py`
- `tests/test_nutricost_deal_utils.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Existing helper names remain available through `agent_skills.nutricost_deal_monitor`.
- Marketing detection still requires the Nutricost sender plus a bulk/marketing signal.
- Discount extraction still accepts percent/`percent` wording and ignores values outside `1..95`.
- Deal-link extraction still prefers Nutricost product links, filters unsubscribe/social/noisy links, deduplicates, and returns at most five links.
- URL cleanup still decodes HTML entities and trims trailing punctuation.

Boundary chosen:
- Nutricost deal parsing is deterministic and independent of Gmail side effects.
- The monitor now separates product-specific deal rules from message parsing and cleanup orchestration.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/nutricost_deal_utils.py agent_skills/nutricost_deal_monitor.py tests/test_nutricost_deal_utils.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nutricost_deal_utils.py tests/test_gmail_message_utils.py tests/test_gmail_cleanup_monitor.py -q` passed (`19 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`483 passed`).

Remaining follow-up slices:
- Gmail query builders are still pure and could move into a small query helper.
- The monitor's process functions now mostly coordinate Gmail reads, policy checks, and side effects; avoid splitting those further without a broader fake Gmail service.

## 2026-07-02 - Gmail Message Utility Module

Goal/scope:
- Move Gmail message/header/body/date/sender/calendar parsing helpers out of `nutricost_deal_monitor.py`.
- Keep Nutricost deal policy, cleanup policies, Gmail API calls, trashing, alert sending, state persistence, and CLI flow in the monitor.

Files/modules changed:
- `agent_skills/gmail_message_utils.py`
- `agent_skills/nutricost_deal_monitor.py`
- `tests/test_gmail_message_utils.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Existing helper names remain available through `agent_skills.nutricost_deal_monitor`.
- MIME text extraction still prefers `text/plain` parts over stripped HTML fallback.
- Sender-domain matching still accepts exact/subdomain matches and rejects similar unrelated domains such as `amazonses.com` for `amazon.com`.
- Message age checks still use `internalDate` in the New York timezone.
- Google Calendar cleanup still parses event end times from ICS parts or Google Calendar notification subjects.

Boundary chosen:
- Gmail message parsing is pure and reusable across cleanup policies.
- The monitor now reads more like policy/orchestration over message utilities and Gmail side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/gmail_message_utils.py agent_skills/nutricost_deal_monitor.py tests/test_gmail_message_utils.py tests/test_gmail_cleanup_monitor.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_gmail_message_utils.py tests/test_gmail_cleanup_monitor.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`478 passed`).

Remaining follow-up slices:
- Nutricost deal parsing and Gmail query builders are still pure enough to extract in smaller modules.
- The actual Gmail API process functions should stay in the monitor unless a broader fake-service fixture is added.

## 2026-07-02 - Google Cloud Receipt Helper Module

Goal/scope:
- Move Google Cloud Billing receipt dataclasses and pure date/amount/filename/sort helpers out of the browser automation script.
- Keep profile capture, billing-account selection, Playwright page scanning, downloads, manifest writing, and CLI behavior in `google_cloud_receipts.py`.

Files/modules changed:
- `agent_skills/google_cloud_receipt_utils.py`
- `agent_skills/google_cloud_receipts.py`
- `tests/test_google_cloud_receipts.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Existing imports from `agent_skills.google_cloud_receipts` still expose the receipt helper classes/functions.
- Receipt date parsing still supports full month, abbreviated month, ISO, and slash dates.
- Amount parsing still prefers currency-prefixed values and strips thousands separators.
- Filename, ISO-date validation, candidate sorting, and date-range filtering contracts are unchanged.

Boundary chosen:
- Receipt parsing and ranking are deterministic and independent of browser profile state, gcloud, and Playwright.
- The downloader script now separates pure receipt-model logic from live Google Cloud console automation.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/google_cloud_receipt_utils.py agent_skills/google_cloud_receipts.py tests/test_google_cloud_receipts.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_google_cloud_receipts.py -q` passed (`8 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`473 passed`).

Remaining follow-up slices:
- `google_cloud_receipts.py` is still browser-automation heavy; further extraction should target locator/discovery fixtures only if fake Playwright objects are introduced.
- `nutricost_deal_monitor.py` remains a stronger next target because its Gmail cleanup policy helpers are pure enough to isolate.

## 2026-07-02 - Education Homework Parser Module

Goal/scope:
- Move homework prompt/client-version/feedback parsing and displayed-response linting out of `edu_homework_audit.py`.
- Keep DB access, HTTP requests, grading control flow, report writing, and cleanup behavior in the audit script.

Files/modules changed:
- `agent_skills/edu_homework_parsers.py`
- `agent_skills/edu_homework_audit.py`
- `tests/test_edu_homework_parsers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Prompt parsing still returns raw `div.prompt` inner HTML plus visible text, or empty strings when missing.
- Client version parsing still returns the integer hidden-input value, or `0` for missing/bad values.
- Feedback parsing still maps `ok`/`warn`/`bad`/missing panels to `correct`/`stale|locked`/`incorrect`/`unknown` and extracts the rendered response after `Your answer:` or `You answered`.
- Displayed-response lint still flags answer-type leakage, empty rendered responses, and `(none)` rendered responses.

Boundary chosen:
- HTML fragment parsing and rendered-response linting are deterministic and independent of DB/HTTP/live grading.
- The audit runner now reads as orchestration over client calls, parsers, answer formatting, prompt linting, and report output.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/edu_homework_parsers.py agent_skills/edu_homework_audit.py tests/test_edu_homework_parsers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_edu_homework_parsers.py tests/test_edu_homework_lint.py tests/test_edu_homework_answers.py tests/test_edu_homework_report.py -q` passed (`12 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`472 passed`).

Remaining follow-up slices:
- `edu_homework_audit.py` is now mostly side-effect orchestration; further splitting should wait for fake `EduClient`/DB fixtures.
- The next better candidates are other large standalone helpers such as `nutricost_deal_monitor.py` or `google_cloud_receipts.py`.

## 2026-07-02 - Education Homework Prompt Lint Module

Goal/scope:
- Move static homework prompt lint checks out of `edu_homework_audit.py`.
- Keep page parsing, live audit control flow, grading, cleanup, and report writing in the audit script.

Files/modules changed:
- `agent_skills/edu_homework_lint.py`
- `agent_skills/edu_homework_audit.py`
- `tests/test_edu_homework_lint.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Unrendered Jinja, odd inline math delimiters, brace mismatch, common typos, short prompts, author markers, unwrapped LaTeX, and `Fraction(a, b)` repr leaks are still flagged with the same severities/kinds/messages.
- Display math environments and properly wrapped inline math still avoid false `unwrapped_latex` findings.

Boundary chosen:
- Prompt linting is deterministic and independent of DB/HTTP/live grading.
- The audit runner now reads as orchestration over parsing, formatting, linting, grading, and reporting helpers.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/edu_homework_lint.py agent_skills/edu_homework_audit.py tests/test_edu_homework_lint.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_edu_homework_lint.py tests/test_edu_homework_answers.py tests/test_edu_homework_report.py -q` passed (`9 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`469 passed`).

Remaining follow-up slices:
- Page/feedback parsers in `edu_homework_audit.py` are another pure boundary.
- The live audit loop should stay in place unless a fake EduClient fixture is added.

## 2026-07-02 - Education Homework Answer Formatting Module

Goal/scope:
- Move solution-to-form response formatting and Sympy linear-algebra helpers out of `edu_homework_audit.py`.
- Keep live audit flow, DB access, HTTP client behavior, submission, grading, cleanup, and report writing in the audit script.

Files/modules changed:
- `agent_skills/edu_homework_answers.py`
- `agent_skills/edu_homework_audit.py`
- `tests/test_edu_homework_answers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Simple, multiple-choice, vector, subspace basis, linear-system, classify/reach, invertibility, and solve-with-basis answer types still format to the same strings/JSON shapes.
- Infinite-solution systems still choose a particular solution by setting free parameters to zero.
- Unsupported answer types still raise `ValueError`.

Boundary chosen:
- Answer formatting is pure and mirrors the browser form/comparator contract.
- Moving it out of the live audit runner makes the DB/HTTP workflow easier to read and gives the math formatting direct tests.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/edu_homework_answers.py agent_skills/edu_homework_audit.py tests/test_edu_homework_answers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_edu_homework_answers.py tests/test_edu_homework_report.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`466 passed`).

Remaining follow-up slices:
- Prompt linting in `edu_homework_audit.py` is another pure boundary.
- Live grading and attempt cleanup should stay in the audit script until integration fixtures exist.

## 2026-07-02 - Education Homework Audit Report Builder

Goal/scope:
- Extract Markdown report assembly from `edu_homework_audit.write_report()`.
- Keep report path generation, directory creation, Markdown file writing, and JSON sidecar writing in the audit script.

Files/modules changed:
- `agent_skills/edu_homework_report.py`
- `agent_skills/edu_homework_audit.py`
- `tests/test_edu_homework_report.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Report filenames and JSON sidecar output are unchanged.
- Full-grade reports still include score and correct/total counts.
- Issue summaries still bold high-severity issue counts.
- Flagged question sections still include prompt text, canonical solution, submitted response when present, verdict, server feedback, errors, and issue details.

Boundary chosen:
- Markdown assembly is pure and testable.
- The audit script remains responsible for DB/HTTP/grading side effects and filesystem output.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/edu_homework_report.py agent_skills/edu_homework_audit.py tests/test_edu_homework_report.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_edu_homework_report.py -q` passed (`2 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`462 passed`).

Remaining follow-up slices:
- Homework answer formatting and prompt linting are also pure and could move into dedicated modules.
- DB cleanup and live grading paths should be left alone without integration fixtures.

## 2026-07-02 - Stage 3 Extractor Import Decoupling

Goal/scope:
- Change v2 Stage 3 escalation to import `ToolMarkerExtractor` from `client_tool_markers` instead of `jane_proxy.py`.
- Keep streaming extraction behavior and Stage 3 escalation flow unchanged.

Files/modules changed:
- `jane_web/jane_v2/stage3_escalate.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Stage 3 still uses a long-lived `ToolMarkerExtractor` while relaying v1 stream chunks.
- Ack suppression, class protocol injection, voice wrapping, and Stage 3 error handling are unchanged.

Boundary chosen:
- `client_tool_markers.py` owns the extractor; Stage 3 should not depend on `jane_proxy.py` just for that class.
- The change reduces import coupling without touching the stream state machine.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/stage3_escalate.py jane_web/client_tool_markers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_stage3_escalate_helpers.py tests/test_client_tool_markers.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`460 passed`).

Remaining follow-up slices:
- Stage 3 escalation still delegates most behavior to v1 by design.
- Further Stage 3 refactors should focus on route-level characterization before changing stream relay logic.

## 2026-07-02 - V3 Stage 2 Marker Helper Reuse

Goal/scope:
- Reuse the shared complete-payload client-tool marker helper in the v3 Stage 2 direct response paths.
- Keep v3 classification, privacy gate, pending-action emission, Stage 3 escalation, and persistence behavior unchanged.

Files/modules changed:
- `jane_web/jane_v3/pipeline.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Non-streaming v3 Stage 2 responses still strip embedded client-tool markers from the visible response and expose structured `client_tool_calls`.
- Streaming v3 Stage 2 responses still emit `pending_action` before text, then emit extracted `client_tool_call` events before `delta` and `done`.
- No changes were made to v3 classifier confidence, force-Stage-3 handling, or conversation-end emission.

Boundary chosen:
- V3 was still manually constructing a complete-text `ToolMarkerExtractor` even after the shared helper existed.
- Using the helper removes a dependency on importing `ToolMarkerExtractor` from `jane_proxy.py` inside v3.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v3/pipeline.py jane_web/client_tool_markers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_client_tool_markers.py tests/test_stage2_response.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`460 passed`).

Remaining follow-up slices:
- V3 still has dense classifier/resolver flow, but the remaining code is more routing-heavy than pure helper logic.
- Route-level v3 tests would be useful before deeper changes.

## 2026-07-02 - Complete Client Tool Marker Helper

Goal/scope:
- Add a shared helper for stripping `[[CLIENT_TOOL:...]]` markers from complete text payloads.
- Reuse it in v2 Stage 2 response handling and proxy sync/done payload sanitization.

Files/modules changed:
- `jane_web/client_tool_markers.py`
- `jane_web/jane_v2/stage2_response.py`
- `jane_web/jane_proxy.py`
- `tests/test_client_tool_markers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Streaming delta handling still uses the long-lived `ToolMarkerExtractor` instance for partial chunks.
- Complete sync responses still strip raw client-tool markers before user-visible output.
- Sync-mode extracted tool calls are still counted and logged as non-dispatchable.
- Done payloads still strip client-tool markers before Android TTS sees the final response text.
- Stage 2 direct responses still return visible text plus structured client tool calls.

Boundary chosen:
- Complete-payload marker stripping was repeated in several places.
- The helper centralizes extractor plumbing without changing the streaming state machine.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/client_tool_markers.py jane_web/jane_v2/stage2_response.py jane_web/jane_proxy.py tests/test_client_tool_markers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_client_tool_markers.py tests/test_stage2_response.py tests/test_proxy_text.py -q` passed (`17 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`460 passed`).

Remaining follow-up slices:
- v3 pipeline still instantiates `ToolMarkerExtractor` directly for complete Stage 2 text and can move to this helper later.
- The live stream emitter still owns client-tool dispatch side effects and should stay separate from this pure helper.

## 2026-07-02 - Auth Trusted Device Resolution Helper

Goal/scope:
- Extract trusted-device id resolution from Google OAuth, native Google token, and OTP login success paths.
- Keep fingerprint construction, authorization checks, session creation, prewarming, and cookie attachment in `main.py`.

Files/modules changed:
- `jane_web/auth_devices.py`
- `jane_web/main.py`
- `tests/test_auth_devices.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Google OAuth and native Google-token login still register immediately when `is_device_trusted(fp)` is false.
- When the device is trusted and a row exists, the existing trusted-device id is reused.
- If the trust check says trusted but no row is found, registration still creates a replacement id.
- OTP login still skips the trust predicate and uses the existing row-or-register behavior.

Boundary chosen:
- Trusted-device resolution is deterministic control flow with injected store functions.
- Auth routes remain responsible for external token validation and response/cookie behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/auth_devices.py jane_web/main.py tests/test_auth_devices.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_auth_devices.py tests/test_auth_cookies.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`459 passed`).

Remaining follow-up slices:
- Auth token storage for Gmail OAuth is still inline in the Google callback.
- That path touches external OAuth token semantics, so it should only move with route-level characterization.

## 2026-07-02 - Auth Success Cookie Helper Reuse

Goal/scope:
- Replace repeated session/trusted-device cookie writes in auth success routes with the shared `_attach_auth_cookies()` helper.
- Keep OAuth token handling, Google ID token verification, OTP verification, session creation, trusted-device registration, and response bodies unchanged.

Files/modules changed:
- `jane_web/main.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Successful Google OAuth callback, native Google token login, and OTP login still return the same response types and bodies.
- Auth cookies still use the shared `httponly`, `secure`, `samesite=lax`, and 30-day max-age spec from `auth_cookies.py`.
- Existing `_attach_auth_cookies()` behavior still avoids rewriting unchanged cookie values.

Boundary chosen:
- Cookie attribute planning was already centralized; the routes were the remaining manual writers.
- Consolidating these calls removes drift without changing auth/session ownership.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/main.py jane_web/auth_cookies.py tests/test_auth_cookies.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_auth_cookies.py tests/test_request_helpers.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`456 passed`).

Remaining follow-up slices:
- Auth routes still duplicate trusted-device resolution for Google OAuth and native Google token login.
- Extracting that requires route-level characterization or an injected helper to avoid changing registration behavior.

## 2026-07-02 - RA Deterministic Markdown Builders

Goal/scope:
- Move deterministic RA compressed-context, action-plan, and recommendation-scheme Markdown builders out of the cron orchestration module.
- Keep timestamp selection, mission-statement wiring, file writes, LLM synthesis, and cron flow in `ra_research_cron.py`.

Files/modules changed:
- `agent_skills/ra_research_report_markdown.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_report_markdown.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Compressed context still lists up to 40 summaries, includes the mission statement, and ends with the standing safety boundary.
- Deterministic action plans still include the same standing sections, evidence matrix, no-source fallback row, and medication/supplement safety language.
- Deterministic recommendation schemes still include the same status, safety boundary, working model, minimum data, evidence register, and next research questions.
- The cron still controls `local_now()` formatting and mission text injection.

Boundary chosen:
- Markdown assembly belongs with the existing report markdown helpers.
- The cron module should orchestrate collection, synthesis, writing, and notification instead of owning large static report templates.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_report_markdown.py agent_skills/ra_research_cron.py tests/test_ra_research_report_markdown.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_report_markdown.py tests/test_ra_research_text.py -q` passed (`12 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`456 passed`).

Remaining follow-up slices:
- RA cron still owns PubMed/XML artifact persistence and LLM prompt execution.
- If RA work continues, source artifact saving is a better next boundary than notification delivery, which is already helper-backed.

## 2026-07-02 - Janitor Consolidation Helpers

Goal/scope:
- Extract janitor consolidation topic grouping, candidate selection, prompt construction, and consolidated metadata construction.
- Keep LLM calls, quarantine deletes, Chroma adds, and merge-log/result counting in `janitor_memory.py`.

Files/modules changed:
- `memory/v1/janitor_consolidation.py`
- `memory/v1/janitor_memory.py`
- `tests/test_janitor_consolidation.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Known-junk rows are still skipped before consolidation.
- User-memory rows with `permanent`, `forgettable`, `short_term`, `short_term_theme`, saved-file text, location text, or `file_path` metadata are still excluded.
- Permanent user-memory rows still increment the permanent count.
- Only topics with at least three rows are selected for consolidation.
- Consolidated user-memory metadata still sets `memory_type=long_term`, preserves user id, and keeps a non-empty subtopic.
- Consolidated long-term metadata still uses `source=janitor`.

Boundary chosen:
- Grouping and metadata construction are deterministic rule logic with high regression risk if edited inline.
- The side-effecting consolidation loop remains responsible for LLM merge decisions and Chroma mutations.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/janitor_consolidation.py memory/v1/janitor_memory.py tests/test_janitor_consolidation.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_janitor_consolidation.py tests/test_janitor_normalization.py tests/test_janitor_rules.py tests/test_janitor_duplicates.py -q` passed (`16 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`454 passed`).

Remaining follow-up slices:
- Janitor code-memory verification still combines frontier prompts, fix planning, and Chroma updates.
- Conversation manager window archival still has dense retry/watermark behavior but requires careful characterization.

## 2026-07-02 - Janitor Long-Term Normalization Helpers

Goal/scope:
- Extract pure long-term memory normalization candidate filtering and metadata construction from the janitor's Chroma/LLM loop.
- Keep LLM calls, Chroma add/update/delete operations, quarantine writes, and result counting in `janitor_memory.py`.

Files/modules changed:
- `memory/v1/janitor_normalization.py`
- `memory/v1/janitor_memory.py`
- `tests/test_janitor_normalization.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Theme topics are still excluded from long-term normalization.
- Known junk rows, short rows, missing-topic rows, and already `long_term_normalized_v2` rows are still skipped.
- Candidate selection still respects `MAX_LONG_TERM_NORMALIZE_PER_RUN`.
- Split metadata still records raw chars, summary chars, source id, part index, total parts, style, and timestamp.
- Rewrite metadata still records raw chars, summary chars, style, and timestamp.

Boundary chosen:
- Candidate filtering and metadata shape are deterministic and easy to regress silently.
- The side-effecting janitor loop remains responsible for LLM decisions and Chroma writes.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/janitor_normalization.py memory/v1/janitor_memory.py tests/test_janitor_normalization.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_janitor_normalization.py tests/test_janitor_rules.py tests/test_janitor_duplicates.py tests/test_janitor_expiry.py -q` passed (`15 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`450 passed`).

Remaining follow-up slices:
- Janitor consolidation prompt execution still mixes prompt construction, LLM parsing, and Chroma mutation.
- Window archival in `conversation_manager.py` remains dense but is more side-effect-heavy than this normalization boundary.

## 2026-07-02 - Stage 2 Client Tool Marker Extraction Helper

Goal/scope:
- Extract embedded `[[CLIENT_TOOL:...]]` marker stripping from v2 Stage 2 direct response handling.
- Use the same helper for non-streaming JSON responses and streaming NDJSON responses.

Files/modules changed:
- `jane_web/jane_v2/stage2_response.py`
- `jane_web/jane_v2/pipeline.py`
- `tests/test_stage2_response.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Stage 2 visible response text still has embedded client-tool markers stripped before display.
- Extracted markers are still surfaced as structured client tool calls.
- Streaming responses still serialize `client_tool_call` data as a JSON string for Android's NDJSON parser.
- Structured `client_tools` returned by handlers are still emitted by the streaming path after embedded markers.

Boundary chosen:
- Stage 2 response formatting already owns marker-aware spoken wrapping and extras extraction.
- The v2 pipeline no longer needs to import `ToolMarkerExtractor` from `jane_proxy.py` for Stage 2 responses.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/stage2_response.py jane_web/jane_v2/pipeline.py tests/test_stage2_response.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_stage2_response.py tests/test_client_tool_markers.py tests/test_jane_v2_pipeline_helpers.py -q` passed (`15 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`447 passed`).

Remaining follow-up slices:
- Stage 2 private-class deflection JSON and streaming branches still duplicate response construction.
- Stage 3 body mutation and pending-action persistence remain dense but already have helper modules around the riskiest pieces.

## 2026-07-02 - Music Play Marker Helpers

Goal/scope:
- Extract `[MUSIC_PLAY:<query>]` fallback marker detection and replacement from the streaming proxy `done` path.
- Keep playlist creation, logging, and payload emission in `jane_proxy.py`.

Files/modules changed:
- `jane_web/music_playlists.py`
- `jane_web/jane_proxy.py`
- `tests/test_music_playlists.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `[MUSIC_PLAY:<16 lowercase hex chars>]` is still treated as an existing playlist id and bypasses fallback creation.
- Non-id markers still trim the query text before playlist lookup.
- When fallback playlist creation succeeds, the original marker text is replaced with `[MUSIC_PLAY:{playlist_id}]`.
- The proxy still logs create/no-match/error outcomes and still creates playlists through `create_music_playlist_from_query`.

Boundary chosen:
- Marker parsing and replacement are deterministic string rules that belong with music playlist helpers.
- Side effects remain in the stream proxy so import cycles and route/runtime behavior stay unchanged.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/music_playlists.py jane_web/jane_proxy.py tests/test_music_playlists.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_music_playlists.py tests/test_stage2_response.py -q` passed (`9 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`446 passed`).

Remaining follow-up slices:
- The stream `emit()` closure still has client-tool dispatch and TTS latency stamping mixed together.
- The v1/v2 music handling paths now share marker rules but still duplicate some playlist-context prompt text.

## 2026-07-02 - Proxy Phone Tool Message Prep Helper

Goal/scope:
- Extract duplicated phone-tool result message preparation from sync and streaming proxy request paths.
- Keep request-mode logging, stream queue emission, client-tool extraction during assistant deltas, and persistence dispatch in `jane_proxy.py`.

Files/modules changed:
- `jane_web/proxy_text.py`
- `jane_web/jane_proxy.py`
- `tests/test_proxy_text.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Leading `[TOOL_RESULT:{...}]` markers are still removed from the user-visible message.
- Parsed phone-tool results are still formatted into a `[PHONE TOOL RESULTS ...]` block for Jane's brain before the cleaned user message.
- Stage 3 injected protocol/context blocks are still stripped only from the user-visible/persisted input, not from the brain-visible message.
- Stream mode still logs each phone-tool result with its tool, status, message, and serializable data snippet.

Boundary chosen:
- Sync and stream paths previously duplicated the same tool-result stripping and brain-visible message assembly.
- The helper is pure text preparation; the proxy still owns mode-specific logging, context resolution, brain execution, streaming, and persistence.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/proxy_text.py jane_web/jane_proxy.py tests/test_proxy_text.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_proxy_text.py tests/test_client_tool_markers.py -q` passed (`12 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`445 passed`).

Remaining follow-up slices:
- The stream `emit()` closure still mixes TTS timing, client-tool marker dispatch, and music fallback handling.
- A future slice can extract music-play marker replacement with a small tested helper before touching playlist side effects.

## 2026-07-02 - TTS Generation Planning Helpers

Goal/scope:
- Extract deterministic TTS cache-path, chunk WAV path, Docker command, ffmpeg command, and GPU-flag planning from `/api/tts/generate`.
- Keep request validation, cache existence checks, subprocess execution, WAV concatenation, and temporary directory cleanup in the route.

Files/modules changed:
- `jane_web/tts_generation.py`
- `jane_web/main.py`
- `tests/test_tts_generation.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- TTS cache keys still use the first 12 hex characters of `md5(text)`.
- Cached files still live under `{VESSENCE_DATA_HOME}/cache/tts/{hash}.ogg` with `{hash}.wav` as the legacy fallback.
- Docker generation still uses the same image, memory/CPU limits, XTTS-v2 model, speaker/language args, and `/output/chunk_NNN.wav` output names.
- GPU flags are still enabled only when `/usr/bin/nvidia-smi` exists.
- ffmpeg still writes Opus OGG with `libopus` at `48k`.

Boundary chosen:
- Command and path construction are pure planning logic that can be tested without launching Docker or ffmpeg.
- The route remains responsible for all I/O, subprocess calls, and HTTP response behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/tts_generation.py jane_web/main.py tests/test_tts_generation.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_tts_generation.py tests/test_tts_chunks.py -q` passed (`9 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`442 passed`).

Remaining follow-up slices:
- The upload hash-index file-I/O blocks are now too small to be worth extracting by themselves.
- Large proxy and conversation modules still have better extraction candidates than additional TTS route cleanup.

## 2026-07-02 - Upload Memory Fact Command Helpers

Goal/scope:
- Extract upload memory fact text and `add_fact.py` command construction from the web and Android upload routes.
- Keep file writes, ChromaDB indexing, auth/capability checks, and subprocess execution in the routes.

Files/modules changed:
- `jane_web/upload_helpers.py`
- `jane_web/main.py`
- `tests/test_upload_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Web uploads still store fact text `File uploaded via web UI: {name} saved to vault/{subdir}/`.
- Android uploads still store fact text `File uploaded from Android: {name} saved to vault/{subdir}/`.
- Upload memory commands still pass `--topic vault`, `--subtopic upload`, and the route-selected `--user-id`.
- Optional `--memory-path` is still appended only when present.
- Each route still supplies its existing Python interpreter and `add_fact.py` path.

Boundary chosen:
- The argv assembly is duplicated pure logic shared by both upload routes.
- The routes retain ownership of subprocess execution and upload side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/upload_helpers.py jane_web/main.py tests/test_upload_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_upload_helpers.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`437 passed`).

Remaining follow-up slices:
- Upload route hash-index loading and persistence can be extracted if a small pure boundary remains after auditing.
- TTS command/cache helpers are another candidate, but Docker-facing behavior needs careful characterization.

## 2026-07-02 - File Search Index Merge Helper

Goal/scope:
- Extract the ChromaDB file-description result merge loop from `/api/files/search`.
- Keep vector database path setup, collection query fallback, and auth/scope selection in the route.

Files/modules changed:
- `jane_web/file_search_helpers.py`
- `jane_web/main.py`
- `tests/test_file_search_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Managed user scope filtering still allows untagged legacy rows and rejects rows for other users.
- Indexed paths still normalize absolute paths to vault-relative paths and reject escapes.
- Type filtering still applies to vector-index hits.
- Missing files from vector results are still skipped before adding new results.
- Existing filename hits are still enriched with descriptions only when their description is empty.

Boundary chosen:
- Merging already returned docs/metas into a result map is deterministic and independent of ChromaDB availability.
- The route still owns live `_query_collection` calls and collection fallback behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/file_search_helpers.py jane_web/main.py tests/test_file_search_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_file_search_helpers.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`436 passed`).

Remaining follow-up slices:
- Upload routes still duplicate memory-fact command construction.
- Search route result limiting and response shaping are simple enough to leave unless broader file-route extraction happens.

## 2026-07-02 - File Search Filename Phase Helper

Goal/scope:
- Extract the vault filename-walk phase from `/api/files/search` into `jane_web/file_search_helpers.py`.
- Keep auth, ChromaDB description queries, managed-user scope filtering, and result merging in the route.

Files/modules changed:
- `jane_web/file_search_helpers.py`
- `jane_web/main.py`
- `tests/test_file_search_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Hidden filenames are still skipped.
- Filename matching still uses the lowercased query as a substring of the lowercased filename.
- Optional type filtering still uses extension sets from the route.
- Results are still keyed by vault-relative path and use the same search result payload shape.

Boundary chosen:
- Filesystem filename scanning is deterministic and independent of vector search.
- The route remains responsible for vector description lookup and avoiding duplicate path results.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/file_search_helpers.py jane_web/main.py tests/test_file_search_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_file_search_helpers.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`435 passed`).

Remaining follow-up slices:
- The ChromaDB description merge phase can be extracted with an injected query function.
- Upload memory-fact command construction is duplicated between multi and Android single upload routes.

## 2026-07-02 - Active Essence Context Module

Goal/scope:
- Move active essence names, personality loading, ChromaDB path lookup, tool signature extraction, and essence/tool context description out of `context_builder.py`.
- Preserve existing private context-builder call sites through import aliases.

Files/modules changed:
- `context_builder/v1/essence_context.py`
- `context_builder/v1/context_builder.py`
- `tests/test_essence_context.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Active essence state still supports both `active` and legacy `active_essence` formats.
- Personality lookup still checks tools/skills first, then `ambient/essences`.
- Essence ChromaDB path lookup still returns the first active essence with an existing `knowledge/chromadb` directory.
- Tool signature extraction still ignores private functions and trims return annotations.
- Tool and AI-agent essence prompt sections keep the same headings, invoke strings, and function lists.

Boundary chosen:
- Active essence context is separate from prompt profile selection and system section assembly.
- The moved module owns filesystem/manifests for essence context; `context_builder.py` only consumes the resulting strings/paths.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile context_builder/v1/essence_context.py context_builder/v1/context_builder.py tests/test_essence_context.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_essence_context.py tests/test_saved_articles_context.py -q` passed (`9 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`434 passed`).

Remaining follow-up slices:
- `_build_system_sections` still combines dynamic section ordering and profile gates.
- Recent history formatting and context result assembly remain small enough to test next.

## 2026-07-02 - Saved Article Context Module

Goal/scope:
- Move saved Daily Briefing article query, loading, scoring, formatting, and context assembly out of `context_builder.py`.
- Preserve the existing `_build_saved_articles_context` call sites through an import alias.

Files/modules changed:
- `context_builder/v1/saved_articles_context.py`
- `context_builder/v1/context_builder.py`
- `tests/test_saved_articles_context.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Article context is still included only for article/news/briefing-like prompts.
- Saved article index path still comes from `VESSENCE_DATA_HOME/briefing_saved/saved.json`.
- Inline article objects still win; otherwise valid article IDs are loaded from the Daily Briefing article directory.
- Search terms keep the existing stop-word behavior, including retaining `say` and `the`.
- Metadata/title/source/url matches still score higher than summary/body matches.
- Context output still includes up to three highest-scoring/saved-time candidates within the same character budget.

Boundary chosen:
- Saved article context selection is independent of general prompt section assembly.
- Splitting it enables direct tests around scoring and external article-file loading without importing the whole context builder path.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile context_builder/v1/saved_articles_context.py context_builder/v1/context_builder.py tests/test_saved_articles_context.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_saved_articles_context.py tests/test_prompt_profiles.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`429 passed`).

Remaining follow-up slices:
- Active essence personality/tool description loading remains in `context_builder.py`.
- Recent-history transcript formatting and managed-user context are still isolated enough for focused tests.

## 2026-07-02 - Prompt Profile Message Categories

Goal/scope:
- Extract message-based prompt profile category rules from `_classify_prompt_profile`.
- Keep `_classify_prompt_profile` as the dispatcher between explicit intent profiles and message category profiles.

Files/modules changed:
- `context_builder/v1/context_builder.py`
- `tests/test_prompt_profiles.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- File/vault/document markers still win before project work classification.
- Project/coding requests still include task state, conversation summary, memory, and code map.
- Research offload remains decided by `should_offload_research` in production.
- Factual personal questions and short questions still skip conversation summary.
- Casual follow-ups still include user background and memory and only include file context when present.

Boundary chosen:
- Message-category selection is distinct from explicit upstream intent modes.
- The helper accepts an injectable research decider so project profile behavior is testable without invoking live routing.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile context_builder/v1/context_builder.py tests/test_prompt_profiles.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_prompt_profiles.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`425 passed`).

Remaining follow-up slices:
- Conversation-summary inclusion and anaphoric detection can be tested and split from prompt profile selection.
- Saved-article context scoring remains a separate medium-sized pure helper cluster.

## 2026-07-02 - Prompt Profile Intent Table

Goal/scope:
- Extract explicit `intent_level` profile selection from `_classify_prompt_profile`.
- Add focused tests for tool, data, greeting, simple, and fallback message-category profiles.

Files/modules changed:
- `context_builder/v1/context_builder.py`
- `tests/test_prompt_profiles.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `tool_mode` still includes user background, disables memory/tool protocol bulk injection, and carries the tool context override.
- `data_mode`, `greeting`, and `simple` keep their existing profile flags.
- Unknown intent levels still fall through to message-based classification.
- File, project, factual, and casual message categories keep the same priority order.

Boundary chosen:
- Explicit intent levels are a table of pre-decided profiles independent of message text classification.
- The remaining classifier still owns message keyword/category rules and research offload decisions.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile context_builder/v1/context_builder.py tests/test_prompt_profiles.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_prompt_profiles.py tests/test_system_prompt_sections.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`423 passed`).

Remaining follow-up slices:
- Message-category profile rules can be split next, but research offload must stay injectable or route-level to avoid side effects in tests.
- Conversation-summary inclusion rules are now covered only indirectly and could use focused tests.

## 2026-07-02 - Context Builder Static Prompt Sections

Goal/scope:
- Move large static operational system prompt sections out of `_build_system_sections`.
- Keep dynamic section decisions, profile gating, tool loader fallback, and prompt assembly in `context_builder.py`.

Files/modules changed:
- `context_builder/v1/system_prompt_sections.py`
- `context_builder/v1/context_builder.py`
- `tests/test_system_prompt_sections.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Standing-brain override, acknowledgment, delegation, rich content/download, music playback, available tools, recent-message priority, and conversational hygiene sections keep the same text and order.
- `_build_system_sections` still appends these sections after dynamic tool protocol handling.
- The new accessor returns a fresh list so callers cannot mutate module-level section order.

Boundary chosen:
- These prompt blocks are static configuration text, independent of context retrieval and profile logic.
- Moving them makes the context builder’s dynamic assembly easier to inspect without changing prompt content.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile context_builder/v1/system_prompt_sections.py context_builder/v1/context_builder.py tests/test_system_prompt_sections.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_system_prompt_sections.py tests/test_memory_sections.py tests/test_memory_sections_cache.py -q` passed (`9 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`419 passed`).

Remaining follow-up slices:
- `_build_system_sections` still mixes dynamic essence/tool loading with section assembly.
- Context profile classification remains a large pure-ish function that can be characterized before extraction.

## 2026-07-02 - Stage 3 Protocol Module

Goal/scope:
- Split Stage 3 class reason normalization, metadata protocol synthesis, optional `protocol.md` loading, and protocol cache behavior out of `stage3_escalate.py`.
- Keep stream escalation, NDJSON emission, v1 delegation, and body injection flow in `stage3_escalate.py`.

Files/modules changed:
- `jane_web/jane_v2/stage3_protocols.py`
- `jane_web/jane_v2/stage3_escalate.py`
- `tests/test_stage3_protocols.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Reason strings still normalize spaces to underscores, drop confidence suffixes, strip fallback/decline suffixes, and reject unsafe class names.
- `others` still has no class protocol.
- Protocol synthesis still uses live class registry metadata, description, escalation context, handler presence, and up to 12 few-shot examples.
- `protocol.md` files are still cached by mtime and missing files are still not cached.
- Generated protocol text and optional protocol extension are still joined with a blank line.

Boundary chosen:
- Protocol lookup and synthesis are independent of streaming and v1 delegation.
- A separate module makes path-safety and cache behavior directly testable.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/stage3_protocols.py jane_web/jane_v2/stage3_escalate.py tests/test_stage3_protocols.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_stage3_protocols.py tests/test_stage3_escalate_helpers.py tests/test_stage3_injections.py -q` passed (`15 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`417 passed`).

Remaining follow-up slices:
- Stage 3 streaming error/result parsing still lives in `stage3_escalate.py`.
- v2 `handle_chat` and `handle_chat_stream` still have parallel Stage 3 preparation flows.

## 2026-07-02 - Stage 3 Body Message Copy Helper

Goal/scope:
- Extract repeated `model_copy`/`copy` message replacement branches from `jane_web/jane_v2/stage3_escalate.py`.
- Use the helper for voice hints, extracted params, structured state, and class protocol injection.

Files/modules changed:
- `jane_web/jane_v2/stage3_escalate.py`
- `tests/test_stage3_escalate_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Message copying still prefers Pydantic v2 `model_copy`.
- Pydantic v1-style `copy` remains the fallback.
- Non-voice requests still return the original body unchanged.
- Voice hints, extracted params blocks, structured state blocks, and class protocols are still inserted with the same text placement.

Boundary chosen:
- Message replacement is the shared compatibility seam in Stage 3 injection helpers.
- The injection decision logic and block construction remain local to each function.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/stage3_escalate.py tests/test_stage3_escalate_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_stage3_escalate_helpers.py tests/test_stage3_injections.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`412 passed`).

Remaining follow-up slices:
- Stage 3 protocol synthesis and path validation could be tested more directly before further refactor.
- v2 streaming and non-streaming Stage 3 preparation still share concepts but differ enough to avoid a broad extraction for now.

## 2026-07-02 - V2 Pipeline Body Copy Helpers

Goal/scope:
- Reuse the v2 pipeline append/prepend body-copy helpers for Stage 3 context injections instead of repeating `model_copy`/`copy` blocks.
- Add focused tests for the append/prepend helpers across copy-capable and mutable body objects.

Files/modules changed:
- `jane_web/jane_v2/pipeline.py`
- `tests/test_jane_v2_pipeline_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Empty append context still returns the original body.
- Copy-capable bodies still produce copied objects without mutating the original.
- Mutable bodies without copy APIs still get their `message` updated in place.
- Prepended context still inserts a blank-line separator unless the prefix already ends with a double newline.
- Stage 3 SMS, follow-up, and self-improvement context strings are still appended in the same order.

Boundary chosen:
- The helper already represented the body-copy compatibility boundary for Pydantic v1/v2 and mutable fallback objects.
- Reusing it removes duplicated exception-handling branches without moving Stage 3 decision logic.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/pipeline.py tests/test_jane_v2_pipeline_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_jane_v2_pipeline_helpers.py tests/test_verify_first_policy.py tests/test_stage2_response.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`408 passed`).

Remaining follow-up slices:
- `handle_chat` and `handle_chat_stream` still duplicate Stage 3 preparation flow.
- `stage3_escalate.py` has its own body-copy branches that may be extractable after a focused read.

## 2026-07-02 - Essence Detail Load Payload Helpers

Goal/scope:
- Extract essence detail manifest loading and loaded-essence response shaping from essence management routes.
- Keep essence discovery, loader calls, capability registry mutation, and FastAPI error mapping in `jane_web/main.py`.

Files/modules changed:
- `jane_web/essence_helpers.py`
- `jane_web/main.py`
- `tests/test_essence_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Essence detail still reads `manifest.json` and adds `loaded` based on the requested essence name and loaded-name list.
- Manifest JSON and OS read failures still map to the same HTTP 500 route error.
- Loaded responses still include `status`, `role_title`, and `permissions`.
- Missing permissions still default to an empty list.
- Capability registration still happens only in the route after a successful `load_essence`.

Boundary chosen:
- Manifest detail shaping and response payload construction are deterministic helper behavior.
- Loader state mutation and registry side effects remain in the endpoint where the operational sequence is visible.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/essence_helpers.py jane_web/main.py tests/test_essence_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_essence_helpers.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`403 passed`).

Remaining follow-up slices:
- Unload/delete/activate route payloads are simple enough to leave for now unless broader essence-router extraction happens.
- Work Log and capability map routes still have direct route-local data access.

## 2026-07-02 - Essence Tool Command Payload Helpers

Goal/scope:
- Extract essence custom-tool command construction plus stdout/stderr response payload rules from `jane_web/main.py`.
- Keep request JSON reading, subprocess execution, cwd selection, timeout handling, and HTTP status decisions in the route.

Files/modules changed:
- `jane_web/essence_helpers.py`
- `jane_web/main.py`
- `tests/test_essence_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Empty request bodies still do not append a JSON argument to the custom-tools command.
- Nonempty request bodies are still appended as `json.dumps(body)`.
- Nonzero tool exits still return `{"status": "error", "message": stderr[:300]}` with HTTP 500.
- JSON stdout is still returned as parsed JSON; non-JSON stdout still falls back to `{"status": "ok", "output": stdout.strip()}`.
- Tool timeout and generic exception handling remain route-level and unchanged.

Boundary chosen:
- Command assembly and payload parsing are pure essence route rules already colocated with essence lookup helpers.
- The route remains responsible for process execution and FastAPI exception mapping.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/essence_helpers.py jane_web/main.py tests/test_essence_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_essence_helpers.py -q` passed (`9 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`401 passed`).

Remaining follow-up slices:
- Essence detail/load/unload routes still mix manifest lookup, state mutation, and HTTP errors.
- Essence cache invalidation can be made more explicit if those routes are split further.

## 2026-07-02 - CLI Provider Auth Status Helpers

Goal/scope:
- Extract provider auth-status command selection, unsupported/error payloads, base detail payloads, and stderr-tail shaping from `jane_web/main.py`.
- Keep status caching, `subprocess.run`, Claude token refresh, and provider auth execution in `main.py`.

Files/modules changed:
- `jane_web/cli_login_helpers.py`
- `jane_web/main.py`
- `tests/test_cli_login_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Claude status checks still use `claude auth status`; unsupported providers still return `supported=False` and `logged_in=False`.
- Status command exceptions still return the same `status_error` payload shape.
- Base status details still include provider, supported flag, return code, and `logged_in=False`.
- Failed status checks still attach only the last stderr line, truncated to 200 characters.
- Main still avoids caching failed or empty status checks and still performs the existing Claude refresh retry.

Boundary chosen:
- Status payload scaffolding is deterministic and belongs beside existing CLI-login parsing helpers.
- Main still owns side effects: cache timing, subprocess execution, and credential refresh.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/cli_login_helpers.py jane_web/main.py tests/test_cli_login_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_cli_login_helpers.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`399 passed`).

Remaining follow-up slices:
- CLI login OAuth exchange branches remain high side-effect and should be split only with stronger route-level characterization.
- `jane_web/main.py` still has large essence and web-automation route groups worth modularizing.

## 2026-07-02 - CLI Login Debug Payload Helpers

Goal/scope:
- Extract CLI-login process-state and debug snapshot payload shaping from `jane_web/main.py`.
- Keep OAuth flows, subprocess lifecycle, provider auth status checks, and route responses in `main.py`.

Files/modules changed:
- `jane_web/cli_login_helpers.py`
- `jane_web/main.py`
- `tests/test_cli_login_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing CLI login process still reports `process_state="missing"` and `process_returncode=None`.
- Running processes still report `process_state="running"`, exited processes still report `process_state="exited"`.
- Debug snapshots keep the same keys: provider, process state, return code, authenticated flag, transcript tail, and auth status.
- Transcript tails still include only the last three nonblank transcript lines read by the existing helper.

Boundary chosen:
- Debug snapshot formatting is pure and belongs with the existing CLI-login parsing helpers.
- Main remains responsible for live globals, transcript path lookup, and provider auth status execution.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/cli_login_helpers.py jane_web/main.py tests/test_cli_login_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_cli_login_helpers.py -q` passed (`12 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`397 passed`).

Remaining follow-up slices:
- Provider auth status command/result shaping can move into `cli_login_helpers.py`.
- The Claude and Gemini OAuth code-entry branches are still too side-effect-heavy to move without more characterization.

## 2026-07-02 - Provider Status Payload Helpers

Goal/scope:
- Extract `/api/jane/current-provider` provider availability and health payload shaping into `jane_web/model_settings.py`.
- Keep standing-brain manager access and FastAPI response construction in `jane_web/main.py`.

Files/modules changed:
- `jane_web/model_settings.py`
- `jane_web/main.py`
- `tests/test_model_settings.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The current provider response still includes `provider`, `model`, `alive`, and `available`.
- Missing health model still returns `"unknown"`, and missing alive state still returns `False`.
- Provider availability still checks `claude`, `gemini`, and `codex` CLI binaries for Claude, Gemini, and OpenAI respectively.
- The active provider flag still compares each provider name with the standing-brain `_PROVIDER` value.

Boundary chosen:
- Model/provider payload construction already lived in `model_settings.py`.
- The route remains responsible for live manager calls; the helper only formats deterministic response data.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/model_settings.py jane_web/main.py tests/test_model_settings.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_model_settings.py tests/test_proxy_brain.py -q` passed (`12 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`395 passed`).

Remaining follow-up slices:
- Provider switch request validation can be extracted if more provider-route slimming is needed.
- Large CLI login callback branches remain route-local and would need careful characterization before extraction.

## 2026-07-02 - Chat Stream Limit Helpers

Goal/scope:
- Extract active stream limit checks and per-IP open/close accounting from `_handle_jane_chat_stream`.
- Keep the route-level 429 response body, status code, and logging in `jane_web/main.py`.

Files/modules changed:
- `jane_web/chat_stream_limits.py`
- `jane_web/main.py`
- `tests/test_chat_stream_limits.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Local stream hosts `127.0.0.1`, `::1`, and `localhost` are still exempt from the concurrent-stream limit.
- Remote IPs are still rejected when the active count is greater than or equal to `_MAX_STREAMS_PER_IP`.
- Stream open still increments the active count before message streaming begins.
- Stream close still decrements, clamps at zero, and removes zero-count entries.
- The user-facing 429 JSON payload remains unchanged.

Boundary chosen:
- Active stream accounting is deterministic state mutation on a dictionary.
- The route still owns request IP lookup, error responses, and lifecycle logging.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/chat_stream_limits.py jane_web/main.py tests/test_chat_stream_limits.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_chat_stream_limits.py tests/test_chat_stream_dedupe.py tests/test_auth_cookies.py -q` passed (`15 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`393 passed`).

Remaining follow-up slices:
- Provider/current-model response shaping still has route-local formatting logic.
- The main chat stream route can be revisited for task-offload response construction if more route slimming is needed.

## 2026-07-02 - Auth Cookie Refresh Helpers

Goal/scope:
- Extract conditional auth/trusted-device cookie refresh decisions from repeated `jane_web/main.py` route blocks.
- Keep explicit login, Google token, TOTP, share-code, and logout cookie behavior unchanged.

Files/modules changed:
- `jane_web/auth_cookies.py`
- `jane_web/main.py`
- `tests/test_auth_cookies.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Bootstrapped session cookies are still set only when the current request cookie differs from the resolved session id.
- Trusted-device cookies are still set only when a trusted device id exists and differs from the request cookie.
- Cookies keep the same names, `httponly=True`, `samesite="lax"`, secure flag resolution, and 30-day max age.
- Explicit auth flows still always write freshly minted session and trusted-device cookies directly.

Boundary chosen:
- `auth_cookie_specs` is a pure decision helper, so route responses still own FastAPI `set_cookie` calls and secure-cookie resolution.
- The local `_attach_auth_cookies` wrapper keeps request-specific cookie reads in `main.py` while removing repeated route boilerplate.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/auth_cookies.py jane_web/main.py tests/test_auth_cookies.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_auth_cookies.py tests/test_chat_stream_dedupe.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`389 passed`).

Remaining follow-up slices:
- Stream active-IP accounting can be moved out of `_handle_jane_chat_stream`.
- Provider/current-model response shaping still has route-local formatting logic.

## 2026-07-02 - Chat Stream Dedupe Helpers

Goal/scope:
- Extract Android streaming turn idempotency begin/replay/finalize rules from `_handle_jane_chat_stream`.
- Keep FastAPI response construction, auth/session selection, cookies, stream limits, task offload, and brain streaming in `jane_web/main.py`.

Files/modules changed:
- `jane_web/chat_stream_dedupe.py`
- `jane_web/main.py`
- `tests/test_chat_stream_dedupe.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Existing completed turns still replay cached nonblank NDJSON lines without dispatching the brain.
- Pending retries still wait on the original turn and replay cached output when available.
- Pending timeout/failure still falls through to `try_begin`, and races without cached output still disable dedupe for that request.
- New turns still call `try_begin` before dispatch and still mark completed with concatenated captured chunks.
- Erroring turns still mark the turn failed, and finalize exceptions are still caught and logged by the route.
- The pending join-wait log signal is preserved even when no cached replay is available.

Boundary chosen:
- Turn idempotency is a storage/state-machine decision independent of FastAPI route mechanics.
- Returning plain decisions keeps route-level HTTP and cookie behavior visible in `main.py` while making retry rules unit-testable.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/chat_stream_dedupe.py jane_web/main.py tests/test_chat_stream_dedupe.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_chat_stream_dedupe.py -q` passed (`8 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`386 passed`).

Remaining follow-up slices:
- Chat stream active-IP limit and cookie-setting helpers can be extracted separately.
- Provider status response shaping remains embedded in `main.py`.

## 2026-07-02 - Proxy Dead Code Map Keywords

Goal/scope:
- Remove the unused proxy code-map keyword catalog after the code-map loader was disabled.
- Keep the disabled compatibility hook in place so existing prompt-building call sites remain unchanged.

Files/modules changed:
- `jane_web/jane_proxy.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `_maybe_prepend_code_map` still returns `(message, False)` unconditionally.
- Persistent Claude, standing Codex, persistent Codex, and stream call sites still invoke the same hook.
- `_cm_loaded` and `_cm` branches remain unreachable exactly as before because the hook still returns `False`.
- No prompt text, status emission, session state, or model routing behavior changes.

Boundary chosen:
- The removed keyword tuple had no readers after code-map injection was disabled.
- The disabled hook remains as the narrow compatibility boundary for future deletion or reactivation decisions.

Verification:
- `rg -n "CODE_MAP_KEYWORDS|_maybe_prepend_code_map|code map" jane_web/jane_proxy.py jane_web tests` confirmed no `CODE_MAP_KEYWORDS` references remain.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_proxy.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_proxy_text.py tests/test_proxy_brain.py tests/test_proxy_sessions.py -q` passed (`12 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`378 passed`).

Remaining follow-up slices:
- The repeated persistent-brain prompt setup in sync and streaming execution can be extracted carefully.
- Chat stream idempotency/replay helpers in `jane_web/main.py` remain a good low-risk target.

## 2026-07-02 - Instant Command Helpers

Goal/scope:
- Extract exact instant-command phrase classification, command-reference markdown, and cron output formatting from `jane_web/main.py`.
- Keep job queue imports, crontab subprocess execution, stream response handling, and route behavior in `main.py`.

Files/modules changed:
- `jane_web/instant_commands.py`
- `jane_web/main.py`
- `tests/test_instant_commands.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Instant commands still match only normalized commands of 40 characters or fewer.
- Job queue, completed jobs, commands, and cron phrase sets are unchanged.
- The commands table text is unchanged.
- Cron output still filters blank/comment lines and returns `No active cron jobs.` when empty.
- Failures still return the same route-level fallback strings.

Boundary chosen:
- Phrase classification and formatting are pure helpers.
- Actual data lookup and subprocess execution remain in the route helper.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/instant_commands.py jane_web/main.py tests/test_instant_commands.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_instant_commands.py tests/test_music_playlists.py tests/test_essence_helpers.py -q` passed (`15 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`378 passed`).

Remaining follow-up slices:
- Chat stream idempotency/replay helpers can be split from `_handle_jane_chat_stream`.
- Provider status response shaping can be extracted from route logic.

## 2026-07-02 - Dynamic Essence Lookup Helpers

Goal/scope:
- Extract dynamic essence search-dir construction, manifest lookup, custom-tools path resolution, and page target resolution from `jane_web/main.py`.
- Reuse the existing `jane_web/essence_helpers.py` module rather than introducing a parallel abstraction.

Files/modules changed:
- `jane_web/essence_helpers.py`
- `jane_web/main.py`
- `tests/test_essence_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Tool lookup still first checks the direct `<tools_dir>/<essence_slug>/functions/custom_tools.py` path.
- Manifest lookup still matches `essence_name` case-insensitively and ignores bad manifests.
- Dynamic essence pages still redirect type `essence` items to `/?essence=<folder>`.
- Missing tools and missing templates still produce the same 404 route behavior.
- `TOOLS_DIR=""` still remains an explicit value instead of falling back to `<ambient>/skills`.

Boundary chosen:
- Filesystem manifest scanning is deterministic and shared by two routes.
- Subprocess execution, JSON output handling, HTML response creation, and FastAPI errors remain in `main.py`.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/essence_helpers.py jane_web/main.py tests/test_essence_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_essence_helpers.py tests/test_music_playlists.py -q` passed (`12 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`375 passed`).

Remaining follow-up slices:
- Essence tool subprocess result parsing can be split from request/routing.
- Essence detail/load/unload routes still have repeated manifest/state handling.

## 2026-07-02 - Music Playlist Matching Helpers

Goal/scope:
- Extract music query normalization, temporary playlist cleanup rules, named-playlist matching, music-file tier matching, playlist naming, and track shaping from `jane_web/main.py`.
- Keep playlist DB reads/writes, filesystem globbing, random sampling, route auth, and HTTP errors in `main.py`.

Files/modules changed:
- `jane_web/music_playlists.py`
- `jane_web/main.py`
- `tests/test_music_playlists.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Temporary playlists are still names `Random Mix` or prefixed with `Playing:` and still age out by string timestamp cutoff.
- Voice wrappers like `play my ... playlist` still normalize to a core playlist name for Tier 0 matching.
- Existing real playlists still win before creating a temporary playlist.
- File matching still uses filename-only substring, all-content-word, any-content-word, then fuzzy tiers.
- Random queries still create `Random Mix`; non-random temporary playlists still use `Playing: {query.title()}`.
- Track paths remain relative to the vault root parent of `Music`.

Boundary chosen:
- Matching and shaping rules are pure helpers.
- DB-backed playlist operations and filesystem/random side effects stay in the web route function.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/music_playlists.py jane_web/main.py tests/test_music_playlists.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_music_playlists.py tests/test_file_search_helpers.py tests/test_upload_helpers.py -q` passed (`15 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`373 passed`).

Remaining follow-up slices:
- A behavior-improvement pass could decide whether music matching should include folder/artist path segments.
- Chat streaming idempotency and stream-limit helpers are still embedded in `main.py`.

## 2026-07-02 - Janitor Duplicate Selection Helpers

Goal/scope:
- Extract exact-duplicate normalization, timestamp parsing, keep-row selection, and stale-row grouping from `memory/v1/janitor_memory.py`.
- Keep quarantine append, Chroma deletion, and janitor logging in the runner.

Files/modules changed:
- `memory/v1/janitor_duplicates.py`
- `memory/v1/janitor_memory.py`
- `tests/test_janitor_duplicates.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Duplicate document matching still collapses whitespace and casefolds content.
- Groups still key by normalized topic, subtopic, and document text.
- Documents under 20 normalized characters still do not participate in duplicate purges.
- The kept row is still the one with the newest recognized timestamp, breaking ties by highest ID.
- Timestamp parsing still accepts naive UTC strings, `Z`, and offset-aware ISO values.
- Code-memory reverification still uses the same stored-UTC parser through the imported alias.

Boundary chosen:
- Selecting which rows are stale duplicates is pure metadata/text logic.
- The destructive delete/quarantine path remains centralized in `janitor_memory.py`.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/janitor_duplicates.py memory/v1/janitor_memory.py tests/test_janitor_duplicates.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_janitor_duplicates.py tests/test_janitor_rules.py tests/test_janitor_expiry.py -q` passed (`12 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`368 passed`).

Remaining follow-up slices:
- Long-term normalization candidate selection can be extracted before touching LLM rewrite/split calls.
- Verification report writing can be separated from Codex/frontier execution.

## 2026-07-02 - Janitor Known-Junk Rule Helpers

Goal/scope:
- Extract known-junk memory classification rules from `memory/v1/janitor_memory.py`.
- Keep Chroma collection scanning/deletion, quarantine writes, logging, and runtime filesystem/skill probes in the janitor runner.

Files/modules changed:
- `memory/v1/janitor_rules.py`
- `memory/v1/janitor_memory.py`
- `tests/test_janitor_rules.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- User-memory and long-term deletion reasons are unchanged.
- Queue/prompt artifacts, system test artifacts, outdated Amber/Discord/Docker memories, superseded Waterlily planning gaps, and low-value classes deploy snapshots keep the same labels.
- Docker-compose and Codex-skill existence checks are still evaluated by the runtime wrapper in `janitor_memory.py`.
- Duplicate grouping still uses the same lowercased metadata labels through the imported `_meta_label` alias.

Boundary chosen:
- Classification is pure rule evaluation once collection names and runtime probes are supplied.
- The destructive path remains in `janitor_memory.py`, so delete/quarantine behavior is not moved.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/janitor_rules.py memory/v1/janitor_memory.py tests/test_janitor_rules.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_janitor_rules.py tests/test_janitor_expiry.py -q` passed (`8 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`364 passed`).

Remaining follow-up slices:
- Duplicate grouping/timestamp selection in `janitor_memory.py` can be extracted next.
- Code-memory verification report assembly is still intertwined with Codex/frontier calls.

## 2026-07-02 - Janitor Expiry Helpers

Goal/scope:
- Extract short-term memory expiration decisions from `memory/v1/janitor_memory.py`.
- Keep ChromaDB client access, collection deletion, and logging in the janitor runner.

Files/modules changed:
- `memory/v1/janitor_expiry.py`
- `memory/v1/janitor_memory.py`
- `tests/test_janitor_expiry.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Janitor expiry still accepts Unix int/float and ISO-string `expires_at` values.
- Missing or malformed expiry values still do not expire.
- TTL purge still looks only at `expires_at`.
- Hard age purge still looks only at `timestamp`, not `created_at`.
- Janitor parsing stays separate from retrieval expiration parsing, which has a different timezone/Z handling contract.

Boundary chosen:
- Expired-ID selection is pure metadata filtering.
- DB existence checks, Chroma collection reads/deletes, and log messages remain in `janitor_memory.py`.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/janitor_expiry.py memory/v1/janitor_memory.py tests/test_janitor_expiry.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_janitor_expiry.py tests/test_memory_text.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`359 passed`).

Remaining follow-up slices:
- Known-junk classification in `janitor_memory.py` is another pure rule cluster, but it has environment probes that need dependency injection before extraction.
- Code-memory verification report assembly can be split from frontier/Codex calls.

## 2026-07-02 - Context Compaction Split Helper

Goal/scope:
- Extract context-window split-index calculation from `memory/v1/conversation_manager.py`.
- Keep token counting, summary generation, injected-metadata cleanup, and conversation-history mutation in the manager.

Files/modules changed:
- `memory/v1/context_compaction.py`
- `memory/v1/conversation_manager.py`
- `tests/test_context_compaction.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- No compaction occurs when current tokens are at or below the threshold.
- The removal target still includes the threshold overflow plus 25% of `max_tokens`.
- The split still clamps to keep at least two history entries when possible.
- Single-entry histories still return no split.

Boundary chosen:
- Split calculation is pure arithmetic over token counts.
- LLM summarization and history mutation stay in the manager where side effects are visible.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/context_compaction.py memory/v1/conversation_manager.py tests/test_context_compaction.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_context_compaction.py tests/test_conversation_text.py tests/test_conversation_windows.py tests/test_conversation_themes.py -q` passed (`17 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`356 passed`).

Remaining follow-up slices:
- Context compaction can get an integration-style fake manager test if we want coverage for summary insertion.
- The thematic prompt builders remain embedded near LLM calls.

## 2026-07-02 - Conversation Theme Helper Extraction

Goal/scope:
- Extract pure theme-title normalization, theme registry prompt formatting, and user-identity signal counting from `memory/v1/conversation_manager.py`.
- Keep DB-backed theme registry fetch/seed/register and archival topic resolution in `ConversationManager`.

Files/modules changed:
- `memory/v1/conversation_themes.py`
- `memory/v1/conversation_manager.py`
- `tests/test_conversation_themes.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Theme titles still collapse whitespace, strip punctuation/spacing at the ends, and truncate at 80 characters.
- Empty theme registries still render as `- (none)`.
- Theme prompt rows still render as `theme_id: title — description`, with `No description.` fallback.
- User-identity reclassification still requires at least two identity-signal matches and still logs the match count from the manager.
- Theme registration and new-theme fallback behavior remain unchanged.

Boundary chosen:
- The extracted pieces are pure formatting/matching rules around the theme registry.
- DB writes and registry mutation stay in the manager to avoid changing durable memory side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/conversation_themes.py memory/v1/conversation_manager.py tests/test_conversation_themes.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_conversation_themes.py tests/test_conversation_text.py tests/test_conversation_windows.py -q` passed (`13 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`352 passed`).

Remaining follow-up slices:
- `_resolve_archival_topic` can be characterized with fake theme registration before extracting more.
- Prompt construction for archivist/theme-summary calls is still embedded in the manager.

## 2026-07-02 - Conversation Window Archival Helpers

Goal/scope:
- Extract pure timestamp parsing, metadata timestamp selection, ledger-turn window grouping, SQL timestamp normalization, and window transcript rendering from `memory/v1/conversation_manager.py`.
- Keep SQLite reads/writes, watermark state, archival failure counters, throttling, and long-term promotion side effects in `ConversationManager`.

Files/modules changed:
- `memory/v1/conversation_windows.py`
- `memory/v1/conversation_manager.py`
- `tests/test_conversation_windows.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Ledger timestamps still accept SQLite and ISO-ish shapes by stripping timezone and fractional seconds.
- Long-term watermark seeding still uses the first available metadata key in `archived_at`, `timestamp`, `created_at`, `updated_at` order.
- Window splitting still uses idle gaps and the existing maximum-turn cap.
- Transcript rendering still strips injected metadata, skips protocol/meta chatter, uppercases roles, and preserves the existing empty-role transcript prefix.
- The manager still exposes `_parse_ledger_ts` and `_build_window_transcript` as compatibility methods.

Boundary chosen:
- Window grouping and transcript rendering are pure transformations over ledger rows.
- Keeping DB queries and archive writes in the manager avoids changing concurrency, watermark, or poison-window behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/conversation_windows.py memory/v1/conversation_manager.py tests/test_conversation_windows.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_conversation_windows.py tests/test_conversation_text.py -q` passed (`10 passed`).
- Imported and instantiated `ConversationManager` smoke path successfully.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`349 passed`).

Remaining follow-up slices:
- `run_window_archival` can now be tested with a fake DB/archiver before moving more control flow.
- Theme classification and update prompt construction remain intertwined with LLM calls.

## 2026-07-02 - Conversation Text Helper Extraction

Goal/scope:
- Extract pure conversation text cleanup, thematic-turn preparation, low-value turn filtering, code-edit detection, and short-term summary normalization from `memory/v1/conversation_manager.py`.
- Keep `ConversationManager` method names as compatibility facades so existing callers and injected cleaners continue to work.

Files/modules changed:
- `memory/v1/conversation_text.py`
- `memory/v1/conversation_manager.py`
- `tests/test_conversation_text.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Metadata stripping still removes protocol/state blocks but preserves the existing blank-line behavior.
- Bad thematic output detection still requires protocol/meta markers instead of rejecting all clarification-like text.
- Thematic turn preparation still labels surviving turns as `User:` and `Jane:`.
- Short-term turn filtering keeps the existing low-value chatter rules.
- The existing uppercase marker check behavior is preserved, including the current quirk where already-lowercased text means `MEMORY_SYSTEM_OK` is not filtered by that branch.
- `ConversationManager._strip_injected_metadata`, `_prepare_thematic_turn`, `_should_store_short_term_turn`, `_looks_like_code_edit`, and `_normalize_short_term_summary` still exist.

Boundary chosen:
- These helpers are pure text rules that do not need SQLite, ChromaDB, timers, or LLM calls.
- Keeping compatibility facades reduces risk while making the rules directly unit-testable.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/conversation_text.py memory/v1/conversation_manager.py tests/test_conversation_text.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_conversation_text.py -q` passed (`5 passed`).
- Imported `ConversationManager` and exercised the delegated facade methods successfully.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`344 passed`).

Remaining follow-up slices:
- Decide separately whether the uppercase-marker filter should be fixed as a behavior change.
- Window archival helpers in `ConversationManager` still mix timestamp parsing, transcript assembly, cursor pagination, and archive side effects.

## 2026-07-02 - RA JSON Response Parsing Helper

Goal/scope:
- Move LLM JSON response extraction from `agent_skills/ra_research_cron.py` into the RA text helper module.
- Keep Ollama request/response handling and warning behavior in the cron runner.

Files/modules changed:
- `agent_skills/ra_research_text.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_text.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Direct JSON objects, fenced `json` blocks, generic fenced blocks, and embedded objects are still accepted.
- Empty, malformed, and non-object JSON payloads still return `None`.
- The cron's `ollama_chat_json` still treats `None` as invalid JSON and falls back through the existing path.

Boundary chosen:
- Parsing model text into a JSON object is pure text normalization, not cron orchestration.
- Housing it with the existing RA text helpers gives malformed-response coverage without mocking HTTP.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_cron.py agent_skills/ra_research_text.py tests/test_ra_research_text.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_text.py tests/test_ra_research_candidates.py tests/test_ra_research_summary_cache.py -q` passed (`16 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`339 passed`).

Remaining follow-up slices:
- `process_candidates` still has multiple responsibilities around PubMed efetch, artifact creation, summarization, and state mutation.
- The deterministic action-plan/recommendation fallback sections can be audited for pure extraction once RA source processing is cleaner.

## 2026-07-02 - RA Candidate Selection Helpers

Goal/scope:
- Extract deterministic RA source-candidate selection rules from `agent_skills/ra_research_cron.py`.
- Keep live PubMed requests, throttling, warnings, cache writes, and run orchestration in the cron runner.

Files/modules changed:
- `agent_skills/ra_research_candidates.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_candidates.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Seed web sources still create `seed_web_source` findings and `web_<id>` candidates.
- Seed-source selection still stops immediately once the requested new-source limit is reached.
- PubMed findings keep the same `pubmed_search_result` cache shape.
- Processed PubMed PMIDs still count toward backlog page consumption before the next unprocessed candidate is selected.
- Backlog query offsets still advance by the number of PMIDs consumed from the returned page.

Boundary chosen:
- Candidate selection is pure list/state-shape logic; PubMed I/O and cache file emission remain in `collect_candidate_sources`.
- This makes pagination and duplicate-skipping behavior testable without network calls.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_cron.py agent_skills/ra_research_candidates.py tests/test_ra_research_candidates.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_candidates.py tests/test_ra_research_summary_cache.py tests/test_ra_research_text.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`337 passed`).

Remaining follow-up slices:
- LLM JSON extraction can move into `ra_research_text.py` with direct malformed/fenced JSON tests.
- `process_candidates` still mixes PubMed efetch batching, artifact saving, summarization, and state updates.

## 2026-07-02 - RA Summary Cache Helpers

Goal/scope:
- Extract RA source-summary cache loading, finalized summary metadata, processed-source state entries, artifact text lookup, and per-source summary markdown from `agent_skills/ra_research_cron.py`.
- Keep PubMed/web fetching, LLM calls, fallback summary creation, state mutation, and cron orchestration in the cron runner.

Files/modules changed:
- `agent_skills/ra_research_summary_cache.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_summary_cache.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Complete cached summaries still bypass a new LLM call unless `needs_llm_review` is set.
- Existing fallback summaries are still reused when an attempted LLM upgrade returns no valid summary.
- Processed-source state entries keep the same keys and path formats.
- Retry upgrades still read artifact text in `full_text.txt`, `readable_text.txt`, then `abstract.txt` order.
- Per-source markdown keeps the same source trace sections and `None captured.` placeholders.

Boundary chosen:
- Summary cache and artifact lookup are deterministic I/O helpers with narrow state shapes.
- Network fetching, prompt construction, source selection, and report delivery remain in `ra_research_cron.py`, where the run-level control flow is still visible.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_cron.py agent_skills/ra_research_summary_cache.py tests/test_ra_research_summary_cache.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_*.py -q` passed (`30 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`332 passed`).

Remaining follow-up slices:
- Candidate source selection in `collect_candidate_sources` still mixes seed source handling, PubMed pagination, duplicate detection, and cache writes.
- LLM JSON parsing can move into the RA text helpers as a pure parsing boundary.

## 2026-07-02 - Nearest Memory Query Specs

Goal/scope:
- Extract nearest-memory plan-to-Chroma-query-spec construction from `memory/v1/memory_retrieval.py`.
- Keep embedding, Chroma querying, candidate scoring, sorting, and output selection in `memory_retrieval.py`.

Files/modules changed:
- `memory/v1/nearest_query_specs.py`
- `memory/v1/memory_retrieval.py`
- `tests/test_nearest_query_specs.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Query source order remains user/shared memories, Jane long-term, short-term, file index, then essence memory.
- Managed user memory still uses the supplied private user-memory path; shared mode uses the global user-memory DB.
- Search limits still use `max(source_default, limit * 4)`.
- File-index nearest search still has a minimum of `8`.
- Essence memory still uses collection name `essence_knowledge` and falls back to an empty path when no essence path is supplied.

Boundary chosen:
- Query-spec construction is pure and plan-driven; the noisy Chroma/SentenceTransformer work remains sequential in the caller.
- This makes nearest-memory source coverage easy to test without loading vector stores.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/nearest_query_specs.py memory/v1/memory_retrieval.py tests/test_nearest_query_specs.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nearest_query_specs.py tests/test_nearest_memory.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`327 passed`).

Remaining follow-up slices:
- Source-specific memory row filtering in `build_memory_sections` can be split with test fixtures for docs/metas/distances.
- Full Chroma query execution should stay in place until there are fake collection tests.

## 2026-07-02 - Memory Section Assembly Helper

Goal/scope:
- Extract memory context section dedupe, labeling, ordering, and formatting from `memory/v1/memory_retrieval.py`.
- Keep Chroma queries, distance filtering, recency boost, cache lookup/write, and retrieval planning in `memory_retrieval.py`.

Files/modules changed:
- `memory/v1/memory_sections.py`
- `memory/v1/memory_retrieval.py`
- `tests/test_memory_sections.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Cross-section dedupe still uses one shared content-key set, so higher-priority sections claim duplicate facts first.
- Section order remains permanent, user/shared long-term, Jane archived long-term, short-term, file index, legacy forgettable, then essence memory.
- Long-term section label still switches between `current user` and `shared` based on `plan.use_user_memory`.
- Short-term and file-index advisory headings are unchanged.
- Empty fact groups still produce no section.

Boundary chosen:
- The extracted function is pure output assembly after all retrieval/filtering decisions are complete.
- This gives direct coverage for memory context format without faking ChromaDB or embedding models.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/memory_sections.py memory/v1/memory_retrieval.py tests/test_memory_sections.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_memory_sections.py tests/test_memory_text.py tests/test_memory_sections_cache.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`323 passed`).

Remaining follow-up slices:
- Query execution/result filtering could be split by source, but needs Chroma fixtures or fakes.
- Nearest-memory query-spec construction can be extracted if it remains pure and plan-driven.

## 2026-07-02 - Proxy Session Pruning Helpers

Goal/scope:
- Extract Jane proxy session-key, stale-session, global-idle, and oldest-session calculations from `jane_web/jane_proxy.py`.
- Keep session table mutation, ConversationManager creation, `end_session` calls, and logging in `jane_proxy.py`.

Files/modules changed:
- `jane_web/proxy_sessions.py`
- `jane_web/jane_proxy.py`
- `tests/test_proxy_sessions.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Composite session keys are still `<user_id>:<session_id>`.
- Malformed keys without `:` still split to an empty session ID so pruning drops them without calling `end_session`.
- Global Claude Code activity still blocks pruning when `now - last_active <= ttl`.
- Session expiry still uses a strict `>` TTL comparison.
- Capacity eviction still picks the session with the smallest `last_accessed_at`.

Boundary chosen:
- These rules are pure decisions around stateful session lifecycle behavior.
- The helper returns keys and booleans only; actual eviction, archival, and logging remain in the proxy.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/proxy_sessions.py jane_web/jane_proxy.py tests/test_proxy_sessions.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_proxy_sessions.py tests/test_proxy_brain.py -q` passed (`9 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`319 passed`).

Remaining follow-up slices:
- Persistent brain sync/stream branches still repeat prompt/session setup, but moving them needs fakes for manager/session behavior.
- Conversation persistence worker setup can be revisited with focused tests around summary update and FIFO skip behavior.

## 2026-07-02 - Permission Route Payload Helpers

Goal/scope:
- Extract Jane permission-request, permission-response, wait-result, and pending-entry shapes from `jane_web/main.py`.
- Keep permission broker creation, blocking waits, resolution, and FastAPI routing in place.

Files/modules changed:
- `jane_web/permission_helpers.py`
- `jane_web/main.py`
- `tests/test_permission_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Permission request payloads still require `request_id` and `tool_name` via direct indexing.
- `tool_input` still defaults to `{}` and `session_id` still defaults to `""`.
- Permission responses still require `request_id`; `approved` defaults to `False` and is not coerced to `bool`.
- Wait responses still include `approved` and `reason`.
- Pending responses still expose `request_id`, `tool_name`, `tool_input`, and `created_at`.

Boundary chosen:
- The extracted logic is pure payload/response shaping around the stateful permission broker.
- The broker’s async wait and resolution behavior remains in the route handlers where control flow is visible.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/permission_helpers.py jane_web/main.py tests/test_permission_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_permission_helpers.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`315 passed`).

Remaining follow-up slices:
- Admin localhost-control helpers are still possible but low payoff.
- CLI login endpoint cleanup remains a larger candidate, but should proceed only through pure parser/status helpers.

## 2026-07-02 - Essence Management Helpers

Goal/scope:
- Extract active-essence JSON state handling, essence manifest summary reading, essence list-item shaping, lookup rules, and active-list removal from `jane_web/main.py`.
- Keep essence load/unload/delete calls, capability registry mutation, context-cache invalidation, and FastAPI error mapping in the routes.

Files/modules changed:
- `jane_web/essence_helpers.py`
- `jane_web/main.py`
- `tests/test_essence_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing, invalid, or unreadable `active_essence.json` still reads as an empty active list.
- Active essence state still writes `{"active": [...]}` with indent `2`.
- Essence list summaries still include `name`, `role_title`, `description`, `type`, `has_brain`, `loaded`, `capabilities`, and `preferred_model`.
- Manifest summary reads still fall back to empty `capabilities` and `preferred_model` on JSON/OS errors.
- Detail/load endpoints still match by exact essence name only.
- Activation still tries exact display name first, then folder basename.
- Unload/delete still only rewrite active state when the removed essence was active.

Boundary chosen:
- Active-state and manifest shaping are deterministic/file-backed support code around route-owned lifecycle side effects.
- Keeping lifecycle mutations in `main.py` avoids hiding capability registry and cache invalidation behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/essence_helpers.py jane_web/main.py tests/test_essence_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_essence_helpers.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`312 passed`).

Remaining follow-up slices:
- Essence lifecycle route tests would allow moving more load/unload/delete orchestration later.
- Top-level admin/local-control response shaping remains possible but has lower payoff than the extracted route clusters.

## 2026-07-02 - Tax Route Helper Module

Goal/scope:
- Extract tax-accountant route validation, generated-form lookup, upload-path construction, and tax-tool argument shaping from `jane_web/main.py`.
- Keep uploaded file writes, tax tool execution, Chroma knowledge search, and FastAPI response/error handling in the routes.

Files/modules changed:
- `jane_web/tax_helpers.py`
- `jane_web/main.py`
- `tests/test_tax_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Tax form names still use the same `^[a-zA-Z0-9_-]+$` validation.
- Interview answer calls still default to `step_id="filing_status"` and `user_response={}`.
- Generated forms still resolve under `working_files/output` and choose the reverse-sorted first filename starting with the requested form name.
- Tax summaries still read `working_files/calculations/tax_result.json`.
- Uploads still land under `user_data/uploads` with `os.path.basename(file.filename or "upload")`.
- Upload-document tool args still contain `file_path` and `doc_type`.

Boundary chosen:
- These helpers are deterministic path/argument rules around a subprocess-backed essence integration.
- The route remains responsible for all file I/O and external tax tool behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/tax_helpers.py jane_web/main.py tests/test_tax_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_tax_helpers.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`307 passed`).

Remaining follow-up slices:
- Tax knowledge-search result shaping can move once Chroma query result fixtures are added.
- CLI login code remains a larger route cluster; only pure parser/status helpers should be moved without route-level OAuth tests.

## 2026-07-02 - Web Automation Profile And Secret Helpers

Goal/scope:
- Extend `jane_web/web_automation_helpers.py` with profile create/capture payload cleanup and secret list/create response shaping.
- Keep browser profile storage, visible capture sessions, encrypted secret storage, and FastAPI error mapping in `jane_web/main.py`.

Files/modules changed:
- `jane_web/web_automation_helpers.py`
- `jane_web/main.py`
- `tests/test_web_automation_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Profile `display_name` and `domain` are still stripped and required.
- Capture `login_url` and `success_url_pattern` are still stripped; `timeout_s` still uses `int(body.get("timeout_s") or 300)`.
- Secret `domain` and `label` are still stripped and required with `password`.
- Secret `username`, `password`, and `notes` still preserve surrounding whitespace.
- Secret list responses still expose `secret_id`, `domain`, `label`, `created_at`, and `last_used`.

Boundary chosen:
- These are deterministic payload and response-shaping rules in the same route cluster as the previous web automation plan helper.
- The storage and browser automation side effects remain directly in the route handlers.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/web_automation_helpers.py jane_web/main.py tests/test_web_automation_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_web_automation_helpers.py -q` passed (`9 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`303 passed`).

Remaining follow-up slices:
- Workflow save payload shaping can be extracted if it does not obscure `workflow.save` validation.
- Browser capture timeout/error behavior should remain route-owned unless route-level tests are added.

## 2026-07-02 - Web Automation Plan Helpers

Goal/scope:
- Extract web automation plan request normalization and result response shaping from `jane_web/main.py`.
- Keep web automation imports, `TaskStep` construction, profile domain binding, browser execution, and workflow storage side effects in the routes.

Files/modules changed:
- `jane_web/web_automation_helpers.py`
- `jane_web/main.py`
- `tests/test_web_automation_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing/non-list/empty `steps` still produce `400` with `'steps' must be a non-empty array`.
- Individual malformed steps still produce `400` with the same indexed `step N malformed` detail, after automation imports happen.
- Step actions are still stringified, falsey args still become `{}`, and `confirm` still coerces through `bool`.
- Labels still default to `adhoc` and truncate to 40 characters.
- `headless` is still accepted only as a real boolean; `record_trace` still uses `bool(...)`.
- Profile IDs are still passed through unstripped after the existing strip-only truthiness check.
- Plan and workflow-run result payloads still include `ok`, `run_id`, `summary`, and `data`.

Boundary chosen:
- The extracted pieces are deterministic request/response shaping shared by the plan and workflow-run routes.
- The route remains responsible for import-time failures, profile loading, browser execution, and workflow lookup errors.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/web_automation_helpers.py jane_web/main.py tests/test_web_automation_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_web_automation_helpers.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`299 passed`).

Remaining follow-up slices:
- Web automation profile/secret create payload cleanup can be extracted next.
- Browser profile capture should stay route-owned unless timeout and regex behavior are characterized separately.

## 2026-07-02 - Canonical Docs Helper Module

Goal/scope:
- Move canonical docs whitelist, config directory resolution, metadata stat, and body read helpers out of `jane_web/main.py`.
- Keep FastAPI route registration, auth, and 404 response mapping in `main.py`.

Files/modules changed:
- `jane_web/canonical_docs.py`
- `jane_web/main.py`
- `tests/test_canonical_docs.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The public doc slugs and titles remain `architecture`, `memory`, `skills`, `todos`, `accomplishments`, and `cron`.
- Config docs still resolve under `$VESSENCE_HOME/configs`, defaulting to `~/ambient/vessence/configs`.
- List metadata still returns `slug`, `title`, `file`, `bytes`, and integer `last_modified` without reading the body.
- Body responses still include `content` plus the same metadata fields.
- Unknown, missing, or unreadable docs still return `None` from helpers so the route can keep returning 404.

Boundary chosen:
- Canonical doc access was already a coherent read-only helper cluster embedded in `main.py`.
- Extracting it makes the docs API easier to audit while preserving route-level HTTP behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/canonical_docs.py jane_web/main.py tests/test_canonical_docs.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_canonical_docs.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`294 passed`).

Remaining follow-up slices:
- Web automation request validation is another contained route cluster with pure payload rules.
- Marketplace manual-refresh process/log planning can be extracted once env-cleanup behavior has tests.

## 2026-07-02 - Marketplace Route Validation Helpers

Goal/scope:
- Extract Facebook Marketplace route validation and create-search payload normalization from `jane_web/main.py`.
- Keep marketplace config/harvester/summarizer imports, saved-search persistence, detail lookup, photo lookup, and refresh subprocess launching in the routes.

Files/modules changed:
- `jane_web/marketplace_helpers.py`
- `jane_web/main.py`
- `tests/test_marketplace_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Search names still match `^[a-z0-9_-]{1,40}$`.
- Listing slugs and IDs still match `^[a-z0-9_-]{1,60}$` and `^[0-9]{4,25}$`.
- Photo names still match `photo_<2-3 digits>.(jpg|jpeg|png|webp)`.
- Create-search names are still stripped before validation.
- `label` still falls back to the safe name, query values are still stringified/stripped, and `location_id` still falls back to the marketplace default.
- The original raw `queries` gate is preserved: any non-empty list passes the route-level "queries required" check, even if all values strip to empty.

Boundary chosen:
- The extracted rules are deterministic input policy shared by multiple Marketplace endpoints.
- The routes remain responsible for translating validation failures to HTTP responses and for all Marketplace module side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/marketplace_helpers.py jane_web/main.py tests/test_marketplace_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_marketplace_helpers.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`290 passed`).

Remaining follow-up slices:
- Marketplace manual-refresh process/log planning can be extracted after adding tests for environment cleanup and log-path selection.
- The canonical docs routes have compact file-reading helpers that can be extracted next if route behavior is easy to characterize.

## 2026-07-02 - Briefing Request Payload Helpers

Goal/scope:
- Extract URL/title/text/category request cleanup from briefing article submit and summarization routes.
- Keep daily-briefing tool calls, article fetching, summarization, processor spawning, and FastAPI error mapping in `jane_web/main.py`.

Files/modules changed:
- `jane_web/briefing_requests.py`
- `jane_web/main.py`
- `tests/test_briefing_requests.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- URL fields still use the existing `body.get("url", "").strip()` behavior.
- HTTP URL validation still only checks for an `http://` or `https://` prefix.
- Submit payloads still strip `title`, `text`, and category fields.
- `save_category` still wins over `category`.
- Text-summary payloads still strip `title` and `text`, and route-level blank-text rejection is unchanged.

Boundary chosen:
- Payload cleanup is deterministic and repeated across three briefing routes.
- The side-effectful briefing imports, article extraction, summarization, and background processor spawn remain directly visible in the route handlers.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/briefing_requests.py jane_web/main.py tests/test_briefing_requests.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_briefing_requests.py tests/test_briefing_media.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`285 passed`).

Remaining follow-up slices:
- Background shared-queue path/log-path planning can be extracted, but process spawning itself should stay route-owned.
- Marketplace route validation is another compact pure-helper candidate outside the briefing area.

## 2026-07-02 - Briefing Media And Identifier Helpers

Goal/scope:
- Extract briefing article identifier/date validation plus audio/image/archive path selection from `jane_web/main.py`.
- Keep FastAPI response construction, load-shedding, file existence checks for image/archive routes, and route-specific HTTP errors in place.

Files/modules changed:
- `jane_web/briefing_media.py`
- `jane_web/main.py`
- `tests/test_briefing_media.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Briefing article IDs and summary types still use the same `^[a-zA-Z0-9_-]+$` validation.
- Archive dates still validate shape only as `YYYY-MM-DD`; calendar validity is unchanged.
- Audio lookup still checks `<article_id>_<summary_type>.ogg` before `.wav` and returns `audio/ogg` or `audio/wav`.
- Image lookup still tries `.jpg`, `.jpeg`, `.png`, `.webp`, then `.gif`.
- Archive files still resolve to `<archive_dir>/<date>.json`.

Boundary chosen:
- Repeated validation and path construction are deterministic and shared across article detail, audio, dismiss/undismiss, unsave, image, and archive routes.
- The routes remain responsible for FileResponse creation, not-found errors, and system-load checks.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/briefing_media.py jane_web/main.py tests/test_briefing_media.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_briefing_media.py tests/test_briefing_articles.py tests/test_briefing_saved.py -q` passed (`13 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`280 passed`).

Remaining follow-up slices:
- Briefing URL submission/summarization request cleanup can be extracted if the route-specific subprocess/tool calls stay in place.
- Saved-article JSON read/write helpers still need corrupt/missing file characterization before moving.

## 2026-07-02 - Saved Briefing Article Helpers

Goal/scope:
- Extract saved-briefing article path, record, category, and list shaping from `jane_web/main.py`.
- Keep request parsing, async JSON file reads/writes, vault file writes/deletes, and route HTTP errors in place.

Files/modules changed:
- `jane_web/briefing_saved.py`
- `jane_web/main.py`
- `tests/test_briefing_saved.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The saved index remains `<briefing_saved>/saved.json`.
- Daily briefing article cache lookup still uses `<TOOLS_DIR>/daily_briefing/essence_data/articles/<article_id>.json`.
- Vault copies still write to `vault/saved_articles/<category>/<article_id>.json`.
- Saved records still contain `article_id`, `category`, `saved_at`, and `article`.
- Category listing still combines vault folder names with categories from the JSON index, using `Uncategorized` when a saved record lacks a category.
- Saved articles are still optionally filtered by exact category and sorted newest-first by `saved_at`.

Boundary chosen:
- The extracted functions are deterministic path and collection shaping shared across save/list/category/unsave endpoints.
- Route-owned storage side effects remain visible in `main.py`, which avoids bundling file persistence semantics into this refactor.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/briefing_saved.py jane_web/main.py tests/test_briefing_saved.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_briefing_saved.py tests/test_briefing_articles.py -q` passed (`8 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`275 passed`).

Remaining follow-up slices:
- Briefing identifier validation and audio path selection are still duplicated but should be extracted with route tests for invalid IDs and missing audio files.
- Saved-article JSON read/write helpers should wait until corrupt-file and missing-file behavior is characterized.

## 2026-07-02 - Briefing Article List Response Helper

Goal/scope:
- Extract briefing article list normalization, filtering, pagination, and response shaping from `jane_web/main.py`.
- Keep the lazy daily-briefing tool import, cache reads, and FastAPI route error mapping in place.

Files/modules changed:
- `jane_web/briefing_articles.py`
- `jane_web/main.py`
- `tests/test_briefing_articles.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Cards with no `categories` still derive them from `tags`, or from `topic` when tags are missing.
- Cards with `image_path` and no `image_url` still get `/api/briefing/image/<id>`.
- `view="saved"` and case-insensitive topic filtering are unchanged.
- `full_summary` is still stripped only from the returned page.
- Pagination still coerces `limit`/`offset` to non-negative integers and reports the same `has_more`, `total`, `offset`, and `limit` values.
- Bad pagination values still map to `400` with `limit/offset must be integers`.

Boundary chosen:
- The route had pure response construction mixed with tool/cache orchestration. Moving that deterministic block makes the endpoint easier to audit without changing any briefing storage behavior.
- The helper intentionally preserves in-place card mutation because callers may depend on the current object-shaping side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/briefing_articles.py jane_web/main.py tests/test_briefing_articles.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_briefing_articles.py tests/test_cache_control.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`271 passed`).

Remaining follow-up slices:
- Saved-article record/category/path helpers are the next briefing-area candidate, but file read/write behavior should remain in the route.
- Briefing article/audio identifier validation can be centralized after adding route tests for the affected endpoints.

## 2026-07-02 - Contact Alias Payload Helper

Goal/scope:
- Extract contact alias body normalization from `jane_web/main.py`.
- Keep authentication, JSON parsing, `agent_skills.sms_helpers.add_alias`, and the route response in place.

Files/modules changed:
- `jane_web/sync_payloads.py`
- `jane_web/main.py`
- `tests/test_sync_payloads.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `alias` and `phone_number` are still stripped before validation and use.
- Requests missing either required field still return `400` with `alias and phone_number are required`.
- `display_name` is still passed through exactly as provided.
- The alias write side effect and `{"ok": ok}` response shape are unchanged.

Boundary chosen:
- This is another deterministic request-payload normalization rule in the same helper module that already owns contact and SMS sync payload shaping.
- The route remains responsible for external alias storage and FastAPI-specific error handling.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/sync_payloads.py jane_web/main.py tests/test_sync_payloads.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_sync_payloads.py tests/test_contact_search.py tests/test_sms_classification.py -q` passed (`13 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`267 passed`).

Remaining follow-up slices:
- Briefing saved-article path/category/result helpers have enough duplicated deterministic logic to extract next.
- Contact route SQL should stay in `main.py` until database fixture tests cover search/list behavior.

## 2026-07-02 - Web Upload Planning Helpers

Goal/scope:
- Extract deterministic file-upload planning from `jane_web/main.py`.
- Keep file reads/writes, SHA-256 hashing, hash-index persistence, Chroma file indexing, memory writes, database change notifications, and FastAPI error handling in the routes.

Files/modules changed:
- `jane_web/upload_helpers.py`
- `jane_web/main.py`
- `tests/test_upload_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Multi-upload descriptions still parse from JSON lists, and invalid/non-list payloads still behave as no descriptions.
- Image uploads without a description still fail in the route.
- Explicit destinations still win over MIME-based routing, including the existing `"/"` to empty-subdir behavior.
- Images without a destination still use `make_descriptive_filename`; all other uploads still use `Path(filename).name`.
- Existing destination filename collisions still suffix `_1`, `_2`, and so on.
- Duplicate, success, and `.hash_index.json` entry shapes are unchanged.

Boundary chosen:
- Upload naming and payload shaping are pure logic shared by multi-file and Android single-file uploads.
- Route-level I/O and indexing side effects remain in `main.py` so no upload storage, memory, or Chroma contract changes are bundled into the refactor.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/upload_helpers.py jane_web/main.py tests/test_upload_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_upload_helpers.py tests/test_file_browser_helpers.py tests/test_file_search_helpers.py -q` passed (`16 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`265 passed`).

Remaining follow-up slices:
- Upload hash-index read/write helpers could move later, but need route-level fixture tests around corrupt index files and write failures first.
- Contact alias validation and saved-briefing metadata shaping remain candidates for small route-helper extractions.

## 2026-07-02 - Web File Search Helpers

Goal/scope:
- Extract file-search path normalization, managed-user scope checks, type filtering, description excerpts, and result-shape construction from `jane_web/main.py`.
- Keep filesystem walking, Chroma lookup, and file-existence verification in the route.

Files/modules changed:
- `jane_web/file_search_helpers.py`
- `jane_web/main.py`
- `tests/test_file_search_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- File type filtering still compares lowercase filename extensions against the selected extension set.
- Absolute indexed paths are still made relative to the active vault root.
- Paths starting with `..` are still rejected.
- Managed users still reject indexed rows tagged with another `user_id`, while untagged rows remain allowed.
- Descriptions are still capped to 200 characters.
- File search result payloads still include `name`, `path`, `type`, `description`, and `/api/files/serve/<path>` URLs.

Boundary chosen:
- Chroma and filesystem work remains in the route, while deterministic row/path/result shaping moves into a tested helper.
- This reduces the most fragile part of the search route without changing route dependencies or query behavior.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/file_search_helpers.py jane_web/main.py tests/test_file_search_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_file_search_helpers.py tests/test_file_browser_helpers.py tests/test_file_context.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`259 passed`).

Remaining follow-up slices:
- The file-search route could get database/Chroma fakes later, but should not move query execution until then.
- Upload planning has similar deterministic pieces, but image-description enforcement and hash-index updates need route-level characterization.

## 2026-07-02 - Android Sync Payload Normalizers

Goal/scope:
- Extract contact and SMS sync row normalization from `jane_web/main.py`.
- Keep JSON parsing, capability checks, database deletes/inserts, logging, and duplicate handling in the routes.

Files/modules changed:
- `jane_web/sync_payloads.py`
- `jane_web/main.py`
- `tests/test_sync_payloads.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Contacts with blank `display_name` are still skipped.
- Contact phone/email empty strings still become `None`.
- `is_primary` still maps to 1/0.
- Existing `contact_id=None` behavior is preserved as the string `"None"`.
- SMS messages with blank sender or falsey `timestamp_ms` are still skipped.
- SMS body/sender are still stripped, `is_read` and `is_contact` still map to 1/0, and classification still receives the stripped body plus contact status.

Boundary chosen:
- Row normalization is deterministic payload shaping and can be tested without SQLite or FastAPI.
- Routes remain responsible for transaction behavior and route-level error handling.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/sync_payloads.py jane_web/main.py tests/test_sync_payloads.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_sync_payloads.py tests/test_sms_classification.py tests/test_contact_search.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`255 passed`).

Remaining follow-up slices:
- Contact alias validation can be extracted if route-level tests cover `agent_skills.sms_helpers.add_alias`.
- Message search/readback SQL should stay in routes until database fixture tests exist.

## 2026-07-02 - Web Self-Healing Report Helpers

Goal/scope:
- Extract self-healing report authorization and payload normalization from `jane_web/main.py`.
- Keep JSON parsing, HTTP response handling, and self-healing dispatch side effects in the route.

Files/modules changed:
- `jane_web/self_healing_reports.py`
- `jane_web/main.py`
- `tests/test_self_healing_reports.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Local requests still bypass the self-healing token.
- External requests still require a non-empty `JANE_SELF_HEAL_TOKEN` matching `x-jane-self-heal-token` via constant-time compare.
- Report defaults still use `external_app`, `error`, the web project root, `["external"]`, and the whole body as payload when fields are missing or malformed.
- Messages are still truncated to 2000 characters.
- Dict `payload` and list `tags` values are still preserved.

Boundary chosen:
- Auth and body shaping are deterministic request policy and easy to test without FastAPI route dispatch.
- The route remains responsible for parsing JSON, rejecting invalid bodies, and calling `_dispatch_self_healing_report`.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/self_healing_reports.py jane_web/main.py tests/test_self_healing_reports.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_self_healing_reports.py tests/test_request_helpers.py tests/test_request_logging.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`251 passed`).

Remaining follow-up slices:
- Self-healing dispatch wrappers should stay in `main.py` unless fakes are added for `capture_exception`/`capture_report`.
- Other route body-normalization helpers can move when they are similarly deterministic and side-effect free.

## 2026-07-02 - Web Request Logging Policy

Goal/scope:
- Extract request logging middleware polling-path, idle-state touch, and exception-context policy from `jane_web/main.py`.
- Keep actual logging, `_touch_idle_state`, and self-healing dispatch side effects in `main.py`.

Files/modules changed:
- `jane_web/request_logging.py`
- `jane_web/main.py`
- `tests/test_request_logging.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `/api/jane/announcements`, `/health`, `/api/files/changes`, and `/api/jane/live` remain polling paths that skip access-log lines and idle-state touches.
- Non-polling `GET`/`POST` API requests still touch idle state.
- Non-API pages and non-GET/POST API requests still do not touch idle state.
- Self-healing exception context still contains `elapsed_ms`, `method`, and `path`.

Boundary chosen:
- The extracted logic is deterministic request policy and can be tested without ASGI middleware, logging, or filesystem writes.
- Middleware remains the owner of request/response objects, timing, logs, and exception dispatch.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/request_logging.py jane_web/main.py tests/test_request_logging.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_request_logging.py tests/test_request_helpers.py tests/test_rate_limit.py tests/test_cache_control.py -q` passed (`14 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`247 passed`).

Remaining follow-up slices:
- Self-healing dispatch wrappers should stay in `main.py` unless fakes are added for `capture_exception`/`capture_report`.
- Auth/session bootstrap remains route-critical and should be characterized before moving.

## 2026-07-02 - Nearest Memory Candidate Filter

Goal/scope:
- Extract nearest-memory query term extraction, lexical overlap, and candidate filtering from `memory/v1/memory_retrieval.py`.
- Preserve Chroma query execution and result ordering in `query_nearest_memory_lines`.

Files/modules changed:
- `memory/v1/nearest_memory.py`
- `memory/v1/memory_retrieval.py`
- `tests/test_nearest_memory.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Query terms still keep tokens of length 4+ and drop the same stopwords.
- Candidates with missing/invalid distance, expired metadata, none-like content, distance above threshold, or insufficient lexical overlap are still rejected.
- Recent short-term memories can still be promoted ahead of distance filtering when they are <=14 days old and overlap is high enough.
- User memory candidates still drop file-index records, low-signal shared memories, low-signal short-term/forgettable memories, and prompt-queue entries.
- Short-term candidates still drop stale or low-signal entries unless they qualify for recent promotion.
- Accepted candidates still return priority, distance, source, content key, and formatted memory line with distance metadata.

Boundary chosen:
- Nearest-memory filtering is dense retrieval policy but deterministic once a Chroma result is available.
- Moving it out leaves `memory_retrieval.py` focused on query planning, Chroma calls, and final de-duplication.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/nearest_memory.py memory/v1/memory_retrieval.py tests/test_nearest_memory.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_nearest_memory.py tests/test_query_plan.py tests/test_query_intent.py tests/test_memory_text.py tests/test_low_signal_memory.py -q` passed (`22 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`244 passed`).

Remaining follow-up slices:
- Chroma query execution and section assembly remain in `memory_retrieval.py`; move only with integration fakes.
- Broad memory-section filtering could be extracted later, but needs fixture coverage for every section type.

## 2026-07-02 - Memory Retrieval Query Plan

Goal/scope:
- Extract shared memory retrieval target planning from `memory/v1/memory_retrieval.py`.
- Preserve Chroma query scheduling, filtering, and section formatting in `memory_retrieval.py`.

Files/modules changed:
- `memory/v1/query_plan.py`
- `memory/v1/memory_retrieval.py`
- `tests/test_query_plan.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Managed users still use their private memory path when it exists, suppress shared/Jane long-term/short-term/file-index lookups, and may still include essence memory.
- Shared Jane queries still include user memories, Jane long-term memory for `general` and `project_work` intents, and short-term memory.
- Amber queries still suppress Jane long-term memory.
- File lookup intent still enables file-index search only for shared-memory queries.
- Essence memory still depends on the configured essence Chroma path existing.

Boundary chosen:
- Both broad section retrieval and nearest-line retrieval used the same target booleans; extracting them removes duplicated policy while leaving query execution untouched.
- The plan helper accepts an injectable `path_exists` function, making managed/shared/essence combinations easy to test without filesystem setup.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/query_plan.py memory/v1/memory_retrieval.py tests/test_query_plan.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_query_plan.py tests/test_query_intent.py tests/test_query_markers.py tests/test_memory_sections_cache.py tests/test_memory_summary_cache.py tests/test_memory_text.py tests/test_low_signal_memory.py -q` passed (`30 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`238 passed`).

Remaining follow-up slices:
- Nearest-memory candidate filtering could be extracted next, but should get fixtures covering distance, lexical overlap, age promotion, and low-signal skips.
- Chroma query execution should stay in `memory_retrieval.py` unless integration fakes are added.

## 2026-07-02 - Proxy Ack Picker

Goal/scope:
- Extract quick acknowledgement category matching from `jane_web/jane_proxy.py`.
- Preserve the proxy's `_pick_ack` private name by importing the extracted helper as that alias.

Files/modules changed:
- `jane_web/proxy_ack.py`
- `jane_web/jane_proxy.py`
- `tests/test_proxy_ack.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Category priority remains question, status, fix/debug, opinion/advice, explanation, greeting, thanks, show/list, build, remove, frustration.
- Existing acknowledgement strings are preserved.
- Uncategorized messages still return `None` so the model can produce a context-aware acknowledgement.
- Production selection still uses `random.choice`; tests inject a deterministic chooser.

Boundary chosen:
- Ack selection is pure text classification plus response selection, independent from streaming, brain execution, persistence, and TTS.
- Extracting it removes a long response table from the proxy orchestration module and makes category priority explicit in tests.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/proxy_ack.py jane_web/jane_proxy.py tests/test_proxy_ack.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_proxy_ack.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_proxy_ack.py tests/test_proxy_brain.py tests/test_proxy_text.py tests/test_proxy_logging.py -q` passed (`15 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`234 passed`).

Remaining follow-up slices:
- Proxy persistence branch decisions remain a candidate after fakes are added for FIFO, `ConversationManager`, and summary dispatch.
- Stream event orchestration remains too broad to move without route-level streaming tests.

## 2026-07-02 - Proxy Brain Configuration Helpers

Goal/scope:
- Extract Jane proxy brain/provider selection helpers from `jane_web/jane_proxy.py`.
- Preserve existing private helper names in the proxy module through imported aliases/wrappers.

Files/modules changed:
- `jane_web/proxy_brain.py`
- `jane_web/jane_proxy.py`
- `tests/test_proxy_brain.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Active brain resolution still prefers a valid `JANE_BRAIN` in the env file, updates `os.environ`, and falls back to `JANE_BRAIN` from the process env.
- Session log IDs still truncate to 12 characters and use `none` for empty values.
- Gemini API, persistent Gemini, persistent Claude, standing Codex, and persistent Codex mode flags keep the same default env behavior.
- Persistent Codex is still disabled when standing Codex is enabled.
- Web-chat model selection still prefers provider-specific model env vars and falls back to provider `smart` defaults, with Codex using the OpenAI model env var.

Boundary chosen:
- Provider/mode/model selection is deterministic configuration logic shared by sync, stream, warmup, cleanup, and status paths.
- Moving it out reduces proxy orchestration noise without touching provider managers or request execution.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/proxy_brain.py jane_web/jane_proxy.py tests/test_proxy_brain.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_proxy_brain.py tests/test_proxy_text.py tests/test_proxy_logging.py -q` passed (`12 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`231 passed`).

Remaining follow-up slices:
- Proxy persistence worker branch decisions remain a candidate, but should be protected with fakes for FIFO, `ConversationManager`, and summary dispatch.
- Session cleanup remains riskier because it calls live provider managers and background threads.

## 2026-07-02 - RA Email Report Delivery Helpers

Goal/scope:
- Extract RA email report subject/body construction and successful email-send state mutation from `agent_skills/ra_research_cron.py`.
- Keep the actual `send_email` import/call, failure handling, and logging in the cron module.

Files/modules changed:
- `agent_skills/ra_research_delivery.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_delivery.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Email subjects still use `RA research update: remission/asymptomatic evidence (<date>)`.
- Email bodies still include latest report, recommendation scheme, action plan, action-plan snapshot, scheme snapshot, and the safety boundary.
- Action-plan and recommendation snapshots still truncate to 12000 and 6000 characters respectively.
- Successful email sends still update `last_report_sent_at`, `last_report_source_count`, `initial_report_sent`, and clear `last_report_error` without changing `last_report_channel`.

Boundary chosen:
- Email text/state shaping is deterministic and testable without mail credentials.
- The cron function still owns external email I/O and exception-state handling.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_delivery.py agent_skills/ra_research_cron.py tests/test_ra_research_delivery.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_delivery.py tests/test_ra_research_report_markdown.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`226 passed`).

Remaining follow-up slices:
- Announcement JSONL append can remain as direct I/O; extract only if file fake tests are added.
- RA source fetching and LLM synthesis remain intentionally in the cron runner until fixture-backed integration tests exist.

## 2026-07-02 - RA Report Delivery Helpers

Goal/scope:
- Extract report send-cadence decision, app notification payload construction, and app-delivery state mutation from `agent_skills/ra_research_cron.py`.
- Keep email sending, announcement file append, and logging side effects in the cron module.

Files/modules changed:
- `agent_skills/ra_research_delivery.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_delivery.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Forced sends still bypass cadence checks.
- Initial reports still wait until `RA_RESEARCH_INITIAL_REPORT_AFTER_RUNS`.
- Subsequent reports still use `last_report_sent_at` plus `RA_RESEARCH_REPORT_INTERVAL_HOURS`.
- Invalid or missing `last_report_sent_at` still falls back to the initial run-count gate.
- App notification payloads still use the same IDs, URLs, timestamps, message text, source counts, and path fields.
- App report state updates still set the same `last_report_*`, `initial_report_sent`, and `last_html_report_path` fields.

Boundary chosen:
- Cadence and payload/state shaping are deterministic and can be tested without writing announcement files or sending email.
- The cron module remains the owner of I/O: email import/send, JSONL append, path-derived report IDs, and logging.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_delivery.py agent_skills/ra_research_cron.py tests/test_ra_research_delivery.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_delivery.py tests/test_ra_research_report_markdown.py tests/test_ra_research_report_items.py tests/test_ra_research_text.py tests/test_ra_research_html.py -q` passed (`23 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`224 passed`).

Remaining follow-up slices:
- Email body construction can be extracted once tests pin subject/body truncation and failure-state behavior.
- Announcement JSONL appending should stay in the cron module unless file I/O fakes are added.

## 2026-07-02 - RA Full Run Report Markdown Renderer

Goal/scope:
- Extract full RA cron run-report Markdown assembly from `write_run_report`.
- Keep timestamped file path selection, atomic writes, and HTML report generation in `agent_skills/ra_research_cron.py`.

Files/modules changed:
- `agent_skills/ra_research_report_markdown.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_report_markdown.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Run reports still include generated label, source counts, recommendation/action/context/Codex/discoveries paths, the useful app-facing report, new source details, usefulness labels, signal scores, and action-plan/scheme snapshots.
- `write_run_report` still returns the Markdown and HTML paths and still writes the HTML version through `write_html_report`.
- Action-plan and recommendation snapshots keep the same truncation lengths.

Boundary chosen:
- Full report text assembly is deterministic rendering over summary data and static path labels.
- The cron runner remains responsible for filesystem paths, timestamps, writes, and HTML rendering side effects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_report_markdown.py agent_skills/ra_research_cron.py tests/test_ra_research_report_markdown.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_report_markdown.py tests/test_ra_research_report_items.py tests/test_ra_research_text.py tests/test_ra_research_html.py -q` passed (`19 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`220 passed`).

Remaining follow-up slices:
- Report delivery state mutation can be split next; keep email/app delivery I/O in the cron module unless fakes are added.
- Source fetching and LLM synthesis remain intentionally coupled to the cron runner until fixture-backed integration tests exist.

## 2026-07-02 - RA Useful Report Markdown Renderer

Goal/scope:
- Extract app-facing RA research report Markdown assembly from `agent_skills/ra_research_cron.py`.
- Keep a compatibility wrapper in the cron module so callers still use `build_useful_report_markdown(new_summaries, all_summaries, codex_result, source_count)`.

Files/modules changed:
- `agent_skills/ra_research_report_markdown.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_report_markdown.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The useful report still dedupes new summaries, ranks high-signal items, reports low-value/noisy sources, infers themes, and uses Codex discoveries/open questions when present.
- Default clinician questions and tracking items still fill in when no useful extracted items exist.
- Source headings, evidence labels, safety flags, full-file links, and source trace formatting stay the same.
- The cron wrapper still injects the live recommendation, action-plan, compressed-context, and discoveries paths into the final report.

Boundary chosen:
- Markdown assembly is deterministic rendering over cached summaries and belongs outside the network/LLM cron runner.
- The extracted renderer accepts paths as keyword arguments, keeping repo-specific path constants in `ra_research_cron.py`.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_report_markdown.py agent_skills/ra_research_cron.py tests/test_ra_research_report_markdown.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_report_markdown.py tests/test_ra_research_report_items.py tests/test_ra_research_text.py tests/test_ra_research_html.py -q` passed (`18 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`219 passed`).

Remaining follow-up slices:
- `write_run_report` still assembles the full cron report around the useful report and can be split after snapshot tests cover the full run markdown.
- Source fetching and LLM synthesis remain intentionally in the cron runner until fixture-backed integration tests exist.

## 2026-07-02 - Web Cache-Control Helper

Goal/scope:
- Extract response `Cache-Control` path classification from `jane_web/main.py`.
- Preserve the middleware wrapper and response mutation in `main.py`.

Files/modules changed:
- `jane_web/cache_control.py`
- `jane_web/main.py`
- `tests/test_cache_control.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `/static/` assets still get `public, max-age=86400`.
- `/api/briefing/image/` responses still get `public, max-age=3600`.
- Other `/api/` responses still get `no-store`.
- HTML/page routes still get `no-cache`.

Boundary chosen:
- Cache header selection is deterministic path policy and can be tested independently from ASGI middleware.
- The middleware still owns request/response objects and applies the returned header.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/cache_control.py jane_web/main.py tests/test_cache_control.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_cache_control.py tests/test_rate_limit.py tests/test_request_helpers.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`216 passed`).

Remaining follow-up slices:
- Request logging/self-healing middleware is a candidate only after tests pin exception dispatch behavior.
- Auth/session bootstrap remains a larger route-critical extraction and should get fakes before moving.

## 2026-07-02 - Web Request Inspection Helpers

Goal/scope:
- Extract deterministic request inspection helpers from `jane_web/main.py`.
- Leave session cookies, trusted-device bootstrap, and auth validation in `main.py`.

Files/modules changed:
- `jane_web/request_helpers.py`
- `jane_web/main.py`
- `tests/test_request_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Session IDs used in logs are still truncated to 12 characters and use `none` for empty values.
- Client IP selection still prefers `CF-Connecting-IP`, then `X-Real-IP`, then the request client host, then `unknown`.
- Secure-cookie detection still accepts direct HTTPS or the first `x-forwarded-proto` value equal to `https`.
- Local browser access still accepts only `127.0.0.1` and `::1` when no Cloudflare header is present.
- Single-user no-auth mode still depends only on a blank or missing `GOOGLE_CLIENT_ID`.
- Local request detection still rejects Cloudflare and forwarded-for headers, and accepts `127.0.0.1`, `::1`, and `localhost`.
- Android WebView detection still looks for `VessencesAndroid/` in the user agent.

Boundary chosen:
- These helpers are pure header/client/env checks shared by middleware, auth, page rendering, and logging.
- The extracted module avoids moving any code that mutates cookies, validates sessions, or creates trusted-device sessions.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/request_helpers.py jane_web/main.py tests/test_request_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_request_helpers.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_request_helpers.py tests/test_rate_limit.py tests/test_ra_reports.py tests/test_user_access.py tests/test_conversation_keys.py -q` passed (`27 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`215 passed`).

Remaining follow-up slices:
- Auth/session bootstrap can be tested separately with fake vault auth dependencies before any extraction.
- Cache-control middleware is still a small candidate, but lower value than the auth/request helpers just moved.

## 2026-07-02 - Web Rate Limit Helpers

Goal/scope:
- Extract the in-memory sliding-window rate limiter and endpoint bucket classification from `jane_web/main.py`.
- Preserve the middleware's localhost exemption and response/logging behavior in `main.py`.

Files/modules changed:
- `jane_web/rate_limit.py`
- `jane_web/main.py`
- `tests/test_rate_limit.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Chat, auth, upload, generic API, exempt telemetry, and page/static paths map to the same category/limit/window tuples.
- The limiter still drops timestamps outside the active window before deciding whether to allow a request.
- Denied requests still do not append another timestamp.
- Cleanup still runs only after more than 60 seconds and removes keys whose last hit is older than 120 seconds.

Boundary chosen:
- Rate limiting is middleware infrastructure, independent from FastAPI route handlers and session/auth logic.
- The extracted class accepts a clock function so sliding-window and cleanup behavior can be tested deterministically.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/rate_limit.py jane_web/main.py tests/test_rate_limit.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_rate_limit.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_rate_limit.py tests/test_model_settings.py tests/test_user_access.py tests/test_announcements.py tests/test_device_commands.py tests/test_file_browser_helpers.py -q` passed (`31 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`208 passed`).

Remaining follow-up slices:
- Request logging/cache-control middleware could be split only after tests pin header and self-healing behavior.
- The session bootstrap/auth cluster remains higher risk because it controls cookies, trusted devices, and account identity.

## 2026-07-02 - Web Model Settings Save Path

Goal/scope:
- Extract model-save env-var selection from `jane_web/main.py` into `jane_web/model_settings.py`.
- Replace the route's hand-written `.env` rewrite with the existing `EnvFileSettings.write_var` helper.
- Preserve the standing-brain restart block in the route.

Files/modules changed:
- `jane_web/model_settings.py`
- `jane_web/main.py`
- `tests/test_model_settings.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The save route still resolves the active provider from `JANE_BRAIN` and maps unknown providers to the Claude model env var.
- Missing or falsey `model` values still return `{"ok": False, "error": "No model specified"}` before any restart attempt.
- Successful saves still update the provider-specific env var and then run the same standing-brain restart try/except.
- `.env` line replacement semantics now use the same tested `EnvFileSettings` helper already used by other settings routes.

Boundary chosen:
- Provider/env-var selection is deterministic settings logic and belongs with the model settings payload helpers.
- The restart side effect stays in `main.py` because it depends on live standing-brain manager state.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/model_settings.py jane_web/main.py tests/test_model_settings.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_model_settings.py tests/test_env_settings.py -q` passed (`9 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_model_settings.py tests/test_env_settings.py tests/test_user_access.py tests/test_user_identity.py tests/test_conversation_keys.py -q` passed (`27 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`205 passed`).

Remaining follow-up slices:
- A future route-level test could fake the standing-brain manager if restart behavior needs to move.
- Other settings/admin routes can be split gradually around pure request validation and serialization helpers.

## 2026-07-02 - Web Admin Access Helper

Goal/scope:
- Extract `_is_user_admin` policy logic from `jane_web/main.py` into `jane_web/user_access.py`.
- Keep `_require_admin_session` and FastAPI route/session dependencies in `main.py`.

Files/modules changed:
- `jane_web/user_access.py`
- `jane_web/main.py`
- `tests/test_user_access.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Explicit configured admin identity variants still grant admin access before user-manager lookup.
- Managed user configs still grant admin access only when `user_admin` appears in `capabilities`.
- Missing user configs and configs without `user_admin` still return `False`.
- User-manager lookup failures still log `Failed checking user_admin capability for %s` and return `False`.

Boundary chosen:
- Admin-access policy belongs with the managed-user access helpers extracted in the prior slice.
- The helper accepts injectable identity/admin variant functions and user-manager loader so the behavior can be tested without importing the full web app.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/user_access.py jane_web/main.py tests/test_user_access.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_user_access.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_user_access.py tests/test_user_identity.py tests/test_conversation_keys.py tests/test_model_settings.py tests/test_env_settings.py tests/test_device_commands.py tests/test_announcements.py tests/test_file_browser_helpers.py -q` passed (`37 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`203 passed`).

Remaining follow-up slices:
- Model settings save can reuse `EnvFileSettings` after route-level tests cover standing-brain restart behavior.
- Remaining `main.py` route clusters should be split only where helper boundaries avoid request/response churn.

## 2026-07-02 - Web User Access Helpers

Goal/scope:
- Extract managed-user vault context, capability checks, request vault-root fallback, user memory path lookup, and public user config serialization from `jane_web/main.py`.
- Preserve the route layer's FastAPI dependencies, session lookup, and existing tuple return contracts.

Files/modules changed:
- `jane_web/user_access.py`
- `jane_web/main.py`
- `tests/test_user_access.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- User context still resolves session user first and falls back to the default user ID.
- User-manager import failure still returns the global vault, no capabilities, unmanaged status, and the resolved user ID.
- Unmanaged users still receive all capability IDs from `AVAILABLE_CAPABILITIES`.
- Managed users still read `vault_root_path` and `capabilities` from their config, falling back to the global vault when no private path is configured.
- Missing capabilities still raise `HTTPException(403)` only for managed users, with the same detail string.
- Request vault-root resolution still never raises and falls back to the global vault on any error.
- Managed user memory writes still use `memory_chromadb_path`; unmanaged and failure paths still return an empty string.
- Public admin-user payloads still include the same fields and defaults while excluding unrelated config keys.

Boundary chosen:
- The moved logic is per-user access-policy resolution and serialization, which is shared by file, phone, upload, and admin routes.
- FastAPI route dependencies and live request/cookie extraction stay in `main.py` to keep route behavior explicit.
- The helper accepts injectable dependencies so managed/unmanaged/import-failure paths can be tested without importing the full web app.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/user_access.py jane_web/main.py tests/test_user_access.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_user_access.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_user_access.py tests/test_user_identity.py tests/test_conversation_keys.py tests/test_file_browser_helpers.py tests/test_device_commands.py tests/test_env_settings.py tests/test_model_settings.py tests/test_app_settings.py -q` passed (`31 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`199 passed`).

Remaining follow-up slices:
- `_is_user_admin` can move once its user-manager success/failure paths are covered with fakes.
- Model settings save can reuse `EnvFileSettings` after route-level tests cover standing-brain restart behavior.

## 2026-07-02 - Web Conversation Key Helpers

Goal/scope:
- Extract pure conversation device-id and key payload construction from `jane_web/main.py`.
- Preserve request/session/cookie/user-manager lookups in `main.py`.

Files/modules changed:
- `jane_web/conversation_keys.py`
- `jane_web/main.py`
- `tests/test_conversation_keys.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Device ID selection still prefers `x-jane-device-id`, then the first 32 characters of the trusted-device cookie, then the first 16 characters of the request fingerprint, then `nodevice`.
- Managed conversation keys still use `<sanitized_user_id>__<device_id>__<client_session_id>`.
- Unmanaged sessions still preserve the legacy raw client session ID, falling back to the auth session ID and then `default`.
- Returned payloads still include `user_id`, `sanitized_user_id`, `device_id`, `client_session_id`, `conversation_key`, and `managed`.

Boundary chosen:
- The moved logic is deterministic key construction; live request/session extraction and user-manager normalization stay in the route layer.
- The extracted helper makes account-isolation key rules easier to test without FastAPI request objects.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/conversation_keys.py jane_web/main.py tests/test_conversation_keys.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_conversation_keys.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_conversation_keys.py tests/test_user_identity.py tests/test_model_settings.py tests/test_cli_login_helpers.py tests/test_env_settings.py tests/test_device_commands.py tests/test_announcements.py tests/test_file_browser_helpers.py tests/test_contact_search.py tests/test_release_downloads.py tests/test_app_settings.py tests/test_device_diagnostics.py tests/test_ra_reports.py -q` passed (`53 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`192 passed`).

Remaining follow-up slices:
- `_user_vault_context`, `_require_capability`, and `_user_memory_path` can move once tests fake managed-user config and import failures.
- Full `resolve_conversation_key` route-level behavior should be characterized before moving request/cookie extraction.

## 2026-07-02 - Web User Identity Helpers

Goal/scope:
- Extract pure user identity normalization and configured-admin variant helpers from `jane_web/main.py`.
- Preserve live user-manager capability checks in `main.py`.

Files/modules changed:
- `jane_web/user_identity.py`
- `jane_web/main.py`
- `tests/test_user_identity.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Default user ID still prefers the first `ALLOWED_GOOGLE_EMAILS` entry, then lowercased underscored `USER_NAME`, then `user`.
- Identity variants still include the normalized identifier, the `_at_` / dot-replaced variant, and `user_id_from_email` for email identifiers.
- Configured admin variants still combine `VESSENCE_ADMIN_USERS` and `ADMIN_EMAILS`; if neither is set, they fall back to the first allowed Google email, then `auth_default_user_id`.
- `jane_web.main` still exposes `_default_user_id`, `_identity_variants`, and `_configured_admin_variants` as imported aliases.

Boundary chosen:
- Identity normalization is pure env/string logic and can be tested with fake env mappings and fake ID conversion functions.
- Keeping `_is_user_admin` in `main.py` avoids moving the live `agent_skills.user_manager` dependency until its capability checks have fakes.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/user_identity.py jane_web/main.py tests/test_user_identity.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_user_identity.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_user_identity.py tests/test_model_settings.py tests/test_cli_login_helpers.py tests/test_env_settings.py tests/test_device_commands.py tests/test_announcements.py tests/test_file_browser_helpers.py tests/test_contact_search.py tests/test_release_downloads.py tests/test_app_settings.py tests/test_device_diagnostics.py tests/test_ra_reports.py -q` passed (`50 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`189 passed`).

Remaining follow-up slices:
- `_is_user_admin` can move once tests fake `agent_skills.user_manager` success and failure paths.
- Per-user vault/capability resolution remains route-critical and should be covered before extraction.

## 2026-07-02 - Web Model Settings Payload

Goal/scope:
- Extract model settings constants and response payload construction from `jane_web/main.py`.
- Preserve the POST route's env-file write and standing-brain restart behavior in `main.py`.

Files/modules changed:
- `jane_web/model_settings.py`
- `jane_web/main.py`
- `tests/test_model_settings.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Available model lists and provider env-var names keep the same values.
- Default models still come from each provider's `smart` config.
- Current model resolution still prefers `JANE_MODEL_<PROVIDER>`, then legacy `BRAIN_HEAVY_<PROVIDER>`, then the provider default.
- Tier payloads still use the same Orchestrator, Agent, Utility, and Local labels and roles.
- `jane_web.main` still exposes `_AVAILABLE_MODELS` and `_ENV_VAR_FOR_MODEL` as imported aliases.

Boundary chosen:
- Model settings payload construction is pure env/config shaping and does not need FastAPI request state.
- The route now delegates read-only response assembly while keeping mutation/restart side effects local.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/model_settings.py jane_web/main.py tests/test_model_settings.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_model_settings.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_model_settings.py tests/test_cli_login_helpers.py tests/test_env_settings.py tests/test_device_commands.py tests/test_announcements.py tests/test_file_browser_helpers.py tests/test_contact_search.py tests/test_release_downloads.py tests/test_app_settings.py tests/test_device_diagnostics.py tests/test_ra_reports.py -q` passed (`46 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`185 passed`).

Remaining follow-up slices:
- The model settings save route can reuse `EnvFileSettings`, but should get a route-level test because it also restarts the standing brain.
- Admin identity helpers remain a possible extraction target with env/user-manager fakes.

## 2026-07-02 - Jane Proxy Request Logging

Goal/scope:
- Extract request timing and prompt dump logging from `jane_web/jane_proxy.py`.
- Preserve log line formats, prompt JSON fields, and existing monkeypatchable proxy helper names.

Files/modules changed:
- `jane_web/proxy_logging.py`
- `jane_web/jane_proxy.py`
- `tests/test_proxy_logging.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Timing logs still truncate to the last 2000 lines when over the 5 MB cap.
- Stage log lines still include timestamp, session, stage, integer duration, and extra fields in insertion order.
- Start log lines still include message length only, not message content.
- Prompt dumps still write one JSON object per line with the same summary, bootstrap, retrieved-memory, system prompt, transcript, and file-context fields.
- `jane_web.jane_proxy` still exposes `_LOG_MAX_BYTES`, `_truncate_log_if_needed`, `_log_stage`, `_log_start`, and `_dump_prompt` as aliases.

Boundary chosen:
- Request logging is file-output infrastructure separate from provider execution and persistence side effects.
- Moving it out makes privacy-sensitive log formats directly testable and keeps proxy orchestration smaller.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/proxy_logging.py jane_web/jane_proxy.py tests/test_proxy_logging.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_proxy_logging.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_proxy_logging.py tests/test_proxy_text.py tests/test_prefetch_cache.py tests/test_client_tool_markers.py tests/test_server_email_tools.py tests/test_persistent_prompt.py tests/test_file_context.py tests/test_stage3_injections.py tests/test_tts_contract.py -q` passed (`42 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`182 passed`).

Remaining follow-up slices:
- Persistence worker branch decisions remain the next proxy candidate, but should be tested with fakes for FIFO, `ConversationManager`, and summary update dispatch.
- Session eviction/cleanup remains risky because it calls provider managers and background threads.

## 2026-07-02 - Jane Proxy Text Helpers

Goal/scope:
- Extract pure proxy text helpers from `jane_web/jane_proxy.py`.
- Preserve persistence message assembly and context progress status wording.

Files/modules changed:
- `jane_web/proxy_text.py`
- `jane_web/jane_proxy.py`
- `tests/test_proxy_text.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Persistence messages still trim the user-visible message and append file context separated by a blank line.
- Empty messages with file context still collapse to just the file context after stripping.
- Progress snapshots still return `Context is ready.` when no context signals were loaded.
- Progress findings still appear in the same order: prior summary, retrieved memory, task state, research brief, file context.
- `jane_web.jane_proxy` still exposes `_message_for_persistence` and `_progress_snapshot` as imported aliases.

Boundary chosen:
- These helpers are deterministic string assembly concerns and do not need session state, provider adapters, or stream orchestration.
- Extracting them keeps proxy route flow focused on concurrency, persistence, and provider calls.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/proxy_text.py jane_web/jane_proxy.py tests/test_proxy_text.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_proxy_text.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_proxy_text.py tests/test_prefetch_cache.py tests/test_client_tool_markers.py tests/test_server_email_tools.py tests/test_persistent_prompt.py tests/test_file_context.py tests/test_stage3_injections.py tests/test_tts_contract.py -q` passed (`38 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`178 passed`).

Remaining follow-up slices:
- Request logging helpers and persistence worker branch decisions are still candidates, but need fakes for logger/file state or `ConversationManager`.
- Avoid pulling more provider orchestration out of `jane_proxy.py` without branch-call characterization tests.

## 2026-07-02 - Jane Proxy Prefetch Cache

Goal/scope:
- Extract the short-lived memory prefetch cache from `jane_web/jane_proxy.py`.
- Preserve the background prefetch worker and context-builder call in the proxy module.

Files/modules changed:
- `jane_web/prefetch_cache.py`
- `jane_web/jane_proxy.py`
- `tests/test_prefetch_cache.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Freshness still uses a strict `age < TTL` check.
- Cache gets still return `""` for missing or stale entries.
- Stores still write `{"result": result, "timestamp": now}`.
- The cache still prunes expired entries only when the entry count exceeds the hard cap; fresh over-cap entries are not evicted.
- `jane_web.jane_proxy` still exposes `_prefetch_cache`, `_PREFETCH_CACHE_MAX`, and `PREFETCH_TTL` as aliases.

Boundary chosen:
- TTL lookup, storage, and pruning are independent cache mechanics separate from the expensive memory-summary fetch.
- The extracted class makes cache policy testable without starting background threads or querying Chroma.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/prefetch_cache.py jane_web/jane_proxy.py tests/test_prefetch_cache.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_prefetch_cache.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_prefetch_cache.py tests/test_client_tool_markers.py tests/test_server_email_tools.py tests/test_persistent_prompt.py tests/test_file_context.py tests/test_stage3_injections.py tests/test_tts_contract.py -q` passed (`35 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`175 passed`).

Remaining follow-up slices:
- Session-state eviction and cleanup remain in `jane_proxy.py`; extract only after tests cover end-session side effects.
- Persistence writeback is still a large candidate, but it needs fakes for `ConversationManager`, FIFO, and memory summary updates.

## 2026-07-02 - Web CLI Login Output Parsers

Goal/scope:
- Extract pure CLI login output parsing from `jane_web/main.py`.
- Preserve PTY/subprocess polling, transcript writes, process state, and response shaping in `main.py`.

Files/modules changed:
- `jane_web/cli_login_helpers.py`
- `jane_web/main.py`
- `tests/test_cli_login_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- OAuth state extraction still returns the first `state` query parameter or `None`.
- PTY raw output still strips the same ANSI/OSC escape patterns before UTF-8 replacement decoding.
- CLI output lines are still stripped and blank lines skipped.
- Claude auth URL extraction still accepts only `claude.com` or `anthropic.com` URLs and strips trailing `)` or `\`.
- Device-auth URL extraction still returns the first HTTP(S) token stripped of trailing `)`.
- Device code extraction still matches uppercase `XXXX-XXXX` through `XXXX-XXXXXX` tokens.
- The OpenAI extra-read loop still waits for a device code and only breaks early when one is actually found.

Boundary chosen:
- Output parsing is deterministic string/bytes work and is separate from subprocess lifecycle, timing, and PTY file descriptors.
- Tests now cover the parsing rules without spawning any CLI processes.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/cli_login_helpers.py jane_web/main.py tests/test_cli_login_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_cli_login_helpers.py -q` passed (`10 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_cli_login_helpers.py tests/test_env_settings.py tests/test_device_commands.py tests/test_announcements.py tests/test_file_browser_helpers.py tests/test_contact_search.py tests/test_release_downloads.py tests/test_app_settings.py tests/test_device_diagnostics.py tests/test_ra_reports.py -q` passed (`43 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`172 passed`).

Remaining follow-up slices:
- CLI process lifecycle and OAuth token exchange remain in `main.py`; extract only with process/network fakes.
- Provider auth status cache can still be separated from subprocess execution later.

## 2026-07-02 - Web CLI Auth Status Parser

Goal/scope:
- Extract the pure auth-status output parser from `jane_web/main.py` into the CLI helper module.
- Preserve subprocess status checks, token refresh, and auth-status caching in `main.py`.

Files/modules changed:
- `jane_web/cli_login_helpers.py`
- `jane_web/main.py`
- `tests/test_cli_login_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- JSON status output still sets `logged_in`, `auth_method`, masked `email_hint`, and `subscription_type` when present.
- Non-JSON output still marks logged-in only when it contains `logged in` and not `not logged in`.
- Plaintext parsing still stores the final output line truncated to 200 characters as `status_stdout_tail`.
- `jane_web.main` still invokes the parser after the first status command and again after a successful Claude token refresh.

Boundary chosen:
- Status output parsing is pure dict/string logic and is independent of subprocess execution, refresh-token exchange, and cache lifetime.
- Extracting it makes provider auth parsing directly testable while keeping operational login flow state in `main.py`.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/cli_login_helpers.py jane_web/main.py tests/test_cli_login_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_cli_login_helpers.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_cli_login_helpers.py tests/test_env_settings.py tests/test_device_commands.py tests/test_announcements.py tests/test_file_browser_helpers.py tests/test_contact_search.py tests/test_release_downloads.py tests/test_app_settings.py tests/test_device_diagnostics.py tests/test_ra_reports.py -q` passed (`39 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`168 passed`).

Remaining follow-up slices:
- Auth-status cache and subprocess execution can be extracted later with command-runner fakes.
- Claude refresh token exchange should stay put until tested with credential fixtures and network-call fakes.

## 2026-07-02 - Web CLI Login Helpers

Goal/scope:
- Extract pure CLI login helper functions from `jane_web/main.py`.
- Preserve provider command selection, email masking, and transcript-line reading while leaving subprocess/PTTY login orchestration in `main.py`.

Files/modules changed:
- `jane_web/cli_login_helpers.py`
- `jane_web/main.py`
- `tests/test_cli_login_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Claude, Gemini, and OpenAI still map to the same login command candidates.
- CLI binary selection still returns the first command binary or `None`.
- Email masking keeps the same outputs for empty strings, non-email values, short locals, normal emails, and missing local parts.
- Transcript reading still returns `[]` for missing paths and strips blank lines from existing files.
- `jane_web.main` still exposes `_cli_login_candidates`, `_cli_binary_for_provider`, `_mask_email`, and `_read_cli_transcript_lines` as imported aliases.

Boundary chosen:
- These helpers are pure provider/string/file-line utilities and do not need access to live subprocess state.
- Keeping process lifecycle, PTY writes, OAuth state, and auth-status cache in `main.py` avoids changing the active login flow while reducing CLI-helper clutter.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/cli_login_helpers.py jane_web/main.py tests/test_cli_login_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_cli_login_helpers.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_cli_login_helpers.py tests/test_env_settings.py tests/test_device_commands.py tests/test_announcements.py tests/test_file_browser_helpers.py tests/test_contact_search.py tests/test_release_downloads.py tests/test_app_settings.py tests/test_device_diagnostics.py tests/test_ra_reports.py -q` passed (`37 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`166 passed`).

Remaining follow-up slices:
- Provider auth-status parsing/caching could be split next, but it needs subprocess and token-refresh fakes.
- PTY login and port discovery should stay in `main.py` until there are integration-style tests around running login processes.

## 2026-07-02 - Web Env Settings Store

Goal/scope:
- Extract `.env` mutation and Google allowlist add/remove behavior from `jane_web/main.py`.
- Preserve managed-user create/delete route behavior while isolating file updates.

Files/modules changed:
- `jane_web/env_settings.py`
- `jane_web/main.py`
- `tests/test_env_settings.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Active `KEY=value` lines are still replaced while comments and unrelated lines are preserved.
- Missing keys are still appended and parent directories are created.
- `os.environ` is still updated after writes.
- Allowed Google emails are still lowercased, stripped, comma-joined, and duplicate additions return `False`.
- Managed-user deletion now uses the same helper to remove an email from `ALLOWED_GOOGLE_EMAILS`, preserving the same env/file result.
- `jane_web.main` still exposes `_write_env_var`, `_add_allowed_google_email`, and `_remove_allowed_google_email` as aliases bound to the configured env file.

Boundary chosen:
- Env-file mutation is a persistence concern independent of FastAPI route validation and user-manager calls.
- The new helper lets create/delete managed-user routes share allowlist behavior and makes `.env` updates testable without touching the real environment file.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/env_settings.py jane_web/main.py tests/test_env_settings.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_env_settings.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_env_settings.py tests/test_device_commands.py tests/test_announcements.py tests/test_file_browser_helpers.py tests/test_contact_search.py tests/test_release_downloads.py tests/test_app_settings.py tests/test_device_diagnostics.py tests/test_ra_reports.py -q` passed (`33 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`162 passed`).

Remaining follow-up slices:
- Admin identity and capability checks still live in `main.py`; extract only with env/user-manager fakes.
- Model settings env updates could use the same helper, but route behavior should be characterized first because it also restarts standing brains.

## 2026-07-02 - Web Device Command Queue

Goal/scope:
- Extract the in-memory server-to-Android command queue from `jane_web/main.py`.
- Preserve announcement polling and server-initiated SMS sync behavior.

Files/modules changed:
- `jane_web/device_commands.py`
- `jane_web/main.py`
- `tests/test_device_commands.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Commands are still dictionaries shaped as `{"command": command, **kwargs}`.
- Commands still drain in FIFO order.
- Draining still returns a copy and clears the pending queue.
- `jane_web.main` still exposes `_pending_device_commands`, `_pending_lock`, `queue_device_command`, and `_drain_pending_commands` as aliases bound to the same queue instance.

Boundary chosen:
- The Android command queue is independent mutable infrastructure used by the SMS sync endpoint and announcement polling.
- Moving it out keeps `main.py` route code focused on auth/capability checks and response shaping.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/device_commands.py jane_web/main.py tests/test_device_commands.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_device_commands.py -q` passed (`2 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_device_commands.py tests/test_announcements.py tests/test_file_browser_helpers.py tests/test_contact_search.py tests/test_release_downloads.py tests/test_app_settings.py tests/test_device_diagnostics.py tests/test_ra_reports.py -q` passed (`29 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`158 passed`).

Remaining follow-up slices:
- Admin identity/env helpers remain a likely next web-layer target.
- Streaming chat route extraction still needs route-level characterization tests before deeper movement.

## 2026-07-02 - Web Announcements Log Reader

Goal/scope:
- Extract Jane web announcement JSONL reading, filtering, and truncation from `jane_web/main.py`.
- Preserve announcement route behavior, RA report tokenization, and pending device command piggybacking in `main.py`.

Files/modules changed:
- `jane_web/announcements.py`
- `jane_web/main.py`
- `tests/test_announcements.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing announcement logs still return an empty list.
- Logs larger than 1 MB are still truncated to the last 200 lines before reading.
- Blank lines and invalid JSON lines are still skipped.
- Invalid `since` values still disable date filtering.
- `created_at` and `timestamp` are still both accepted; entries at or before `since` are skipped, while invalid/missing entry timestamps are retained.
- `jane_web.main._read_announcements` remains available as an alias bound to the configured announcement log.

Boundary chosen:
- Announcement reading is a self-contained JSONL storage concern and does not need FastAPI route state.
- Moving it out keeps the route focused on tokenizing announcements and attaching pending Android commands.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/announcements.py jane_web/main.py tests/test_announcements.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_announcements.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_announcements.py tests/test_file_browser_helpers.py tests/test_contact_search.py tests/test_release_downloads.py tests/test_app_settings.py tests/test_device_diagnostics.py tests/test_ra_reports.py -q` passed (`27 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`156 passed`).

Remaining follow-up slices:
- Auth/admin identity helpers are a possible next target, but they need careful env and user-manager fakes.
- Device command queueing can be extracted if Android polling semantics get focused tests.

## 2026-07-02 - Web File Browser Helpers

Goal/scope:
- Extract vault file-browser helpers from `jane_web/main.py`.
- Preserve route handlers, vault permission checks, file serving behavior, upload routing, and search result shapes.

Files/modules changed:
- `jane_web/file_browser_helpers.py`
- `jane_web/main.py`
- `tests/test_file_browser_helpers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- MIME-to-upload-subdir routing still maps PDFs to `pdf`, image/audio/video top-level types to their existing subdirectories, and everything else to `documents`.
- Directory pagination still returns the original listing when `limit <= 0` or the listing contains `error`, and still mutates file slices plus pagination metadata when enabled.
- HTTP range responses still parse the same `bytes=start-end` shape, fall back to full-file headers on invalid ranges, and stream the requested bytes with the same headers.
- File type detection still uses the same extension groups and defaults to `other`.
- `jane_web.main` still exposes `_MIME_TO_SUBDIR`, `_FILE_TYPE_EXTENSIONS`, `_route_subdir`, `_paginate_listing`, `_range_response`, and `_detect_file_type` as imported aliases.

Boundary chosen:
- These helpers are pure or narrowly file-response related and do not need FastAPI route auth/session state.
- Moving them out reduces `main.py` route clutter while making file-browser behavior independently testable.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/file_browser_helpers.py jane_web/main.py tests/test_file_browser_helpers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_file_browser_helpers.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_file_browser_helpers.py tests/test_contact_search.py tests/test_release_downloads.py tests/test_app_settings.py tests/test_device_diagnostics.py tests/test_ra_reports.py -q` passed (`23 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`152 passed`).

Remaining follow-up slices:
- Consider extracting file search result assembly only after adding fakes for Chroma file-description lookup.
- Upload handling is a possible future split, but it touches durable vault writes and file-index updates, so it needs stronger route-level tests first.

## 2026-07-02 - Memory Sections Cache Module

Goal/scope:
- Extract the in-process short-TTL cache for assembled memory sections from `memory/v1/memory_retrieval.py`.
- Preserve `build_memory_sections` cache behavior without touching Chroma query fan-out or section assembly.

Files/modules changed:
- `memory/v1/memory_sections_cache.py`
- `memory/v1/memory_retrieval.py`
- `tests/test_memory_sections_cache.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Cache gets still return `None` for missing entries.
- Entries expire only when age is strictly greater than the TTL.
- Expired entries are removed on read.
- Stored and returned sections are copied, so caller mutations do not mutate cached lists.
- Puts still evict the oldest entry when the cache is already at the max-entry cap.
- `memory.v1.memory_retrieval` still exposes `_SECTIONS_CACHE`, `_SECTIONS_CACHE_LOCK`, `_SECTIONS_CACHE_TTL_S`, `_SECTIONS_CACHE_MAX_ENTRIES`, `_sections_cache_get`, and `_sections_cache_put` as imported aliases.

Boundary chosen:
- The sections cache is stateful TTL/eviction infrastructure separate from retrieval classification and vector-store queries.
- Moving it out leaves `memory_retrieval.py` closer to the actual memory retrieval algorithm and gives cache semantics direct tests.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/memory_sections_cache.py memory/v1/memory_retrieval.py tests/test_memory_sections_cache.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_memory_sections_cache.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_memory_sections_cache.py tests/test_low_signal_memory.py tests/test_query_intent.py tests/test_query_markers.py tests/test_memory_summary_cache.py tests/test_memory_text.py test_code/test_short_term_memory_hygiene.py -q` passed (`33 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`146 passed`).

Remaining follow-up slices:
- The remaining high-risk part of `memory_retrieval.py` is Chroma query fan-out plus section assembly; defer until collection fakes or fixture-backed tests exist.
- `jane_web/main.py` and `jane_web/jane_proxy.py` remain higher-value targets after this memory cleanup pass.

## 2026-07-02 - Low-Signal Memory Filters

Goal/scope:
- Extract shared-memory and short-term-memory low-signal filters from `memory/v1/memory_retrieval.py`.
- Preserve retrieval filtering behavior and the existing private import path used by hygiene tests.

Files/modules changed:
- `memory/v1/low_signal_memory.py`
- `memory/v1/memory_retrieval.py`
- `tests/test_low_signal_memory.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Empty shared memories, known low-signal shared prefixes, and `prompt_list` / `audit_flow` / `performance_logs` topics are still filtered.
- Short-term `short_term_theme` and `context_snapshot` records are still filtered.
- Class protocol headings, `<class_protocol>`, `[EXTRACTED PARAMS]`, current conversation state, and standing brain markers are still filtered as protocol noise.
- Text that merely discusses class protocol metadata without a metadata-chatter prefix or marker remains allowed.
- `memory.v1.memory_retrieval` still exposes `LOW_SIGNAL_SHARED_PREFIXES`, `LOW_SIGNAL_SHORT_TERM_META_PREFIX_PATTERNS`, `LOW_SIGNAL_SHORT_TERM_PROTOCOL_PATTERNS`, `_is_low_signal_shared_memory`, and `_is_low_signal_short_term_memory` as imported aliases.

Boundary chosen:
- The low-signal filters are pure text/metadata classification rules used at multiple retrieval points.
- Moving them out reduces retrieval orchestration size and makes noise-filter rules easier to extend without touching Chroma query code.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/low_signal_memory.py memory/v1/memory_retrieval.py tests/test_low_signal_memory.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_low_signal_memory.py test_code/test_short_term_memory_hygiene.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_low_signal_memory.py tests/test_query_intent.py tests/test_query_markers.py tests/test_memory_summary_cache.py tests/test_memory_text.py test_code/test_short_term_memory_hygiene.py -q` passed (`30 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`143 passed`).

Remaining follow-up slices:
- Consider extracting the small in-process memory sections cache next.
- Chroma query fan-out and section assembly should stay in `memory_retrieval.py` until covered by collection fakes.

## 2026-07-02 - Memory Query Intent Helpers

Goal/scope:
- Extract pure query intent helpers from `memory/v1/memory_retrieval.py`.
- Preserve file lookup gating, personal/project/general classification, and DS3000 lecture-anchor parsing while leaving Chroma anchor retrieval in place.

Files/modules changed:
- `memory/v1/query_intent.py`
- `memory/v1/memory_retrieval.py`
- `tests/test_query_intent.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- File-index records are still recognized through the same metadata fields and saved-file text patterns.
- File-query detection still combines the same static file markers with dynamic file markers.
- Intent classification priority remains file lookup first, then project markers, then personal markers or short question fallback, then general.
- DS3000 lecture parsing still dedupes subtopics, accepts one- or two-digit lecture numbers with optional `a`, ignores `00` and `100`, and only adds `series_index` when the query contains literal `ds3000`, `lecture`, and a series/index marker.
- `memory.v1.memory_retrieval` still exposes `_STATIC_FILE_MARKERS`, `_is_file_index_record`, `_is_file_query`, `_classify_query_intent`, and `_ds3000_lecture_subtopics` as imported aliases.

Boundary chosen:
- These helpers are pure classification/parsing logic and only feed retrieval orchestration decisions.
- Moving them out keeps `memory_retrieval.py` smaller without touching vector-store fan-out, section assembly, or distance filtering.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/query_intent.py memory/v1/memory_retrieval.py tests/test_query_intent.py` passed.
- First focused test run found an existing DS3000 detail: `series_index` requires literal `ds3000`, not spaced `ds 3000`; the test was corrected to preserve current behavior.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_query_intent.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_query_intent.py tests/test_query_markers.py tests/test_memory_summary_cache.py tests/test_memory_text.py test_code/test_short_term_memory_hygiene.py -q` passed (`26 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`139 passed`).

Remaining follow-up slices:
- Extract low-signal memory filters next if paired with tests for shared, short-term, and protocol/noise patterns.
- Keep `_get_ds3000_lecture_anchors` in `memory_retrieval.py` because it opens Chroma collections and applies expiry/none-content filters.

## 2026-07-02 - Memory Query Marker Registry

Goal/scope:
- Extract dynamic query marker loading from `memory/v1/memory_retrieval.py`.
- Preserve memory retrieval's query-intent classification behavior while isolating file-mtime and JSON marker state.

Files/modules changed:
- `memory/v1/query_markers.py`
- `memory/v1/memory_retrieval.py`
- `tests/test_query_markers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing dynamic marker files still leave static personal/project markers active and file markers empty.
- Unchanged mtimes still skip JSON reparsing.
- Successful reloads still tuple-convert `personal_markers`, `project_markers`, and `file_markers`.
- Failed reloads still keep the previous markers and previous mtime, so the next changed file can retry.
- `memory.v1.memory_retrieval` still exposes `_STATIC_PERSONAL_MARKERS`, `_STATIC_PROJECT_MARKERS`, `_reload_dynamic_markers_if_changed`, `_get_personal_markers`, `_get_project_markers`, and `_get_file_markers` as imported aliases.

Boundary chosen:
- Dynamic marker loading is independent stateful file-watching logic and only feeds query classification through three accessor functions.
- Moving it out keeps `memory_retrieval.py` focused on retrieval orchestration and makes marker reload semantics testable without Chroma or embedding dependencies.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/query_markers.py memory/v1/memory_retrieval.py tests/test_query_markers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_query_markers.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_query_markers.py tests/test_memory_summary_cache.py tests/test_memory_text.py test_code/test_short_term_memory_hygiene.py -q` passed (`22 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`135 passed`).

Remaining follow-up slices:
- Query intent classification can be extracted next if paired with tests around personal, project, file, DS3000 lecture, and managed-user branches.
- Keep vector-store query fan-out in `memory_retrieval.py` until Chroma calls are covered with fakes.

## 2026-07-02 - Memory Summary Cache Module

Goal/scope:
- Extract the short-lived semantic memory summary cache from `memory/v1/memory_retrieval.py`.
- Keep embedding model loading, Chroma collection queries, query intent classification, and section assembly in `memory_retrieval.py`.

Files/modules changed:
- `memory/v1/memory_summary_cache.py`
- `memory/v1/memory_retrieval.py`
- `tests/test_memory_summary_cache.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Query normalization still lowercases and collapses whitespace.
- Cosine similarity still returns `-1.0` for empty, mismatched, or zero-norm vectors.
- Cache pruning still drops expired entries, sorts newest-first, and caps entries per session.
- Lookup still returns the highest-similarity summary above the configured threshold and prunes empty sessions.
- Store still ignores missing session IDs, empty embeddings, or empty summaries, normalizes the query, caps per-session entries, and evicts oldest sessions over the hard session cap.
- `memory.v1.memory_retrieval` still exposes `MemorySummaryCacheEntry`, `_memory_summary_cache`, `_normalize_query`, `_cosine_similarity`, `_prune_cache_entries`, `_lookup_cached_memory_summary`, `_store_cached_memory_summary`, and `invalidate_memory_summary_cache` as aliases.

Boundary chosen:
- The cache has independent mutable state, TTL policy, similarity thresholding, and invalidation semantics.
- Moving it out lets retrieval stay focused on query classification, Chroma access, and memory section formatting while making cache behavior testable without loading embedding models.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/memory_summary_cache.py memory/v1/memory_retrieval.py tests/test_memory_summary_cache.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_memory_summary_cache.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_memory_summary_cache.py tests/test_memory_text.py test_code/test_short_term_memory_hygiene.py -q` passed (`17 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`130 passed`).

Remaining follow-up slices:
- Consider extracting dynamic query marker loading from `memory_retrieval.py`; it is another bounded stateful concern with file-mtime semantics.
- Avoid moving Chroma query fan-out until there are fakes for collection query behavior.

## 2026-07-02 - RA Research Report HTML Renderer

Goal/scope:
- Extract app-facing RA research report Markdown-to-HTML rendering from `agent_skills/ra_research_cron.py`.
- Keep report writing, latest-report file updates, and cron state in the cron module.

Files/modules changed:
- `agent_skills/ra_research_html.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_html.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- The renderer still supports headings up to `h4`, paragraphs, unordered lists, ordered lists, inline code, bold text, and HTTP/HTTPS Markdown links.
- Raw HTML in headings and paragraphs is still escaped.
- Report IDs still strip the `ra_research_run_` prefix from filenames.
- The full HTML wrapper keeps the same title, safety notice, metadata pills, source pluralization, body insertion, and CSS.
- `agent_skills.ra_research_cron` still exposes `markdown_to_report_html`, `report_id_from_path`, and `build_report_html` as imported aliases.

Boundary chosen:
- HTML rendering is pure presentation logic and does not depend on report paths, source fetching, LLM synthesis, or app notification behavior.
- The new module allows deterministic rendering tests by passing a generated timestamp while preserving the cron's existing call signature.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_html.py agent_skills/ra_research_cron.py tests/test_ra_research_html.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_html.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_text.py tests/test_ra_research_report_items.py tests/test_ra_research_html.py -q` passed (`15 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`124 passed`).

Remaining follow-up slices:
- Consider extracting the useful-report Markdown assembly once there are snapshot-like tests for section order and fallback wording.
- Leave `write_html_report` in the cron module because it owns durable report paths and latest-report writes.

## 2026-07-02 - RA Research Report Item Helpers

Goal/scope:
- Extract RA research report scoring, low-value detection, item filtering, and theme inference from `agent_skills/ra_research_cron.py`.
- Preserve report markdown ordering and usefulness labels while making the evidence-surfacing rules independently testable.

Files/modules changed:
- `agent_skills/ra_research_report_items.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_report_items.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Signal scoring keeps the same guideline/RCT/systematic-review/cohort/review boosts and the same abstract-only, manual-review, off-topic, and speculative penalties.
- Abstract-only summaries are still not treated as low-value when the remaining score is at least 2.
- Strong high-score evidence that says it does not directly address the target can still avoid the low-value bucket.
- Report item filters still drop empty, generic safety, feasibility, lupus, and SLE items.
- Theme inference still ranks the same rule-based topic buckets from summary text.
- `agent_skills.ra_research_cron` still exposes the moved helper names as imported aliases.

Boundary chosen:
- The moved functions are pure ranking and text-selection logic used by the useful report and source-detail labels.
- Keeping markdown assembly in the cron file avoids changing report structure while separating the rules that decide what gets surfaced.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_report_items.py agent_skills/ra_research_cron.py tests/test_ra_research_report_items.py` passed.
- First focused test run found a characterization mismatch: missing `study_type` labels currently render as `unknown`, not `unknown type`; the test was corrected to preserve current output.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_report_items.py -q` passed (`7 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_text.py tests/test_ra_research_report_items.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`120 passed`).

Remaining follow-up slices:
- Extract report HTML rendering separately if app-facing HTML needs more tests.
- Leave cron source fetching and LLM synthesis orchestration in place until there are fixture-backed integration tests for those paths.

## 2026-07-02 - RA Research Text Payload Helpers

Goal/scope:
- Extract pure RA research text normalization, field coercion, summary deduplication, and compact payload construction from `agent_skills/ra_research_cron.py`.
- Preserve cron report generation behavior while keeping fetch/orchestration code in the cron module.

Files/modules changed:
- `agent_skills/ra_research_text.py`
- `agent_skills/ra_research_cron.py`
- `tests/test_ra_research_text.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Text cleanup still collapses whitespace and trims values.
- `text_value` still truncates with the same `text[:max_chars - 1] + "..."` behavior.
- List extraction still accepts lists, tuples, sets, and scalar values while dropping empty values.
- Summary deduplication still keys by `(title, publication/outlet, date)` and keeps the first matching item.
- Compact summary payloads still include the same fields, truncation limits, and evidence/confidence lists.

Boundary chosen:
- These helpers are pure data-shaping logic independent of browser/login flow, cache paths, markdown writing, and report orchestration.
- The new module makes RA summary formatting testable without touching network, browser automation, or cron state.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile agent_skills/ra_research_text.py agent_skills/ra_research_cron.py tests/test_ra_research_text.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_research_text.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`113 passed`).

Remaining follow-up slices:
- Extract RA research report item scoring/filtering only after adding focused tests for low-value evidence and markdown ordering.
- Keep cron/browser orchestration in place until there is a fake report source or fixture-backed integration test.

## 2026-07-02 - Memory Retrieval Text Helpers

Goal/scope:
- Extract memory age, formatting, none-sentinel, and deduplication helpers from `memory/v1/memory_retrieval.py`.
- Preserve memory retrieval aliases while keeping Chroma query and embedding code untouched.

Files/modules changed:
- `memory/v1/memory_text.py`
- `memory/v1/memory_retrieval.py`
- `tests/test_memory_text.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Expiry parsing still accepts numeric timestamps, ISO timestamps, `Z` suffixes, and naive UTC timestamps.
- Too-old and age calculations still use timestamp/created_at metadata and pass through malformed or missing timestamps.
- Recency labels, formatted memory lines, distance formatting, none-content sentinels, and dedupe keys keep the same output.
- `memory.v1.memory_retrieval` still exposes `_is_expired`, `_is_too_old`, `_age_days`, `_is_none_content`, `_recency_label`, `_fmt_memory`, `_extract_content_key`, and `_dedupe_fact_lines` as aliases.

Boundary chosen:
- The extracted helpers are pure text/time formatting logic and do not depend on ChromaDB, embeddings, or section-building control flow.
- This makes retrieval formatting testable without loading embedding models or opening vector stores.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile memory/v1/memory_text.py memory/v1/memory_retrieval.py tests/test_memory_text.py` passed.
- First focused test run found an expected-value mistake in the new test: `0.12345` rounds to `0.1235` with `:.4f`, matching existing behavior; the test was corrected.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_memory_text.py test_code/test_short_term_memory_hygiene.py tests/test_client_tool_sanitizer.py -q` passed (`17 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`109 passed`).

Remaining follow-up slices:
- Consider extracting memory summary cache management separately; it has enough state and locking to need focused tests.
- Avoid moving Chroma collection query code until there are fixtures or fakes for vector-store behavior.

## 2026-07-02 - File Context Follow-Up Resolver

Goal/scope:
- Extract the pure decision for resolving request-provided vs recent file context from `jane_web/jane_proxy.py`.
- Keep session-state mutation and logging in the proxy wrapper.

Files/modules changed:
- `jane_web/file_context.py`
- `jane_web/jane_proxy.py`
- `tests/test_file_context.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- A truthy request `file_context` still wins and updates `state.recent_file_context`.
- Follow-up phrases like "that file" / "this image" still reuse recent file context.
- Messages without follow-up markers still do not reuse recent context.
- Empty-string `file_context` remains falsey and can fall back to recent context when the message contains a follow-up marker.

Boundary chosen:
- Marker matching is pure text/context selection logic; the proxy wrapper only needs to apply the result to session state and logs.
- The extracted helper makes future file-follow-up phrase changes testable without constructing `JaneSessionState`.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/file_context.py jane_web/jane_proxy.py tests/test_file_context.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_file_context.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`105 passed`).

Remaining follow-up slices:
- Extract `_message_for_persistence` with tests if file-context persistence behavior gets more complex.
- Consider memory module helpers next; remaining proxy changes now touch broader session or provider behavior.

## 2026-07-02 - Persistent Brain Prompt Preparation Helper

Goal/scope:
- Extract the repeated persistent Claude/Codex prompt preparation decision from `jane_web/jane_proxy.py`.
- Preserve fresh-session, skip-context, and warm-session behavior across sync and stream paths.

Files/modules changed:
- `jane_web/persistent_prompt.py`
- `jane_web/jane_proxy.py`
- `tests/test_persistent_prompt.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Fresh persistent sessions still receive `system_prompt + transcript`.
- Skip-context turns with an empty system prompt still send the whole transcript unchanged.
- Warm persistent sessions still send only the latest user prompt and pass it through `_maybe_prepend_code_map`.
- Code-map status/log behavior remains in the caller so stream paths still emit the same status if code-map injection is re-enabled.
- `jane_web.jane_proxy._latest_user_prompt_from_transcript` remains available as an imported compatibility alias.

Boundary chosen:
- The same three-branch prompt decision was duplicated across persistent Claude, standing Codex, and persistent Codex sync/stream paths.
- Extracting it reduces branch drift while keeping provider-specific manager calls and stream callbacks in `jane_proxy.py`.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/persistent_prompt.py jane_web/jane_proxy.py tests/test_persistent_prompt.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_persistent_prompt.py -q` passed (`5 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`101 passed`).

Remaining follow-up slices:
- Consider a provider-branch table for persistent Claude/Codex only after tests cover manager call arguments.
- Leave disabled `CODE_MAP_KEYWORDS` in `jane_proxy.py` for now because the documented cron updater still expects it there.
- Revisit stale ad hoc timeout-profile tests separately; current environment sets `JANE_RESPONSE_WAIT_SECONDS=7200`.

## 2026-07-02 - Server-Side Email Tool Dispatcher

Goal/scope:
- Extract server-side handling for `email.*` client-tool markers out of `jane_web/jane_proxy.py`.
- Preserve the proxy alias and all visible status strings returned into the stream.

Files/modules changed:
- `jane_web/server_email_tools.py`
- `jane_web/jane_proxy.py`
- `tests/test_server_email_tools.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `email.read_inbox`, `email.read`, `email.search`, `email.send`, and `email.delete` keep the same argument defaults, validation messages, success strings, and error strings.
- Runtime credential failures still tell the user Gmail is not set up.
- Generic exceptions still return `Email error: ...`.
- Unknown email tools still return an empty string and log a warning.
- The logger name remains `jane.proxy`, and `jane_web.jane_proxy._execute_email_tool_serverside` remains available as an alias.

Boundary chosen:
- Email marker execution is a server-side adapter concern distinct from proxy streaming/session orchestration.
- Tests can inject a fake `agent_skills.email_tools` module, so the behavior is now covered without requiring Gmail credentials.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/server_email_tools.py jane_web/jane_proxy.py tests/test_server_email_tools.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_server_email_tools.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`96 passed`).

Remaining follow-up slices:
- Extract transcript prompt helpers and provider prompt assembly only with branch-focused tests.
- Consider a separate Gmail adapter interface if more server-side email behavior grows.
- Keep live Gmail integration tests out of the lightweight suite unless credentials are explicitly mocked.

## 2026-07-02 - Client Tool Marker Extraction Module

Goal/scope:
- Extract the streaming `[[CLIENT_TOOL:...]]` marker parser and Android `[TOOL_RESULT:...]` feedback formatter from `jane_web/jane_proxy.py`.
- Keep proxy compatibility aliases for callers that import the old private names.

Files/modules changed:
- `jane_web/client_tool_markers.py`
- `jane_web/jane_proxy.py`
- `tests/test_client_tool_markers.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Streaming marker extraction remains split-chunk safe, JSON brace/string aware, code-fence aware, and fail-open on malformed or oversized markers.
- Orphan trailing `]]` cleanup remains available as `ToolMarkerExtractor._strip_orphan_close`.
- `[TOOL_RESULT:{...}]` parsing still supports nested JSON and marker-like strings inside JSON string values.
- Phone-tool result context formatting still neutralizes delimiter injection, collapses newlines, preserves data/extra JSON, and truncates oversized strings.
- `jane_web.jane_proxy` still exposes `ToolMarkerExtractor`, `_extract_tool_results`, `_neutralize_delimiters`, and `_format_tool_results_for_brain`.

Boundary chosen:
- Client-tool marker parsing is a cohesive protocol concern and was occupying hundreds of lines at the top of the proxy orchestration module.
- Extracting it removes parser complexity from `jane_proxy.py` while preserving imports used by v2/v3 pipelines and existing tests.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/client_tool_markers.py jane_web/jane_proxy.py tests/test_client_tool_markers.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_client_tool_markers.py tests/test_client_tool_sanitizer.py -q` passed (`12 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`90 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest test_code/test_stage3_awaiting_marker.py tests/test_awaiting_markers.py tests/test_pending_sms.py tests/test_stage2_response.py -q` passed (`31 passed`).

Remaining follow-up slices:
- Move `_latest_user_prompt_from_transcript` into a transcript helper if paired with provider-branch tests.
- Consider a small adapter around server-side email tool execution, but only after tests cover the Gmail connector fallback behavior.
- Re-run the stale ad hoc Jane proxy bundle after its expectations are updated.

## 2026-07-02 - Stage 3 Injection Redaction Helper

Goal/scope:
- Extract Stage 3 brain-only prompt injection stripping from `jane_web/jane_proxy.py`.
- Preserve the persistence redaction behavior used by both sync and stream paths.

Files/modules changed:
- `jane_web/stage3_injections.py`
- `jane_web/jane_proxy.py`
- `tests/test_stage3_injections.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `<class_protocol>...</class_protocol>` blocks are removed.
- `[EXTRACTED PARAMS]` blocks are removed through the next blank line or end of message.
- `[CURRENT CONVERSATION STATE] ... [END CURRENT CONVERSATION STATE]` blocks are removed.
- Voice request hints are removed.
- Empty input still returns unchanged, and non-empty output is still stripped.
- `jane_web.jane_proxy._strip_stage3_injections` remains available as an alias.

Boundary chosen:
- Stage 3 injection cleanup is pure text redaction used before persistence and does not belong inside the proxy orchestration body.
- Focused tests now cover the persisted-text safety behavior without invoking model adapters or streams.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/stage3_injections.py jane_web/jane_proxy.py tests/test_stage3_injections.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_stage3_injections.py -q` passed (`6 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`84 passed`).

Remaining follow-up slices:
- Extract `_message_for_persistence` or file-context follow-up helpers only if paired with tests around file context persistence.
- Revisit stale ad hoc proxy tests before attempting larger `jane_proxy.py` orchestration moves.
- Consider small memory-manager extractions next, where pure normalization/deduplication helpers already exist.

## 2026-07-02 - Jane Proxy TTS Contract Helper

Goal/scope:
- Extract the regex-heavy TTS output contract helpers from `jane_web/jane_proxy.py`.
- Preserve existing private helper imports used by older tests and callers.

Files/modules changed:
- `jane_web/tts_contract.py`
- `jane_web/jane_proxy.py`
- `tests/test_tts_contract.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `<spoken>` extraction, preface merging, trailing visual/detail normalization, client-tool marker stripping, music marker stripping, abbreviation-aware sentence splitting, spoken length limits, fallback `Got it.`, and warning logging all keep the same semantics.
- The logger name remains `jane.proxy`.
- `jane_web.jane_proxy` still exposes `_normalize_tts_text`, `_split_tts_sentences`, `_take_short_tts_spoken`, `_truncate_tts_spoken_text`, `_combine_tts_detail`, and `_enforce_tts_output_contract` as aliases.

Boundary chosen:
- TTS output enforcement is pure text processing and does not need to be embedded in the proxy's stream/session orchestration.
- Keeping compatibility aliases avoids a broad caller migration while reducing `jane_proxy.py` complexity.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/tts_contract.py jane_web/jane_proxy.py tests/test_tts_contract.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_tts_contract.py test_code/test_message_readback.py -q` passed (`11 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`78 passed`).
- Attempted `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest test_code/test_jane_proxy_persistence.py test_code/test_jane_web_streaming.py test_code/test_message_readback.py -q`; it failed (`8 failed, 11 passed`). The failures did not exercise the extracted TTS helper: stale persistence stubs no longer accept `cls` / `update_short_term_memory`, one streaming endpoint test hit the live v3 route instead of its monkeypatched `main.stream_message`, timeout profile expectations conflict with `JANE_RESPONSE_WAIT_SECONDS=7200`, and an existing context-build failure path raises through `send_message`.

Remaining follow-up slices:
- Decide separately whether to update or retire the stale `test_code/test_jane_proxy_persistence.py` and `test_code/test_jane_web_streaming.py` expectations.
- Continue extracting pure `jane_proxy.py` helpers only when there are focused tests independent of live app startup.
- Consider moving Stage 3 injection stripping after adding tests around persistence redaction.

## 2026-07-02 - TTS Text Chunking Helper

Goal/scope:
- Extract the pure chat TTS text chunking helper from `jane_web/main.py`.
- Leave Docker/ffmpeg TTS generation and cache behavior unchanged.

Files/modules changed:
- `jane_web/tts_chunks.py`
- `jane_web/main.py`
- `tests/test_tts_chunks.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Short sentences are still combined when they fit within `max_chars`.
- Sentence boundaries still split on punctuation followed by whitespace.
- Overlong sentence chunks still split on commas.
- Blank text still falls back to `text[:max_chars]`.
- The old `_split_tts_chunks` name in `jane_web.main` remains available as an alias.

Boundary chosen:
- Chunking is pure text transformation and can be tested without Docker, ffmpeg, cache files, or HTTP routes.
- The heavier TTS orchestration remains in `main.py` because it needs stronger characterization before moving.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/tts_chunks.py jane_web/main.py tests/test_tts_chunks.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_tts_chunks.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`73 passed`).

Remaining follow-up slices:
- Add characterization around the existing overlong comma-splitting edge case before changing chunking semantics.
- Consider extracting only TTS cache path selection next; defer Docker command orchestration until it has tests.
- Re-audit `jane_web/jane_proxy.py` now that several `main.py` route helpers have been removed.

## 2026-07-02 - Device Diagnostics JSONL Store

Goal/scope:
- Extract Android device diagnostics JSONL append/read behavior from `jane_web/main.py`.
- Preserve the unauthenticated write route and authenticated read route behavior while making log parsing testable.

Files/modules changed:
- `jane_web/device_diagnostics.py`
- `jane_web/main.py`
- `tests/test_device_diagnostics.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Diagnostic submissions still append one JSON object per line to `LOGS_DIR/android_diagnostics.jsonl`.
- Reads still return newest entries first.
- Missing diagnostics files still return an empty list.
- Malformed JSON lines are still skipped rather than failing the request.
- The `chat_error` / `error` self-healing dispatch remains in the route and is unchanged.

Boundary chosen:
- JSONL storage is mechanical file I/O and does not need to sit beside route-specific self-healing behavior.
- The extracted `DeviceDiagnosticsLog` gives focused coverage for malformed-line tolerance and ordering without changing request handling.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/device_diagnostics.py jane_web/main.py tests/test_device_diagnostics.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_device_diagnostics.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`69 passed`).

Remaining follow-up slices:
- Extract TTS text chunking into a pure helper with tests.
- Audit `jane_web/jane_proxy.py` for similarly pure stream/text helpers that can move without changing stream contracts.
- Avoid moving self-healing dispatch until route-level tests cover incident filing behavior.

## 2026-07-02 - Android App Settings JSON Store

Goal/scope:
- Extract Android app settings file persistence from `jane_web/main.py`.
- Keep the app settings routes unchanged while giving the JSON storage behavior focused tests.

Files/modules changed:
- `jane_web/app_settings.py`
- `jane_web/main.py`
- `tests/test_app_settings.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing settings files still load as `{}`.
- Invalid JSON still loads as `{}`.
- Saves still create the parent directory and write indented JSON.
- `/api/app/settings` and `PUT /api/app/settings` still use the same path under `VESSENCE_DATA_HOME/data/app_settings.json`.
- The old `_load_app_settings` and `_save_app_settings` names in `jane_web.main` remain available as aliases.

Boundary chosen:
- Settings persistence is a tiny file-backed store and does not need to be embedded in the route module.
- The route handlers now focus on HTTP request/response behavior while `JsonSettingsStore` owns disk I/O.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/app_settings.py jane_web/main.py tests/test_app_settings.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_app_settings.py -q` passed (`2 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`66 passed`).

Remaining follow-up slices:
- Extract device diagnostics JSONL append/read helpers.
- Extract TTS text chunking into a pure helper test before considering any Docker TTS orchestration changes.
- Continue avoiding route splits that would require live auth or database fixtures without characterization tests.

## 2026-07-02 - Contact Search Aggregation Helper

Goal/scope:
- Extract the pure contact row aggregation from `/api/contacts/search`.
- Preserve the search SQL, capability checks, and response shape while making contact merging independently testable.

Files/modules changed:
- `jane_web/contact_search.py`
- `jane_web/main.py`
- `tests/test_contact_search.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Rows still merge by `contact_id`, falling back to `display_name`.
- The first row for a person still supplies the response `display_name`.
- Phone numbers and emails are still deduplicated in first-seen order.
- Person ordering still follows the SQL row order.
- The `/api/contacts/search` route still returns a list of `{display_name, phones, emails}` dictionaries.

Boundary chosen:
- Aggregation is pure transformation logic embedded after a database query.
- Keeping the SQL in the route avoids changing DB behavior while removing branchy list/dict mutation from `main.py`.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/contact_search.py jane_web/main.py tests/test_contact_search.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_contact_search.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`64 passed`).

Remaining follow-up slices:
- Extract app settings JSON persistence.
- Extract device diagnostics JSONL append/read helpers with tests for malformed-line skipping and newest-first ordering.
- Consider DB-facing tests before moving contact or SMS database writes.

## 2026-07-02 - SMS Sync Message Classification Helper

Goal/scope:
- Extract the pure SMS message-type decision from the `/api/messages/sync` database route.
- Preserve the existing `synced_messages.msg_type` values and keyword precedence.

Files/modules changed:
- `jane_web/sms_classification.py`
- `jane_web/main.py`
- `tests/test_sms_classification.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Contact messages still classify as `personal` before keyword checks.
- Reminder keywords still take precedence over spam and notification keywords.
- Spam keywords still take precedence over notification keywords.
- Notification and unknown classifications keep the same keyword lists and output strings.
- SMS sync persistence, pruning, upsert behavior, logging, and response shape are unchanged.

Boundary chosen:
- The classifier is pure route-adjacent domain logic embedded in a DB write loop.
- Moving it makes the route easier to scan and lets future keyword changes be tested without exercising SQLite writes.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/sms_classification.py jane_web/main.py tests/test_sms_classification.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_sms_classification.py -q` passed (`4 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`61 passed`).

Remaining follow-up slices:
- Extract contact aggregation from `/api/contacts/search` into a pure helper with tests.
- Extract app settings persistence into a tiny JSON store helper.
- Consider DB-facing SMS sync tests before moving more of the route body.

## 2026-07-02 - Release Download Resolver Helper

Goal/scope:
- Continue reducing route-adjacent logic in `jane_web/main.py`.
- Move Android version reads, startup APK sanity logging, dynamic APK resolution, installer alias resolution, release artifact lookup, media-type selection, and latest-version payload construction into a focused helper module.

Files/modules changed:
- `jane_web/release_downloads.py`
- `jane_web/main.py`
- `tests/test_release_downloads.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- `version.json` remains the source for startup Android version metadata and `/api/app/latest-version`.
- `/downloads/vessences-android.apk` still resolves dynamically from `version.json` and falls back to the unversioned APK alias if version lookup fails.
- Versioned APK filenames, newest installer aliases, static release artifacts, generic legacy APK fallback, content types, cache-control headers, and 404 behavior are unchanged.
- `/api/app/latest-version` still avoids advertising a missing versioned APK by falling back to the newest deployed versioned APK while keeping the `version_code` from `version.json`.
- Existing private names in `jane_web.main` are retained as aliases for compatibility.

Boundary chosen:
- Release artifact resolution is pure filesystem/version logic and does not need to live in the route module.
- The new `ReleaseDownloads` object keeps path ownership explicit (`code_root`, `marketing_site`, `downloads`) and lets tests cover behavior without importing the full FastAPI app.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/release_downloads.py jane_web/main.py tests/test_release_downloads.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_release_downloads.py tests/test_ra_reports.py -q` passed (`9 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`57 passed`).

Remaining follow-up slices:
- Extract app settings persistence (`_load_app_settings` / `_save_app_settings`) into a tiny JSON store helper.
- Consider extracting device diagnostics persistence and SMS/contact sync helpers after adding DB-facing characterization tests.
- Keep Docker TTS generation in `main.py` until a stronger test seam exists because it shells out to Docker and ffmpeg.

## 2026-07-02 - RA Research Report Access Helper

Goal/scope:
- Continue the Vessence refactor loop with one small behavior-preserving slice.
- Move RA research report path lookup, signed-token handling, recent access grants, announcement tokenization, and metadata construction out of `jane_web/main.py`.

Files/modules changed:
- `jane_web/ra_reports.py`
- `jane_web/main.py`
- `tests/test_ra_reports.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- RA report IDs still use the `YYYYMMDD_HHMMSS` format.
- Missing, malformed, or non-file reports still raise `404`.
- Latest-report lookup still chooses the valid HTML report with the newest mtime.
- Authenticated users still receive a recent temporary report grant and signed report URL.
- Signed report URLs, announcement item shapes, metadata fields, token lifetimes, and temporary access sentinel remain unchanged.
- The old private helper names in `jane_web.main` remain available as aliases bound to the extracted helper object.

Boundary chosen:
- The RA report code was a self-contained access-control and metadata cluster embedded in the 6k-line route module.
- Extracting it to `RaReportAccess` removes route-file weight without changing FastAPI route contracts or importing `main.py` from the helper module.
- `session_secret`, `client_ip`, and `require_auth` are injected so the helper keeps the existing web behavior while staying unit-testable.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/ra_reports.py jane_web/main.py tests/test_ra_reports.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_ra_reports.py -q` passed (`3 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`51 passed`).

Remaining follow-up slices:
- Continue reducing `jane_web/main.py` by extracting similarly coherent route-adjacent clusters, especially device command queue, app settings/version helpers, and TTS proxy helpers.
- Keep `jane_web/jane_proxy.py` and memory manager refactors behind focused characterization tests because they own stream contracts and persisted state.

## 2026-06-30 - Pending Action Expiry Timezone Helper

Goal/scope:
- Complete one small behavior-preserving Vessence refactor slice from the previous follow-up list.
- Replace the pending-action resolver's naive UTC expiry comparison with a tiny UTC-aware parsing helper.

Files/modules changed:
- `jane_web/jane_v2/pending_action_resolver.py`
- `tests/test_pending_action_expiry.py`
- `REFACTORING.md`

Behavior intentionally preserved:
- Missing or malformed `pending_action.expires_at` still fails open as "not expired".
- Existing `YYYY-MM-DDTHH:MM:SSZ` timestamps still parse.
- Older naive ISO timestamps without `Z` still parse and are treated as UTC.
- Public route behavior, FIFO record shape, pending-action action names, and Stage 2/Stage 3 routing decisions are unchanged.

Boundary chosen:
- Expiry parsing is pure resolver-local logic with focused tests, so it is safer than splitting `jane_web/main.py`, `jane_proxy.py`, or `conversation_manager.py`.
- The helper removes the resolver's remaining `datetime.utcnow()` deprecation path without changing handlers that create expiry strings.

Verification:
- `/home/chieh/google-adk-env/adk-venv/bin/python -m py_compile jane_web/jane_v2/pending_action_resolver.py tests/test_pending_action_expiry.py` passed.
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests/test_pending_action_expiry.py test_code/test_stage3_awaiting_marker.py test_code/test_stage2_followup_pending_resolution.py -q` passed (`24 passed`).
- `/home/chieh/google-adk-env/adk-venv/bin/python -m pytest tests -q` passed (`41 passed`).
- A first attempt to run `test_code/test_pending_action_resolver.py` as part of a broader focused command exposed unrelated stale `TimerStateMachineTests` expectations: they assert no resolved pending marker, while the current timer handler emits `{"type": "STAGE2_FOLLOWUP", "handler_class": "timer", "status": "resolved"}`.

Lock note:
- `python agent_skills/code_lock.py status --project vessence` reported the lock free, but acquiring it failed because this sandbox cannot write `/home/chieh/ambient/vessence-data/locks/code_edit_vessence.lock`.

Remaining follow-up slices:
- Extract expiry-string construction used by Stage 2 handlers into a shared helper, once handler-focused tests are updated around resolved pending markers.
- Split `jane_web/main.py`, `jane_web/jane_proxy.py`, or `memory/v1/conversation_manager.py` only after adding route/stream/persistence characterization tests.
- Repair the stale timer state-machine assertions in `test_code/test_pending_action_resolver.py` or move them to current resolved-marker semantics.

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
