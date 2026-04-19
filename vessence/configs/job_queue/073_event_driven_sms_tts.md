# Job: Event-Driven SMS TTS for Android Jane
Status: completed
Priority: 1
Created: 2026-04-18
Completed: 2026-04-18

## Objective
Make Android Jane speak promptly when a new text message arrives, instead of waiting for a user-initiated Jane chat turn. The first spoken response should be event-driven from the incoming notification/SMS event, with privacy and interruption controls.

## Context
Chieh reported that while using Android Jane, a text message visibly arrives, but Jane waits before TTS starts. Investigation on 2026-04-18 found the current behavior is not a TTS engine delay. The incoming-message path only records/syncs the message; it does not call TTS or trigger Jane to answer.

Current code path:

1. `VessenceNotificationListener.onNotificationPosted()` receives the Android notification.
2. `handlePosted()` extracts message entries.
3. Each entry is recorded into `RecentMessagesBuffer`.
4. `SmsSyncManager.pushNewMessages(applicationContext)` runs on an IO coroutine.
5. No `tts.speak(...)`, no `ActionQueue.speak(...)`, no `sendMessage(...)`, and no `SttResultBus` event is triggered by the notification itself.

Important evidence:

- `android/app/src/main/java/com/vessences/android/notifications/VessenceNotificationListener.kt`
  - `handlePosted()` currently records entries and launches SMS sync.
  - This function already has sender/body/timestamp/package at notification time.
- `android/app/src/main/java/com/vessences/android/contacts/SmsSyncManager.kt`
  - `pushNewMessages()` syncs SMS to the server for later Jane reasoning/search.
  - This should remain, but should not be on the critical path for first speech.
- `android/app/src/main/java/com/vessences/android/tools/MessagesFetchUnreadHandler.kt`
  - `messages.fetch_unread` returns unread notification data to Jane and explicitly does not speak itself.
- `android/app/src/main/java/com/vessences/android/tools/MessagesReadRecentHandler.kt`
  - Legacy `messages.read_recent` speaks directly through `ActionQueue`, but only when Jane emits that client tool call during a chat turn.
- `android/app/src/main/java/com/vessences/android/ui/chat/ChatViewModel.kt`
  - Normal Jane response TTS happens after `/api/jane/chat/stream` returns assistant text.

Terminology from the investigation:

- A "chat turn" means: user says/types something -> Android calls `/api/jane/chat/stream` -> server routes/thinks -> Android receives assistant response -> Android TTS speaks it.
- The bug/latency here is that a new SMS notification is treated only as synced data, not as an event that can produce speech.

Related current work:

- In the active working tree on 2026-04-18, the STT possibly-complete silence timeout was reduced from `6000L` to `4000L` in all Android STT paths found:
  - `MainActivity.kt`
  - `VoiceController.kt`
  - `JaneChatScreen.kt`
  - `ChatInputRow.kt`
- That STT change is separate from this job. Do not undo it.

## Desired Behavior
When a safe, user-visible text/message notification arrives, Android Jane should be able to speak quickly without waiting for the user to ask "what did they say?"

Minimum fast path:

1. Notification listener extracts a safe message entry.
2. Android immediately speaks a short local TTS line, for example:
   - "New text from Kathia."
   - Optionally, if configured: "New text from Kathia: <body>."
3. SMS sync still runs in the background for server memory/search/history.

Optional richer path:

1. Android speaks a fast local line immediately.
2. Android may then ask the server/Jane for deeper triage or summary in the background if the user preference allows it.
3. The server-generated follow-up must not block the initial local TTS.

The product target is low latency. The critical path for the first spoken line should be notification extraction -> local Android TTS, not server sync, classifier routing, Opus, or tool-result follow-up.

## Privacy And Safety Requirements
Do not blindly read every message aloud in every context. Implement explicit policy gates before speech:

