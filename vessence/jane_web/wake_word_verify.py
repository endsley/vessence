"""Stage 2 wake word verification using Whisper-tiny.

Receives 1 second of raw PCM audio, transcribes it, and checks
if the transcript contains the wake word (fuzzy match for "jane"/"james"/"jayne").

Returns True if verified, False if false positive.
"""

import logging
import time
import numpy as np

logger = logging.getLogger(__name__)

# Lazy-load the model on first use
_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        logger.info("Loading Whisper-tiny.en model for wake word verification...")
        t0 = time.time()
        _model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
        logger.info("Whisper-tiny loaded in %.1fs", time.time() - t0)
    return _model


# Fuzzy match: Whisper sometimes transcribes "Jane" as "James", "Jayne", "J", "Chain", etc.
_WAKE_WORD_MATCHES = {"jane", "james", "jayne", "jain", "jeanne", "j"}


def verify_wake_word(audio_pcm_int16: bytes, sample_rate: int = 16000) -> dict:
    """Verify if the audio contains the wake word.

    Args:
        audio_pcm_int16: Raw 16-bit PCM audio bytes (mono, 16kHz)
        sample_rate: Sample rate (should be 16000)

    Returns:
        {"verified": bool, "transcript": str, "duration_ms": int}
    """
    t0 = time.time()

    # Convert bytes to float32
    audio = np.frombuffer(audio_pcm_int16, dtype=np.int16).astype(np.float32) / 32768.0

    if len(audio) < sample_rate * 0.3:  # less than 0.3s
        return {"verified": False, "transcript": "", "duration_ms": 0}

    model = _get_model()
    segments, _ = model.transcribe(audio, language="en")
    transcript = " ".join(s.text.strip() for s in segments).strip()

    elapsed_ms = int((time.time() - t0) * 1000)

    # Check if any wake word variant appears in the transcript
    words = set(transcript.lower().replace(",", "").replace(".", "").replace("!", "").replace("?", "").split())
    verified = bool(words & _WAKE_WORD_MATCHES)

    # Also check substrings for cases like "Hey, James" or "PJ"
    lower_transcript = transcript.lower()
    if not verified:
        verified = any(match in lower_transcript for match in _WAKE_WORD_MATCHES)

    logger.info("Wake word verify: transcript='%s' verified=%s (%dms)", transcript, verified, elapsed_ms)

    return {
        "verified": verified,
        "transcript": transcript,
        "duration_ms": elapsed_ms,
    }
