#!/usr/bin/env python3
"""
Collect negative samples for wake word evaluation.

Sources:
1. Record ambient background noise from your mic
2. Download free speech/noise datasets (LibriSpeech, ESC-50, etc.)
3. Generate synthetic negatives (silence, tones, noise)
4. Chunk long audio files into utterance-length segments

Usage:
    python collect_negatives.py --record 60          # Record 60s of ambient noise, auto-chunk
    python collect_negatives.py --generate 500        # Generate 500 synthetic negative samples
    python collect_negatives.py --download             # Download free datasets
    python collect_negatives.py --chunk audio.wav      # Chunk a long audio file
    python collect_negatives.py --all                  # Do everything
"""

import argparse
import wave
import sys
from pathlib import Path

import numpy as np
import sounddevice as sd

from config import WakeWordConfig


NEGATIVES_DIR = Path("negatives")


def save_wav(audio: np.ndarray, path: str, sample_rate: int):
    audio_int16 = (audio * 32767).clip(-32768, 32767).astype(np.int16)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())


def record_ambient(duration_s: int, cfg: WakeWordConfig) -> int:
    """Record ambient noise and chunk into utterance-length segments."""
    print(f"Recording {duration_s}s of ambient noise...")
    print("  (Just let it run — capture your normal environment: AC, keyboard, etc.)")

    audio = sd.rec(
        int(cfg.sample_rate * duration_s),
        samplerate=cfg.sample_rate,
        channels=1,
        dtype=np.float32,
    )
    sd.wait()
    audio = audio.flatten()
    print(f"  Recorded {len(audio)/cfg.sample_rate:.1f}s")

    # Chunk into utterance-length segments with 50% overlap
    chunk_len = cfg.utterance_samples
    hop = chunk_len // 2
    count = 0
    existing = len(list(NEGATIVES_DIR.glob("ambient_*.wav")))

    for i in range(0, len(audio) - chunk_len, hop):
        chunk = audio[i:i + chunk_len]
        path = NEGATIVES_DIR / f"ambient_{existing + count:04d}.wav"
        save_wav(chunk, str(path), cfg.sample_rate)
        count += 1

    print(f"  Saved {count} ambient chunks")
    return count


def record_speech(duration_s: int, cfg: WakeWordConfig) -> int:
    """Record yourself talking (NOT saying hey jane) and chunk it."""
    print(f"\nRecording {duration_s}s of speech...")
    print("  Talk normally about anything — but DON'T say 'hey jane'.")
    input("  Press Enter to start...")

    audio = sd.rec(
        int(cfg.sample_rate * duration_s),
        samplerate=cfg.sample_rate,
        channels=1,
        dtype=np.float32,
    )
    sd.wait()
    audio = audio.flatten()

    chunk_len = cfg.utterance_samples
    hop = chunk_len // 2
    count = 0
    existing = len(list(NEGATIVES_DIR.glob("speech_*.wav")))

    for i in range(0, len(audio) - chunk_len, hop):
        chunk = audio[i:i + chunk_len]
        # Only save chunks with actual speech (not silence)
        if np.abs(chunk).max() > 0.01:
            path = NEGATIVES_DIR / f"speech_{existing + count:04d}.wav"
            save_wav(chunk, str(path), cfg.sample_rate)
            count += 1

    print(f"  Saved {count} speech chunks")
    return count


def generate_synthetic(count: int, cfg: WakeWordConfig) -> int:
    """Generate synthetic negative samples."""
    from augment import white_noise, pink_noise, brownian_noise, hum_noise, babble_noise

    generators = {
        "silence": lambda n: np.zeros(n, dtype=np.float32) + np.random.randn(n).astype(np.float32) * 0.001,
        "white": lambda n: white_noise(n, amplitude=np.random.uniform(0.01, 0.1)),
        "pink": lambda n: pink_noise(n, amplitude=np.random.uniform(0.01, 0.1)),
        "brown": lambda n: brownian_noise(n, amplitude=np.random.uniform(0.01, 0.1)),
        "hum": lambda n: hum_noise(n, cfg.sample_rate, amplitude=np.random.uniform(0.005, 0.05)),
        "babble": lambda n: babble_noise(n, amplitude=np.random.uniform(0.01, 0.08)),
        "tone": lambda n: np.sin(2 * np.pi * np.random.uniform(100, 2000) *
                                  np.arange(n, dtype=np.float32) / cfg.sample_rate) *
                          np.random.uniform(0.01, 0.05),
        "mixed": lambda n: (white_noise(n, 0.02) + hum_noise(n, cfg.sample_rate, 0.01) +
                            pink_noise(n, 0.01)),
    }

    existing = len(list(NEGATIVES_DIR.glob("synth_*.wav")))
    gen_names = list(generators.keys())
    saved = 0

    for i in range(count):
        gen_name = gen_names[i % len(gen_names)]
        audio = generators[gen_name](cfg.utterance_samples)
        path = NEGATIVES_DIR / f"synth_{existing + i:04d}.wav"
        save_wav(audio, str(path), cfg.sample_rate)
        saved += 1

    print(f"Generated {saved} synthetic negative samples")
    return saved


