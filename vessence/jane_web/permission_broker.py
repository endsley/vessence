"""permission_broker.py — Real-time tool-permission gating for Jane web.

Coordinates between the PreToolUse hook (sync, runs inside CLI subprocess)
and the web frontend (async, serves the approve/deny UI).

Flow:
  1. Hook POST /api/jane/permission/request  → broker creates PermissionRequest, blocks
  2. Broker emits SSE "permission_request" event to the active stream
  3. Frontend shows approve/deny dialog
  4. User clicks → POST /api/jane/permission/respond → broker resolves the request
  5. Hook unblocks, returns approve or block to the CLI
"""

from __future__ import annotations

import asyncio
import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)

PERMISSION_TIMEOUT_SECONDS = 300  # 5 minutes max wait for user response


@dataclass
class PermissionRequest:
    request_id: str
    tool_name: str
    tool_input: dict
    session_id: str
    created_at: float = field(default_factory=time.time)
    resolved: asyncio.Event = field(default_factory=asyncio.Event)
    approved: bool = False
    reason: str = ""


class PermissionBroker:
    """Singleton broker managing pending permission requests."""

    def __init__(self) -> None:
        self._pending: dict[str, PermissionRequest] = {}
        self._emitters: dict[str, Callable] = {}  # session_id → emit()
        self._lock = threading.Lock()

    # ── Emitter registration (called by jane_proxy.stream_message) ────────

    def register_emitter(self, session_id: str, emit: Callable) -> None:
        with self._lock:
            self._emitters[session_id] = emit

    def unregister_emitter(self, session_id: str) -> None:
        with self._lock:
            self._emitters.pop(session_id, None)

    # ── Hook side: create request and wait ────────────────────────────────

    async def create_request(
        self,
        request_id: str,
        tool_name: str,
        tool_input: dict,
        session_id: str,
    ) -> PermissionRequest:
        req = PermissionRequest(
            request_id=request_id,
            tool_name=tool_name,
            tool_input=tool_input,
            session_id=session_id,
        )
        with self._lock:
            self._pending[request_id] = req
            emitter = self._emitters.get(session_id)

        # Emit the permission request to the SSE stream
        if emitter:
            import json
            emitter("permission_request", json.dumps({
                "request_id": request_id,
                "tool_name": tool_name,
                "tool_input": tool_input,
            }))
            logger.info("Permission request %s emitted to stream (tool=%s)", request_id, tool_name)
        else:
            # No active stream — try all emitters (user may have a different session_id)
            logger.warning("No emitter for session %s; broadcasting to all", session_id)
            import json
            payload = json.dumps({
                "request_id": request_id,
                "tool_name": tool_name,
                "tool_input": tool_input,
            })
            with self._lock:
                for emit_fn in self._emitters.values():
                    emit_fn("permission_request", payload)

        return req

    async def wait_for_response(self, req: PermissionRequest, timeout: float = PERMISSION_TIMEOUT_SECONDS) -> bool:
        """Block until the user responds or timeout. Returns True if approved."""
        try:
            await asyncio.wait_for(req.resolved.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            req.approved = False
            req.reason = "Timed out waiting for user approval"
            logger.warning("Permission request %s timed out after %ds", req.request_id, timeout)
        finally:
            with self._lock:
                self._pending.pop(req.request_id, None)
        return req.approved

    # ── Frontend side: resolve a pending request ──────────────────────────

    def resolve(self, request_id: str, approved: bool, reason: str = "") -> bool:
        with self._lock:
            req = self._pending.get(request_id)
        if not req:
            logger.warning("Tried to resolve unknown permission request: %s", request_id)
            return False
        req.approved = approved
        req.reason = reason or ("Approved by user" if approved else "Denied by user")
        req.resolved.set()
        logger.info("Permission request %s resolved: approved=%s", request_id, approved)
        return True

    # ── Query ─────────────────────────────────────────────────────────────

    def get_pending(self, request_id: str) -> Optional[PermissionRequest]:
        with self._lock:
            return self._pending.get(request_id)

    def get_all_pending(self) -> list[PermissionRequest]:
        with self._lock:
            return list(self._pending.values())

    def cleanup_stale(self, max_age: float = PERMISSION_TIMEOUT_SECONDS + 60) -> int:
        """Remove requests older than max_age seconds. Returns count removed."""
        now = time.time()
        stale = []
        with self._lock:
            for rid, req in self._pending.items():
                if now - req.created_at > max_age:
                    stale.append(rid)
            for rid in stale:
                req = self._pending.pop(rid)
                if not req.resolved.is_set():
                    req.approved = False
                    req.resolved.set()
        return len(stale)


# ── Singleton ─────────────────────────────────────────────────────────────

_broker: Optional[PermissionBroker] = None
_broker_lock = threading.Lock()


def get_permission_broker() -> PermissionBroker:
    global _broker
    if _broker is None:
        with _broker_lock:
            if _broker is None:
                _broker = PermissionBroker()
    return _broker
