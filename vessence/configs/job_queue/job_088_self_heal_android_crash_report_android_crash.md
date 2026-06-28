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