1. Do not speak OTP/2FA/security codes. Reuse `NotificationSafety.looksLikeOtp(...)`.
2. Do not speak placeholder/sensitive notification bodies. Reuse `NotificationSafety.isPlaceholderBody(...)` and `NotificationSafety.filterSafe(...)` where applicable.
3. Respect phone lock state:
   - If phone is locked, default to sender-only: "New text from <sender>."
   - Do not read the body while locked unless there is an explicit setting enabling that.
4. Avoid speaking messages from Jane's own package.
5. Avoid duplicate speech for notification updates from the same message. Use `sbnKey`, timestamp, sender/body hash, or a small TTL dedupe cache.
6. Avoid interrupting active Jane TTS unless the setting says incoming SMS can interrupt.
7. If STT is actively capturing user speech, do not seize the mic path. Either queue the SMS announcement until STT ends or speak only if Android audio focus rules allow it without breaking STT.
8. Add a user-facing setting or preference gate. Suggested defaults:
   - `announce_incoming_messages`: off or conservative by default if uncertain.
   - `announce_message_body`: off when locked, configurable when unlocked.
   - `announce_contacts_only`: on by default.

## Proposed Architecture
Add a small event-driven SMS announcement component on Android.

Suggested new component:

- `android/app/src/main/java/com/vessences/android/notifications/IncomingMessageAnnouncer.kt`

Responsibilities:

1. Accept `RecentMessagesBuffer.Entry` values from `VessenceNotificationListener.handlePosted()`.
2. Apply safety/privacy filters.
3. Deduplicate repeated notification updates.
4. Decide the spoken line:
   - sender-only
   - sender + body
   - suppressed
5. Speak through Android local TTS.

TTS integration options:

- Preferred for speed and isolation: instantiate/use `AndroidTtsManager` directly in the announcer or a process-wide singleton.
- If reusing existing `ActionQueue`, ensure it can be safely accessed outside `ChatViewModel`; current `ActionQueue` is attached to `ChatViewModel`'s `AndroidTtsManager`, so a notification service may not always have an attached queue.
- Do not route initial speech through `HybridTtsManager` server TTS. `HybridTtsManager.USE_SERVER_TTS` is currently `false`, but the event path should explicitly prefer local Android TTS for speed.

Notification listener integration:

- In `VessenceNotificationListener.handlePosted()` after `RecentMessagesBuffer.record(entry)`, pass the new entries to `IncomingMessageAnnouncer`.
- Keep the existing SMS sync coroutine unchanged, except do not make announcement depend on `pushNewMessages()`.

Settings integration:

- Add preference keys near existing chat/voice preferences if appropriate:
  - `announce_incoming_messages`
  - `announce_incoming_message_body`
  - `announce_incoming_messages_contacts_only`
  - `announce_incoming_messages_when_locked`
- If there is already a settings screen section for phone tools / voice, expose toggles there.

## Implementation Steps
1. Read the current Android notification, TTS, and settings code before editing:
   - `VessenceNotificationListener.kt`
   - `RecentMessagesBuffer.kt`
   - `NotificationSafety.kt`
   - `AndroidTtsManager.kt`
   - `HybridTtsManager.kt`
   - `ActionQueue.kt`
   - `ChatPreferences.kt`
   - relevant settings UI files under `android/app/src/main/java/com/vessences/android/ui/settings/`
2. Design the smallest safe announcer API. Example:
   - `IncomingMessageAnnouncer.onMessagesPosted(context, entries)`
   - or `IncomingMessageAnnouncer.announce(context, entry)`
3. Implement safety filtering:
   - listener permission is already implied by the notification callback
   - phone lock check via `NotificationSafety.isPhoneLocked(ctx)`
   - OTP/placeholder filtering via existing `NotificationSafety`
   - contacts-only policy if contact metadata is available; if notification entries do not know contact status, either resolve conservatively or skip contacts-only in v1 with a clear note.
4. Implement dedupe:
   - Small in-memory LRU/TTL set keyed by `sbnKey` or stable sender/body/timestamp key.
   - TTL around 1-5 minutes is enough to avoid repeated Android notification update speech.
