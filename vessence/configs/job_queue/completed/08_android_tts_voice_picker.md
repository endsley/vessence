# Job: Android TTS Voice Picker — Preview and Switch Voices in Settings

Status: complete
Priority: 3
Created: 2026-03-22

## Objective
Add a TTS voice selection screen in the Android app's Settings where users can preview available voices and pick their preferred one.

## Design

### Settings Screen
- New section: "Voice Settings"
- List all available TTS voices from the device's `TextToSpeech` engine
- Each voice shows: name, language, locale, quality label (if available)
- Tap a voice → plays a short preview sentence ("Hi Chieh, this is how I sound.")
- Radio button or checkmark to select the active voice
- Selected voice saved to SharedPreferences + synced to server via `/api/app/settings`

### Implementation

#### `TtsVoicePicker.kt` (new composable)
- On mount: `tts.voices` returns `Set<Voice>` — list all available
- Filter to English voices (or user's preferred language)
- Sort by quality (prefer `QUALITY_VERY_HIGH` > `QUALITY_HIGH` > others)
- Show as a LazyColumn with voice name, locale, and a "Preview" button
- Selected voice highlighted, persisted to `ChatPreferences`

#### `AndroidTtsManager.kt` (update)
- Add `setVoice(voiceName: String)` method
- On init, load saved voice preference and apply it
- `speak()` uses the selected voice

#### Settings integration
- Add "Voice" row in the existing settings screen
- Shows current voice name
- Taps opens `TtsVoicePicker` (either as a dialog or a new screen)

## Files Involved
- New: `android/.../ui/settings/TtsVoicePicker.kt`
- Update: `android/.../voice/AndroidTtsManager.kt` — voice selection
- Update: `android/.../util/ChatPreferences.kt` — persist voice choice
- Update: settings screen — add Voice row

## Notes
- Available voices depend on the device — Samsung, Pixel, etc. have different TTS engines
- Some devices need Google TTS or Samsung TTS installed for good voices
- Preview should be short (under 5 seconds) so user can quickly compare
- Consider showing a "Download more voices" link to system TTS settings
