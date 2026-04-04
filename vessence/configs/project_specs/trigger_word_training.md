# Trigger Word Training Interface — Design Spec
**Parent Project:** #8 Always-Listening Voice Mode
**Status:** Future Feature (spec only — not yet implemented)
**Created:** 2026-03-21
**Dependencies:** Phase 5 wake word detection must be working first

---

## Problem

Picovoice Porcupine offers pre-trained keywords and a web console for custom models, but:
1. Users must leave the app to train custom wake words via Picovoice's web tool.
2. No way to evaluate detection quality with the user's actual voice/mic/environment.
3. Per-essence wake words (e.g., "Hey Amber" for one essence, "Hey Chef" for another) need a unified workflow.
4. OpenWakeWord (our vendor-free fallback) requires local audio samples for training — there's no web console at all.

## Goal

An in-app interface that lets users:
- Record voice samples of their chosen trigger phrase
- Train or submit a custom wake word model
- Test detection accuracy in their real environment
- Assign wake words per-essence

---

## Architecture

### Two Backend Paths

| Backend | When to use | Training method |
|---------|-------------|-----------------|
| **Picovoice Porcupine** | Default (free tier, high accuracy) | Upload samples via Picovoice Console API → receive `.ppn` model file |
| **OpenWakeWord** | Offline/self-hosted, no vendor dependency | Train locally using `openwakeword.train()` with recorded + synthetic samples |

The training UI is the same for both — the backend is selected in settings.

### Component Overview

```
┌─────────────────────────────────────────────┐
│  Flutter App / Web UI                        │
│  ┌─────────────────────────────────────┐     │
│  │  Trigger Word Training Screen       │     │
│  │  - Phrase input                     │     │
│  │  - Record button (5-10 samples)     │     │
│  │  - Progress indicator               │     │
│  │  - Test mode (live mic)             │     │
│  │  - Assign to essence               │     │
│  └──────────────┬──────────────────────┘     │
└─────────────────┼───────────────────────────┘
                  │ HTTP POST /api/wake-word/*
                  ▼
┌─────────────────────────────────────────────┐
│  Vessence Server (FastAPI)                   │
│  /api/wake-word/upload-samples              │
│  /api/wake-word/train                       │
│  /api/wake-word/test                        │
│  /api/wake-word/list                        │
│  /api/wake-word/assign                      │
└──────────────┬──────────────────────────────┘
               │
     ┌─────────┴─────────┐
     ▼                   ▼
 Picovoice API     OpenWakeWord
 (remote train)    (local train)
     │                   │
     ▼                   ▼
  .ppn model file    .onnx model file
  saved to:          saved to:
  vessence-data/     vessence-data/
  wake_words/        wake_words/
```

---

## Server API Endpoints

### `POST /api/wake-word/upload-samples`
Upload recorded audio samples for a wake phrase.
```json
{
  "phrase": "Hey Amber",
  "samples": ["<base64 wav>", ...],  // 5-10 samples, 16kHz mono PCM
  "sample_rate": 16000
}
```
Response: `{ "phrase_id": "hey-amber-abc123", "sample_count": 8, "status": "ready_to_train" }`

Samples saved to: `vessence-data/wake_words/hey-amber-abc123/samples/`

### `POST /api/wake-word/train`
Kick off model training.
```json
{
  "phrase_id": "hey-amber-abc123",
  "backend": "porcupine"  // or "openwakeword"
}
```
Response (immediate): `{ "status": "training", "estimated_seconds": 60 }`
Response (poll `/api/wake-word/status/{phrase_id}`): `{ "status": "ready", "model_path": "wake_words/hey-amber-abc123/model.ppn" }`

**Porcupine path:** Calls Picovoice Console API to create custom keyword → downloads `.ppn`.
**OpenWakeWord path:** Generates synthetic negative samples, trains locally using `openwakeword` Python package → produces `.onnx`.

### `POST /api/wake-word/test`
Stream mic audio and return detection events in real time.
```json
{ "phrase_id": "hey-amber-abc123" }
```
Opens a WebSocket at `/ws/wake-word/test/{phrase_id}`.
Server loads the trained model, streams mic frames, sends `{ "detected": true, "confidence": 0.97 }` events.

