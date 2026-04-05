# Job #9: Wake Word v7 — More Speech + Music Negatives

Priority: 1
Status: pending
Created: 2026-04-04

## Description
v6 drastically reduced false positives (user-confirmed). v7 scales up negatives further, especially in regimes v6 doesn't cover: larger speech corpus + music.

## Data Strategy

### Current (v6) negatives: ~11,700
- 5,000 LibriSpeech dev-clean clips
- 5,000 LibriSpeech test-clean clips
- 1,702 original (speech_commands, ESC-50, TTS hard negatives, bg_noise, synth)

### v7 additions:

**More speech (~15-20K new clips):**
- LibriSpeech `train-clean-100` (6.3GB, ~28K utterances)
- Cut to 15-20K clips using `build_speech_negatives.py --prefix speech3`

**Music negatives (~3-5K new clips):**
- User's vault `$VAULT_HOME/Music/**/*.mp3` (~229 tracks)
- Cut each track into 1.5s slices with `build_speech_negatives.py --prefix music`
- Most important — matches the actual listening environment

**Optional (if vault music is too limited):**
- MUSAN music subset (~42 hours) as additional music diversity
- URL: https://www.openslr.org/17/ (~11GB)

### Target: ~30,000 total negatives (2.5x v6)

## Training changes:
- Keep 800 epochs, lr=0.0005, patience=120 (v6 settings worked)
- Source-disjoint split (music tracks stay together in train OR val)
- Consider slightly lowering positive class weight if precision drops

## Target metrics:
- Real "hey jane": stay at 0.9999+
- Background speech: < 0.1 (v6: already near 0)
- Background music: < 0.2 (v6 not tested)
- FPR at thr=0.6: < 0.5% on held-out set

## Files to modify:
- `wake_word/build_speech_negatives.py` — already supports any FLAC/WAV/MP3 dir
- `wake_word/train_oww.py` — no changes needed, just more data in negatives/
- Output: `android/app/src/main/assets/openwakeword/hey_jane.onnx`
- Preserve v6 as `hey_jane_v6_backup.onnx`

## Execution steps:
1. Download LibriSpeech train-clean-100 to `wake_word/downloads/`
2. Run `build_speech_negatives.py --source-dir downloads/LibriSpeech/train-clean-100 --prefix speech3 --max-clips 15000`
3. Run `build_speech_negatives.py --source-dir $VAULT_HOME/Music --prefix music --max-clips 5000`
4. Backup current model: `cp hey_jane.onnx hey_jane_v6_backup.onnx`
5. Retrain: `python train_oww.py`
6. Rebuild and deploy APK