5. Implement local TTS:
   - Use Android TTS, not server TTS, for the immediate event announcement.
   - Ensure TTS initialization is lazy and does not block notification handling on the main thread.
6. Wire `VessenceNotificationListener.handlePosted()` to call the announcer before or alongside SMS sync.
7. Add settings gates. If UI work is too large, at minimum add preference defaults and document how they will be exposed; but prefer exposing toggles in the Android settings UI.
8. Add diagnostics:
   - Report or log event categories such as `sms_announce_started`, `sms_announce_skipped`, `sms_announce_spoken`.
   - Include skip reason, not message body.
9. Build and deploy Android using the dedicated project script. Do not run raw `gradlew` directly. Follow AGENTS.md Android build/version rules.

## Verification
Evidence-based verification is required. Do not guess.

1. Static checks:
   - `rg -n "announce_incoming|IncomingMessageAnnouncer|sms_announce|onMessagesPosted" android/app/src/main/java/com/vessences/android`
   - `rg -n "looksLikeOtp|filterSafe|isPhoneLocked" android/app/src/main/java/com/vessences/android/notifications android/app/src/main/java/com/vessences/android/tools`
2. Confirm that `VessenceNotificationListener.handlePosted()` invokes the announcer and still invokes `SmsSyncManager.pushNewMessages(...)`.
3. Confirm that the announcer's first speech path does not call `/api/jane/chat/stream`.
4. Confirm that OTP/placeholder messages are skipped.
5. Confirm that duplicate notification updates do not speak repeatedly.
6. Confirm locked-phone behavior follows the implemented policy.
7. Build/deploy APK using the dedicated Android project script, not raw Gradle.
8. Runtime test on device:
   - Send a real test SMS while Android Jane is open/unlocked.
   - Verify TTS starts from the notification event within roughly 1 second after notification extraction.
   - Verify server `/api/messages/sync` still receives the message.
   - Send a second notification update for the same message and verify no duplicate speech.
   - Test locked screen behavior if feasible.

## Files Involved
Likely modified:

- `android/app/src/main/java/com/vessences/android/notifications/VessenceNotificationListener.kt`
- `android/app/src/main/java/com/vessences/android/notifications/NotificationSafety.kt`
- `android/app/src/main/java/com/vessences/android/notifications/IncomingMessageAnnouncer.kt` (new)
- `android/app/src/main/java/com/vessences/android/voice/AndroidTtsManager.kt`
- `android/app/src/main/java/com/vessences/android/util/ChatPreferences.kt` or a new notification preferences helper
- Android settings UI files under `android/app/src/main/java/com/vessences/android/ui/settings/`

Read-only context:

- `android/app/src/main/java/com/vessences/android/contacts/SmsSyncManager.kt`
- `android/app/src/main/java/com/vessences/android/tools/MessagesFetchUnreadHandler.kt`
- `android/app/src/main/java/com/vessences/android/tools/MessagesReadRecentHandler.kt`
- `android/app/src/main/java/com/vessences/android/tools/ActionQueue.kt`
- `android/app/src/main/java/com/vessences/android/ui/chat/ChatViewModel.kt`

## Non-Goals
Do not redesign the full Jane message-reading pipeline in this job.

Do not block immediate speech on:

- SMS database sync
- server routing
- Stage 1/2/3 classification
- Opus/standing brain
- `messages.fetch_unread`
- `/api/jane/chat/stream`

Do not speak raw private message bodies while locked unless there is an explicit user preference for that behavior.

## Notes For New Session
Chieh specifically wants evidence-based causes and implementation work, not speculative diagnosis. Read the code and logs before deciding behavior.

There are existing completed/pending SMS jobs in `configs/job_queue/` that provide useful background:

- `job_064_sms_display_cleanup.md`
- `job_067_sms_full_inbox_read.md`

This job is about proactive event-driven announcement latency, not about SMS search depth.

---

## Research And Implementation References (added 2026-04-18)

