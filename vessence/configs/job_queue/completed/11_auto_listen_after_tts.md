# Job: Auto-Listen After TTS — Continuous Voice Conversation Mode

Status: complete
Priority: 2
Created: 2026-03-22

## Objective
After Jane finishes reading her response aloud (TTS), automatically start listening for the user's next voice input. If nothing is said within 6 seconds, stop listening. This creates a hands-free conversational flow.

## Design
- After `tts.speak()` completes, if TTS mode is enabled, auto-trigger speech recognition
- Speech recognition runs for up to 6 seconds of silence
- If user speaks, send the transcript as the next message
- If 6 seconds of silence, stop listening and return to idle
- Visual indicator: mic icon pulses while listening, shows "Listening..." status
- User can tap to cancel listening at any time

## Files Involved
- `android/.../voice/AndroidTtsManager.kt` — add completion callback
- `android/.../ui/chat/ChatViewModel.kt` — wire auto-listen after TTS completes
- `android/.../voice/VoiceController.kt` — add timed listen mode with 6s timeout

## Settings
- Add "Auto-listen after response" toggle in Android settings
- Default: ON (enabled by default)
- Saved in ChatPreferences, synced to server via SettingsSync

## Notes
- Only active when TTS is enabled AND auto-listen setting is on
- Should respect the "always listening" toggle if it exists
- The 6-second silence timeout uses Android's `SpeechRecognizer` built-in silence detection
