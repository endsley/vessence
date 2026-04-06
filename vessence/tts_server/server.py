"""Standalone XTTS-v2 TTS server with streaming support.

Run: python -m uvicorn tts_server.server:app --port 8095
"""

import os
os.environ.setdefault("COQUI_TOS_AGREED", "1")

import struct
import asyncio
import logging
import time

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel

from tts_server.config import PORT, HOST, SAMPLE_RATE, DEFAULT_SPEAKER, DEFAULT_LANGUAGE, MAX_TEXT_LENGTH
from tts_server.model_manager import manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("tts_server")

app = FastAPI(title="XTTS-v2 TTS Server", version="1.0.0")


class TtsRequest(BaseModel):
    text: str
    speaker: str = DEFAULT_SPEAKER
    language: str = DEFAULT_LANGUAGE


def _float32_to_int16(audio: np.ndarray) -> bytes:
    """Convert float32 audio [-1, 1] to 16-bit PCM bytes."""
    audio = np.clip(audio, -1.0, 1.0)
    int16 = (audio * 32767).astype(np.int16)
    return int16.tobytes()


def _make_wav_header(data_size: int, sample_rate: int = SAMPLE_RATE,
                     channels: int = 1, bits: int = 16) -> bytes:
    """Build a WAV file header."""
    byte_rate = sample_rate * channels * (bits // 8)
    block_align = channels * (bits // 8)
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        36 + data_size,
        b'WAVE',
        b'fmt ',
        16,           # chunk size
        1,            # PCM format
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits,
        b'data',
        data_size,
    )
    return header


@app.on_event("startup")
async def startup():
    await manager.start_idle_monitor()
    logger.info("TTS server started on %s:%d", HOST, PORT)


@app.on_event("shutdown")
async def shutdown():
    manager.stop_idle_monitor()
    manager.unload()


@app.get("/tts/health")
async def health():
    return {
        "status": "ok",
        "model_loaded": manager.is_loaded,
        "idle_seconds": round(manager.idle_seconds, 1),
    }


@app.post("/tts/generate")
async def generate(req: TtsRequest):
    """Generate complete WAV file for text. Used for summarization reads."""
    if not req.text.strip():
        raise HTTPException(422, "text is required")
    if len(req.text) > MAX_TEXT_LENGTH:
        raise HTTPException(422, f"text exceeds {MAX_TEXT_LENGTH} characters")

    loop = asyncio.get_event_loop()
    try:
        audio = await loop.run_in_executor(
            None, manager.generate, req.text, req.speaker, req.language
        )
    except Exception as e:
        logger.error("TTS generation failed: %s", e)
        raise HTTPException(500, f"TTS generation failed: {e}")

    pcm = _float32_to_int16(audio)
    wav_header = _make_wav_header(len(pcm))

    return Response(
        content=wav_header + pcm,
        media_type="audio/wav",
        headers={"Content-Disposition": "inline; filename=tts.wav"},
    )


@app.post("/tts/stream")
async def stream(req: TtsRequest, request: Request):
    """Stream audio as chunked raw 16-bit PCM at 24kHz, mono.

    Each chunk is a sentence worth of audio, sent as soon as it's generated.
    The first 12 bytes are a header: sample_rate (4 bytes LE int),
    channels (4 bytes LE int), bits_per_sample (4 bytes LE int).
    After that, raw PCM int16 data flows continuously.
    """
    if not req.text.strip():
        raise HTTPException(422, "text is required")
    if len(req.text) > MAX_TEXT_LENGTH:
        raise HTTPException(422, f"text exceeds {MAX_TEXT_LENGTH} characters")

    loop = asyncio.get_event_loop()
    # Bounded queue prevents unbounded memory if client is slow
    queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=8)
    cancelled = asyncio.Event()

    def _produce():
        try:
            # Header
            _queue_put(struct.pack('<III', SAMPLE_RATE, 1, 16))
            if cancelled.is_set():
                return
            for chunk_audio in manager.generate_chunks(req.text, req.speaker, req.language):
                if cancelled.is_set():
                    logger.info("Stream cancelled by client disconnect")
                    return
                pcm = _float32_to_int16(chunk_audio)
                _queue_put(pcm)
        except Exception as e:
            logger.error("Stream generation error: %s", e)
        finally:
            _queue_put(None)  # sentinel

    def _queue_put(item):
        try:
            asyncio.run_coroutine_threadsafe(queue.put(item), loop).result(timeout=60)
        except Exception:
            cancelled.set()

    async def _stream_response():
        producer = loop.run_in_executor(None, _produce)
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    cancelled.set()
                    break
                try:
                    chunk = await asyncio.wait_for(queue.get(), timeout=60)
                except asyncio.TimeoutError:
                    logger.warning("Stream chunk timeout, ending stream")
                    break
                if chunk is None:
                    break
                yield chunk
        finally:
            cancelled.set()
            # Wait for producer to finish
            try:
                await asyncio.wait_for(asyncio.shield(producer), timeout=5)
            except (asyncio.TimeoutError, Exception):
                pass

    return StreamingResponse(
        _stream_response(),
        media_type="application/octet-stream",
        headers={
            "X-Audio-Sample-Rate": str(SAMPLE_RATE),
            "X-Audio-Channels": "1",
            "X-Audio-Bits": "16",
        },
    )


@app.post("/tts/unload")
async def unload():
    """Manually unload model from GPU. Will not unload during active generation."""
    if manager.active_streams > 0:
        raise HTTPException(409, f"Cannot unload: {manager.active_streams} active stream(s)")
    manager.unload()
    return {"status": "unloaded"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)
