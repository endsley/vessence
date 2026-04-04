#!/usr/bin/env python3
"""
Enroll: build wake word model with multi-prototype + multi-centroid UBM + hard negatives.
"""

import argparse
import sys
import os
import subprocess
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans

from config import WakeWordConfig
from record import load_wav
from features import extract_dct_features, batch_extract
from augment import augment_samples
from rff import compute_mean_embedding, mmd_distance, save_model


def load_samples(samples_dir: Path, sample_rate: int) -> list[np.ndarray]:
    wavs = sorted(samples_dir.glob("*.wav"))
    samples = []
    for wav in wavs:
        audio, sr = load_wav(str(wav))
        if sr != sample_rate:
            ratio = sample_rate / sr
            indices = np.arange(0, len(audio), 1.0 / ratio).astype(int)
            indices = indices[indices < len(audio)]
            audio = audio[indices]
        samples.append(audio)
    return samples


def generate_hard_negatives(cfg: WakeWordConfig, output_dir: Path) -> list[np.ndarray]:
    """Generate hard negative samples: TTS confusables + partial keywords."""
    confusable = [
        # Near-miss phrases
        "hey james", "hey chain", "hey rain", "hey pain", "hey jay",
        "hey jamie", "hey jain", "hey jeanne", "hey gene", "hey joanne",
        "hey change", "hey john", "hey jan",
        # Partial keywords
        "hey", "jane", "hey hey", "jane jane",
        # Context phrases
        "okay jane", "say jane", "play jane", "agent jane",
        # Common speech
        "hey there", "hey everyone", "hey what's up", "good morning",
        "the rain in spain", "how are you doing", "what time is it",
        # Similar sounds
        "hey chain gang", "hey train", "hey brain", "hey crane",
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    samples = []

    for i, phrase in enumerate(confusable):
        out_path = output_dir / f"hard_neg_{i:03d}.wav"
        if out_path.exists():
            audio, _ = load_wav(str(out_path))
            samples.append(audio)
            continue
        try:
            subprocess.run(
                ["espeak-ng", "-w", str(out_path), "-s", "150", phrase],
                capture_output=True, timeout=10,
            )
            if out_path.exists():
                audio, _ = load_wav(str(out_path))
                samples.append(audio)
        except Exception:
            pass

    if samples:
        print(f"  Generated {len(samples)} hard negatives (TTS confusables)")
    return samples


def score_samples(centroids, neg_centroids, mapper, features):
    """Score using multi-centroid UBM: min(pos_dist) - min(neg_dist)."""
    embs = mapper.transform(features)
    scores = []
    for emb in embs:
        pos_dist = min(mmd_distance(c, emb) for c in centroids)
        neg_dist = min(mmd_distance(c, emb) for c in neg_centroids)
        scores.append(pos_dist - neg_dist)
    return np.array(scores)


def estimate_threshold(centroids, neg_centroids, mapper, pos_features, neg_features):
    pos_scores = score_samples(centroids, neg_centroids, mapper, pos_features)
    neg_scores = score_samples(centroids, neg_centroids, mapper, neg_features)

    print(f"\nUBM Score statistics (lower = more like positive):")
    print(f"  Positive: mean={pos_scores.mean():.4f}, std={pos_scores.std():.4f}")
    print(f"  Negative: mean={neg_scores.mean():.4f}, std={neg_scores.std():.4f}")
    print(f"  Separation: {abs(neg_scores.mean()) / (abs(pos_scores.mean()) + 1e-10):.2f}x")

    candidates = np.linspace(pos_scores.min() * 1.5, neg_scores.max(), 2000)
    best_rec, best_t, best_stats = 0, 0, {}

    for t in candidates:
        tp = np.sum(pos_scores <= t)
        fn = np.sum(pos_scores > t)
        fp = np.sum(neg_scores <= t)
        tn = np.sum(neg_scores > t)
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0

        if fpr <= 0.01 and rec > best_rec:
            best_rec = rec
            best_t = float(t)
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
            best_stats = {"prec": prec, "rec": rec, "f1": f1, "fpr": fpr,
                          "tp": int(tp), "fn": int(fn), "fp": int(fp), "tn": int(tn)}

    if best_t == 0:
        for t in candidates:
            tp, fp = np.sum(pos_scores <= t), np.sum(neg_scores <= t)
            fn, tn = np.sum(pos_scores > t), np.sum(neg_scores > t)
            p = tp / (tp + fp) if (tp + fp) > 0 else 0
            r = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
            if f1 > best_stats.get("f1", 0):
                best_t = float(t)
                best_stats = {"prec": p, "rec": r, "f1": f1, "fpr": fpr,
                              "tp": int(tp), "fn": int(fn), "fp": int(fp), "tn": int(tn)}

    print(f"\nThreshold: {best_t:.6f}")
    if best_stats:
        print(f"  Recall={best_stats['rec']:.3f} Prec={best_stats['prec']:.3f} "
              f"F1={best_stats['f1']:.3f} FPR={best_stats['fpr']:.4f}")
    return best_t


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--augment-factor", type=int, default=50)
    parser.add_argument("--negatives", type=str, default="negatives")
    parser.add_argument("--n-pos-prototypes", type=int, default=8)
    parser.add_argument("--n-neg-prototypes", type=int, default=12)
    parser.add_argument("--snr-low", type=float, default=5.0)
    parser.add_argument("--snr-high", type=float, default=20.0)
    parser.add_argument("--sigma", type=float, default=0.24)
    parser.add_argument("--fastfood", action="store_true", help="Use Fastfood structured RFF")
    parser.add_argument("--no-hard-neg", action="store_true")
    args = parser.parse_args()

    cfg = WakeWordConfig()
    samples_dir = Path(cfg.samples_dir)
    neg_dir = Path(args.negatives)

    print("=== Wake Word Enrollment (v3: multi-UBM + Fastfood) ===")
    print(cfg.summary())

    # Load positives
    print(f"\nLoading positive samples...")
    pos_samples = load_samples(samples_dir, cfg.sample_rate)
    if not pos_samples:
        print("ERROR: No samples. Run 'python record.py' first.")
        sys.exit(1)
    print(f"  {len(pos_samples)} clean samples")

    # Augment positives
    print(f"\nAugmenting (factor={args.augment_factor})...")
    augmented = augment_samples(pos_samples, cfg, augment_factor=args.augment_factor,
                                snr_range=(args.snr_low, args.snr_high))

    # Extract features
    print(f"\nExtracting features...")
    pos_features = batch_extract(augmented, cfg)
    print(f"  Positive: {pos_features.shape}")

    # Compute mean embedding + RFF mapper
    mean_emb, mapper, sigma_used = compute_mean_embedding(
        pos_features, cfg, sigma=args.sigma, use_fastfood=args.fastfood)
    print(f"  Mean embedding: {mean_emb.shape}, σ={sigma_used:.4f}")
    print(f"  RFF type: {'Fastfood' if args.fastfood else 'Standard'}")

    # Multi-prototype: K-means on positive RFF embeddings
    print(f"\nComputing {args.n_pos_prototypes} positive prototypes...")
    pos_rff = mapper.transform(pos_features)
    km_pos = KMeans(n_clusters=args.n_pos_prototypes, random_state=42, n_init=10)
    km_pos.fit(pos_rff)
    centroids = km_pos.cluster_centers_

    # Load negatives + hard negatives
    threshold = 0.0
    neg_centroids = None
    neg_mean = None

    if neg_dir.exists() and any(neg_dir.glob("*.wav")):
        print(f"\nLoading negatives...")
        neg_samples = load_samples(neg_dir, cfg.sample_rate)
        print(f"  {len(neg_samples)} negative samples")

        # Generate hard negatives (Codex suggestion #7)
        if not args.no_hard_neg:
            print("\nGenerating hard negatives...")
            hard_negs = generate_hard_negatives(cfg, neg_dir / "hard_negatives")
            neg_samples.extend(hard_negs)
            print(f"  Total negatives: {len(neg_samples)}")

        neg_aug = augment_samples(neg_samples, cfg, augment_factor=3, snr_range=(5, 25))
        neg_features = batch_extract(neg_aug, cfg)

        # K-Means UBM: multi-centroid negatives (Gemini suggestion #2)
        print(f"\nComputing {args.n_neg_prototypes} negative prototypes (K-Means UBM)...")
        neg_rff = mapper.transform(neg_features)
        km_neg = KMeans(n_clusters=args.n_neg_prototypes, random_state=42, n_init=10)
        km_neg.fit(neg_rff)
        neg_centroids = km_neg.cluster_centers_
        neg_mean = neg_rff.mean(axis=0)  # keep for backward compat

        # Estimate threshold: score = min(pos_dist) - min(neg_dist)
        threshold = estimate_threshold(centroids, neg_centroids, mapper, pos_features, neg_features)
    else:
        pos_dists = np.array([min(mmd_distance(c, e) for c in centroids) for e in pos_rff])
        threshold = float(pos_dists.mean() + 3 * pos_dists.std())
        print(f"\nNo negatives. Fallback threshold: {threshold:.6f}")

    # Save
    save_model(mapper, mean_emb, sigma_used, threshold, cfg, "model.npz",
               len(pos_samples), len(augmented),
               centroids=centroids, neg_mean=neg_mean, neg_centroids=neg_centroids)
    print(f"\nModel saved: model.npz ({Path('model.npz').stat().st_size // 1024}KB)")
    print("Done.")


if __name__ == "__main__":
    main()
