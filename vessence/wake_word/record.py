#!/usr/bin/env python3
"""
Record enrollment samples for wake word detection.

Usage:
    python record.py                  # Record samples interactively
    python record.py --count 10       # Record 10 samples
    python record.py --list           # List existing samples
"""

import argparse
import sys
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

from config import WakeWordConfig


def record_sample(cfg: WakeWordConfig, duration: float = 2.0) -> np.ndarray:
    """Record a single audio sample from the microphone."""
    print(f"  Recording {duration}s... ", end="", flush=True)
    audio = sd.rec(
        int(cfg.sample_rate * duration),
        samplerate=cfg.sample_rate,
        channels=1,
        dtype=np.float32,
    )
    sd.wait()
    audio = audio.flatten()
    # Trim silence from start and end (threshold-based)
    threshold = 0.02
    above = np.where(np.abs(audio) > threshold)[0]
    if len(above) > 0:
        # Keep 50ms padding on each side
        pad = int(cfg.sample_rate * 0.05)
        start = max(0, above[0] - pad)
        end = min(len(audio), above[-1] + pad)
        audio = audio[start:end]
    peak = np.abs(audio).max()
    print(f"done ({len(audio)/cfg.sample_rate:.2f}s, peak={peak:.3f})")
    return audio


def save_sample(audio: np.ndarray, path: str, sample_rate: int):
    """Save audio. OGG Vorbis for .ogg paths (default), WAV otherwise."""
    import soundfile as sf
    if path.endswith(".ogg"):
        sf.write(path, audio.astype(np.float32, copy=False), sample_rate,
                 format="OGG", subtype="VORBIS")
    else:
        audio_int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
        with wave.open(path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_int16.tobytes())


# Kept for back-compat with earlier import sites.
save_wav = save_sample


def load_wav(path: str) -> tuple[np.ndarray, int]:
    """Load a sample as (float32 audio, sample_rate). Reads WAV and OGG."""
    import soundfile as sf
    data, sr = sf.read(path, dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1).astype(np.float32)
    return data, sr


def _list_sample_paths(samples_dir: Path):
    import itertools
    return sorted(itertools.chain(
        samples_dir.glob("hey_jane_*.ogg"),
        samples_dir.glob("hey_jane_*.wav"),
    ))


def list_samples(samples_dir: Path):
    """List existing enrollment samples."""
    paths = _list_sample_paths(samples_dir)
    if not paths:
        print("No samples recorded yet.")
        return
    print(f"\n{len(paths)} samples in {samples_dir}/:")
    for p in paths:
        audio, sr = load_wav(str(p))
        print(f"  {p.name}: {len(audio)/sr:.2f}s, peak={np.abs(audio).max():.3f}")


def main():
    parser = argparse.ArgumentParser(description="Record wake word samples")
    parser.add_argument("--count", type=int, default=10, help="Number of samples to record")
    parser.add_argument("--duration", type=float, default=2.0, help="Recording duration per sample (seconds)")
    parser.add_argument("--list", action="store_true", help="List existing samples")
    parser.add_argument("--config", type=str, default=None, help="Config file path")
    args = parser.parse_args()

    cfg = WakeWordConfig()
    samples_dir = Path(cfg.samples_dir)
    samples_dir.mkdir(exist_ok=True)

    if args.list:
        list_samples(samples_dir)
        return

    # Find next sample number — max-existing + 1, over both OGG and legacy
    # WAV, so deleted gaps don't cause an overwrite collision.
    import re as _re
    _num_re = _re.compile(r"hey_jane_(\d+)\.(?:ogg|wav)$")
    highest = -1
    for p in _list_sample_paths(samples_dir):
        m = _num_re.search(p.name)
        if m:
            highest = max(highest, int(m.group(1)))
    next_num = highest + 1

    print(f"\n=== Wake Word Sample Recording ===")
    print(f"Say 'Hey Jane' when prompted. Recording {args.count} samples.")
    print(f"Duration: {args.duration}s per sample")
    print(f"Press Ctrl+C to stop early.\n")

    try:
        for i in range(args.count):
            sample_num = next_num + i
            input(f"[{i+1}/{args.count}] Press Enter, then say 'Hey Jane'... ")
            audio = record_sample(cfg, args.duration)

            if np.abs(audio).max() < 0.01:
                print("  ⚠ Very quiet — try speaking louder. Skipping.")
                continue

            path = samples_dir / f"hey_jane_{sample_num:03d}.ogg"
            save_sample(audio, str(path), cfg.sample_rate)
            print(f"  Saved: {path}")

    except KeyboardInterrupt:
        print("\nStopped.")

    list_samples(samples_dir)


if __name__ == "__main__":
    main()