The problem — `NotificationListenerService` emits a posted-notification event, safety-filter + dedupe the entry, then fire Android TTS without blocking — is well-trodden territory. Two GPL/Apache Android apps solve exactly this pattern and their source is worth reading before writing ours:

- **Voice Notify** by pilot51 — https://github.com/pilot51/voicenotify (Apache-2.0, ~750 line core service). Canonical reference. Relevant files:
  - `app/src/main/java/com/pilot51/voicenotify/Service.kt` — the notification listener + TTS announcer. Single file, ~737 lines. `onNotificationPosted(sbn)` → build `NotificationInfo` → safety/ignore filter chain → `tts.speak()`.
  - `app/src/main/java/com/pilot51/voicenotify/IgnoreReason.kt` — enum of skip reasons (SUSPENDED, QUIET, SILENT, CALL, SCREEN_OFF, SCREEN_ON, HEADSET_OFF, APP, STRING_REQUIRED, STRING_IGNORED, EMPTY_MSG, **IDENTICAL**, TTS_FAILED, TTS_RESTARTED, TTS_INTERRUPTED, TTS_ERROR, TTS_LENGTH_LIMIT). Worth mirroring the pattern — a typed enum beats ad-hoc strings for diagnostics.
  - `app/src/main/java/com/pilot51/voicenotify/prefs/db/Settings.kt` — preference schema for quiet-time, string-ignore/require lists, per-app suspend, repeat-TTS interval, ignore-repeat window.

- **SpeakThat** by mitchib1440 — https://github.com/mitchib1440/SpeakThat (GPL-3.0, larger/more feature-rich). Relevant file:
  - `app/src/main/java/com/micoyc/speakthat/NotificationReaderService.kt` — ~7700 lines, production-grade. Skim for: (1) multi-layer dedupe — system key AND content-based key with SHA-256 hashing; (2) conditional filters (bluetooth/quiet-time/screen-state); (3) TTS voice + speed/pitch preferences; (4) in-app logger for skip reasons.

### Concrete patterns to borrow

**1. Audio focus (from VoiceNotify `Service.kt:98`):**

```kotlin
private val audioFocusRequest by lazy {
    AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
        .setAudioAttributes(AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_MEDIA)
            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
            .build())
        .build()
}
// Request before tts.speak(); abandon in UtteranceProgressListener.onDone().
audioMan.requestAudioFocus(audioFocusRequest)
// ...speak...
audioMan.abandonAudioFocusRequest(audioFocusRequest)
```

`AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK` is the correct choice for SMS announcements: short speech, other audio (music/podcast) should duck not pause. `USAGE_MEDIA` + `CONTENT_TYPE_SPEECH` tells the system this is human-speech content so auto-ducking rules apply.

Android docs: https://developer.android.com/media/optimize/audio-focus — confirms `GAIN_TRANSIENT_MAY_DUCK` is the right pattern for short speech prompts, and that automatic ducking is suppressed when the user is already listening to other speech content (e.g. voice navigation) — the OS handles that conflict for us.

**2. Dedupe — from SpeakThat (`NotificationReaderService.kt:2548`):**

```kotlin
private fun generateNotificationKey(packageName: String, notificationId: Int, content: String): String {
    val hash = MessageDigest.getInstance("SHA-256")
        .digest(content.toByteArray())
        .take(8).joinToString("") { "%02x".format(it) }
    return "${packageName}_${notificationId}_${hash}"
}
```

Key design choice: **no timestamp** in the dedupe key. Reason: when a notification is updated (new message appended, read-receipt flipped), Android posts it again with the same id but a new timestamp. Including timestamp would miss the dedupe.

For Jane's use case a simpler dedupe is sufficient since we only care about SMS entries, not all notifications:

```kotlin
// key = "${sender}|${body.trim()}|${packageName}" — normalized, no timestamp
// TTL cache bounded to 5 minutes + 50 entries
```

**3. Ignore-repeat window — from VoiceNotify `Service.kt:351-363`:**

