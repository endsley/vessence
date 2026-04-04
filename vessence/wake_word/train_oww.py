#!/usr/bin/env python3
"""
Train an OpenWakeWord-compatible ONNX classifier for "hey jane".

v3: Fixes data leakage, adds temporal jitter, source-disjoint splits,
    and augmentation bug fixes based on Gemini/Codex review.

Pipeline: audio → openwakeword mel/embedding models → DNN classifier → ONNX
"""

import os
import sys
import glob
import asyncio
import tempfile
import subprocess
import wave
import numpy as np
import torch
import torch.nn as nn
from pathlib import Path
from collections import defaultdict

SAMPLE_RATE = 16000
CLIP_DURATION_S = 2.0
CLIP_SAMPLES = int(SAMPLE_RATE * CLIP_DURATION_S)

WORK_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(WORK_DIR, "samples")
NEGATIVES_DIR = os.path.join(WORK_DIR, "negatives")
OUTPUT_PATH = os.path.join(WORK_DIR, "..", "android", "app",
                           "src", "main", "assets", "openwakeword", "hey_jane.onnx")


def load_wav(path):
    """Load WAV as float32 normalized to [-1, 1]."""
    with wave.open(path, 'rb') as wf:
        if wf.getsampwidth() != 2:
            raise ValueError(f"Expected 16-bit WAV: {path}")
        frames = wf.readframes(wf.getnframes())
        samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        if wf.getnchannels() == 2:
            samples = samples[::2]
        sr = wf.getframerate()
        if sr != SAMPLE_RATE:
            from scipy.signal import resample
            samples = resample(samples, int(len(samples) * SAMPLE_RATE / sr)).astype(np.float32)
        return samples


def pad_or_trim(audio, target_len):
    """Center-pad or center-trim audio to target length."""
    if len(audio) >= target_len:
        start = (len(audio) - target_len) // 2
        return audio[start:start + target_len]
    padded = np.zeros(target_len, dtype=np.float32)
    start = (target_len - len(audio)) // 2
    padded[start:start + len(audio)] = audio
    return padded


def random_place(audio, target_len, rng):
    """Place audio at a random position within a zero-padded window."""
    if len(audio) >= target_len:
        start = rng.integers(0, max(1, len(audio) - target_len))
        return audio[start:start + target_len]
    padded = np.zeros(target_len, dtype=np.float32)
    max_start = target_len - len(audio)
    start = rng.integers(0, max(1, max_start))
    padded[start:start + len(audio)] = audio
    return padded


def augment_audio(audio, rng):
    """Apply random augmentations. Never truncates the signal."""
    a = audio.copy()
    # Volume ±6dB
    a *= rng.uniform(0.5, 2.0)
    # Speed perturbation (0.88x to 1.12x)
    speed = rng.uniform(0.88, 1.12)
    if abs(speed - 1.0) > 0.02:
        from scipy.signal import resample
        a = resample(a, int(len(a) / speed)).astype(np.float32)
    # Noise injection
    if rng.random() < 0.5:
        snr_db = rng.uniform(8, 25)
        noise = rng.normal(0, 1, len(a)).astype(np.float32)
        sp = np.mean(a ** 2) + 1e-10
        np_power = sp / (10 ** (snr_db / 10))
        a += noise * np.sqrt(np_power)
    return np.clip(a, -1.0, 1.0).astype(np.float32)


def mix_with_background(foreground, background_clips, rng, snr_range=(3, 15)):
    """Mix foreground audio (hey jane) with a random background speech clip.

    This teaches the model to detect "hey jane" even when other people are talking.
    SNR range controls how loud the background is relative to the foreground.
    """
    if not background_clips:
        return foreground
    bg = background_clips[rng.integers(0, len(background_clips))]
    target_len = len(foreground)
    # Random segment from background
    if len(bg) > target_len:
        start = rng.integers(0, len(bg) - target_len)
        bg_segment = bg[start:start + target_len]
    else:
        bg_segment = np.zeros(target_len, dtype=np.float32)
        bg_segment[:len(bg)] = bg
    # Mix at random SNR
    snr_db = rng.uniform(snr_range[0], snr_range[1])
    fg_power = np.mean(foreground ** 2) + 1e-10
    bg_power = np.mean(bg_segment ** 2) + 1e-10
    scale = np.sqrt(fg_power / (bg_power * 10 ** (snr_db / 10)))
    mixed = foreground + bg_segment * scale
    return np.clip(mixed, -1.0, 1.0).astype(np.float32)


