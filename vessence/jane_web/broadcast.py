"""Lightweight broadcast system for Jane chat events.

Instead of raw streaming deltas, broadcasts periodic Gemini-summarized
status updates so other clients see concise progress like:
  "Jane is explaining the USB sync architecture and recommending cron..."
"""
import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field

logger = logging.getLogger("jane.broadcast")

SUMMARY_INTERVAL_SECONDS = float(os.environ.get("BROADCAST_SUMMARY_INTERVAL", "3.0"))
CLAUDE_CLI = os.environ.get("CLAUDE_CLI_PATH", "claude")

_SUMMARY_SYSTEM = (
    "You summarize an AI assistant's in-progress response for a status display. "
    "Write ONE short sentence (max 20 words) describing what the assistant is currently "
    "doing or explaining. Use present tense. Be specific about the topic, not generic. "
    'Examples: "Explaining how to fix the USB backup script using rsync" '
    '"Writing a broadcast system with SSE endpoints for real-time updates" '
    '"Debugging why Android TTS is silent — checking the VoiceController flow"'
)


def _summarize_sync(user_message: str, partial_response: str) -> str:
    """Call Claude Haiku via CLI to summarize the partial response."""
    try:
        import subprocess

        prompt = (
            f"{_SUMMARY_SYSTEM}\n\n"
            f"User asked: {user_message[:200]}\n\n"
            f"Partial response so far ({len(partial_response)} chars):\n"
            f"{partial_response[:1500]}\n\n"
            "Write ONE sentence summarizing what the assistant is currently working on:"
        )
        result = subprocess.run(
            [CLAUDE_CLI, "--model", "haiku", "--print"],
            input=prompt,
            capture_output=True,
            text=True,
            # 50s — Haiku CLI routinely takes 10-30s cold, 3-8s warm, and
            # occasional slower responses are real, not hangs. Previously
            # 10s which tripped too frequently (2026-04-18 investigation).
            timeout=50,
        )
        summary = result.stdout.strip() if result.returncode == 0 else ""
        # Log for quality evaluation
        if summary:
            try:
                import json as _json
                import datetime as _dt
                log_path = os.path.join(
                    os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data")),
                    "logs", "haiku_summaries.jsonl",
                )
                os.makedirs(os.path.dirname(log_path), exist_ok=True)
                # Truncate log if it exceeds 2MB to prevent disk growth
                try:
                    if os.path.exists(log_path) and os.path.getsize(log_path) > 2 * 1024 * 1024:
                        # Keep only the last 500 lines
                        with open(log_path, "r") as rf:
                            lines = rf.readlines()
                        with open(log_path, "w") as wf:
                            wf.writelines(lines[-500:])
                except Exception:
                    pass
                entry = _json.dumps({
                    "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                    "model": "haiku",
                    "source": "broadcast",
                    "user_msg": user_message[:150],
                    "partial_len": len(partial_response),
                    "summary": summary,
                })
                with open(log_path, "a") as f:
                    f.write(entry + "\n")
            except Exception:
                pass
        return summary
    except Exception as exc:
        logger.warning("Broadcast summary failed: %s", exc)
        return ""


@dataclass
class BroadcastEvent:
    """A single broadcast event sent to listening clients."""
    event_type: str          # "start", "progress", "done", "error"
    data: str | None = None
    source_session: str = ""
    source_platform: str = ""
    user_message: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_json(self) -> str:
        return json.dumps({
            "type": self.event_type,
            "data": self.data,
            "source_session": self.source_session[:12] if self.source_session else "",
            "source_platform": self.source_platform,
            "user_message": self.user_message,
            "ts": self.timestamp,
        }, ensure_ascii=True)


