# Job #3: Retrain Wake Word Model with Speaker Diversity

Priority: 1
Status: partial (temporal smoothing implemented, Whisper stage-2 deferred)
Created: 2026-04-03

## Description
The current hey_jane.onnx model triggers on background speech from other people because it was only trained on the user's voice + TTS voices with Gaussian noise. It needs negative examples of real human speech and positive examples of the user's voice mixed with background conversation.

### What to add:
1. **Positive: the user's voice + background speech** — mix the 11 real "hey jane" recordings with speech command samples, podcast-style audio, and conversational background at various SNRs (5-20dB)
2. **Negative: Other people speaking naturally** — download LibriSpeech or similar dataset, extract clips of general conversation as negatives
3. **Negative: Other people saying "hey jane"** — the edge-tts voices already cover this, but add more variety
4. **Negative: Background conversation without trigger word** — long-form speech clips (podcasts, TV dialogue)

### Current state:
- Model: hey_jane.onnx (v3, 256-dim, 3 blocks)
- Val F1: 0.90 (source-disjoint)
- Real recording detection: 11/11 at 0.9998
- False positive on speech commands: 0/500
- Problem: triggers on background speakers at score 0.82+
- Threshold raised to 0.7 as temporary mitigation

### Two-Stage Verification Design:
- **Stage 1**: Current hey_jane.onnx (OpenWakeWord DNN, runs continuously, ~80ms per check)
- **Stage 2**: When stage 1 score > threshold, buffer last 1 second of audio, run Whisper-tiny locally
  - If transcript contains "jane" → real trigger → proceed
  - If transcript does NOT contain "jane" → false positive → suppress, resume listening
  - Audio window: 1.0 seconds (captures full "hey jane" at 0.6-0.8s with buffer)
  - Expected latency: ~100-250ms on phone CPU
  - Battery: negligible (only runs on stage 1 candidates, ~1-5 times per hour)

### Also needed:
- Hard negative mining: run current model against podcast/TV audio, collect FP clips, retrain
- Temporal smoothing: require 3+ consecutive frames above threshold (kills random spikes)
- Contrastive/triplet loss for better score separation

### Target:
- Real triggers: total latency < 1.2s from speech to STT popup
- False positives: < 1 per hour during normal conversation
- Real voice detection: 100% at reasonable threshold

### Training script: `wake_word/train_oww.py`
### Assets: `android/app/src/main/assets/openwakeword/hey_jane.onnx`
