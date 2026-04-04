#!/usr/bin/env python3
"""
Live wake word detection with:
- Stage 0: cheap energy gate (skips MFCC/RFF when no speech)
- Multi-prototype positive scoring (8 K-means centroids)
- Multi-centroid UBM negative scoring (12 K-means centroids)
- Incremental MFCC extraction
"""

import argparse
import time

import numpy as np
import sounddevice as sd

from config import WakeWordConfig
from features import IncrementalMFCC
from rff import load_model, mmd_distance


class WakeWordDetector:
    def __init__(self, model_path: str = "model.npz"):
        self.mean_embedding, self.mapper, self.threshold, self.cfg = load_model(model_path)

        data = np.load(model_path, allow_pickle=False)
        self.centroids = data.get("centroids", None)
        self.neg_centroids = data.get("neg_centroids", None)
        self.neg_mean = data.get("neg_mean", None)

        self.mfcc = IncrementalMFCC(self.cfg)
        self.cooldown_s = 2.0
        self.last_detection = 0.0

        # Stage 0: energy gate parameters
        # Skip the expensive MFCC/RFF pipeline if audio energy is too low
        self.energy_gate_threshold = 0.01  # RMS threshold for "might be speech"
        self.stage0_skips = 0
        self.stage0_passes = 0

    def feed(self, audio_chunk: np.ndarray) -> tuple[bool, float]:
        """Feed one stride of audio. Returns (detected, score)."""
        # ── Stage 0: cheap energy gate ──
        rms = np.sqrt(np.mean(audio_chunk ** 2))
        if rms < self.energy_gate_threshold:
            # Too quiet — no speech possible. Skip expensive pipeline.
            # Still feed audio to keep the ring buffer current.
            self.mfcc.feed_audio(audio_chunk)
            self.stage0_skips += 1
            return False, float("inf")
        self.stage0_passes += 1

        # ── Stage 1: full MFCC + RFF + scoring ──
        features = self.mfcc.feed_audio(audio_chunk)
        if features is None:
            return False, float("inf")

        embedding = self.mapper.transform(features.reshape(1, -1))[0]

        # Multi-prototype positive scoring
        if self.centroids is not None:
            pos_dist = min(mmd_distance(c, embedding) for c in self.centroids)
        else:
            pos_dist = mmd_distance(self.mean_embedding, embedding)

        # Multi-centroid UBM scoring (Gemini suggestion #2)
        if self.neg_centroids is not None:
            neg_dist = min(mmd_distance(c, embedding) for c in self.neg_centroids)
            score = pos_dist - neg_dist
        elif self.neg_mean is not None:
            neg_dist = mmd_distance(self.neg_mean, embedding)
            score = pos_dist - neg_dist
        else:
            score = pos_dist

        now = time.time()
        detected = score <= self.threshold and (now - self.last_detection) > self.cooldown_s
        if detected:
            self.last_detection = now
        return detected, score

    def reset(self):
        self.mfcc.reset()

    @property
    def stage0_skip_rate(self) -> float:
        total = self.stage0_skips + self.stage0_passes
        return self.stage0_skips / total if total > 0 else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="model.npz")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--energy-gate", type=float, default=0.01)
    args = parser.parse_args()

    detector = WakeWordDetector(args.model)
    if args.threshold is not None:
        detector.threshold = args.threshold
    detector.energy_gate_threshold = args.energy_gate

    cfg = detector.cfg
    stride = cfg.detection_stride_samples

    print(f"=== Wake Word Detection (v3) ===")
    print(f"Threshold: {detector.threshold:.6f}")
    print(f"Energy gate: {detector.energy_gate_threshold}")
    print(f"Positive prototypes: {len(detector.centroids) if detector.centroids is not None else 1}")
    print(f"Negative prototypes: {len(detector.neg_centroids) if detector.neg_centroids is not None else ('1 (mean)' if detector.neg_mean is not None else 0)}")
    print(f"Listening... (Ctrl+C to stop)\n")

    sample_count = 0
    check_times = []
    try:
        with sd.InputStream(samplerate=cfg.sample_rate, channels=1,
                            dtype=np.float32, blocksize=stride) as stream:
            while True:
                audio, _ = stream.read(stride)
                audio = audio.flatten()
                sample_count += len(audio)

                t0 = time.perf_counter()
                detected, score = detector.feed(audio)
                check_ms = (time.perf_counter() - t0) * 1000
                check_times.append(check_ms)

                if args.verbose and sample_count % (cfg.sample_rate // 2) < stride:
                    avg_ms = np.mean(check_times[-30:])
                    skip_rate = detector.stage0_skip_rate
                    bar_len = max(0, min(50, int(50 * (1 - score / (detector.threshold * 3)))))
                    bar = "#" * bar_len + "." * (50 - bar_len)
                    status = " <<< TRIGGER!" if detected else ""
                    print(f"\r  score={score:.4f} [{bar}] {avg_ms:.1f}ms "
                          f"skip={skip_rate:.0%}{status}",
                          end="", flush=True)

                if detected:
                    elapsed = sample_count / cfg.sample_rate
                    avg_ms = np.mean(check_times[-30:])
                    print(f"\n*** HEY JANE DETECTED *** (score={score:.4f}, "
                          f"t={elapsed:.1f}s, avg={avg_ms:.1f}ms/check, "
                          f"stage0_skip={detector.stage0_skip_rate:.0%})")
    except KeyboardInterrupt:
        if check_times:
            print(f"\nStopped. Avg: {np.mean(check_times):.2f}ms "
                  f"(median: {np.median(check_times):.2f}ms, "
                  f"stage0 skip: {detector.stage0_skip_rate:.0%})")


if __name__ == "__main__":
    main()
