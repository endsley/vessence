# Job #62: Replace Vosk with OpenWakeWord + Android SpeechRecognizer

Priority: 1
Status: completed
Created: 2026-03-31

## Description
Replace Vosk (CPU-heavy full ASR) with OpenWakeWord (lightweight wake word only) for always-on listening. Use Android's built-in SpeechRecognizer for command capture instead of Vosk.

### Current Flow (Vosk — battery-hungry)
wake word (Vosk full ASR with grammar) → command capture (Vosk full ASR) → send to Jane → notification only

### New Flow (OpenWakeWord + SpeechRecognizer — efficient)
wake word (OpenWakeWord, lightweight ONNX) → SpeechRecognizer (Google, brief) → STT → send to Jane → TTS response → SpeechRecognizer (follow-up, no wake word) → STT → send to Jane → ... → silence → back to wake word

### Changes
1. **Add OpenWakeWord dependency** — community Android port uses ONNX Runtime (already in project). Train/obtain "hey jane" model via OpenWakeWord training pipeline.
2. **Rewrite `AlwaysListeningService.kt`**:
   - Replace Vosk wake word detection (`runWakeWordDetection()`) with OpenWakeWord inference
   - Replace Vosk command capture (`captureCommand()` / `captureFollowUpCommand()`) with Android `SpeechRecognizer`
   - Keep the TTS response + conversation loop we just built
3. **Remove Vosk from `VoiceController.kt`** — use same OpenWakeWord + SpeechRecognizer pattern
4. **Remove Vosk dependency** from `build.gradle.kts` and delete `VoskModelManager.kt`
5. **Remove Vosk model download** — no more 50MB model download on first use

### Key Resources
- OpenWakeWord GitHub: https://github.com/dscripka/openWakeWord
- Android port: https://github.com/hasanatlodhi/OpenwakewordforAndroid
- ONNX Runtime Android: already in project dependencies

### Stop / Interrupt Controls
6. **Notification action button** — add a "Stop" action to the persistent "Vessence is listening" notification. Tapping it stops the service immediately (stops TTS, stops listening, kills the foreground service). Works without opening the app.
7. **Home screen FAB** — when always-listening is active, show a visible floating stop button on the home screen. Tapping it stops the service and toggles the setting off.

### Acceptance Criteria
- "hey jane" wake word detected reliably with <4% CPU usage
- Commands captured via Android SpeechRecognizer (accurate, brief)
- Full conversation loop works with screen off: wake word → command → TTS reply → follow-up → ...
- Vosk completely removed from the project
- Battery drain significantly reduced compared to Vosk always-on
- Stop button in notification — one tap to kill everything
- Stop FAB on home screen when service is active
