# Job: Interruptible (barge-in) voice conversation for Jane
Status: in_progress
Priority: medium
Created: 2026-07-11
Tags: voice, wake-word, android, pipecat, livekit, architecture

## Objective
Replace the current strict turn-based voice loops with a full-duplex conversation flow where Chieh can interrupt Jane mid-sentence, like GPT-5.5 advanced voice mode — instead of waiting for Jane to finish speaking before he can talk again. The new path must be swappable: keep the old stable behavior available behind a flag/fallback so Talk to Jane remains usable if the new interruption system performs poorly.

## Context
- 2026-07-11 Android Talk-to-Jane findings:
  - `android/.../ui/chat/ChatViewModel.kt` currently treats input during `isSending` as queued work (`pendingQueue`) rather than interruption. This makes mid-response speech wait for Jane's current turn to finish.
  - Voice replies relaunch STT only after TTS playback completes (`sentence_tts` and non-sentence paths), so the normal voice loop is half-duplex: listen -> send -> stream -> speak -> listen.
  - `VoiceController.kt` also blocks wake/listen while waiting for Jane's reply, and `JaneChatScreen.kt`/`ChatInputRow.kt` expose manual stop buttons rather than a true barge-in path.
  - Current manual workaround: tap Stop/Stop speaking, then speak again. There is no smooth automatic barge-in.
- Current pipeline (`wake_word/voice_daemon.py`, ~350 lines): wake word (openWakeWord) -> `record_until_silence()` blocks until user stops talking -> STT via `faster_whisper` (`STTEngine`, default `base` model) -> blocking call to Jane's brain (`send_to_jane()`) -> `speak_text()` via `edge_tts` plays the full reply -> loop back to wake-word listening. No VAD runs during TTS playback, so there is no way to detect or act on speech while Jane is talking.
- Jane's brain is currently Codex (not a locally-hosted model) — inference happens on OpenAI's servers. This does not change any local VRAM/compute needs for the voice pipeline itself; the brain call is just a network round trip regardless of which agent runtime answers it.
- Local GPU: RTX A5000, 24GB VRAM, ~17GB free at time of writing. Not a constraint for this work — `faster_whisper` (base/small) is ~1-2GB VRAM, and a local TTS swap to Kokoro (`agent_skills/kokoro_tts.py` already exists) is also ~1-2GB. `edge_tts` (current TTS) is a free cloud API call, 0 local VRAM, but offers no mid-stream cancel control.
- Researched options:
  - **LiveKit Agents** is the best strategic fit for a production full-duplex Android/WebRTC replacement. It supports Android clients, explicit `session.interrupt()`, automatic interruption on detected user speech, conversation-history truncation to what the user actually heard, false-interruption recovery, and adaptive barge-in in LiveKit Cloud.
  - **Pipecat** is the best vendor-neutral Python pipeline option. It has VAD, turn-start/turn-stop strategies, Smart Turn, Android SDKs, and transports including Daily/WebRTC, Gemini Live, OpenAI WebRTC, and SmallWebRTC. It is a strong fit for the local daemon or a self-owned voice stack.
  - **OpenAI Realtime / Agents SDK** is the fastest path to GPT-like behavior. Realtime VAD cancels the active response, starts a new one, and handles truncation automatically for WebRTC/SIP. Tradeoff: more of Jane's voice session and turn-taking moves into OpenAI's realtime stack.
  - **Vocode** supports streaming conversation interruption sensitivity, but current public release activity looks older; use as reference, not the foundation.
- Both frameworks are free/open source; only paid components would be hosted STT/TTS APIs if swapped in later (not needed here).
- 2026-07-12 follow-up design decision:
  - Android already has a Jane wake word. Reuse it as the passive entry point; do not rebuild wake-word detection.
  - The new system starts after wake-word activation. The wake word should wake Jane from passive mode, then the active conversation should support natural barge-in without requiring Chieh to say "Jane" before every interruption.
  - Once audio has been converted to text, feed that text into Jane's existing three-stage model path. Do not replace Jane's reasoning architecture with a realtime voice vendor.
  - Codex remains the frontier reasoning brain when the live backend is configured for Codex. The realtime voice shell passes text into Jane/Codex; Codex does not receive raw audio.
  - No separate OpenAI Realtime API is required for this open-source/local version. OpenAI Realtime can remain an optional future transport/provider if Chieh later chooses to pay for it.
  - Target feel: GPT-style flow, meaning fast hands-free wake, natural pause detection, immediate TTS stop on interruption, no waiting for Jane to finish before speaking, and seamless continuation of the same conversation.

## End-to-End Design

### 1. Passive wake-word mode
- `AlwaysListeningService` continues to own passive wake-word detection.
- In passive mode Jane listens only for the wake word and avoids running full STT/conversation capture.
- When the wake word fires, the current code path already navigates to Jane and calls `ChatViewModel.triggerWakeWord()`.
- Legacy mode keeps the existing behavior: `triggerWakeWord() -> MainActivity.launchStt() -> Android SpeechRecognizer`.
- New mode changes only the handoff: `triggerWakeWord() -> RealtimeVoiceSession.start()`.

