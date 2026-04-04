# Job: Android Voice Input With Screen Off

Status: completed
Priority: medium

## Objective
Implement a foreground service in the Android app that keeps the microphone alive when the screen is off, so users can continue talking to Jane without the screen on.

## Requirements
- Start a `ForegroundService` with `FOREGROUND_SERVICE_TYPE_MICROPHONE` when the app opens (auto-start, no manual tap needed)
- Show a persistent notification while the mic service is active (e.g., "Jane is listening")
- Speech recognition continues working with screen off
- TTS responses play through speaker/earpiece with screen off
- Declare `foregroundServiceType="microphone"` in AndroidManifest.xml
- Request `RECORD_AUDIO` and `FOREGROUND_SERVICE_MICROPHONE` permissions
- Cannot start from background (Android 14+ restriction) — service starts when app is foregrounded

## Technical Notes
- Android 14+ requires foreground service type declaration or app crashes with MissingForegroundServiceTypeException
- Microphone is a "while-in-use" permission — foreground service is the only way to keep it alive with screen off
- Use wake lock to keep CPU alive during voice recognition
- Service should gracefully stop when user closes the app or explicitly stops listening

## References
- https://developer.android.com/develop/background-work/services/fgs/service-types
- https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start

## Result
Wait — Chieh, I think this context is a stale task state reminder, not a new request from you. I already implemented the Android voice foreground service earlier in this conversation. The code is written, `flutter pub get` is done.  Are you asking me to do something else with it, or was that just
