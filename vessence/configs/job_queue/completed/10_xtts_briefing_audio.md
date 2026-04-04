# Job: XTTS-v2 Audio for Daily Briefing — Server-Generated TTS

Status: complete (Docker-based TTS, waiting for image pull)
Priority: 3
Created: 2026-03-22

## Objective
Use XTTS-v2 on the server to generate high-quality audio files for news article summaries. Serve these to the Android app instead of using the device's built-in TTS. Auto-clean audio files after 2 days.

## Context
- XTTS-v2 is a voice-cloning TTS model from Coqui. Can clone any voice from a short reference sample.
- Currently the Android app uses `AndroidTtsManager` (device built-in TTS) which sounds robotic.
- A starter `tts_generator.py` has been written at `essences/daily_briefing/functions/tts_generator.py` with the core generation logic.

## Pipeline
1. **Cron fetches articles** (every 8h, idle only) — already working
2. **After fetch, generate audio** — call `generate_all_audio_for_articles()` for each article
3. **Serve audio files** — `GET /api/briefing/audio/{article_id}/{type}` returns the .wav file
4. **Android plays server audio** — BriefingViewModel fetches audio URL, plays via MediaPlayer instead of local TTS
5. **Cleanup** — delete audio files older than 2 days (run in the daily reset or as part of janitor_system)

## Implementation Steps

### Step 1: Install XTTS-v2
- **Problem**: Coqui TTS requires Python <3.12 but our venv is Python 3.13
- **Options**:
  a) Create a separate Python 3.11 venv just for TTS: `python3.11 -m venv ~/xtts-venv && ~/xtts-venv/bin/pip install TTS`
  b) Use the `xtts-streaming-server` Docker container (isolates the dependency entirely)
  c) Use a community fork that supports 3.13 (check PyPI for `coqui-tts` or similar)
- First run downloads the model (~1.8GB)
- The `tts_generator.py` should call XTTS via subprocess to the separate venv/container

### Step 2: Wire audio generation into run_briefing.py
After article fetch loop, add:
```python
from tts_generator import generate_all_audio_for_articles, cleanup_old_audio
cleanup_old_audio()  # Clean old files first
generate_all_audio_for_articles()  # Generate for new articles
```

### Step 3: Add API endpoint for serving audio
In `jane_web/main.py` (or better — in the essence itself once Job #09 is done):
```python
@app.get("/api/briefing/audio/{article_id}/{summary_type}")
async def briefing_audio(article_id: str, summary_type: str):
    path = f"essences/daily_briefing/essence_data/audio/{article_id}_{summary_type}.wav"
    if not os.path.exists(path):
        raise HTTPException(404)
    return FileResponse(path, media_type="audio/wav")
```

### Step 4: Update briefing articles API to include audio URLs
Add `audio_url` field to each article card:
```json
{
  "id": "abc123",
  "title": "...",
  "brief_summary": "...",
  "audio_url": "/api/briefing/audio/abc123/brief",
  "audio_full_url": "/api/briefing/audio/abc123/full"
}
```

### Step 5: Update Android BriefingViewModel
- When `audio_url` is present, use `MediaPlayer` to play server audio instead of local TTS
- Show a play/pause button on each article card
- Download audio in background when briefing loads (prefetch)

### Step 6: Optional — Voice cloning
- Place a reference voice sample at `essences/daily_briefing/knowledge/reference_voice.wav`
- XTTS-v2 will clone that voice for all briefing audio
- Could use Chieh's voice or a preferred narrator voice

### Step 7: Cleanup cron
Audio files older than 2 days get deleted by `cleanup_old_audio()` which runs at the start of each briefing fetch.

## Files Involved
- `essences/daily_briefing/functions/tts_generator.py` — already written (starter code)
- `essences/daily_briefing/functions/run_briefing.py` — wire in audio generation
- `jane_web/main.py` — audio serve endpoint
- `android/.../BriefingViewModel.kt` — play server audio
- `android/.../BriefingScreen.kt` — play/pause button per article

## Notes
- XTTS-v2 generation is slow (~5-10s per article on GPU, ~30s on CPU). For 24 articles, budget ~2-4 minutes on GPU.
- Audio files are ~200KB-1MB each (wav). Consider converting to opus/mp3 to save bandwidth.
- The idle gate on the cron job means audio generation won't interfere with active use.
- GPU is preferred — check if CUDA is available on the server.
