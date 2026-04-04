#!/usr/bin/env python3
"""
Voice conversation daemon for Jane.

Always-on loop:
  1. Listen for wake word via OpenWakeWord ("hey jarvis" for now)
  2. On detection -> chime -> STT (faster_whisper) -> send to Jane API -> TTS (edge_tts)
  3. Loop STT/TTS until silence timeout or exit phrase
  4. Return to wake word listening

Works headless (screen off). Runs as a systemd service.
"""

import argparse
import asyncio
import io
import logging
import os
import re
import signal
import tempfile
import time
import wave

import numpy as np
import sounddevice as sd

# ── Config ─────────────────────────────────────────────────────────────
JANE_API = os.environ.get("JANE_API", "http://localhost:8081")
SESSION_ID = "voice-daemon"
SAMPLE_RATE = 16000
OWW_CHUNK = 1280  # 80ms — what OpenWakeWord expects

TTS_VOICE = "en-US-AriaNeural"
TTS_RATE = "+0%"
TTS_VOLUME = "+0%"
TTS_MAX_CHARS = 2000

# ── Logging ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("VoiceDaemon")

# ── TTS text cleaning (same as jane/tts.py) ───────────────────────────
_CLEAN_PATTERNS = [
    (re.compile(r'```[\s\S]*?```'), ''),
    (re.compile(r'`[^`]+`'), ''),
    (re.compile(r'\[([^\]]+)\]\([^)]+\)'), r'\1'),
    (re.compile(r'https?://\S+'), ''),
    (re.compile(r'[#*_~|>]'), ''),
    (re.compile(r'\|[^\n]+\|'), ''),
    (re.compile(r'[-=]{3,}'), ''),
    (re.compile(r'\n{3,}'), '\n\n'),
]


def clean_for_speech(text: str) -> str:
    for pattern, replacement in _CLEAN_PATTERNS:
        text = pattern.sub(replacement, text)
    text = text.strip()
    if len(text) > TTS_MAX_CHARS:
        text = text[:TTS_MAX_CHARS] + "..."
    return text


# ── Wake Word via OpenWakeWord ─────────────────────────────────────────
class WakeWordListener:
    def __init__(self, model_name: str = "hey_jarvis_v0.1", threshold: float = 0.5,
                 custom_model_path: str = None):
        from openwakeword.model import Model

        if custom_model_path:
            self.model = Model(
                wakeword_models=[custom_model_path],
                inference_framework="onnx",
            )
        else:
            self.model = Model(
                wakeword_models=[model_name],
                inference_framework="onnx",
            )
        self.threshold = threshold
        self.model_names = list(self.model.models.keys())
        log.info("Wake word models loaded: %s (threshold=%.2f)", self.model_names, threshold)

    def check(self, audio_int16: np.ndarray) -> tuple[bool, str, float]:
        """Feed audio chunk. Returns (detected, model_name, score)."""
        prediction = self.model.predict(audio_int16)
        for name, score in prediction.items():
            if score >= self.threshold:
                return True, name, score
        return False, "", 0.0

    def reset(self):
        self.model.reset()


# ── STT via faster_whisper ─────────────────────────────────────────────
class STTEngine:
    def __init__(self, model_size: str = "base"):
        from faster_whisper import WhisperModel
        log.info("Loading Whisper model '%s'...", model_size)
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        log.info("Whisper model loaded.")

    def transcribe(self, audio_f32: np.ndarray) -> str:
        """Transcribe float32 audio array to text."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes((audio_f32 * 32767).astype(np.int16).tobytes())
        buf.seek(0)
        segments, _ = self.model.transcribe(buf, language="en", beam_size=3)
        return " ".join(seg.text.strip() for seg in segments).strip()


# ── TTS via edge_tts ───────────────────────────────────────────────────
async def speak_text(text: str):
    """Generate speech with edge_tts and play via ffplay."""
    clean = clean_for_speech(text)
    if len(clean) < 3:
        return

    import edge_tts

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3", prefix="jane_voice_")
    os.close(tmp_fd)
    try:
        communicate = edge_tts.Communicate(clean, TTS_VOICE, rate=TTS_RATE, volume=TTS_VOLUME)
        await communicate.save(tmp_path)
        proc = await asyncio.create_subprocess_exec(
            "ffplay", "-nodisp", "-autoexit", "-loglevel", "error", tmp_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ── Chime ──────────────────────────────────────────────────────────────
async def play_chime():
    """Short two-tone chime to signal 'I'm listening'."""
    sr = 24000
    t = np.linspace(0, 0.25, int(sr * 0.25), dtype=np.float32)
    chime = 0.3 * (np.sin(2 * np.pi * 523 * t) + np.sin(2 * np.pi * 659 * t))
    chime *= np.linspace(1.0, 0.0, len(chime), dtype=np.float32)  # fade out
    sd.play(chime, samplerate=sr)
    sd.wait()


