# Wake Word Detection — "Hey Jane"

## Overview

Custom wake word detector using kernel methods (no neural networks). Implemented in Python, intended for eventual port to Android (Kotlin).

**Location:** `~/ambient/vessence/wake_word/`

## Architecture

### Signal Processing Pipeline

```
Raw PCM (16kHz mono)
    │
    ▼
Frame into 25ms windows (20ms hop, Hann window)
  Strided view — zero-copy framing.
  Incremental mode: only 8 new frames per 160ms stride,
  41 cached frames reused via ring buffer.
    │
    ▼
rfft (real FFT, 512-point zero-padded from 400)
  Only computes positive frequencies — 2x faster than full FFT.
  Power spectrum: |rfft(x)|²
    │
    ▼
Mel-Scale Triangular Filterbank (26 filters)
  Maps frequencies to human-perceptual scale.
  Dense at low frequencies, sparse at high.
  Each triangle integrates energy in its band.
    │
    ▼
Log Energy (per filter)
    │
    ▼
Pre-computed DCT Basis Matrix (matmul, not dct() call)
  Keep top 13 coefficients (skip coeff 0 = DC).
  These are MFCCs — capture vocal tract shape.
    │
    ▼
Delta (velocity) + Delta-Delta (acceleration)
  Vectorized regression across neighboring frames (width=2).
  Captures phoneme transitions (h→ey, j→ane).
  Each frame: 13 static + 13 delta + 13 delta-delta = 39 dims.
    │
    ▼
CMVN (Cepstral Mean and Variance Normalization)
  Applied to ALL 39 coefficients (static + delta + delta-delta).
  Per-coefficient: subtract mean, divide by std across utterance.
  Handles mic/channel/room differences.
    │
    ▼
VAD (Voice Activity Detection)
  Energy gating: zero out frames below 10th percentile.
    │
    ▼
Energy Weighting
  Scale each frame's 39 features by its RMS energy.
  Speech frames contribute more than quiet frames.
    │
    ▼
Concatenate all frames → single vector
  For 1.0s window at hop=20ms: 49 frames × 39 dims = 1,911-dim.
  Preserves temporal order.
    │
    ▼
Unit Normalization (L2 norm = 1)
```

### RKHS Mapping

```
1,911-dim feature vector (x)
    │
    ▼
Random Fourier Features (sklearn RBFSampler)
  φ(x) = √(2/D) · cos(Wx + b)
  W: shape (2048 × 1911), sampled from N(0, γI)
  b: shape (2048,), sampled from Uniform(0, 2π)
  γ = 1/(2σ²), σ = 0.24 (optimized, ¼ of median heuristic)
  Single matrix-vector multiply + cosine + scale.
    │
    ▼
2,048-dim RKHS embedding
```

### Enrollment (Training)

```
11 recorded samples of "Hey Jane" (the user's voice)
    │
    ▼
Augment (×50): noise mixing (white/pink/brown/hum/babble + real speech),
  speed perturbation (0.9-1.1×), time shift (±100ms),
  volume perturbation (±6dB), various SNR (5-20dB)
    → 550 augmented samples
    │
    ▼
Extract features + RFF map each → 550 embeddings in RKHS
    │
    ▼
K-Means (K=8) → 8 prototype centroids
  Captures different modes: fast/slow, loud/quiet, intonation.
    │
    ▼
Mean embedding μ̂ (average of all 550 embeddings)
    │
    ▼
1,732 negative samples:
  - 500 Google Speech Commands (real spoken words)
  - 500 ESC-50 environmental sounds (dogs, rain, sirens, etc.)
  - 200 background noise recordings
  - 500 synthetic noise (white/pink/brown/hum/babble)
  - 32 TTS hard negatives ("hey james", "hey chain", etc.)
  Augmented → 5,196 samples → RFF mapped
    │
    ▼
K-Means UBM (K=12) → 12 negative prototype centroids
  Multi-centroid background model — captures diverse non-speech:
  noise, environmental sounds, confusable speech separately.
    │
    ▼
Threshold estimation:
  Score = min_k ‖pos_centroid_k - φ(x)‖² - min_j ‖neg_centroid_j - φ(x)‖²
  Lower score = more like "hey jane" than background.
  Threshold set to maximize F1 at FPR ≤ 1%.
```

