"""Build speech negative samples for wake word training.

Processes LibriSpeech (or any FLAC/WAV speech corpus) into 1.5-second clips
at 16kHz mono — the format expected by OpenWakeWord feature extraction.

Usage:
    python build_speech_negatives.py [--source-dir PATH] [--output-dir PATH] [--max-clips N]

Default source: wake_word/downloads/LibriSpeech/
Default output: wake_word/negatives/ (prefixed with 'speech_')
"""

import argparse
import glob
import os
import random
import sys

import numpy as np

SAMPLE_RATE = 16000
CLIP_DURATION = 1.5  # seconds
CLIP_SAMPLES = int(SAMPLE_RATE * CLIP_DURATION)
MIN_ENERGY = 0.005  # skip near-silent clips


def load_audio(path: str) -> np.ndarray | None:
    """Load a FLAC or WAV file as float32 mono 16kHz."""
    try:
        import soundfile as sf
        audio, sr = sf.read(path, dtype="float32")
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
        if sr != SAMPLE_RATE:
            duration = len(audio) / sr
            target_len = int(duration * SAMPLE_RATE)
            indices = np.linspace(0, len(audio) - 1, target_len)
            audio = np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)
        return audio
    except Exception:
        return None


def save_wav(path: str, audio: np.ndarray, sr: int = SAMPLE_RATE):
    """Save float32 audio as 16-bit PCM WAV."""
    import wave
    audio_int16 = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio_int16.tobytes())


def slice_into_clips(audio: np.ndarray, rng: random.Random) -> list[np.ndarray]:
    """Slice long audio into CLIP_DURATION-second clips with random offsets."""
    clips = []
    if len(audio) < CLIP_SAMPLES:
        return clips

    pos = 0
    while pos + CLIP_SAMPLES <= len(audio):
        clip = audio[pos:pos + CLIP_SAMPLES]
        energy = np.sqrt(np.mean(clip ** 2))
        if energy > MIN_ENERGY:
            clips.append(clip)
        step = int(CLIP_SAMPLES * rng.uniform(0.75, 1.25))
        pos += step

    return clips


def main():
    parser = argparse.ArgumentParser(description="Build speech negatives from LibriSpeech")
    parser.add_argument("--source-dir", default=None, help="Directory with FLAC/WAV files")
    parser.add_argument("--output-dir", default=None, help="Output directory for clips")
    parser.add_argument("--max-clips", type=int, default=10000, help="Max clips to generate")
    parser.add_argument("--prefix", default="speech", help="Filename prefix")
    args = parser.parse_args()

    work_dir = os.path.dirname(os.path.abspath(__file__))
    source_dir = args.source_dir or os.path.join(work_dir, "downloads", "LibriSpeech")
    output_dir = args.output_dir or os.path.join(work_dir, "negatives")
    os.makedirs(output_dir, exist_ok=True)

    audio_files = []
    for pat in ("**/*.flac", "**/*.wav", "**/*.mp3"):
        audio_files.extend(glob.glob(os.path.join(source_dir, pat), recursive=True))

    if not audio_files:
        print(f"No audio files found in {source_dir}")
        sys.exit(1)

    random.shuffle(audio_files)
    print(f"Found {len(audio_files)} audio files in {source_dir}")
    print(f"Target: up to {args.max_clips} clips → {output_dir}/")

    rng = random.Random(42)
    clip_count = 0
    file_count = 0

    for filepath in audio_files:
        if clip_count >= args.max_clips:
            break

        audio = load_audio(filepath)
        if audio is None:
            continue

        file_count += 1
        clips = slice_into_clips(audio, rng)

        for clip in clips:
            if clip_count >= args.max_clips:
                break
            out_path = os.path.join(output_dir, f"{args.prefix}_{clip_count:05d}.wav")
            save_wav(out_path, clip)
            clip_count += 1

        if file_count % 100 == 0:
            print(f"  Processed {file_count} files → {clip_count} clips so far...")

    print(f"\nDone: {clip_count} clips from {file_count} files")
    print(f"Output: {output_dir}/{args.prefix}_*.wav")


if __name__ == "__main__":
    main()
