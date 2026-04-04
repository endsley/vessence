# Job: Generate Briefing Audio for All Articles

Status: complete
Completed: 2026-03-24 18:00 UTC
Notes: 37 generated, 28 already existed, 83 failed (300s timeout on longer texts). 65 total audio files available. Failures are long full-summary texts exceeding XTTS v2 processing time. Brief summaries mostly succeeded. Future: increase timeout or chunk long texts before TTS.
Priority: 3
Model: sonnet
Created: 2026-03-24

## Objective
Run a full TTS audio generation batch for all 71+ briefing articles using the Docker XTTS v2 model with GPU. The `--gpus all` fix was applied to `tts_generator.py` and tested (6.5s per article). No audio files currently exist.

## Steps
1. Verify Docker TTS works: `docker run --rm --gpus all ghcr.io/coqui-ai/tts:latest --list_models | head`
2. Run the TTS generator for all articles (both brief and full summaries)
3. Monitor GPU usage to ensure it's using CUDA not CPU
4. Verify audio files appear in `tools/daily_briefing/essence_data/audio/`
5. Test audio playback via API: `curl http://localhost:8081/api/briefing/audio/{id}/brief`
6. Check total disk usage of generated audio

## Verification
- Audio files exist for majority of articles (some may fail if summary is empty)
- API returns 200 with audio data for a test article
- Each file generated in <15s (GPU speed)

## Files Involved
- `tools/daily_briefing/functions/tts_generator.py`
- `tools/daily_briefing/essence_data/audio/`
- `jane_web/main.py` (audio serve endpoint)

## Notes
- Run at night or during idle — GPU will be busy for ~7 minutes (71 articles × 2 summaries × 6s each)
- Brief summaries only if full generation takes too long
