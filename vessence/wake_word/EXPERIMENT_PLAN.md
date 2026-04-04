# Wake Word Detection — Experiment Plan

## Method
Kernel mean embedding via DCT + Random Fourier Features + MMD.

## Pipeline
```
Raw PCM → Frame (window + hop) → DCT per frame → Top-k coefficients
→ Concatenate all frames → RFF (RBFSampler) → RKHS embedding
→ Mean embedding μ̂ from all positive samples
→ Detection: ‖μ̂ - φ(x_test)‖² < threshold
```

## Parameters to Optimize

### 1. Frame Size (`frame_ms`)
- Values to sweep: **15, 20, 25, 30, 40 ms**
- Tradeoff: Smaller → more frames → finer time resolution but higher feature dim. Larger → fewer frames → smoother but may miss transients.
- Default: 25ms (standard for speech)

### 2. Frame Hop (`hop_ms`)
- Values to sweep: **5, 8, 10, 15, 20 ms**
- Tradeoff: Smaller → more overlap → more frames per utterance → higher feature dim. Larger → less redundancy.
- Default: 10ms

### 3. Number of DCT Coefficients (`n_dct_coeffs`)
- Values to sweep: **8, 10, 13, 16, 20, 25**
- Tradeoff: Fewer → captures only low-frequency structure (fundamental pitch). More → captures higher harmonics and fricatives ("J" in Jane).
- Default: 13 (MFCC convention)

### 4. Utterance Window Duration (`utterance_duration_s`)
- Values to sweep: **0.6, 0.8, 1.0, 1.2, 1.5 s**
- Tradeoff: Too short → clips the phrase. Too long → includes silence that dilutes the signal.
- Default: 1.0s

### 5. RFF Dimension (`rff_dim`)
- Values to sweep: **256, 512, 1024, 2048, 4096, 8192**
- Tradeoff: More dimensions → better kernel approximation but slower detection. Diminishing returns past a point.
- Default: 2048

### 6. RBF Bandwidth σ (`rff_sigma`)
- Values to sweep: **auto (median heuristic), 0.5×auto, 1×auto, 2×auto, 5×auto**
- Also try fixed: **1.0, 2.0, 5.0, 10.0, 20.0**
- Tradeoff: Small σ → tight kernel, sensitive to exact match. Large σ → smooth kernel, more tolerant but may accept false positives.
- Default: auto (median heuristic on training pairwise distances)

### 7. SNR Range for Augmentation (`snr_low`, `snr_high`)
- Values to sweep: **(0, 10), (3, 15), (5, 20), (10, 30) dB**
- Tradeoff: Lower SNR → model learns to handle noisy conditions but μ̂ may be too diffuse. Higher SNR → cleaner model but fragile in noise.

### 8. Augmentation Factor (`augment_factor`)
- Values to sweep: **10, 25, 50, 100, 200**
- Tradeoff: More augmentation → better μ̂ estimate but longer enrollment time. Diminishing returns expected.

### 9. Detection Stride (`detection_stride_ms`)
- Values to sweep: **80, 160, 250, 500 ms**
- Tradeoff: Lower → faster reaction but more CPU. Higher → lower CPU but may miss short utterances.
- Default: 160ms

### 10. Detection Threshold
- Not swept independently — derived from positive/negative distance distributions at each parameter setting.
- Optimized for best F1, then manually adjusted for desired FPR.

## Experiment Protocol

### Phase 1: Data Collection
1. Record 10 samples of "hey jane" (via `record.py`)
2. Collect negatives:
   - 60s ambient noise from mic
   - 60s of normal speech (not "hey jane")
   - 200+ synthetic negatives
   - Optional: ESC-50 environmental sounds dataset

### Phase 2: Single-Parameter Sweeps
Hold all other parameters at default, sweep one at a time:
```bash
python evaluate.py --sweep-dct 8 10 13 16 20 25
python evaluate.py --sweep-frame 15 20 25 30 40
python evaluate.py --sweep-rff 256 512 1024 2048 4096 8192
python evaluate.py --sweep-sigma 1.0 2.0 5.0 10.0 20.0
```

### Phase 3: Multi-Parameter Grid Search
Take the top-2 values from each sweep and do a combinatorial search on the most impactful parameters (likely: n_dct_coeffs, rff_dim, σ).

### Phase 4: Live Testing
Enroll with best parameters and test real-time detection:
```bash
python enroll.py --augment-factor 50
python detect.py --verbose
```
Test with:
- "Hey Jane" at normal volume
- "Hey Jane" whispered
- "Hey Jane" from across the room
- Similar phrases: "Hey James", "Hey chain", "Hey Jane!" (excited)
- Background music playing
- Multiple people talking

### Phase 5: Port to Android (Kotlin)
Once parameters are locked, rewrite in Kotlin for the Android app.

## Success Criteria
- **Recall ≥ 95%** on positive samples (including augmented noise variants)
- **FPR ≤ 0.1%** on negative samples (1 false positive per ~17 minutes at 160ms stride)
- **Latency < 50ms** per detection check on desktop (< 100ms on Android)
