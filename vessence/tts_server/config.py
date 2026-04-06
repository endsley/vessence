"""TTS Server configuration constants."""

import os

PORT = int(os.getenv("TTS_SERVER_PORT", "8095"))
HOST = os.getenv("TTS_SERVER_HOST", "0.0.0.0")

# XTTS-v2 settings
MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
DEFAULT_SPEAKER = os.getenv("TTS_SPEAKER", "Barbora MacLean")
DEFAULT_LANGUAGE = os.getenv("TTS_LANGUAGE", "en")
SAMPLE_RATE = 24000  # XTTS-v2 native sample rate

# Idle management — unload model from GPU after this many seconds of no requests
IDLE_TIMEOUT_SECONDS = int(os.getenv("TTS_IDLE_TIMEOUT", "300"))  # 5 minutes

# Generation limits
MAX_TEXT_LENGTH = 2000
CHUNK_MAX_CHARS = 150  # split long text into chunks for streaming