def chunk_audio_file(filepath: str, cfg: WakeWordConfig) -> int:
    """Chunk a long audio file into utterance-length negatives."""
    with wave.open(filepath, "r") as wf:
        sr = wf.getframerate()
        data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        audio = data.astype(np.float32) / 32768.0

    # Resample if needed
    if sr != cfg.sample_rate:
        ratio = cfg.sample_rate / sr
        indices = np.arange(0, len(audio), 1.0 / ratio).astype(int)
        indices = indices[indices < len(audio)]
        audio = audio[indices]

    chunk_len = cfg.utterance_samples
    hop = chunk_len // 2
    count = 0
    stem = Path(filepath).stem
    existing = len(list(NEGATIVES_DIR.glob(f"{stem}_*.wav")))

    for i in range(0, len(audio) - chunk_len, hop):
        chunk = audio[i:i + chunk_len]
        path = NEGATIVES_DIR / f"{stem}_{existing + count:04d}.wav"
        save_wav(chunk, str(path), cfg.sample_rate)
        count += 1

    print(f"Chunked {filepath} → {count} segments")
    return count


def download_datasets(cfg: WakeWordConfig) -> int:
    """Download free audio datasets for negative samples."""
    import urllib.request
    import tarfile
    import zipfile

    total = 0
    dl_dir = Path("downloads")
    dl_dir.mkdir(exist_ok=True)

    # ESC-50: Environmental Sound Classification (50 categories, 2000 clips)
    esc_url = "https://github.com/karolpiczak/ESC-50/archive/master.zip"
    esc_zip = dl_dir / "esc50.zip"
    esc_dir = dl_dir / "ESC-50-master" / "audio"

    if not esc_dir.exists():
        print("Downloading ESC-50 dataset (environmental sounds)...")
        try:
            urllib.request.urlretrieve(esc_url, str(esc_zip))
            with zipfile.ZipFile(str(esc_zip)) as zf:
                zf.extractall(str(dl_dir))
            print("  Downloaded and extracted ESC-50")
        except Exception as e:
            print(f"  Failed to download ESC-50: {e}")
            print("  You can manually download environmental sound WAVs into negatives/")

    if esc_dir.exists():
        for wav_file in sorted(esc_dir.glob("*.wav"))[:500]:  # Use up to 500
            total += chunk_audio_file(str(wav_file), cfg)

    return total


def main():
    parser = argparse.ArgumentParser(description="Collect negative samples")
    parser.add_argument("--record", type=int, default=0, help="Record N seconds of ambient noise")
    parser.add_argument("--speech", type=int, default=0, help="Record N seconds of speech (not hey jane)")
    parser.add_argument("--generate", type=int, default=0, help="Generate N synthetic negatives")
    parser.add_argument("--chunk", type=str, default=None, help="Chunk a .wav file into negatives")
    parser.add_argument("--download", action="store_true", help="Download free datasets")
    parser.add_argument("--all", action="store_true", help="Record 60s ambient + 60s speech + 200 synthetic")
    args = parser.parse_args()

    cfg = WakeWordConfig()
    NEGATIVES_DIR.mkdir(exist_ok=True)

    total = 0

    if args.all:
        args.record = 60
        args.speech = 60
        args.generate = 200

    if args.record > 0:
        total += record_ambient(args.record, cfg)

    if args.speech > 0:
        total += record_speech(args.speech, cfg)

    if args.generate > 0:
        total += generate_synthetic(args.generate, cfg)

    if args.chunk:
        total += chunk_audio_file(args.chunk, cfg)

    if args.download:
        total += download_datasets(cfg)

    if total == 0 and not any([args.record, args.speech, args.generate, args.chunk, args.download]):
        print("Usage:")
        print("  python collect_negatives.py --record 60      # 60s ambient noise")
        print("  python collect_negatives.py --speech 60       # 60s of your speech")
        print("  python collect_negatives.py --generate 500    # 500 synthetic samples")
        print("  python collect_negatives.py --all             # All of the above")
        print("  python collect_negatives.py --download        # Download ESC-50 dataset")

    existing = list(NEGATIVES_DIR.glob("*.wav"))
    print(f"\nTotal negative samples: {len(existing)}")


if __name__ == "__main__":
    main()