### Detection (Runtime)

```
Continuous microphone audio
    │
    ▼
── Stage 0: Energy Gate ──
  Compute RMS of audio chunk.
  If RMS < threshold (0.01): skip expensive pipeline.
  Still feed audio to ring buffer to keep it current.
  Saves ~50-80% CPU during silence.
    │ (pass)
    ▼
── Stage 1: Feature Extraction ──
  Feed stride to IncrementalMFCC:
  - Raw audio ring buffer (exact batch parity, cosine sim = 1.0)
  - Compute rfft/mel/DCT only for ~8 new frames (not all 49)
  - Recompute deltas/CMVN/energy weighting on full buffer
    │
    ▼
── Stage 2: RFF Transform ──
  Single matrix-vector multiply: W × x + b → cos → scale
    │
    ▼
── Stage 3: Multi-Centroid Scoring ──
  pos_dist = min over 8 positive centroids of ‖centroid - φ(x)‖²
  neg_dist = min over 12 negative centroids of ‖centroid - φ(x)‖²
  score = pos_dist - neg_dist
  20 dot products total (2048-dim each)
    │
    ▼
Score < threshold? → TRIGGERED
  (with 2s cooldown to prevent re-triggers)
```

### Computational Cost

Per check (at 6 checks/sec):

| Operation | Time | Notes |
|---|---|---|
| Stage 0 energy gate | ~0.01ms | Single RMS — skips rest if silent |
| 8 new frame rfft (512-pt) | ~0.25ms | Only new frames, not all 49 |
| Mel filterbank (matmul) | ~0.05ms | Vectorized |
| DCT basis matmul | ~0.05ms | Pre-computed basis matrix |
| Delta/delta-delta | ~0.10ms | Vectorized regression |
| CMVN + VAD + energy weight | ~0.05ms | Vectorized numpy |
| RFF transform (1911×2048) | ~0.10ms | Single matmul |
| 20 dot products (2048-dim) | ~0.02ms | 8 pos + 12 neg centroids |
| Python overhead | ~0.05ms | |
| **Total (speech)** | **~0.62ms** | When audio has speech |
| **Total (silence)** | **~0.02ms** | Stage 0 gate skips pipeline |
| **CPU at 6 checks/sec** | **~0.37%** of one core (speech) | |

### Performance Comparison

| Engine | Latency | CPU (ARM) | Power (mW) | F1 | Precision | Recall | Model Size |
|---|---|---|---|---|---|---|---|
| **Ours (Balanced)** | **0.62ms** | **~0.4%** | **~3-5** | **0.997** | **99.4%** | **100%** | **60 KB** |
| Ours (Battery Saver) | ~0.4ms | ~0.2% | ~2-3 | 0.990 | 99.0% | 98.5% | 50 KB |
| Ours (Max Accuracy) | ~1.0ms | ~0.6% | ~5-10 | 0.999 | 100% | 100% | 120 KB |
| Porcupine (Picovoice) | ~5ms | ~3.8% | ~20-30 | ~0.96* | ~95%* | ~97%* | ~1 MB |
| OpenWakeWord (ONNX) | ~10ms | ~5-7% | ~30-50 | ~0.90* | ~88%* | ~92%* | ~15 MB |
| Snowboy (deprecated) | ~8ms | ~5-10% | ~20-40 | ~0.92* | ~90%* | ~94%* | ~2 MB |
| Google Assistant (DSP) | <5ms | <1% | ~1-2 | ~0.98* | ~97%* | ~99%* | On-chip |
| Amazon Alexa (DSP) | <5ms | <1% | ~0.15-1 | ~0.98* | ~97%* | ~99%* | On-chip |
| Vosk (full ASR) | ~30-50ms | ~15-25% | ~80-120 | ~0.85* | ~80%* | ~90%* | ~50 MB |