### 2. Active realtime voice session
- After wake-word activation, Jane enters an active conversation session.
- Inside this active session, Chieh should not need to repeat the wake word.
- The active session continuously manages:
  - microphone capture
  - VAD / speech-start detection
  - endpointing / speech-stop detection
  - partial transcript display
  - stable transcript commit
  - Jane response playback
  - interruption while Jane is speaking
- This layer owns voice timing and turn-taking only. It must not duplicate Stage 1/2/3 Jane reasoning.

### 3. Audio capture and VAD
- Prefer a streaming capture path over one-shot Android `SpeechRecognizer`.
- Use local/open-source components where practical:
  - VAD: Silero VAD, WebRTC VAD, or framework-native VAD from Pipecat/LiveKit.
  - STT: faster-whisper/whisper.cpp/local STT service, or Android STT as a temporary compatibility fallback.
  - Transport/framework: Pipecat or LiveKit-style session abstractions are acceptable foundations.
- VAD must run during Jane's TTS playback so Chieh can interrupt.
- The system must distinguish user speech from Jane's own output. Use echo cancellation, playback ducking, audio focus, or framework-native AEC where available.

### 4. Speech-to-text commit
- Streaming STT may produce partial transcripts, but only stable committed text should enter Jane's brain.
- Commit conditions:
  - user speech has ended according to VAD/endpointing
  - transcript is non-empty after cleanup
  - text is not just wake-word residue or obvious self-echo
- The committed user utterance becomes a normal Jane user message with `fromVoice=true`.

### 5. Existing Jane three-stage text pipeline
- After STT commit, pass text into the existing Jane request path.
- Preserve the current three-stage architecture:
  1. Stage 1 classifier: fast intent routing and confidence.
  2. Stage 2 deterministic handler: known structured behavior such as timers, music, app commands, pending actions, and simple tool routes.
  3. Stage 3 frontier brain: Jane's main reasoning path, currently Codex-backed when `JANE_BRAIN=codex`.
- The realtime voice work must not bypass Stage 1/2. Local deterministic actions should stay fast and not unnecessarily invoke Codex.
- Stage 3 receives text and context, not audio.

### 6. Response streaming and TTS
- Jane's response text returns through the existing chat stream.
- TTS should speak sentence chunks or stable response chunks as soon as they are safe to speak.
- The TTS layer must be cancellable:
  - stop current audio output immediately on interruption
  - clear queued sentence chunks
  - prevent stale audio from resuming after cancellation
- The first implementation may reuse existing Android/server TTS queues if they can be stopped reliably. A local daemon path may use Kokoro or another cancellable local TTS engine.

### 7. Barge-in interruption semantics
- If Chieh starts speaking while Jane is talking:
  - stop Jane's TTS immediately
  - mark the current assistant message as interrupted
  - cancel or ignore the current active response stream
  - clear queued TTS chunks and pending follow-up voice sends
  - capture Chieh's new speech
  - commit the new transcript as the next active user turn
  - send that text through the same Stage 1 -> Stage 2 -> Stage 3 pipeline
- The old assistant response must not race with the new response. Late deltas/audio from the interrupted turn must be discarded by turn id.

### 8. Conversation state
- Introduce explicit voice session states:
  - `PassiveWakeWord`
  - `Listening`
  - `UserSpeaking`
  - `Thinking`
  - `Speaking`
  - `Interrupted`
  - `Ending`
- Wake word transitions `PassiveWakeWord -> Listening`.
- User speech transitions `Listening -> UserSpeaking -> Thinking`.
- Jane text/TTS transitions `Thinking -> Speaking`.
- Barge-in transitions `Speaking -> Interrupted -> UserSpeaking`.
- Goodbye, music handoff, explicit cancel, or timeout transitions back to `PassiveWakeWord`.

### 9. Swappability and fallback
- Keep the old turn-based path intact.
- Add a preference/flag, conceptually:
  - `voice_conversation_mode = legacy_turn_based | interruptible_realtime`
- Legacy mode should continue to use the current `launchStt()` and auto-relaunch-after-TTS behavior.
- New mode should route wake-word activation and mic button voice capture through `RealtimeVoiceSession`.
- Chieh must be able to switch back without reinstalling the app or reverting code.

### 10. Expected user experience
- Chieh says: "Jane."
- Jane wakes and starts the active session.
- Chieh says a request naturally.
- Jane starts responding by voice.
- Chieh interrupts mid-sentence with a correction or follow-up.
- Jane stops speaking quickly and listens.
- Jane answers the new turn in the same conversation context.
- For simple local/deterministic actions, this should feel nearly immediate.
- For Codex-level reasoning, Jane may still pause while Codex thinks, but the voice shell should remain fluid and interruptible.

