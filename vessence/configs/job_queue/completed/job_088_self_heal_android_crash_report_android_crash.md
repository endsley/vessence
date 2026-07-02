# Job: Self-heal android_crash_report: === VESSENCE CRASH REPORT ===
Time: 2026-06-25 09:44:28
Version: 0.2.97 (code 328)
Device: OnePlus IN2017
Android: 13 (S
Status: completed
Priority: high
Created: 2026-06-26
Auto-generated: true
Source: jane_self_healing
Incident: /home/chieh/ambient/vessence-data/self_healing/incidents/20260626T104225.698556+0000_android_crash_report_a731dc48de8845ad416a3fb3.json

## Objective
Jane should inspect the incident evidence, diagnose the root cause, and apply a
minimal, verified fix if the evidence supports one.

## Context
- Source: `android_crash_report`
- Category: `android_crash`
- Project root: `/home/chieh/ambient/vessence`
- Fingerprint: `a731dc48de8845ad416a3fb3`
- Request path: `/api/crash-report`

## Steps
1. Read the incident JSON at `/home/chieh/ambient/vessence-data/self_healing/incidents/20260626T104225.698556+0000_android_crash_report_a731dc48de8845ad416a3fb3.json` and the relevant service logs.
2. Inspect source code before explaining the cause. Do not speculate from the stack trace alone.
3. Reproduce with a focused test or command when feasible.
4. If the root cause is clear, patch the smallest relevant surface.
5. Do not revert unrelated dirty work. Preserve user changes.
6. Run focused verification. Broaden tests only if the fix touches shared behavior.
7. Record the outcome in the incident report and work log.

## Verification
- The failing route/action no longer throws the captured error.
- A focused test, syntax check, or local smoke test covers the fixed path.
- If no safe fix is possible, leave a clear report explaining the blocker and evidence checked.

## Result
Rechecked 2026-06-27.

Evidence reviewed:
- Incident JSON: `/home/chieh/ambient/vessence-data/self_healing/incidents/20260626T104225.698556+0000_android_crash_report_a731dc48de8845ad416a3fb3.json`
- Android crash log: `/home/chieh/ambient/vessence-data/logs/android_crashes.log`
- Android diagnostics: `/home/chieh/ambient/vessence-data/logs/android_diagnostics.jsonl`
- Existing self-healing report: `/home/chieh/ambient/vessence-data/self_healing/reports/20260626T104225.821409+0000_android_crash_report_a731dc48de8845ad416a3fb3.md`
- Source: `android/app/src/main/java/com/vessences/android/voice/AlwaysListeningService.kt`, `android/app/src/main/java/com/vessences/android/CrashReporter.kt`, `jane_web/main.py`

Outcome:
- The current source already contains the prior minimal fix for the captured Android foreground-service crash: `AlwaysListeningService` promotes itself to foreground immediately in `onCreate()`, guards duplicate `startForegroundService()` calls with shared atomics, defers stop during start-in-flight, and skips late microphone startup when stop is pending.
- All discovered caller sites route through `AlwaysListeningService.start()` / `AlwaysListeningService.stop()`; no direct bypass of the guard was found.
- No new source patch was justified.

Verification:
- `GRADLE_USER_HOME=/tmp/codex-gradle-home nice -n 19 ionice -c 3 ./gradlew :app:compileDebugKotlin` passed: `BUILD SUCCESSFUL`.
- `git diff --check -- android/app/src/main/java/com/vessences/android/voice/AlwaysListeningService.kt android/app/src/main/java/com/vessences/android/CrashReporter.kt jane_web/main.py` passed.
- Full `git diff --check` passed on the final check.

Recording blocker:
- Updating the canonical incident JSON/report and Work Log was attempted but blocked by the current Codex filesystem sandbox as read-only:
  - `/home/chieh/ambient/vessence-data/self_healing/incidents/20260626T104225.698556+0000_android_crash_report_a731dc48de8845ad416a3fb3.json`
  - `/home/chieh/ambient/skills/work_log/user_data/activity_log.json`

## Recheck 2026-06-28

Evidence reviewed again:
- Incident JSON: `/home/chieh/ambient/vessence-data/self_healing/incidents/20260626T104225.698556+0000_android_crash_report_a731dc48de8845ad416a3fb3.json`
- Existing repair report: `/home/chieh/ambient/vessence-data/self_healing/reports/20260626T104225.821409+0000_android_crash_report_a731dc48de8845ad416a3fb3.md`
- Android crash/diagnostic logs: `/home/chieh/ambient/vessence-data/logs/android_crashes.log`, `/home/chieh/ambient/vessence-data/logs/android_diagnostics.jsonl`
- Source: `android/app/src/main/java/com/vessences/android/voice/AlwaysListeningService.kt`, `android/app/src/main/java/com/vessences/android/CrashReporter.kt`, `jane_web/main.py`

Outcome:
- The current source already contains the foreground-service lifecycle repair for the captured Android 13 crash.
- `AlwaysListeningService` promotes itself to foreground in `onCreate()`, suppresses duplicate starts while foreground/start-in-flight, defers stop during start-in-flight, preserves pending restarts, and prevents late microphone startup when stop is pending.
- Source search found no direct caller bypassing `AlwaysListeningService.start()` / `AlwaysListeningService.stop()`.
- No additional source patch was justified.

Verification:
- `GRADLE_USER_HOME=/tmp/codex-gradle-home nice -n 19 ionice -c 3 ./gradlew :app:compileDebugKotlin` passed: `BUILD SUCCESSFUL in 3m 26s`.
- Kotlin daemon startup initially hit the sandboxed `/home/chieh/.local/share/kotlin` path and Gradle fell back to non-daemon compilation; the fallback compile completed successfully.
- `git diff --check -- android/app/src/main/java/com/vessences/android/voice/AlwaysListeningService.kt android/app/src/main/java/com/vessences/android/CrashReporter.kt jane_web/main.py` passed.

Recording blocker:
- Canonical Work Log update failed with read-only filesystem at `/home/chieh/ambient/skills/work_log/user_data/activity_log.json`.
- Canonical incident JSON/report update failed with read-only filesystem at `/home/chieh/ambient/vessence-data/self_healing/incidents/20260626T104225.698556+0000_android_crash_report_a731dc48de8845ad416a3fb3.json`.

## Recheck 2026-06-29

Evidence reviewed again:
- Incident JSON: `/home/chieh/ambient/vessence-data/self_healing/incidents/20260626T104225.698556+0000_android_crash_report_a731dc48de8845ad416a3fb3.json`
- Existing repair report: `/home/chieh/ambient/vessence-data/self_healing/reports/20260626T104225.821409+0000_android_crash_report_a731dc48de8845ad416a3fb3.md`
- Android crash/diagnostic logs: `/home/chieh/ambient/vessence-data/logs/android_crashes.log`, `/home/chieh/ambient/vessence-data/logs/android_diagnostics.jsonl`
- Source: `android/app/src/main/java/com/vessences/android/voice/AlwaysListeningService.kt`, `android/app/src/main/java/com/vessences/android/CrashReporter.kt`, `jane_web/main.py`
- Android call-site search for direct `startForegroundService()` / `startService()` / `stopService()` usage.

Outcome:
- The current source still contains the foreground-service lifecycle repair for the captured Android 13 crash.
- `AlwaysListeningService` promotes itself to foreground in `onCreate()`, suppresses duplicate starts while foreground/start-in-flight, defers stop during start-in-flight, preserves pending restarts, and prevents late microphone startup when stop is pending.
- Source search found no direct caller bypassing `AlwaysListeningService.start()` / `AlwaysListeningService.stop()`.
- No additional source patch was justified.

Verification:
- `GRADLE_USER_HOME=/tmp/codex-gradle-home nice -n 19 ionice -c 3 ./gradlew :app:compileDebugKotlin` passed: `BUILD SUCCESSFUL in 30s`.
- `git diff --check -- android/app/src/main/java/com/vessences/android/voice/AlwaysListeningService.kt android/app/src/main/java/com/vessences/android/CrashReporter.kt jane_web/main.py configs/job_queue/job_088_self_heal_android_crash_report_android_crash.md` passed.

Recording blocker:
- Canonical incident JSON/report update failed with read-only filesystem at `/home/chieh/ambient/vessence-data/self_healing/incidents/20260626T104225.698556+0000_android_crash_report_a731dc48de8845ad416a3fb3.json`.
- Because the incident update failed before the Work Log helper ran, no canonical Work Log entry was written from this recheck. Prior attempts also showed `/home/chieh/ambient/skills/work_log/user_data/activity_log.json` is blocked by the sandbox.

## Recheck 2026-06-30

Evidence reviewed again:
- Incident JSON: `/home/chieh/ambient/vessence-data/self_healing/incidents/20260626T104225.698556+0000_android_crash_report_a731dc48de8845ad416a3fb3.json`
- Existing repair report: `/home/chieh/ambient/vessence-data/self_healing/reports/20260626T104225.821409+0000_android_crash_report_a731dc48de8845ad416a3fb3.md`
- Android diagnostic log: `/home/chieh/ambient/vessence-data/logs/android_diagnostics.jsonl`
- Self-healing logs: `/home/chieh/ambient/vessence-data/logs/self_healing.jsonl`, `/home/chieh/ambient/vessence-data/logs/self_healing_repair.log`
- Source: `android/app/src/main/java/com/vessences/android/voice/AlwaysListeningService.kt`, `android/app/src/main/java/com/vessences/android/CrashReporter.kt`, `jane_web/main.py`
- Android call-site search for direct service start/stop bypasses.

Outcome:
- No new source patch was justified.
- The incident and diagnostic logs still support the prior root cause: Android 13 killed `AlwaysListeningService` after a foreground-service start did not reach foreground promotion in time; diagnostics at `2026-06-25T09:44:28Z` show the service started, stopped within milliseconds, then still loaded the wake-word model and started the mic.
- Current source still contains the existing repair: immediate foreground promotion in `onCreate()`, shared atomics around `startForegroundService()`, deferred stop while start is in flight, preserved restart-after-stop intent, and guard checks that prevent late mic startup when stop is pending.
- Current Android call sites still route through `AlwaysListeningService.start()` / `AlwaysListeningService.stop()`; no direct bypass was found.

Verification:
- `GRADLE_USER_HOME=/tmp/codex-gradle-home nice -n 19 ionice -c 3 ./gradlew :app:compileDebugKotlin` passed: `BUILD SUCCESSFUL in 42s`.
- A temp-data-root smoke test of `receive_crash_report()` passed: the route returned `{"status": "received"}`, wrote `android_crashes.log`, and dispatched source/category metadata with self-healing stubbed.
- `git diff --check -- android/app/src/main/java/com/vessences/android/voice/AlwaysListeningService.kt android/app/src/main/java/com/vessences/android/CrashReporter.kt jane_web/main.py` passed.

Recording blocker:
- Canonical incident JSON is not writable from this sandbox: `/home/chieh/ambient/vessence-data/self_healing/incidents/20260626T104225.698556+0000_android_crash_report_a731dc48de8845ad416a3fb3.json`.
- Canonical repair report is not writable from this sandbox: `/home/chieh/ambient/vessence-data/self_healing/reports/20260626T104225.821409+0000_android_crash_report_a731dc48de8845ad416a3fb3.md`.
- Work Log files are not writable from this sandbox: `/home/chieh/ambient/skills/work_log/user_data/activity_log.json`, `/home/chieh/ambient/essences/work_log/user_data/activity_log.json`.

## Recheck 2026-07-01

Evidence reviewed again:
- Incident JSON: `/home/chieh/ambient/vessence-data/self_healing/incidents/20260626T104225.698556+0000_android_crash_report_a731dc48de8845ad416a3fb3.json`
- Existing repair report: `/home/chieh/ambient/vessence-data/self_healing/reports/20260626T104225.821409+0000_android_crash_report_a731dc48de8845ad416a3fb3.md`
- Android diagnostic log: `/home/chieh/ambient/vessence-data/logs/android_diagnostics.jsonl`
- Job queue log: `/home/chieh/ambient/vessence-data/logs/job_queue.log`
- Source: `android/app/src/main/java/com/vessences/android/voice/AlwaysListeningService.kt`, `android/app/src/main/java/com/vessences/android/CrashReporter.kt`, `jane_web/main.py`
- Android call-site search for direct service start/stop bypasses.

Outcome:
- No new source patch was justified.
- The incident is already marked `repair_finished`, and the current source still contains the foreground-service lifecycle repair for the captured Android 13 crash.
- `AlwaysListeningService` promotes itself to foreground immediately in `onCreate()`, suppresses duplicate starts while already foreground or start-in-flight, defers stop while start is in flight, preserves restart-after-stop requests, and prevents late mic startup when stop is pending.
- Current Android call sites still route through `AlwaysListeningService.start()` / `AlwaysListeningService.stop()`; no direct bypass was found.
- `/home/chieh/ambient/vessence-data/logs/android_crashes.log` is no longer present, but the incident JSON and `android_diagnostics.jsonl` preserve the captured crash and lifecycle evidence.

Verification:
- `GRADLE_USER_HOME=/tmp/codex-gradle-home nice -n 19 ionice -c 3 ./gradlew :app:compileDebugKotlin` passed: `BUILD SUCCESSFUL in 1m 5s`.
- A temp-data-root smoke test of `receive_crash_report()` passed using `/home/chieh/google-adk-env/adk-venv/bin/python`: the route returned `{"status": "received"}`, wrote `android_crashes.log`, and dispatched source/category metadata with self-healing stubbed.
- `git diff --check -- android/app/src/main/java/com/vessences/android/voice/AlwaysListeningService.kt android/app/src/main/java/com/vessences/android/CrashReporter.kt jane_web/main.py configs/job_queue/completed/job_088_self_heal_android_crash_report_android_crash.md` passed before this entry was appended.

Recording blocker:
- Canonical incident JSON/report files live under `/home/chieh/ambient/vessence-data`, which is outside the current writable sandbox roots, so this recheck is recorded in the repository job work log instead.
- The documented Vessence venv path `/home/chieh/ambient/venv/bin/python` is absent on this machine; the route smoke test used the available ADK Python.

## Recheck 2026-07-02

Evidence reviewed again:
- Incident JSON: `/home/chieh/ambient/vessence-data/self_healing/incidents/20260626T104225.698556+0000_android_crash_report_a731dc48de8845ad416a3fb3.json`
- Existing repair report: `/home/chieh/ambient/vessence-data/self_healing/reports/20260626T104225.821409+0000_android_crash_report_a731dc48de8845ad416a3fb3.md`
- Android diagnostic log: `/home/chieh/ambient/vessence-data/logs/android_diagnostics.jsonl`
- Source: `android/app/src/main/java/com/vessences/android/voice/AlwaysListeningService.kt`, `android/app/src/main/java/com/vessences/android/CrashReporter.kt`, `jane_web/main.py`
- Android call-site search for direct service start/stop bypasses.

Outcome:
- No new source patch was justified.
- The incident is already marked `repair_finished`, and the current source still contains the foreground-service lifecycle repair for the captured Android 13 crash.
- Diagnostic evidence at `2026-06-25T09:44:28Z` still shows `AlwaysListening` started, stopped milliseconds later, then continued through model load and mic startup; current code guards this path with immediate foreground promotion, shared start/foreground/stop atomics, deferred stop while start is in flight, restart-after-stop preservation, and late mic-start checks.
- Current Android call sites still route through `AlwaysListeningService.start()` / `AlwaysListeningService.stop()`; no direct bypass was found.
- `/home/chieh/ambient/vessence-data/logs/android_crashes.log` is no longer present; the incident JSON and `android_diagnostics.jsonl` preserve the captured crash and lifecycle evidence.

Verification:
- Temp-data-root smoke test of `POST /api/crash-report` passed using `/home/chieh/google-adk-env/adk-venv/bin/python`: the route returned `{"status": "received"}`, wrote `android_crashes.log`, and dispatched `android_crash_report` / `android_crash` metadata with self-healing stubbed.
- `GRADLE_USER_HOME=/tmp/codex-gradle-home ./gradlew --no-daemon :app:compileDebugKotlin` passed: `BUILD SUCCESSFUL in 5m 41s`.
- The original `GRADLE_USER_HOME=/tmp/codex-gradle-home nice -n 19 ionice -c 3 ./gradlew :app:compileDebugKotlin` check also completed: `BUILD SUCCESSFUL in 7m 27s`.
- Both Gradle runs hit the known sandbox-only Kotlin daemon read-only warning for `/home/chieh/.local/share/kotlin`, then fell back to non-daemon compilation successfully.
- `git diff --check -- android/app/src/main/java/com/vessences/android/voice/AlwaysListeningService.kt android/app/src/main/java/com/vessences/android/CrashReporter.kt jane_web/main.py configs/job_queue/completed/job_088_self_heal_android_crash_report_android_crash.md` passed before this entry was appended.

Recording blocker:
- Canonical incident JSON/report files live under `/home/chieh/ambient/vessence-data`, which is outside the current writable sandbox roots, so this recheck is recorded in the repository job work log instead.
