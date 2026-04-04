# Job: Mic Input Toggle Button

Status: completed
Priority: medium

## Objective
Add a microphone toggle button to the Jane web chat, next to the TTS mute button. Mic should be off by default — user taps to start voice input, taps again to stop. Prevents unwanted speech-to-text popups.

## Requirements
- Mic button next to the TTS mute button in jane.html
- Off by default (no automatic listening)
- Tap to start voice recognition, tap again to stop
- Visual indicator: mic icon when off, red/active mic when listening
- Persist state in localStorage
- Works on both desktop and mobile browsers

## Result
Implemented in jane.html. Mic toggle button next to TTS mute button:
- Off by default (slate icon with strikethrough line)
- Tap to enable: button turns red, starts continuous speech recognition
- Auto-restarts after each result so user can keep talking
- Tap again to disable: stops recognition, reverts to slate
- State persisted in localStorage (`jane_mic_enabled`)
- Auto-resumes on page reload if left on
- Handles permission denial gracefully (disables and saves state)