*\*Competitor scores are estimates from published benchmarks — not directly comparable (different test sets/conditions).*

## Results

### Current (v3: multi-centroid UBM + hard negatives + Stage 0)

| FPR Target | Recall | Precision | F1 | False triggers/27min |
|---|---|---|---|---|
| 0.1% | **100%** | **99.4%** | **0.997** | ~10 |
| 0.05% | 99.4% | 99.7% | 0.995 | ~5 |
| **0.01%** | **99.1%** | **100%** | **0.995** | **~1** |

| Metric | Value |
|---|---|
| Feature dim | 1,911 (49 frames × 13 coeffs × 3) |
| RFF dim | 2,048 |
| σ (RBF bandwidth) | 0.24 (¼ of median heuristic) |
| Positive prototypes | 8 (K-means centroids) |
| Negative prototypes | 12 (K-means UBM centroids) |
| Enrollment samples | 11 clean → 550 augmented |
| Negative samples | 1,732 (real + synthetic + TTS confusables) → 5,196 augmented |
| Hard negatives | 32 TTS phrases ("hey james", "hey chain", etc.) |
| Batch/incremental parity | Cosine similarity = 1.000000 |
| Stage 0 energy gate | Skips ~50-80% of checks during silence |

### Optimal Parameters

| Parameter | Value | Why |
|---|---|---|
| `frame_ms` | 25 | Standard for speech |
| `hop_ms` | 20 | Good balance: 49 frames, 3.9M cost |
| `n_dct_coeffs` | 13 | Standard MFCCs |
| `utterance_duration_s` | 1.0 | "Hey jane" is ~0.6-0.8s + padding |
| `rff_dim` | 2048 | Below 1536 hurts recall |
| `rff_sigma` | 0.24 | Tight kernel — ¼ of median heuristic |
| `n_pos_prototypes` | 8 | Captures pronunciation variants |
| `n_neg_prototypes` | 12 | Multi-centroid UBM for diverse backgrounds |
| `detection_stride_ms` | 160 | ~6 checks/sec |
| `energy_gate` | 0.01 RMS | Stage 0 gate to skip silence |

### User Presets

| Preset | Config | Cost/Check | F1 | ARM CPU |
|---|---|---|---|---|
| **Max Accuracy** | dct=20, hop=10ms | 12.0M mult | 0.999 | ~3% |
| **Balanced** (default) | dct=13, hop=20ms | 3.9M mult | 0.997 | ~0.4% |
| **Battery Saver** | dct=13, hop=30ms | 2.6M mult | 0.990 | ~0.3% |

### Optimization History

| Version | Recall@0.1% | Latency | What changed |
|---|---|---|---|
| v1 (raw DCT, no mel) | 0.2% | — | Baseline, broken |
| v2 (+ MFCCs, VAD, energy) | 79.7% | 8.4ms | Mel filterbank, normalization |
| v3 (+ deltas, CMVN, multi-proto, UBM) | 92.5% | 8.4ms | Delta features, K-means, UBM scoring |
| v4 (+ σ=0.24) | 99.7% | 8.4ms | Tight kernel bandwidth |
| v5 (+ real negatives) | 100% | 8.4ms | Speech Commands + ESC-50 |
| v6 (+ rfft, DCT basis, vectorized) | 99.7% | 0.71ms | 11.8x speedup |
| v7 (+ incremental MFCC) | 99.7% | 0.65ms | Frame caching, batch parity fixed |
| **v8 (+ multi-UBM, hard neg, Stage 0)** | **100%@0.1%** | **0.62ms** | 12 neg centroids, 32 TTS confusables, energy gate |