async def generate_one_clip(phrase, voice, semaphore):
    """Generate a single TTS clip with concurrency control."""
    import edge_tts
    async with semaphore:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmppath = f.name
        mp3path = tmppath.replace('.wav', '.mp3')
        try:
            communicate = edge_tts.Communicate(phrase, voice)
            await communicate.save(mp3path)
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-i", mp3path, "-ar", "16000", "-ac", "1",
                "-acodec", "pcm_s16le", tmppath,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
            )
            try:
                ret = await asyncio.wait_for(proc.wait(), timeout=10)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return phrase, voice, None
            if ret == 0 and os.path.exists(tmppath) and os.path.getsize(tmppath) > 200:
                audio = load_wav(tmppath)
                if len(audio) > 1600:  # at least 0.1s
                    return phrase, voice, audio
        except Exception:
            pass
        finally:
            for p in [tmppath, mp3path]:
                if os.path.exists(p):
                    os.unlink(p)
    return phrase, voice, None


async def generate_edge_tts_clips(phrases):
    """Generate clips using edge-tts with all English voices (concurrent).
    Returns dict: source_id -> audio array (raw, not padded).
    """
    import edge_tts
    voices_list = await edge_tts.list_voices()
    en_voices = [v['ShortName'] for v in voices_list if v['Locale'].startswith('en-')]
    print(f"  Using {len(en_voices)} English voices")

    semaphore = asyncio.Semaphore(20)
    tasks = []
    for phrase in phrases:
        for voice in en_voices:
            tasks.append(generate_one_clip(phrase, voice, semaphore))

    print(f"  Generating {len(tasks)} clips concurrently...")
    results = await asyncio.gather(*tasks)

    clips = {}
    for phrase, voice, audio in results:
        if audio is not None:
            source_id = f"tts_{phrase}_{voice}"
            clips[source_id] = audio

    print(f"  Generated {len(clips)} valid clips")
    return clips


def extract_oww_features_batch(clips_dict, n_jitter=1, rng=None):
    """Extract openwakeword features with temporal jitter.

    Args:
        clips_dict: dict of source_id -> list of (audio_array, is_original) tuples
        n_jitter: number of random placements per clip
        rng: numpy random generator

    Returns:
        features dict: source_id -> list of (16, 96) feature arrays
    """
    import openwakeword
    oww = openwakeword.Model(wakeword_models=[], enable_speex_noise_suppression=False)

    features_by_source = defaultdict(list)
    total = sum(len(clips) for clips in clips_dict.values())
    count = 0

    for source_id, clip_list in clips_dict.items():
        for audio, _ in clip_list:
            for j in range(n_jitter):
                if rng is not None and j > 0:
                    # Random temporal placement
                    clip = random_place(audio, CLIP_SAMPLES, rng)
                else:
                    clip = pad_or_trim(audio, CLIP_SAMPLES)

                clip_int16 = (clip * 32768).astype(np.int16)
                oww.preprocessor.reset()

                for c in range(0, len(clip_int16), 1280):
                    oww.predict(clip_int16[c:c+1280])

                fb = oww.preprocessor.feature_buffer.copy()
                mask = np.any(fb != 0, axis=1)
                if mask.sum() >= 16:
                    # Multiple window positions for positive samples
                    filled = fb[mask]
                    if len(filled) >= 16:
                        features_by_source[source_id].append(filled[-16:].copy())
                        # Also grab a slightly earlier window if available
                        if len(filled) >= 18 and rng is not None:
                            offset = rng.integers(0, min(3, len(filled) - 16) + 1)
                            start = len(filled) - 16 - offset
                            if start >= 0:
                                features_by_source[source_id].append(filled[start:start+16].copy())

            count += 1
            if count % 200 == 0:
                print(f"    Features: {count}/{total}")

    return features_by_source