# ── Jane API ───────────────────────────────────────────────────────────
async def send_to_jane(text: str) -> str:
    import aiohttp
    payload = {
        "message": text,
        "session_id": SESSION_ID,
        "platform": "voice",
        "tts_enabled": False,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{JANE_API}/api/jane/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response", "")
                log.error("Jane API returned %d", resp.status)
                return "Sorry, I couldn't process that."
    except Exception as e:
        log.error("Jane API error: %s", e)
        return "Sorry, I'm having trouble connecting."


# ── Record until silence ───────────────────────────────────────────────
def record_until_silence(
    silence_threshold: float = 0.012,
    silence_duration: float = 1.5,
    max_duration: float = 30.0,
    initial_wait: float = 4.0,
) -> np.ndarray | None:
    """Record from mic until silence. Returns float32 array or None."""
    chunk_ms = 100
    chunk_samples = int(SAMPLE_RATE * chunk_ms / 1000)
    max_chunks = int(max_duration * 1000 / chunk_ms)
    silence_needed = int(silence_duration * 1000 / chunk_ms)
    wait_chunks = int(initial_wait * 1000 / chunk_ms)

    chunks = []
    silence_count = 0
    speech_found = False

    log.info("Listening for speech...")

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype=np.float32,
                        blocksize=chunk_samples) as stream:
        for i in range(max_chunks):
            audio, _ = stream.read(chunk_samples)
            audio = audio.flatten()
            chunks.append(audio)

            rms = np.sqrt(np.mean(audio ** 2))
            if rms > silence_threshold:
                speech_found = True
                silence_count = 0
            else:
                silence_count += 1

            if i >= wait_chunks and not speech_found:
                log.info("No speech after %.1fs — back to wake word.", initial_wait)
                return None

            if speech_found and silence_count >= silence_needed:
                log.info("End of speech (%.1fs recorded).", len(chunks) * chunk_ms / 1000)
                break

    return np.concatenate(chunks) if speech_found else None


# ── Exit detection ─────────────────────────────────────────────────────
EXIT_PHRASES = {
    "goodbye", "bye", "bye bye", "see you", "see ya",
    "stop", "quit", "exit", "that's all", "thank you bye",
    "good night", "goodnight", "nevermind", "never mind",
}


def is_exit(text: str) -> bool:
    return text.strip().lower().rstrip(".!,") in EXIT_PHRASES


# ── Voice conversation loop ───────────────────────────────────────────
async def voice_conversation(stt: STTEngine):
    await play_chime()
    log.info("=== Voice conversation started ===")

    turn = 0
    while True:
        audio = record_until_silence()
        if audio is None:
            log.info("Silence — ending conversation." if turn else "No speech after wake word.")
            break

        text = stt.transcribe(audio)
        log.info("You: %s", text)

        if not text or len(text.strip()) < 2:
            log.info("Empty transcription, trying again...")
            continue

        if is_exit(text):
            await speak_text("Goodbye!")
            break

        log.info("Sending to Jane...")
        response = await send_to_jane(text)
        log.info("Jane: %s", response[:200])

        await speak_text(response)
        turn += 1

    log.info("=== Voice conversation ended ===")


# ── Main daemon loop ──────────────────────────────────────────────────
async def main_loop(args):
    # Wake word
    ww = WakeWordListener(
        model_name=args.wakeword_model,
        threshold=args.threshold,
        custom_model_path=args.custom_model,
    )

    # STT
    stt = STTEngine(args.whisper_model)

    log.info("=== Jane Voice Daemon Ready ===")
    log.info("Say '%s' to start a conversation.", args.wakeword_model)

    while True:
        # Wake word listening loop
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                                dtype="int16", blocksize=OWW_CHUNK) as stream:
                while True:
                    audio, _ = stream.read(OWW_CHUNK)
                    audio = audio.flatten()
                    detected, name, score = ww.check(audio)
                    if detected:
                        log.info("*** Wake word '%s' detected (score=%.3f) ***", name, score)
                        break
        except sd.PortAudioError as e:
            log.error("Audio error: %s — retrying in 5s", e)
            await asyncio.sleep(5)
            continue

        # Conversation
        try:
            await voice_conversation(stt)
        except Exception as e:
            log.error("Conversation error: %s", e, exc_info=True)

        ww.reset()
        log.info("Returning to wake word listening...")
        await asyncio.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description="Jane Voice Daemon")
    parser.add_argument("--wakeword-model", default="hey_jarvis_v0.1",
                        help="OpenWakeWord model name (default: hey_jarvis_v0.1)")
    parser.add_argument("--custom-model", default=None,
                        help="Path to custom .onnx wake word model")
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="Wake word detection threshold (default: 0.5)")
    parser.add_argument("--whisper-model", default="base",
                        help="Whisper model size: tiny/base/small/medium")
    args = parser.parse_args()

    loop = asyncio.new_event_loop()

    def shutdown(sig):
        log.info("Received %s, shutting down...", signal.Signals(sig).name)
        loop.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown, sig)

    try:
        loop.run_until_complete(main_loop(args))
    except KeyboardInterrupt:
        log.info("Interrupted.")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