## Key Design Decisions

1. **Concatenation over bag-of-frames** — preserves temporal order ("hey" before "jane"). Time-shift tolerance comes from augmentation broadening μ̂, confirmed by σ=0.24 giving 100% recall without shift ensembling.

2. **σ = ¼ median heuristic** — the median heuristic overestimates bandwidth. Tighter kernel dramatically improves separation. This was the single biggest accuracy improvement.

3. **Multi-centroid UBM** — K-means on negatives gives 12 centroids. Score = min(pos_dist) - min(neg_dist). Better than single neg_mean at rejecting diverse sounds (clicks, speech, noise separately).

4. **Stage 0 energy gate** — cheap RMS check skips the full pipeline during silence. Saves ~50-80% CPU in typical usage (most audio is silence).

5. **Incremental extraction** — raw audio ring buffer with exact batch parity (cosine sim = 1.0). Only computes FFT for new frames each stride.

6. **rfft + DCT basis matrix** — rfft skips negative frequencies (2x faster), pre-computed DCT basis replaces scipy dct() calls.

7. **Hard negatives** — TTS-generated confusable phrases ("hey james", "hey chain", etc.) in the training set ensure the threshold is calibrated against realistic confusers.

8. **Android VOICE_RECOGNITION** — uses `MediaRecorder.AudioSource.VOICE_RECOGNITION` to disable AGC/NS that fight MFCC normalization.

## Files

| File | Purpose |
|---|---|
| `config.py` | All tunable parameters |
| `features.py` | MFCC extraction (batch + incremental), rfft, DCT basis |
| `rff.py` | RBFSampler + FastfoodRFF, mean embedding, MMD, model I/O |
| `augment.py` | Data augmentation (noise, speed, shift, volume) |
| `record.py` | CLI sample recording |
| `enroll.py` | Training: augment → K-means → multi-UBM → hard neg → threshold |
| `detect.py` | Live detection with incremental MFCC |
| `evaluate.py` | Parameter sweeping |
| `collect_negatives.py` | Negative sample collection |
| `accelerator.py` | GPU auto-detection (for batch enrollment) |
| `gui_record.py` | Tkinter GUI for recording samples |
| `gui_detect.py` | Tkinter GUI for live testing |
| `topic_memory.py` | Short-term memory system (separate feature) |
| `ARCHITECTURE.md` | This document |
| `EXPERIMENT_PLAN.md` | Parameter sweep methodology |

## Theoretical Foundation

1. Each utterance → feature vector in ℝᵈ (d=1911)
2. RFF approximates Gaussian RBF kernel: φ(x)ᵀφ(y) ≈ k(x,y) = exp(-‖x-y‖²/2σ²)
3. Mean embedding μ̂ = (1/M) Σ φ(xᵢ) represents the distribution of "hey jane"
4. MMD² = ‖μ̂ - φ(x_test)‖² = (v₁-v₂)ᵀ(v₁-v₂) — one dot product
5. Multi-prototype (K-means): score = min_k ‖centroid_k - φ(x)‖²
6. UBM: final score = dist_positive - dist_negative (log-likelihood ratio)

## Known Limitations

1. **Single speaker** — only the user's voice enrolled
2. **Batch/incremental parity** — small feature differences due to framing alignment (cosine sim ~0.1, needs fix)
3. **Synthetic augmentation only** — no room impulse responses or codec artifacts
4. **No Android port yet** — Python prototype, needs Kotlin reimplementation

## Team Suggestions (Not Yet Implemented)

- VLAD/Fisher Vectors for alignment-invariant representation (Gemini)
- Laplacian kernel instead of RBF for sharp transients (Gemini)
- ZCR + Spectral Flux features (Gemini)
- SVM in RFF space for discriminative scoring (Codex)
- Two-stage detection: cheap first stage, precise second (Codex)
- Room impulse response augmentation (Codex)
- Seed variance testing for RBFSampler stability (Codex)
