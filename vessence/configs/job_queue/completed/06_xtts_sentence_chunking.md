# Job: Add sentence-level chunking to XTTS-v2 TTS endpoint
Status: completed
Priority: 2
Created: 2026-03-27

## Objective
XTTS-v2 degrades on audio segments longer than ~20-30 seconds. Split text into sentence-level chunks, generate audio for each, and concatenate the WAV files so long summaries (especially "Read All Full" in briefing) sound clean.

## Steps
1. In `jane_web/main.py` `/api/tts/generate` endpoint, split input text into sentences (~100-150 chars each)
2. Generate XTTS-v2 audio for each chunk separately
3. Concatenate the WAV files into a single output (use `wave` module or `pydub`)
4. Cache the final concatenated result as before
5. Also update `tools/daily_briefing/functions/tts_generator.py` if it has the same single-pass issue
6. Test with a full-length briefing article summary (~500 chars)

## Files Involved
- `jane_web/main.py` — `/api/tts/generate` endpoint (line ~698)
- `tools/daily_briefing/functions/tts_generator.py` — briefing audio generation

## Part 2: Compress output to Opus/OGG
- After concatenating WAV chunks, convert to Opus: `ffmpeg -i output.wav -c:a libopus -b:a 48k output.ogg`
- Cache and serve the `.ogg` file instead of `.wav` (media type `audio/ogg`)
- ~10x smaller than WAV (1.3 MB → ~80 KB for 30s)
- Update briefing audio generation (`tts_generator.py`) to output `.ogg` as well
- Update Android `BriefingAudioCache` to handle `.ogg` files
- Ensure `ffmpeg` is available in the Docker image (or install it)

## Notes
- Split on sentence boundaries (`. `, `! `, `? `) not arbitrary char limits
- Keep chunks under ~150 chars / ~20 seconds of speech
- If a single sentence exceeds 150 chars, split on comma or clause boundary
- Opus/OGG plays natively on Android MediaPlayer and all modern browsers