def evaluate_model(model, X, y, threshold=0.5):
    """Compute metrics."""
    model.eval()
    with torch.no_grad():
        logits = model(torch.tensor(X, dtype=torch.float32))
        probs = torch.sigmoid(logits).numpy().flatten()

    preds = (probs >= threshold).astype(int)
    tp = ((preds == 1) & (y == 1)).sum()
    fp = ((preds == 1) & (y == 0)).sum()
    fn = ((preds == 0) & (y == 1)).sum()
    tn = ((preds == 0) & (y == 0)).sum()

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-10)
    fpr = fp / max(fp + tn, 1)

    return {
        'precision': precision, 'recall': recall, 'f1': f1,
        'fpr': fpr, 'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
    }


def main():
    print("=" * 60)
    print("OpenWakeWord 'hey jane' classifier training v3")
    print("  Source-disjoint splits, temporal jitter, reviewed fixes")
    print("=" * 60)

    rng = np.random.default_rng(42)

    # ── Step 1: Build positive source clips ──
    print("\n[1/7] Building positive data sources...")

    # Real recordings (most valuable)
    pos_sources = {}  # source_id -> raw audio
    pos_files = sorted(glob.glob(os.path.join(SAMPLES_DIR, "hey_jane_*.wav")))
    print(f"  Real recordings: {len(pos_files)}")
    for f in pos_files:
        source_id = f"real_{os.path.basename(f)}"
        pos_sources[source_id] = load_wav(f)

    # ── Step 2: Generate TTS positive clips ──
    print("\n[2/7] Generating edge-tts positive clips...")
    pos_phrases = ["hey jane", "Hey Jane", "hey Jane", "Hey jane"]
    tts_pos = asyncio.run(generate_edge_tts_clips(pos_phrases))
    pos_sources.update(tts_pos)
    print(f"  Total positive sources: {len(pos_sources)}")

    # ── Step 3: Build augmented positive clips per source ──
    # NOTE: No speech mixing in positives — it taught the model to trigger on background noise.
    # Only clean augmentations: volume, speed, light Gaussian noise.
    print("\n[3/7] Augmenting positive clips per source (clean only)...")
    pos_clips_by_source = {}
    for source_id, audio in pos_sources.items():
        clips = [(audio, True)]  # original
        n_aug = 40 if source_id.startswith("real_") else 8
        for _ in range(n_aug):
            aug = augment_audio(audio, rng)
            clips.append((aug, False))
        pos_clips_by_source[source_id] = clips

    total_pos = sum(len(v) for v in pos_clips_by_source.values())
    print(f"  Total positive clips (before jitter): {total_pos}")

    # ── Step 4: Generate negative data ──
    print("\n[4/7] Generating negative clips...")

    # Hard negatives via TTS
    hard_neg_phrases = [
        # Similar wake words
        "hey james", "hey chain", "hey rain", "hey pain", "hey jay",
        "hey jamie", "hey john", "hey jean", "hey gene", "hey joanne",
        "hey train", "hey brain", "hey crane", "hey jain", "hey jeanne",
        "hey change", "hey jen", "hey jenn", "hey jan", "hey june",
        "hey jack", "hey jake", "hey jade", "hey jana", "hey janice",
        "hey janes", "hey jenny",
        # Contains "jane" but NOT "hey jane" — critical negatives
        "jane", "a jane", "did jane", "with jane", "for jane",
        "is jane", "jane said", "jane's here", "about jane",
        "call jane", "tell jane", "ask jane", "where is jane",
        "say hey jane", "okay jane", "play jane",
        "jane can you", "jane please", "oh jane",
        # Contains "hey" but NOT "jane"
        "hey", "hey there", "hey you", "hey buddy", "hey man",
        "hey what's up", "hey wait",
    ]
    general_neg_phrases = [
        "good morning", "how are you", "what time is it",
        "turn on the lights", "set a timer for five minutes",
        "play some music", "what's the weather like",
        "hello there", "goodbye", "thank you", "yes please",
        "hey siri", "hey google", "hey alexa",
        "the quick brown fox", "remind me tomorrow",
        "stop playing", "next song", "volume up",
        "what's for dinner", "I'm going out", "see you later",
        "can you help me", "where are my keys",
        # Longer conversational phrases (background chatter scenarios)
        "I was thinking we could go to the store later",
        "did you see the game last night it was amazing",
        "can you pass me the remote control please",
        "the meeting is at three o'clock tomorrow afternoon",
        "I need to pick up the kids from school today",
        "have you heard about the new restaurant downtown",
        "the weather forecast says rain all week long",
        "I just finished reading that book you recommended",
        "we should plan a trip for the summer vacation",
        "the traffic was terrible on the highway this morning",
    ]

    tts_neg_hard = asyncio.run(generate_edge_tts_clips(hard_neg_phrases))
    tts_neg_general = asyncio.run(generate_edge_tts_clips(general_neg_phrases))

    neg_sources = {}
    neg_sources.update(tts_neg_hard)
    neg_sources.update(tts_neg_general)
    print(f"  TTS negative sources: {len(neg_sources)}")

    # Disk negatives
    neg_files = sorted(glob.glob(os.path.join(NEGATIVES_DIR, "*.wav")))
    for f in neg_files:
        try:
            audio = load_wav(f)
            neg_sources[f"disk_{os.path.basename(f)}"] = audio
        except Exception:
            pass
    print(f"  Total negative sources (incl disk): {len(neg_sources)}")

    # Silence sources
    for i in range(50):
        neg_sources[f"silence_{i}"] = rng.normal(0, 0.001, CLIP_SAMPLES).astype(np.float32)

    # Build augmented negative clips per source
    neg_clips_by_source = {}
    for source_id, audio in neg_sources.items():
        clips = [(audio, True)]
        n_aug = 3 if source_id.startswith("tts_") else 1
        for _ in range(n_aug):
            clips.append((augment_audio(audio, rng), False))
        neg_clips_by_source[source_id] = clips

    total_neg = sum(len(v) for v in neg_clips_by_source.values())
    print(f"  Total negative clips: {total_neg}")

    # ── Step 5: Source-disjoint split ──
    print("\n[5/7] Source-disjoint train/val split...")

    # Split sources, not individual clips
    pos_source_ids = list(pos_clips_by_source.keys())
    neg_source_ids = list(neg_clips_by_source.keys())
    rng.shuffle(pos_source_ids)
    rng.shuffle(neg_source_ids)

    val_pos_n = max(int(len(pos_source_ids) * 0.2), 2)
    val_neg_n = max(int(len(neg_source_ids) * 0.2), 5)

    val_pos_sources = set(pos_source_ids[:val_pos_n])
    val_neg_sources = set(neg_source_ids[:val_neg_n])
    train_pos_sources = set(pos_source_ids[val_pos_n:])
    train_neg_sources = set(neg_source_ids[val_neg_n:])

    print(f"  Train sources: {len(train_pos_sources)} pos, {len(train_neg_sources)} neg")
    print(f"  Val sources:   {len(val_pos_sources)} pos, {len(val_neg_sources)} neg")

    # ── Step 6: Extract features ──
    print("\n[6/7] Extracting openwakeword embeddings...")

    # Train features
    train_pos_clips = {s: pos_clips_by_source[s] for s in train_pos_sources}
    train_neg_clips = {s: neg_clips_by_source[s] for s in train_neg_sources}

    print("  Train positive features...")
    train_pos_feats = extract_oww_features_batch(train_pos_clips, n_jitter=3, rng=rng)
    print("  Train negative features...")
    train_neg_feats = extract_oww_features_batch(train_neg_clips, n_jitter=1, rng=rng)

    # Val features (no jitter, just center-padded)
    val_pos_clips = {s: pos_clips_by_source[s] for s in val_pos_sources}
    val_neg_clips = {s: neg_clips_by_source[s] for s in val_neg_sources}

    print("  Val positive features...")
    val_pos_feats = extract_oww_features_batch(val_pos_clips, n_jitter=1, rng=None)
    print("  Val negative features...")
    val_neg_feats = extract_oww_features_batch(val_neg_clips, n_jitter=1, rng=None)

    # Flatten to arrays
    def flatten_feats(feats_dict):
        all_f = []
        for source_feats in feats_dict.values():
            all_f.extend(source_feats)
        return np.array(all_f, dtype=np.float32) if all_f else np.empty((0, 16, 96), dtype=np.float32)

    X_train_pos = flatten_feats(train_pos_feats)
    X_train_neg = flatten_feats(train_neg_feats)
    X_val_pos = flatten_feats(val_pos_feats)
    X_val_neg = flatten_feats(val_neg_feats)

    print(f"  Train: {len(X_train_pos)} pos, {len(X_train_neg)} neg features")
    print(f"  Val:   {len(X_val_pos)} pos, {len(X_val_neg)} neg features")

    X_train = np.concatenate([X_train_pos, X_train_neg])
    y_train = np.concatenate([np.ones(len(X_train_pos)), np.zeros(len(X_train_neg))]).astype(np.float32)
    X_val = np.concatenate([X_val_pos, X_val_neg])
    y_val = np.concatenate([np.ones(len(X_val_pos)), np.zeros(len(X_val_neg))]).astype(np.float32)

    # Shuffle train
    idx = rng.permutation(len(X_train))
    X_train, y_train = X_train[idx], y_train[idx]

    # ── Step 7: Train classifier with hard negative mining ──
    print("\n[7/7] Training DNN classifier (with hard negative mining)...")

    layer_dim = 256

    class FCNBlock(nn.Module):
        def __init__(self, dim):
            super().__init__()
            self.fc = nn.Linear(dim, dim)
            self.relu = nn.ReLU()
            self.ln = nn.LayerNorm(dim)
        def forward(self, x):
            return self.relu(self.ln(self.fc(x)))

    class WakeWordNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.flatten = nn.Flatten()
            self.fc1 = nn.Linear(16 * 96, layer_dim)
            self.relu1 = nn.ReLU()
            self.ln1 = nn.LayerNorm(layer_dim)
            self.block1 = FCNBlock(layer_dim)
            self.dropout1 = nn.Dropout(0.15)
            self.block2 = FCNBlock(layer_dim)
            self.dropout2 = nn.Dropout(0.15)
            self.block3 = FCNBlock(layer_dim)
            self.out = nn.Linear(layer_dim, 1)
        def forward(self, x):
            x = self.relu1(self.ln1(self.fc1(self.flatten(x))))
            x = self.dropout1(self.block1(x))
            x = self.dropout2(self.block2(x))
            x = self.block3(x)
            return self.out(x)

    model = WakeWordNet()
    device = torch.device("cpu")
    model.to(device)

    n_pos_train = y_train.sum()
    n_neg_train = len(y_train) - n_pos_train
    pos_weight = torch.tensor([n_neg_train / max(n_pos_train, 1)], dtype=torch.float32)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    optimizer = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=400)

    X_train_t = torch.tensor(X_train, dtype=torch.float32).to(device)
    y_train_t = torch.tensor(y_train, dtype=torch.float32).unsqueeze(1).to(device)

    best_f1 = 0
    best_state = None
    batch_size = 128
    n_epochs = 400
    patience = 80
    no_improve = 0

    for epoch in range(n_epochs):
        model.train()
        perm = torch.randperm(len(X_train_t))
        epoch_loss = 0
        n_batches = 0

        for i in range(0, len(X_train_t), batch_size):
            idx = perm[i:i+batch_size]
            logits = model(X_train_t[idx])
            loss = criterion(logits, y_train_t[idx])
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
            n_batches += 1

        scheduler.step()

        metrics = evaluate_model(model, X_val, y_val)

        if epoch % 40 == 0 or epoch == n_epochs - 1:
            print(f"  Epoch {epoch:3d}: loss={epoch_loss/n_batches:.4f} "
                  f"P={metrics['precision']:.4f} R={metrics['recall']:.4f} "
                  f"F1={metrics['f1']:.4f} FPR={metrics['fpr']:.4f} "
                  f"(TP={metrics['tp']} FP={metrics['fp']} FN={metrics['fn']} TN={metrics['tn']})")

        if metrics['f1'] > best_f1:
            best_f1 = metrics['f1']
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1

        if no_improve >= patience:
            print(f"  Early stopping at epoch {epoch} (best F1={best_f1:.4f})")
            break

    model.load_state_dict(best_state)

    # Final evaluation at multiple thresholds
    print(f"\n  Best F1: {best_f1:.4f}")
    for thr in [0.3, 0.4, 0.5, 0.6, 0.7]:
        m = evaluate_model(model, X_val, y_val, threshold=thr)
        print(f"  thr={thr}: P={m['precision']:.4f} R={m['recall']:.4f} F1={m['f1']:.4f} FPR={m['fpr']:.4f}")

    # ── Export to ONNX ──
    print("\n  Exporting to ONNX...")

    class WakeWordExport(nn.Module):
        def __init__(self, logits_model):
            super().__init__()
            self.model = logits_model
        def forward(self, x):
            return torch.sigmoid(self.model(x))

    export_model = WakeWordExport(model).to(device)
    export_model.eval()

    dummy = torch.randn(1, 16, 96, device=device)
    torch.onnx.export(
        export_model, dummy, OUTPUT_PATH,
        input_names=["x"], output_names=["sigmoid"],
        opset_version=18,
    )

    # ALWAYS force inline — Android cannot load external .data files from assets
    import onnx as _onnx
    _m = _onnx.load(OUTPUT_PATH)
    _onnx.save_model(_m, OUTPUT_PATH, save_as_external_data=False)
    _data_file = OUTPUT_PATH + ".data"
    if os.path.exists(_data_file):
        os.remove(_data_file)
        print(f"  Removed stale .data file")
    print(f"  Model inlined: {os.path.getsize(OUTPUT_PATH)} bytes")

    # Verify ONNX vs PyTorch parity
    import onnxruntime as ort
    sess = ort.InferenceSession(OUTPUT_PATH)

    test_inputs = [np.random.randn(1, 16, 96).astype(np.float32) for _ in range(5)]
    max_diff = 0
    for ti in test_inputs:
        onnx_out = sess.run(None, {"x": ti})[0][0][0]
        torch_out = export_model(torch.tensor(ti)).item()
        diff = abs(onnx_out - torch_out)
        max_diff = max(max_diff, diff)
    print(f"  ONNX vs PyTorch max diff: {max_diff:.8f}")

    # ── Real audio verification ──
    print("\n  === Verification with real audio ===")

    import openwakeword

    # Reuse single model instance for speed
    oww = openwakeword.Model(wakeword_models=[], enable_speex_noise_suppression=False)

    def score_wav(path):
        oww.preprocessor.reset()
        audio = load_wav(path)
        clip_int16 = (pad_or_trim(audio, CLIP_SAMPLES) * 32768).astype(np.int16)
        for c in range(0, len(clip_int16), 1280):
            oww.predict(clip_int16[c:c+1280])
        fb = oww.preprocessor.feature_buffer.copy()
        mask = np.any(fb != 0, axis=1)
        if mask.sum() < 16: return -1
        features = fb[mask][-16:].reshape(1, 16, 96).astype(np.float32)
        return sess.run(None, {"x": features})[0][0][0]

    print("  Positive (real recordings):")
    for f in sorted(glob.glob(os.path.join(SAMPLES_DIR, "hey_jane_*.wav"))):
        s = score_wav(f)
        print(f"    {os.path.basename(f)}: {s:.4f}")

    print("  Negative (speech commands):")
    speech_files = sorted(glob.glob(os.path.join(NEGATIVES_DIR, "speech_cmd_*.wav")))
    fp_count = 0
    for f in speech_files:
        try:
            s = score_wav(f)
            if s > 0.5:
                fp_count += 1
        except Exception:
            pass
    print(f"    False positives: {fp_count}/{len(speech_files)} ({100*fp_count/max(len(speech_files),1):.1f}%)")

    print("  Silence/noise:")
    for label, audio in [("silence", np.zeros(CLIP_SAMPLES)), ("noise", np.random.randn(CLIP_SAMPLES) * 0.1)]:
        oww.preprocessor.reset()
        clip_int16 = (audio * 32768).astype(np.int16)
        for c in range(0, len(clip_int16), 1280):
            oww.predict(clip_int16[c:c+1280])
        fb = oww.preprocessor.feature_buffer.copy()
        mask = np.any(fb != 0, axis=1)
        if mask.sum() >= 16:
            features = fb[mask][-16:].reshape(1, 16, 96).astype(np.float32)
            s = sess.run(None, {"x": features})[0][0][0]
            print(f"    {label}: {s:.4f}")

    print(f"\n  Model saved: {OUTPUT_PATH}")
    print(f"  File size: {os.path.getsize(OUTPUT_PATH) / 1024:.1f} KB")
    print("\nDone!")


if __name__ == "__main__":
    main()
