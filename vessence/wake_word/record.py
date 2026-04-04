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


def save_wav(audio: np.ndarray, path: str, sample_rate: int):
    """Save audio as 16-bit WAV."""
    audio_int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())


def load_wav(path: str) -> tuple[np.ndarray, int]:
    """Load a WAV file. Returns (audio_float32, sample_rate)."""
    with wave.open(path, "r") as wf:
        sr = wf.getframerate()
        data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        audio = data.astype(np.float32) / 32768.0
    return audio, sr


def list_samples(samples_dir: Path):
    """List existing enrollment samples."""
    wavs = sorted(samples_dir.glob("*.wav"))
    if not wavs:
        print("No samples recorded yet.")
        return
    print(f"\n{len(wavs)} samples in {samples_dir}/:")
    for wav in wavs:
        audio, sr = load_wav(str(wav))
        print(f"  {wav.name}: {len(audio)/sr:.2f}s, peak={np.abs(audio).max():.3f}")


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

    # Find next sample number
    existing = sorted(samples_dir.glob("hey_jane_*.wav"))
    next_num = len(existing)

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

            path = samples_dir / f"hey_jane_{sample_num:03d}.wav"
            save_wav(audio, str(path), cfg.sample_rate)
            print(f"  Saved: {path}")

    except KeyboardInterrupt:
        print("\nStopped.")

    list_samples(samples_dir)


if __name__ == "__main__":
    main()
