"""XTTS-v2 model lifecycle manager with idle auto-unload."""

import asyncio
import logging
import time
import threading
import numpy as np

from tts_engine.v1.config import MODEL_NAME, DEFAULT_SPEAKER, DEFAULT_LANGUAGE, SAMPLE_RATE, IDLE_TIMEOUT_SECONDS

logger = logging.getLogger("tts_server.model")


class XttsModelManager:
    """Singleton that loads/unloads XTTS-v2 on demand with idle timeout."""

    def __init__(self):
        self._tts = None
        self._lock = threading.Lock()
        self._last_used = 0.0
        self._idle_task: asyncio.Task | None = None
        self._loaded = False
        self._active_streams = 0
        self._stream_lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def idle_seconds(self) -> float:
        if not self._loaded:
            return -1
        return time.time() - self._last_used

    @property
    def active_streams(self) -> int:
        return self._active_streams

    def load(self):
        """Load model to GPU. Thread-safe, idempotent."""
        with self._lock:
            if self._loaded:
                self._last_used = time.time()
                return
            logger.info("Loading XTTS-v2 model to GPU...")
            t0 = time.time()
            from TTS.api import TTS
            self._tts = TTS(model_name=MODEL_NAME, gpu=True)
            self._loaded = True
            self._last_used = time.time()
            logger.info("XTTS-v2 loaded in %.1fs", time.time() - t0)

    def unload(self):
        """Unload model and free GPU memory. Refuses if streams are active."""
        with self._stream_lock:
            if self._active_streams > 0:
                logger.warning("Cannot unload: %d active streams", self._active_streams)
                return
        with self._lock:
            if not self._loaded:
                return
            logger.info("Unloading XTTS-v2 from GPU...")
            del self._tts
            self._tts = None
            self._loaded = False
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            import gc
            gc.collect()
            logger.info("XTTS-v2 unloaded, VRAM freed.")

    def _touch(self):
        self._last_used = time.time()

    def _enter_stream(self):
        with self._stream_lock:
            self._active_streams += 1

    def _exit_stream(self):
        with self._stream_lock:
            self._active_streams = max(0, self._active_streams - 1)

    def generate(self, text: str, speaker: str = DEFAULT_SPEAKER,
                 language: str = DEFAULT_LANGUAGE) -> np.ndarray:
        """Generate full audio for text. Returns numpy array of float32 samples."""
        self.load()
        self._enter_stream()
        try:
            self._touch()
            with self._lock:
                wav = self._tts.tts(text=text, speaker=speaker, language=language)
            self._touch()
            return np.array(wav, dtype=np.float32)
        finally:
            self._exit_stream()

    def generate_chunks(self, text: str, speaker: str = DEFAULT_SPEAKER,
                        language: str = DEFAULT_LANGUAGE):
        """Generate audio for text, yielding sentence-level chunks as numpy arrays."""
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        merged = []
        current = ""
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if current and len(current) + len(s) + 1 <= 150:
                current += " " + s
            else:
                if current:
                    merged.append(current)
                current = s
        if current:
            merged.append(current)
        if not merged:
            merged = [text[:500]]

        self.load()
        self._enter_stream()
        try:
            for chunk_text in merged:
                self._touch()
                with self._lock:
                    if not self._loaded:
                        logger.error("Model was unloaded during stream")
                        return
                    wav = self._tts.tts(text=chunk_text, speaker=speaker, language=language)
                self._touch()
                yield np.array(wav, dtype=np.float32)
        finally:
            self._exit_stream()

    async def start_idle_monitor(self):
        """Start background task that unloads model after idle timeout."""
        async def _monitor():
            while True:
                await asyncio.sleep(30)
                if (self._loaded
                        and self._active_streams == 0
                        and (time.time() - self._last_used) > IDLE_TIMEOUT_SECONDS):
                    logger.info("Idle timeout reached (%.0fs), unloading model...",
                                time.time() - self._last_used)
                    self.unload()
        self._idle_task = asyncio.create_task(_monitor())

    def stop_idle_monitor(self):
        if self._idle_task:
            self._idle_task.cancel()


# Module-level singleton
manager = XttsModelManager()
