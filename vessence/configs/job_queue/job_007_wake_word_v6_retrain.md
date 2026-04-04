# Job #7: Wake Word v6 — Paired Background Training

Priority: 1
Status: completed
Created: 2026-04-04

## Description
Retrain hey_jane.onnx with paired positive/negative samples sharing identical backgrounds. Forces the model to learn "hey jane" itself, not background characteristics.

## Data Strategy

### Paired samples (NEW):
For each of 188 TTS "hey jane" clips × 3 background types:
- **Positive**: "hey jane" + light background (SNR 15-25dB)
- **Negative**: same background alone (no "hey jane")

Background types:
1. Background noise (from ESC-50 environmental sounds)
2. Background speech (from speech commands + generated conversations)
3. Background music (from vault music collection)

Estimated: 188 × 3 × 2 = 1,128 new paired clips

### Generated conversation negatives (NEW):
- Use gemma4 to generate 100+ realistic conversation transcripts
- Voice with edge-tts across multiple speaker pairs
- Slice into 1-2 second chunks
- 5,000-10,000 conversation chunks as negatives

### Existing data (KEEP ALL):
- 11 real recordings + 40× augmentations each
- 188 edge-tts positives + 8× augmentations each
- All existing negatives (speech commands, ESC-50, TTS hard negatives, jane-context negatives)

### Training changes:
- Epochs: 800 (up from 400), lower learning rate
- Early stopping patience: 120 (up from 80)
- Source-disjoint split (paired samples stay together)

## Target:
- Background speech scores < 0.2 (currently 0.74-0.75)
- Real voice scores > 0.95 (currently 0.9999)
- Wide separation gap = robust threshold selection

## Files:
- Training script: `wake_word/train_oww.py`
- Output: `android/app/src/main/assets/openwakeword/hey_jane.onnx`
- Keep current model as backup: `hey_jane_v5.onnx`
