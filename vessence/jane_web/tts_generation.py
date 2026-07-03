"""Planning helpers for the web TTS generation route."""
from __future__ import annotations

import hashlib
import os
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class TtsCachePaths:
    cache_dir: str
    ogg_path: str
    legacy_wav_path: str


def tts_cache_key(text: str) -> str:
    """Return the existing short md5 cache key used for generated TTS audio."""
    return hashlib.md5(text.encode()).hexdigest()[:12]


def tts_cache_paths(data_home: str, text: str) -> TtsCachePaths:
    cache_dir = os.path.join(data_home, "cache", "tts")
    text_hash = tts_cache_key(text)
    return TtsCachePaths(
        cache_dir=cache_dir,
        ogg_path=os.path.join(cache_dir, f"{text_hash}.ogg"),
        legacy_wav_path=os.path.join(cache_dir, f"{text_hash}.wav"),
    )


def tts_gpu_flags(nvidia_smi_path: str = "/usr/bin/nvidia-smi") -> list[str]:
    return ["--gpus", "all"] if os.path.exists(nvidia_smi_path) else []


def tts_chunk_wav_path(tmp_dir: str, index: int) -> str:
    return os.path.join(tmp_dir, f"chunk_{index:03d}.wav")


def tts_combined_wav_path(tmp_dir: str) -> str:
    return os.path.join(tmp_dir, "combined.wav")


def tts_docker_command(
    *,
    tmp_dir: str,
    chunk: str,
    speaker: str,
    index: int,
    gpu_flags: Sequence[str] = (),
) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        *gpu_flags,
        "--memory=4g",
        "--cpus=2",
        "-e",
        "COQUI_TOS_AGREED=1",
        "-v",
        f"{tmp_dir}:/output",
        "ghcr.io/coqui-ai/tts:latest",
        "--text",
        chunk,
        "--model_name",
        "tts_models/multilingual/multi-dataset/xtts_v2",
        "--speaker_idx",
        speaker,
        "--language_idx",
        "en",
        "--out_path",
        f"/output/chunk_{index:03d}.wav",
    ]


def tts_ffmpeg_command(combined_wav: str, ogg_path: str) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-i",
        combined_wav,
        "-c:a",
        "libopus",
        "-b:a",
        "48k",
        ogg_path,
    ]