### 11. Non-goals for the first working version
- Do not require OpenAI Realtime.
- Do not replace Codex/Jane reasoning.
- Do not remove Android wake word.
- Do not remove legacy SpeechRecognizer mode.
- Do not require a locally hosted Jane-level reasoning model. Local/open-source is for voice I/O first; Jane-level reasoning remains the existing frontier brain path unless a future job changes that.

## Steps
1. Read `wake_word/voice_daemon.py`, Android `ChatViewModel.kt`, `JaneChatScreen.kt`, `ChatInputRow.kt`, and `VoiceController.kt` in full and confirm current STT/TTS/wake-word wiring before changing anything.
2. Acquire the code edit lock (`agent_skills.code_lock`) before editing.
3. First implementation target: add a swappable Android interruption mode. When enabled, voice/text input during an active reply should stop TTS, cancel the current stream, mark the partial assistant reply as interrupted/cancelled, clear queued follow-ups, and immediately send the new utterance instead of queuing it. Legacy behavior must remain available.
4. Add a visible or preference-backed switch for the new mode so Chieh can toggle between legacy turn-based mode and interruptible mode without reinstalling or reverting code.
5. Prototype a local daemon interruption path after Android is stable: wake-word gate -> streaming/VAD capture -> Jane brain call (`send_to_jane`, currently Codex) -> cancellable TTS, with VAD running during playback so user speech triggers immediate playback cancellation and fresh STT capture.
6. Handle echo cancellation / self-hearing (Jane's own TTS output must not re-trigger her own VAD) — check what Pipecat/LiveKit provides natively vs. what needs a local AEC library.
7. Handle brain-call cancellation: if interrupted mid-response, cancel/discard the in-flight Codex call cleanly rather than letting two replies race.
8. Test barge-in latency end-to-end (target: interrupt-to-silence under ~200ms for local playback cancellation; Android external STT may be slower until replaced with streaming STT/VAD).
9. Update `configs/Jane_architecture.md` with the new voice pipeline design once working.
10. Build a new Android package version using the project bump/build script before closing the job.

## Verification
- Manually test Android: speak/send while Jane is mid-reply in interruptible mode, confirm TTS stops immediately and the new utterance sends without waiting for the old reply to finish.
- Manually test Android fallback: disable interruptible mode and confirm existing queue/turn-based behavior still works.
- Manually test local daemon if implemented: speak while Jane is mid-reply, confirm TTS stops immediately and Jane starts listening to the new input without needing a full stop-then-wake-word restart.
- Confirm normal (non-interrupted) turns still work exactly as before.
- Confirm no regression in wake-word detection reliability.
- Compile/package a new Android version with the bump script.

## Files Involved
- `/home/chieh/ambient/vessence/android/app/src/main/java/com/vessences/android/ui/chat/ChatViewModel.kt`
- `/home/chieh/ambient/vessence/android/app/src/main/java/com/vessences/android/voice/BargeInMonitor.kt`
- `/home/chieh/ambient/vessence/android/app/src/main/java/com/vessences/android/ui/chat/JaneChatScreen.kt`
- `/home/chieh/ambient/vessence/android/app/src/main/java/com/vessences/android/ui/chat/ChatInputRow.kt`
- `/home/chieh/ambient/vessence/android/app/src/main/java/com/vessences/android/util/ChatPreferences.kt`
- `/home/chieh/ambient/vessence/android/app/src/main/java/com/vessences/android/voice/VoiceController.kt`
- `/home/chieh/ambient/vessence/wake_word/voice_daemon.py`
- `/home/chieh/ambient/vessence/agent_skills/kokoro_tts.py` (if switching TTS)
- `/home/chieh/ambient/vessence/configs/Jane_architecture.md`

## Result
2026-07-12 implementation pass:
- Added Android `BargeInMonitor`, a low-latency `AudioRecord` speech-energy monitor that runs only while interruptible voice mode is enabled and Jane is speaking. It uses Android `VOICE_COMMUNICATION` audio source plus echo/noise suppression when available.
- Wired `ChatViewModel` to arm barge-in monitoring during voice playback paths (`ack`, sentence-level streaming TTS, non-sentence TTS, and transient-error notices).
- On detected barge-in, `ChatViewModel` now stops active TTS, cancels the current response stream, marks the partial assistant message interrupted, clears queued follow-ups, shows the listening state, and launches the existing headless `MainActivity.launchStt()` path. The resulting transcript still goes through Jane's existing Stage 1 -> Stage 2 -> Stage 3 pipeline.
- Existing interruptible mode toggle remains the swappable fallback boundary. With the toggle off, the legacy turn-based voice path remains intact.
- Updated `configs/Jane_architecture.md`.
- Verified:
  - `./gradlew :app:compileDebugKotlin` passed.
  - `./gradlew :app:testDebugUnitTest` passed with `NO-SOURCE` unit tests.
  - `python -m py_compile wake_word/voice_daemon.py` passed.
  - Android bump/build script produced and deployed v0.2.101, versionCode 332.
- Not verified from this Codex session:
  - Physical Android barge-in behavior, because `adb devices` showed no attached devices.
