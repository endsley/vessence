"""
tts.py — Background TTS for Jane CLI using edge-tts + ffplay.

Speaks assistant responses without blocking the CLI. Only one utterance
plays at a time; if a new response arrives while the previous is still
speaking, the old one is cancelled.
"""

import asyncio
import logging
import os
import re
import tempfile

from jane.config import TTS_ENABLED, TTS_MAX_CHARS, TTS_RATE, TTS_VOICE, TTS_VOLUME

logger = logging.getLogger("JaneTTS")

# Strip markdown / code blocks / URLs so the voice reads cleanly
_CLEAN_PATTERNS = [
    (re.compile(r'```[\s\S]*?```'), ''),           # code blocks
    (re.compile(r'`[^`]+`'), ''),                   # inline code
    (re.compile(r'\[([^\]]+)\]\([^)]+\)'), r'\1'),  # markdown links → text
    (re.compile(r'https?://\S+'), ''),              # bare URLs
    (re.compile(r'[#*_~|>]'), ''),                  # markdown formatting chars
    (re.compile(r'\|[^\n]+\|'), ''),                # table rows
    (re.compile(r'[-=]{3,}'), ''),                  # horizontal rules
    (re.compile(r'\n{3,}'), '\n\n'),                # collapse blank lines
]


def _clean_for_speech(text: str) -> str:
    for pattern, replacement in _CLEAN_PATTERNS:
        text = pattern.sub(replacement, text)
    text = text.strip()
    if len(text) > TTS_MAX_CHARS:
        text = text[:TTS_MAX_CHARS] + "..."
    return text


class TTSEngine:
    def __init__(self):
        self.enabled = TTS_ENABLED
        self._current_task: asyncio.Task | None = None
        self._player_proc: asyncio.subprocess.Process | None = None

    async def speak(self, text: str):
        if not self.enabled:
            return

        clean = _clean_for_speech(text)
        if len(clean) < 5:
            return

        # Cancel any in-progress speech
        await self.stop()

        self._current_task = asyncio.create_task(self._speak_impl(clean))

    async def _speak_impl(self, text: str):
        tmp_path = None
        try:
            import edge_tts

            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3", prefix="jane_tts_")
            os.close(tmp_fd)

            communicate = edge_tts.Communicate(
                text, TTS_VOICE, rate=TTS_RATE, volume=TTS_VOLUME
            )
            await communicate.save(tmp_path)

            self._player_proc = await asyncio.create_subprocess_exec(
                "ffplay", "-nodisp", "-autoexit", "-loglevel", "error", tmp_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await self._player_proc.wait()

        except asyncio.CancelledError:
            if self._player_proc and self._player_proc.returncode is None:
                self._player_proc.kill()
            raise
        except Exception as e:
            logger.debug(f"TTS error: {e}")
        finally:
            self._player_proc = None
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    async def stop(self):
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass
        self._current_task = None

    async def shutdown(self):
        self.enabled = False
        await self.stop()
