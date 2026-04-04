#!/usr/bin/env python3
"""
Evaluate model performance and tune parameters.

Tests the model against positive and negative samples,
sweeps thresholds, and reports precision/recall/F1.

Usage:
    python evaluate.py                                      # Basic eval
    python evaluate.py --negatives negatives/               # With negative samples
    python evaluate.py --sweep-sigma 1.0 5.0 10.0 20.0     # Sweep σ values
    python evaluate.py --sweep-dct 8 10 13 16 20            # Sweep DCT coefficients
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from config import WakeWordConfig
from record import load_wav
from features import extract_dct_features, batch_extract
from augment import augment_samples
from rff import RFFMapper, median_heuristic, compute_mean_embedding, mmd_distance
from enroll import load_samples


def evaluate_model(
    pos_features: np.ndarray,
    neg_features: np.ndarray | None,
    mean_emb: np.ndarray,
    mapper: RFFMapper,
    threshold: float,
) -> dict:
    """Evaluate model at a given threshold."""
    pos_emb = mapper.transform(pos_features)
    pos_dists = np.array([mmd_distance(mean_emb, e) for e in pos_emb])

    tp = int(np.sum(pos_dists <= threshold))
    fn = int(np.sum(pos_dists > threshold))

    result = {
        "threshold": threshold,
        "pos_mean_dist": float(pos_dists.mean()),
        "pos_std_dist": float(pos_dists.std()),
        "tp": tp, "fn": fn,
        "recall": tp / (tp + fn) if (tp + fn) > 0 else 0,
    }

    if neg_features is not None and len(neg_features) > 0:
        neg_emb = mapper.transform(neg_features)
        neg_dists = np.array([mmd_distance(mean_emb, e) for e in neg_emb])
        fp = int(np.sum(neg_dists <= threshold))
        tn = int(np.sum(neg_dists > threshold))
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = result["recall"]
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        result.update({
            "neg_mean_dist": float(neg_dists.mean()),
            "neg_std_dist": float(neg_dists.std()),
            "fp": fp, "tn": tn,
            "precision": precision,
            "f1": f1,
            "fpr": fp / (fp + tn) if (fp + tn) > 0 else 0,
        })

    return result


def sweep_parameter(
    name: str,
    values: list,
    pos_samples: list[np.ndarray],
    neg_samples: list[np.ndarray] | None,
    base_cfg: WakeWordConfig,
    augment_factor: int = 20,
):
    """Sweep a parameter and report results."""
    print(f"\n{'='*60}")
    print(f"Sweeping {name}: {values}")
    print(f"{'='*60}")

    results = []
    for val in values:
        cfg = WakeWordConfig(**base_cfg.__dict__)
        setattr(cfg, name, val)

        print(f"\n--- {name}={val} ---")
        print(f"  Feature dim: {cfg.feature_dim}")

        # Augment and extract
        aug_pos = augment_samples(pos_samples, cfg, augment_factor=augment_factor)
        pos_features = batch_extract(aug_pos, cfg)

        neg_features = None
        if neg_samples:
            aug_neg = augment_samples(neg_samples, cfg, augment_factor=5)
            neg_features = batch_extract(aug_neg, cfg)

        # Build model
        mean_emb, mapper, sigma = compute_mean_embedding(pos_features, cfg)

        # Find best threshold
        pos_emb = mapper.transform(pos_features)
        pos_dists = np.array([mmd_distance(mean_emb, e) for e in pos_emb])

        if neg_features is not None:
            neg_emb = mapper.transform(neg_features)
            neg_dists = np.array([mmd_distance(mean_emb, e) for e in neg_emb])

            # Search for best F1
            candidates = np.linspace(pos_dists.min() * 0.5, neg_dists.max(), 500)
            best_f1 = 0
            best_t = 0
            for t in candidates:
                tp = np.sum(pos_dists <= t)
                fp = np.sum(neg_dists <= t)
                fn = np.sum(pos_dists > t)
                p = tp / (tp + fp) if (tp + fp) > 0 else 0
                r = tp / (tp + fn) if (tp + fn) > 0 else 0
                f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
                if f1 > best_f1:
                    best_f1 = f1
                    best_t = t

            res = evaluate_model(pos_features, neg_features, mean_emb, mapper, best_t)
        else:
            best_t = float(pos_dists.mean() + 3 * pos_dists.std())
            res = evaluate_model(pos_features, None, mean_emb, mapper, best_t)

        res["param_value"] = val
        res["sigma"] = sigma
        res["feature_dim"] = cfg.feature_dim
        results.append(res)

        # Print summary
        if "f1" in res:
            print(f"  σ={sigma:.2f}, threshold={best_t:.4f}")
            print(f"  P={res['precision']:.3f} R={res['recall']:.3f} F1={res['f1']:.3f} FPR={res['fpr']:.4f}")
        else:
            print(f"  σ={sigma:.2f}, threshold={best_t:.4f}, recall={res['recall']:.3f}")

    # Summary table
    print(f"\n{'='*60}")
    print(f"Summary: {name} sweep")
    print(f"{'='*60}")
    header = f"{'Value':>8} {'σ':>8} {'FeatDim':>8} {'Thresh':>10}"
    if neg_samples:
        header += f" {'Prec':>6} {'Rec':>6} {'F1':>6} {'FPR':>8}"
    else:
        header += f" {'Rec':>6}"
    print(header)
    for r in results:
        line = f"{r['param_value']:>8} {r['sigma']:>8.2f} {r['feature_dim']:>8} {r['threshold']:>10.4f}"
        if "f1" in r:
            line += f" {r['precision']:>6.3f} {r['recall']:>6.3f} {r['f1']:>6.3f} {r['fpr']:>8.4f}"
        else:
            line += f" {r['recall']:>6.3f}"
        print(line)


def main():
    parser = argparse.ArgumentParser(description="Evaluate and tune wake word model")
    parser.add_argument("--model", default="model.json", help="Model path")
    parser.add_argument("--positives", default="samples", help="Positive samples dir")
    parser.add_argument("--negatives", default="negatives", help="Negative samples dir")
    parser.add_argument("--sweep-dct", nargs="+", type=int, help="Sweep DCT coefficient counts")
    parser.add_argument("--sweep-sigma", nargs="+", type=float, help="Sweep σ values")
    parser.add_argument("--sweep-rff", nargs="+", type=int, help="Sweep RFF dimensions")
    parser.add_argument("--sweep-frame", nargs="+", type=float, help="Sweep frame sizes (ms)")
    parser.add_argument("--augment-factor", type=int, default=20, help="Augmentation factor for sweeps")
    args = parser.parse_args()

    cfg = WakeWordConfig()

    # Load samples
    pos_dir = Path(args.positives)
    neg_dir = Path(args.negatives)

    pos_samples = load_samples(pos_dir, cfg.sample_rate)
    if not pos_samples:
        print(f"No positive samples in {pos_dir}/")
        sys.exit(1)
    print(f"Loaded {len(pos_samples)} positive samples")

    neg_samples = None
    if neg_dir.exists() and any(neg_dir.glob("*.wav")):
        neg_samples = load_samples(neg_dir, cfg.sample_rate)
        print(f"Loaded {len(neg_samples)} negative samples")

    # Run sweeps
    if args.sweep_dct:
        sweep_parameter("n_dct_coeffs", args.sweep_dct, pos_samples, neg_samples, cfg, args.augment_factor)
    if args.sweep_sigma:
        # For sigma sweep, we set it directly on cfg and use non-auto
        for s in args.sweep_sigma:
            cfg_copy = WakeWordConfig(**cfg.__dict__)
            cfg_copy.rff_sigma = s
        sweep_parameter("rff_sigma", args.sweep_sigma, pos_samples, neg_samples, cfg, args.augment_factor)
    if args.sweep_rff:
        sweep_parameter("rff_dim", args.sweep_rff, pos_samples, neg_samples, cfg, args.augment_factor)
    if args.sweep_frame:
        sweep_parameter("frame_ms", args.sweep_frame, pos_samples, neg_samples, cfg, args.augment_factor)

    # If no sweeps, just evaluate the existing model
    if not any([args.sweep_dct, args.sweep_sigma, args.sweep_rff, args.sweep_frame]):
        if not Path(args.model).exists():
            print(f"\nNo model found at {args.model}. Run 'python enroll.py' first.")
            print("Or use --sweep-* flags to run parameter sweeps.")
            sys.exit(1)

        with open(args.model) as f:
            model = json.load(f)
        mean_emb = np.array(model["mean_embedding"], dtype=np.float32)
        mapper = RFFMapper.load(model["rff"])
        threshold = model["threshold"]
        model_cfg = WakeWordConfig(**model["config"])

        # Extract features with model's config
        pos_features = batch_extract(pos_samples, model_cfg)
        neg_features = None
        if neg_samples:
            neg_features = batch_extract(neg_samples, model_cfg)

        print(f"\nEvaluating model (threshold={threshold:.6f})...")
        result = evaluate_model(pos_features, neg_features, mean_emb, mapper, threshold)
        print(f"\nResults:")
        for k, v in result.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.4f}")
            else:
                print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