class BroadcastManager:
    """Per-user broadcast channels with periodic summarized updates."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[asyncio.Queue[BroadcastEvent]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, user_id: str) -> asyncio.Queue[BroadcastEvent]:
        q: asyncio.Queue[BroadcastEvent] = asyncio.Queue(maxsize=128)
        async with self._lock:
            if user_id not in self._listeners:
                self._listeners[user_id] = []
            self._listeners[user_id].append(q)
        logger.info("Broadcast: user=%s subscribed (total=%d)", user_id, len(self._listeners.get(user_id, [])))
        return q

    async def unsubscribe(self, user_id: str, q: asyncio.Queue[BroadcastEvent]) -> None:
        async with self._lock:
            listeners = self._listeners.get(user_id, [])
            try:
                listeners.remove(q)
            except ValueError:
                pass
            if not listeners:
                self._listeners.pop(user_id, None)
        logger.info("Broadcast: user=%s unsubscribed", user_id)

    def has_listeners(self, user_id: str) -> bool:
        return bool(self._listeners.get(user_id))

    def publish(self, user_id: str, event: BroadcastEvent) -> None:
        listeners = self._listeners.get(user_id, [])
        for q in listeners:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass


# Singleton
broadcast_manager = BroadcastManager()


class StreamBroadcaster:
    """Attaches to a stream_message flow and periodically broadcasts
    Gemini-summarized progress updates to other clients.

    Usage in stream_message:
        broadcaster = StreamBroadcaster(user_id, session_id, platform, user_message)
        # on each delta:
        broadcaster.feed_delta(chunk)
        # on done:
        broadcaster.finish(final_text)
        # on error:
        broadcaster.error(msg)
    """

    def __init__(
        self,
        user_id: str,
        session_id: str,
        platform: str,
        user_message: str,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        self._user_id = user_id
        self._session_id = session_id
        self._platform = platform or ""
        self._user_message = user_message
        self._loop = loop or asyncio.get_event_loop()
        self._accumulated = ""
        self._last_summary_at = 0.0
        self._last_summary_text = ""
        self._summary_task: asyncio.Task | None = None
        self._started = False

    def start(self) -> None:
        """Broadcast that Jane started working on a message."""
        if not broadcast_manager.has_listeners(self._user_id):
            return
        self._started = True
        broadcast_manager.publish(self._user_id, BroadcastEvent(
            event_type="start",
            data="Jane is working...",
            source_session=self._session_id,
            source_platform=self._platform,
            user_message=self._user_message[:200],
        ))

    def feed_delta(self, chunk: str) -> None:
        """Feed a response chunk. Triggers a summary if interval elapsed."""
        if not self._started:
            return
        self._accumulated += chunk
        now = time.time()
        if now - self._last_summary_at >= SUMMARY_INTERVAL_SECONDS and len(self._accumulated) > 50:
            if self._summary_task is None or self._summary_task.done():
                self._last_summary_at = now
                snapshot = self._accumulated
                self._summary_task = asyncio.ensure_future(
                    self._summarize_and_publish(snapshot),
                    loop=self._loop,
                )

    async def _summarize_and_publish(self, partial: str) -> None:
        try:
            summary = await asyncio.to_thread(_summarize_sync, self._user_message, partial)
            if summary and summary != self._last_summary_text:
                self._last_summary_text = summary
                broadcast_manager.publish(self._user_id, BroadcastEvent(
                    event_type="progress",
                    data=summary,
                    source_session=self._session_id,
                    source_platform=self._platform,
                    user_message=self._user_message[:200],
                ))
        except Exception as exc:
            logger.warning("Broadcast summary task error: %s", exc)

    def finish(self, final_text: str) -> None:
        """Broadcast that Jane finished."""
        if not self._started:
            return
        # Cancel any pending summary
        if self._summary_task and not self._summary_task.done():
            self._summary_task.cancel()
        broadcast_manager.publish(self._user_id, BroadcastEvent(
            event_type="done",
            data=final_text[:300] if final_text else "",
            source_session=self._session_id,
            source_platform=self._platform,
            user_message=self._user_message[:200],
        ))

    def error(self, msg: str) -> None:
        """Broadcast an error."""
        if not self._started:
            return
        broadcast_manager.publish(self._user_id, BroadcastEvent(
            event_type="error",
            data=msg[:200],
            source_session=self._session_id,
            source_platform=self._platform,
            user_message=self._user_message[:200],
        ))
