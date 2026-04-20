# Wake Word Training — "Hey Jane"

The deployed on-device wake word is an OpenWakeWord-style DNN classifier
trained by [`train_oww.py`](./train_oww.py). This doc describes what that
script actually does so the training method and the running model stay
in sync.

> History note: earlier attempts used a pure kernel method
> (DCT + Random Fourier Features + K-Means UBM). That approach was
> abandoned — the DNN classifier below is what ships.

## Files

| Path | Role |
|---|---|
| `train_oww.py` | Training entry point. Reads positives/negatives, trains, exports ONNX. |
| `samples/hey_jane_*.wav` | Real "Hey Jane" recordings (positives). |
| `negatives/*.wav` | All non-positive audio — speech, music, noise, hard-negative TTS. |
| `downloads/` | Source corpora: LibriSpeech, ESC-50, Speech Commands. Not loaded directly; clips are pre-cut into `negatives/`. |
| `record.py`, `gui_record.py` | Tools to add new positive recordings into `samples/`. |
| `build_speech_negatives.py` | Cuts long speech/music files into 1.5s / 16kHz mono negative clips (silence-filtered). |
| `../android/app/src/main/assets/openwakeword/hey_jane.onnx` | Output: the deployed classifier. Always overwritten in place by `train_oww.py`. |
| `../android/app/src/main/assets/openwakeword/melspectrogram.onnx`<br>`../android/app/src/main/assets/openwakeword/embedding_model.onnx` | Shared upstream preprocessor + embedding models (OpenWakeWord's, not trained here). |
| `../android/app/src/main/assets/openwakeword/hey_jane_vN_backup.onnx` | Prior deployed versions, kept for rollback. |

## Runtime pipeline (on Android)

```
Mic PCM (16 kHz mono)
     │
     ▼
melspectrogram.onnx     ← shared OpenWakeWord model
     │
     ▼
embedding_model.onnx    ← shared OpenWakeWord model
     │
     ▼
(16, 96) feature buffer (16 time windows × 96-dim embeddings)
     │
     ▼
hey_jane.onnx           ← the classifier we train
     │
     ▼
sigmoid score ∈ [0, 1]  → trigger if score > threshold (default 0.6)
```

`OpenWakeWordDetector.kt` on Android runs this chain at ~6 checks/sec.

## Classifier architecture

Defined inline in `train_oww.py` (`WakeWordNet`):

```
Input:  (batch, 16, 96)  — 16 windows × 96-dim OWW embeddings
  ↓
Flatten                  → 1,536 dims
  ↓
Linear(1536 → 256) + ReLU + LayerNorm
  ↓
FCNBlock(256)            (Linear(256→256) + ReLU + LayerNorm) + Dropout(0.15)
  ↓
FCNBlock(256)            + Dropout(0.15)
  ↓
FCNBlock(256)            (no dropout on last)
  ↓
Linear(256 → 1)
  ↓
Sigmoid (applied in the exported ONNX, not in training — trained on logits)
```

Deployed model size: ~2.4 MB (weights + graph, inlined — no external `.data`).

## Training loop

| Hyperparameter | Value |
|---|---|
| Optimizer | Adam, lr=0.0005, weight_decay=1e-4 |
| LR schedule | CosineAnnealingLR, T_max=800 |
| Loss | BCEWithLogitsLoss with `pos_weight = n_neg_train / n_pos_train` (auto class-rebalance) |
| Batch size | 128 |
| Max epochs | 800 |
| Early stopping patience | 120 epochs without val-F1 improvement |
| Device | CPU (model is tiny — GPU not used) |
| Random seed | `np.random.default_rng(42)` |

Best model (by val F1) is kept and exported; training logs metrics at
every 40 epochs and at all thresholds 0.3/0.4/0.5/0.6/0.7 at the end.

## Data pipeline

All positive/negative audio is resampled to **16 kHz mono float32** in
`[-1, 1]`. Clips are padded/cropped to **2.0 s (32 000 samples)** before
feature extraction.

### Positives (`samples/` + synthetic)

1. **Real recordings**: every file in `samples/hey_jane_*.wav`
2. **Synthetic TTS**: `edge-tts` generates `"hey jane"`, `"Hey Jane"`,
   `"hey Jane"`, `"Hey jane"` across **all English voices** concurrently
   (~40 voices × 4 phrases ≈ 150 clips).
3. **Per-source augmentation** (`augment_audio`):
   - Volume ±6 dB (uniform 0.5× – 2.0×)
   - Speed perturbation (uniform 0.88× – 1.12×, via `scipy.signal.resample`)
   - Gaussian noise injection with 50% probability, SNR 8–25 dB
   - Clip to `[-1, 1]`
4. **Augmentation multiplicity**:
   - Real recordings: **×40 augmented copies per source**
   - TTS clips: **×8 augmented copies per source**
5. **NO background-speech mixing.** (Kept out intentionally — earlier
   versions that did this taught the model to fire on background
   speech. See comment in `train_oww.py:287`.)
6. **Temporal jitter during feature extraction**: `n_jitter=3` for
   training positives (three random placements within the 2 s window);
   `n_jitter=1` for validation.

### Negatives (TTS + disk + silence)

1. **Hard TTS confusables** — `edge-tts` × all English voices over
   phrases like:
   - "hey james", "hey chain", "hey rain", "hey jay", "hey jane"-adjacent names
   - `"jane"` without `"hey"`: "call jane", "tell jane", "where is jane", "say hey jane", etc.
   - `"hey"` without `"jane"`: "hey there", "hey buddy", "hey siri", "hey google", "hey alexa"
2. **General TTS phrases** — common voice-assistant commands, longer
   conversational sentences, etc.
3. **Disk negatives** — every `.wav` in `negatives/`. Current pool
   (~30 k files): `bg_noise_*`, `esc50_*`, `speech_cmd_*`,
   `synth_*`, `tts_generated_*`, `speech_*` (LibriSpeech dev-clean),
   `speech2_*` (LibriSpeech test-clean), `speech3_*` (LibriSpeech
   train-clean-100), `music_*` (vault MP3s), `hard_negatives_*`.
4. **Silence** — 50 synthetic low-amplitude Gaussian noise clips.
5. **Augmentation multiplicity**: ×3 for TTS sources, ×1 for disk/silence.
6. **Temporal jitter**: `n_jitter=1` for both train and val.

### Source-disjoint train/val split

**Critical:** splits at the *source* level, not per-clip. 20% of source
IDs go to val; the other 80% to train. This prevents augmented copies
of the same recording appearing on both sides — a subtle leakage bug
fixed in v3.

## Export

```
best model state (by val F1) → wrap in Sigmoid module → torch.onnx.export
→ opset 18, input "x" shape (1, 16, 96), output "sigmoid"
→ force-inline weights (save_as_external_data=False)
  (Android can't load external .onnx.data files from assets)
→ delete any stray .onnx.data sidecar
→ ONNX-vs-PyTorch parity check on 5 random inputs (max_diff printed)
```

Output path is hardcoded at the top of `train_oww.py`:
```
OUTPUT_PATH = ../android/app/src/main/assets/openwakeword/hey_jane.onnx
```

## Verification (run after export, before shipping)

`train_oww.py` ends with a verification block that scores the freshly
exported model against:
- Every `samples/hey_jane_*.wav` — should all score ≥ 0.99
- Every `negatives/speech_cmd_*.wav` — counts & reports false-positives at threshold 0.5
- Pure silence and random noise — should score ~0

If any real recording drops below 0.99 or speech_cmd false-positive rate
spikes, roll back:
```bash
cp ../android/app/src/main/assets/openwakeword/hey_jane_vN_backup.onnx \
   ../android/app/src/main/assets/openwakeword/hey_jane.onnx
```

## How to retrain

The typical flow (matches how the deployed v7 was trained — see
`configs/job_queue/completed/job_009_wake_word_v7_more_data.md`):

```bash
cd /home/chieh/ambient/vessence/wake_word
VENV=/home/chieh/google-adk-env/adk-venv/bin

# 1. Add new positive recordings (optional)
$VENV/python gui_record.py          # or record.py --count N

# 2. Add new negatives (optional) — cut a long corpus into clips
$VENV/python build_speech_negatives.py \
  --source-dir downloads/LibriSpeech/train-clean-100 \
  --prefix speech3 --max-clips 15000

# 3. Back up the currently-deployed model
cp ../android/app/src/main/assets/openwakeword/hey_jane.onnx \
   ../android/app/src/main/assets/openwakeword/hey_jane_vN_backup.onnx

# 4. Train (~1 hour on CPU — feature extraction dominates the first ~30 min)
$VENV/python train_oww.py 2>&1 | tee /tmp/train.log

# 5. Ship the new model via the standard Android release flow
$VENV/python ../startup_code/bump_android_version.py
bash ../startup_code/graceful_restart.sh
```

## Known-good metrics (reference points)

| Version | Real hey_jane scores | FPR@0.6 on speech | Best F1 | Notes |
|---|---|---|---|---|
| v6 | 0.9994 – 0.9999 | 0.78 % | 0.9089 | +10k LibriSpeech dev-clean+test-clean negatives |
| v7 (deployed) | ≥ 0.9988 | 0.56 % | 0.8790 | +15k train-clean-100 + 5k vault music negatives (~30k total) |

F1 went *down* v6 → v7 because precision fell on the music-heavy val
split, but the real-world metric — FPR on actual speech and music —
improved. Keep the F1 numbers in context of what the val mix looks like.

## Known limitations / things worth fixing later

1. **Single-speaker enrollment** — current `samples/` has 11 real
   recordings, all one voice. Multi-speaker improvements should just
   mean adding each person's "hey Jane" clips into `samples/` and
   re-running `train_oww.py`. The trainer does not assume one speaker.
2. **No room-impulse-response augmentation** — all positives are close-mic.
3. **Fixed 2 s clip length** — utterances longer than 2 s are center-cropped.
4. **CPU-only** — trainer doesn't try to use GPU even if available.
   Fine for the current model size; would matter if the network grew.