### `GET /api/wake-word/list`
```json
{
  "wake_words": [
    {
      "phrase_id": "hey-amber-abc123",
      "phrase": "Hey Amber",
      "backend": "porcupine",
      "status": "ready",
      "assigned_to": ["amber-default"],
      "created": "2026-03-21T10:00:00Z"
    }
  ]
}
```

### `POST /api/wake-word/assign`
```json
{
  "phrase_id": "hey-amber-abc123",
  "essence_id": "amber-default"
}
```

---

## Training UI Flow

### Step 1: Choose Phrase
- Text input with suggestion chips: "Hey Amber", "Amber", or custom
- Validation: 2-5 syllables recommended, warn if too short (high false positives)

### Step 2: Record Samples
- Minimum 5 samples, recommended 8-10
- Each sample: user taps record, says the phrase, tap stops (or auto-stop on 2s silence via VAD)
- Visual waveform feedback during recording
- Playback button per sample to review
- Delete and re-record individual samples
- Guidance text: "Vary your tone and distance from the mic slightly between recordings"

### Step 3: Train
- Submit button → progress bar
- Porcupine: ~30-60s (API call)
- OpenWakeWord: ~2-5 min (local GPU/CPU training)
- Show estimated time, allow background training

### Step 4: Test
- Live mic test mode: say the trigger phrase and see real-time detection feedback
- Green flash + confidence score on each detection
- "Say something else" prompt to verify no false positives
- Metrics displayed: detections / attempts, false positives in 30s of ambient noise
- Accept or retrain buttons

### Step 5: Assign
- Pick which essence(s) this wake word activates
- Default: the currently active essence
- Option to set as global wake word (activates the last-used essence)

---

## Data Storage

```
vessence-data/wake_words/
├── hey-amber-abc123/
│   ├── metadata.json        # phrase, backend, timestamps, assigned essences
│   ├── model.ppn             # or model.onnx for OpenWakeWord
│   └── samples/
│       ├── sample_001.wav
│       ├── sample_002.wav
│       └── ...
└── hey-chef-def456/
    └── ...
```

---

## Essence Integration

In `manifest.json`, an essence can declare a preferred wake word:
```json
{
  "wake_word": {
    "phrase": "Hey Chef",
    "required": false
  }
}
```

When an essence is installed and declares a wake word that hasn't been trained yet, the app prompts: "This essence uses the wake word 'Hey Chef'. Would you like to set it up now?"

The wake word listener can hold multiple models simultaneously (Porcupine supports this natively; OpenWakeWord supports up to ~15 concurrent models on a single core). Each detection routes to the correct essence.

---

## Privacy & Security

- All audio samples stay local (never uploaded to Vessence cloud)
- Porcupine Console API is the only external call (sends audio to Picovoice for model training) — user must consent
- OpenWakeWord path is fully offline
- Wake word detection runs 100% on-device (both backends)
- Visual indicator (pulsing icon) whenever mic is active
- System tray / notification bar shows "Listening for wake word" when standby mode is on
- Kill switch: physical mic mute respected, software toggle in app settings

---

## Implementation Order

1. **Server endpoints** — sample upload, storage, list/assign (no training yet)
2. **Flutter recording UI** — record, playback, delete samples
3. **Porcupine training integration** — Console API → .ppn download
4. **Live test mode** — WebSocket mic stream + detection feedback
5. **OpenWakeWord training** — local training pipeline as alternative
6. **Multi-model routing** — multiple wake words → correct essence
7. **Essence manifest integration** — auto-prompt on install

---

## Open Questions (to resolve before implementation)

1. **Picovoice free tier limits:** Free tier allows 3 custom keywords. Enough for MVP, but may need paid plan for power users with many essences.
2. **Retraining:** If a user's voice changes (cold, new mic), should the UI offer a "retrain" flow that merges new samples with old, or starts fresh?
3. **Shared wake words:** If two users on the same Vessence instance want the same phrase, train separate models per user or one shared model?
