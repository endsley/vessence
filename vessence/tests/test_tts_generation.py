from jane_web.tts_generation import (
    tts_cache_key,
    tts_cache_paths,
    tts_chunk_wav_path,
    tts_combined_wav_path,
    tts_docker_command,
    tts_ffmpeg_command,
    tts_gpu_flags,
)


def test_tts_cache_paths_preserve_existing_md5_layout():
    paths = tts_cache_paths("/data", "hello")

    assert tts_cache_key("hello") == "5d41402abc4b"
    assert paths.cache_dir == "/data/cache/tts"
    assert paths.ogg_path == "/data/cache/tts/5d41402abc4b.ogg"
    assert paths.legacy_wav_path == "/data/cache/tts/5d41402abc4b.wav"


def test_tts_chunk_and_combined_wav_paths_preserve_names():
    assert tts_chunk_wav_path("/tmp/tts", 7) == "/tmp/tts/chunk_007.wav"
    assert tts_combined_wav_path("/tmp/tts") == "/tmp/tts/combined.wav"


def test_tts_gpu_flags_follow_nvidia_smi_existence(tmp_path):
    nvidia_smi = tmp_path / "nvidia-smi"

    assert tts_gpu_flags(str(nvidia_smi)) == []
    nvidia_smi.write_text("")
    assert tts_gpu_flags(str(nvidia_smi)) == ["--gpus", "all"]


def test_tts_docker_command_preserves_container_arguments():
    assert tts_docker_command(
        tmp_dir="/tmp/tts",
        chunk="Hello.",
        speaker="Barbora MacLean",
        index=3,
        gpu_flags=["--gpus", "all"],
    ) == [
        "docker",
        "run",
        "--rm",
        "--gpus",
        "all",
        "--memory=4g",
        "--cpus=2",
        "-e",
        "COQUI_TOS_AGREED=1",
        "-v",
        "/tmp/tts:/output",
        "ghcr.io/coqui-ai/tts:latest",
        "--text",
        "Hello.",
        "--model_name",
        "tts_models/multilingual/multi-dataset/xtts_v2",
        "--speaker_idx",
        "Barbora MacLean",
        "--language_idx",
        "en",
        "--out_path",
        "/output/chunk_003.wav",
    ]


def test_tts_ffmpeg_command_preserves_opus_arguments():
    assert tts_ffmpeg_command("/tmp/tts/combined.wav", "/data/cache/tts/out.ogg") == [
        "ffmpeg",
        "-y",
        "-i",
        "/tmp/tts/combined.wav",
        "-c:a",
        "libopus",
        "-b:a",
        "48k",
        "/data/cache/tts/out.ogg",
    ]
