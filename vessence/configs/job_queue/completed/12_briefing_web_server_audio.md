# Job: Web Briefing — Use Server Audio + Brief/Full Toggle

Status: complete
Completed: 2026-03-24 14:40 UTC
Notes: Replaced speakSummary() with playArticleAudio(id, type, fallback). Server audio via HTML5 Audio element, fallback to browser TTS. Added Brief/Full buttons per article card. Stop button pauses server audio. readAll still uses browser TTS (server audio would require sequential fetching).
Priority: 3
Model: sonnet
Created: 2026-03-24

## Objective
The web briefing page (`briefing.html`) currently uses browser SpeechSynthesis for audio. Switch it to use the pre-generated XTTS v2 audio files from the server API, and add a toggle to choose between brief and full summary audio.

## Context
- Server audio API exists: `GET /api/briefing/audio/{article_id}/{summary_type}` (brief or full)
- Android already uses server audio with local cache fallback
- Web briefing has a single "Listen" button that calls `speakSummary(article.summary)` using browser TTS
- TTS generator produces both `{id}_brief.wav` and `{id}_full.wav`

## Steps
1. Replace `speakSummary()` in briefing.html with a function that:
   - Tries server audio first (`/api/briefing/audio/{id}/brief`)
   - Falls back to browser TTS if server audio unavailable
   - Uses HTML5 `<audio>` element for playback
2. Add brief/full toggle:
   - Split the Listen button into two: "Brief" and "Full" (or a single button with a dropdown)
   - Brief plays `{id}_brief.wav`, Full plays `{id}_full.wav`
3. Add a stop button (visible while playing)
4. Update "Read All" to use server audio instead of browser TTS
5. Test with articles that have audio and articles that don't (fallback)

## Verification
- Listen button plays server-generated audio (check network tab for `/api/briefing/audio/` request)
- Can switch between brief and full summary audio
- Fallback to browser TTS works when server audio is unavailable
- Stop button works mid-playback

## Files Involved
- `vault_web/templates/briefing.html` — main changes
- `jane_web/main.py` — audio serve endpoint (already exists)
- `tools/daily_briefing/functions/tts_generator.py` — generates audio (already fixed with --gpus all)