```kotlin
// Walk the recent list; if same package + same spoken message within N seconds → IDENTICAL
for (priorInfo in NotifyList.notifyList) {
    val elapsed = Duration.between(priorInfo.instant, info.instant)
    if (ignoreRepeat != null && elapsed >= ignoreRepeat) break
    if (priorInfo.app?.packageName != app?.packageName) continue
    if (priorInfo.ttsMessage == ttsMsg) {
        info.addIgnoreReasonIdentical(...)
        break
    }
}
```

Simpler than a hash set and gives the user a tunable (defaulting to 60-120 s is reasonable).

**4. STT coexistence — a flag + RecognitionListener callbacks:**

- https://developer.android.com/reference/android/speech/SpeechRecognizer
- Use `RecognitionListener.onBeginningOfSpeech()` / `onEndOfSpeech()` to maintain an `isListening` boolean.
- Announcer checks `VoiceController.isSttActive()` before speaking; if true, queue the announcement for after STT ends or drop it (depending on settings).

In our codebase the STT-state flag already exists in `VoiceController.kt` / `ChatViewModel.kt` — we just need to expose a read-only getter.

**5. TTS initialization is async:**

`TextToSpeech(ctx, onInitListener)` fires `onInit(status)` asynchronously. The first announce-request arriving before TTS is ready must NOT drop the message. Voice Notify's pattern: `ttsQueue` — enqueue utterances, drain when engine is ready.

Our `AndroidTtsManager` already handles this for the chat-bubble TTS. We can either (a) inject the same manager into the announcer, or (b) spin up a second dedicated `TextToSpeech` instance for announcements. Two TTS instances means two audio streams — (a) is simpler and avoids race conditions.

### Decisions to lock in for implementation

- **Announcer lifecycle**: a process-wide singleton (like `RecentMessagesBuffer`) — notification callbacks are service-level events, not tied to `ChatViewModel` lifetime.
- **TTS**: reuse `AndroidTtsManager` via a process singleton accessor. The existing manager already handles init-latch and utterance queue.
- **Audio focus**: request `GAIN_TRANSIENT_MAY_DUCK` with `USAGE_MEDIA/CONTENT_TYPE_SPEECH` right before `speak()`, abandon on `onDone()`.
- **Dedupe**: TTL LRU set (5 min, 50 entries) keyed by normalized `sender|body|package`.
- **Lock screen**: if `NotificationSafety.isPhoneLocked(ctx)`, spoken text = `"New text from ${sender}."` — no body. Else = `"New text from ${sender}: ${body}"` (capped at `NotificationSafety.MAX_BODY_CHARS`).
- **STT coexistence**: announcer checks `VoiceController.isSttActive()` (add a read-only getter); if true, skip the announcement and log `sms_announce_skipped: reason=stt_active`. We can queue-and-defer in a later iteration.
- **Do-not-interrupt-Jane**: if `AndroidTtsManager.isSpeaking == true` for a Jane chat response, defer or drop per a setting. v1: drop, log `sms_announce_skipped: reason=jane_speaking`.
- **Settings (v1)**: single `announce_incoming_messages` boolean in `ChatPreferences`, default `false` so there's no surprise behavior on upgrade. Body-reading + lock-screen-body policy ship with safe defaults and become toggles in a later job.
- **Diagnostics**: structured log lines with categories — `sms_announce_started`, `sms_announce_spoken`, `sms_announce_skipped` + reason string. Mirrors VoiceNotify's `IgnoreReason` pattern without importing the full enum.

## Useful Links

- Voice Notify source — https://github.com/pilot51/voicenotify
- SpeakThat source — https://github.com/mitchib1440/SpeakThat
- Android audio focus guide — https://developer.android.com/media/optimize/audio-focus
- Android `NotificationListenerService` — https://developer.android.com/reference/android/service/notification/NotificationListenerService
- Android `SpeechRecognizer` (for STT-coexistence checks) — https://developer.android.com/reference/android/speech/SpeechRecognizer
- Android `KeyguardManager` — https://developer.android.com/reference/android/app/KeyguardManager
