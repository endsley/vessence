# Job: Interruptible (barge-in) voice conversation for Jane
Status: pending
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
- `/home/chieh/ambient/vessence/android/app/src/main/java/com/vessences/android/ui/chat/JaneChatScreen.kt`
- `/home/chieh/ambient/vessence/android/app/src/main/java/com/vessences/android/ui/chat/ChatInputRow.kt`
- `/home/chieh/ambient/vessence/android/app/src/main/java/com/vessences/android/util/ChatPreferences.kt`
- `/home/chieh/ambient/vessence/android/app/src/main/java/com/vessences/android/voice/VoiceController.kt`
- `/home/chieh/ambient/vessence/wake_word/voice_daemon.py`
- `/home/chieh/ambient/vessence/agent_skills/kokoro_tts.py` (if switching TTS)
- `/home/chieh/ambient/vessence/configs/Jane_architecture.md`

## Result
(pending)
