"""Playwright browser + context lifecycle.

Phase 1 semantics (per spec section 9.3):
  - ONE Browser launched on first use, reused across tasks.
  - Each task gets a fresh ``BrowserContext`` (ephemeral by default).
  - Per-task concurrency = 1; additional submissions queue FIFO.

Phase 2 adds profile loading (persistent storage_state per domain).
Phase 4 adds parallel contexts.

The module is async; callers must run inside an event loop.

Example::

    mgr = BrowserSessionManager.instance()
    async with mgr.session(run_id="r_001") as page:
        await page.goto("https://example.com")
        title = await page.title()

The ``session()`` context manager creates a new BrowserContext + Page,
ensures the shared Browser is launched, and closes the context on exit.
The Browser itself stays warm for subsequent tasks.
"""

from __future__ import annotations

import asyncio
import atexit
import logging
import os
import signal
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal

logger = logging.getLogger(__name__)

# Default viewport — small enough to keep accessibility snapshots tidy,
# wide enough that responsive layouts don't collapse into mobile shells.
_DEFAULT_VIEWPORT = {"width": 1366, "height": 900}

# User agent — stable string avoids bot-fingerprint surprises between runs.
_DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


@dataclass
class SessionOptions:
    """Per-task launch knobs.

    ``headless``: explicit override; None means "decide from env + spec rules".
    ``storage_state_path``: filesystem path to a Playwright storage_state
    JSON blob (cookies + localStorage). Phase 2 feature but accepted here
    so Phase 1 tests can exercise the plumbing.
    ``record_video_dir``: if set, Playwright records MP4s into this dir.
    ``record_trace``: if True, collect a Playwright trace zip.
    """

    headless: bool | None = None
    storage_state_path: str | None = None
    record_video_dir: str | None = None
    record_trace: bool = False


def _display_available() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _resolve_headless(explicit: bool | None) -> bool:
    """Apply the precedence rules from spec section 9.2.

    explicit > JANE_BROWSER_VISIBLE env > default (headless).
    Visible requested + no display → fall back to headless.
    """
    if explicit is not None:
        if not explicit and not _display_available():
            logger.info("browser_session: visible requested but no DISPLAY — forcing headless")
            return True
        return explicit
    if os.environ.get("JANE_BROWSER_VISIBLE") == "1":
        if _display_available():
            return False
        logger.info("browser_session: JANE_BROWSER_VISIBLE=1 but no DISPLAY — forcing headless")
        return True
    return True


class BrowserSessionManager:
    """Module-level singleton holding the shared Browser.

    Thread-unsafe by design — Jane's event loop is single-threaded, and
    Playwright's async API mandates the same loop that started it.
    """

    _instance: "BrowserSessionManager | None" = None

    @classmethod
    def instance(cls) -> "BrowserSessionManager":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._register_atexit()
        return cls._instance

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None  # type: ignore[assignment]
        self._browser_headless: bool | None = None
        self._active_task: str | None = None
        self._active_lock = asyncio.Lock()
        self._shutdown_lock = asyncio.Lock()
        self._atexit_registered = False

    def _register_atexit(self) -> None:
        """Best-effort cleanup on process exit.

        atexit runs after the event loop closes, so we can't await.
        We poke Playwright's sync kill path if available; otherwise
        rely on the child Chromium noticing the parent died (it will).
        """
        if self._atexit_registered:
            return
        self._atexit_registered = True
        atexit.register(self._atexit_shutdown)

    def _atexit_shutdown(self) -> None:
        try:
            if self._browser is not None:
                # Playwright exposes _impl_obj... but we just let the child
                # die with the parent. Explicit close() needs an event loop.
                browser = self._browser
                try:
                    # If the event loop is still spinning, schedule graceful close.
                    loop = asyncio.get_event_loop()
                    if not loop.is_closed():
                        loop.run_until_complete(browser.close())
                except Exception:
                    pass
        except Exception:
            pass

    # ── Public API ────────────────────────────────────────────────────────

    async def warmup(self, *, headless: bool = True) -> None:
        """Launch the browser up front. Optional — session() will do it lazily."""
        await self._ensure_browser(headless=headless)

    async def shutdown(self) -> None:
        """Tear down the shared Browser + Playwright. Safe to call multiple times."""
        async with self._shutdown_lock:
            try:
                if self._browser is not None:
                    await self._browser.close()
            except Exception as e:
                logger.warning("browser_session: browser close failed: %s", e)
            self._browser = None
            try:
                if self._playwright is not None:
                    await self._playwright.stop()
            except Exception as e:
                logger.warning("browser_session: playwright stop failed: %s", e)
            self._playwright = None

    @asynccontextmanager
    async def session(
        self,
        *,
        run_id: str,
        options: SessionOptions | None = None,
    ) -> AsyncIterator["ActiveSession"]:
        """Yield an :class:`ActiveSession` owning a fresh BrowserContext.

        Enforces Phase 1's single-active-task invariant via an asyncio lock;
        concurrent ``session()`` calls queue FIFO.
        """
        opts = options or SessionOptions()
        headless = _resolve_headless(opts.headless)

        await self._active_lock.acquire()
        self._active_task = run_id
        try:
            await self._ensure_browser(headless=headless)
            ctx_kwargs: dict[str, Any] = {
                "viewport": _DEFAULT_VIEWPORT,
                "user_agent": _DEFAULT_UA,
                "accept_downloads": True,
            }
            if opts.storage_state_path and os.path.exists(opts.storage_state_path):
                ctx_kwargs["storage_state"] = opts.storage_state_path
            if opts.record_video_dir:
                ctx_kwargs["record_video_dir"] = opts.record_video_dir
            assert self._browser is not None
            context = await self._browser.new_context(**ctx_kwargs)
            if opts.record_trace:
                try:
                    await context.tracing.start(
                        screenshots=True, snapshots=True, sources=False,
                    )
                except Exception as e:
                    logger.warning("browser_session: tracing start failed: %s", e)
            page = await context.new_page()
            active = ActiveSession(
                run_id=run_id, context=context, page=page, options=opts,
            )
            try:
                yield active
            finally:
                await active.close()
        finally:
            self._active_task = None
            self._active_lock.release()

    @property
    def active_task(self) -> str | None:
        return self._active_task

    # ── Internals ─────────────────────────────────────────────────────────

    async def _ensure_browser(self, *, headless: bool) -> None:
        """Launch Playwright + Browser on first use.

        If the running Browser was launched with a different ``headless``
        setting than requested, close + relaunch. Rare path — keeps the
        semantics predictable without bookkeeping two browsers.
        """
        if self._browser is not None and self._browser_headless == headless:
            return
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception as e:
                logger.warning("browser_session: relaunch close failed: %s", e)
            self._browser = None
        if self._playwright is None:
            try:
                from playwright.async_api import async_playwright
            except ImportError as e:
                raise RuntimeError(
                    "Playwright not installed. Run: "
                    "pip install playwright==1.50.0 && playwright install chromium"
                ) from e
            self._playwright = await async_playwright().start()
        assert self._playwright is not None
        self._browser = await self._playwright.chromium.launch(
            headless=headless,
            args=[
                # Stability flags — no-sandbox is safe here: user-level process,
                # not a privileged container. --disable-dev-shm-usage avoids
                # /dev/shm exhaustion in constrained environments.
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        self._browser_headless = headless
        logger.info(
            "browser_session: launched Chromium (headless=%s, pid=active)",
            headless,
        )


@dataclass
class ActiveSession:
    """Handle to a live browser context + page for one task.

    Close via ``close()`` or rely on the ``session()`` context manager.
    """

    run_id: str
    context: Any  # playwright.async_api.BrowserContext
    page: Any     # playwright.async_api.Page
    options: SessionOptions
    closed: bool = False

    async def close(self, trace_out_path: str | None = None) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            if self.options.record_trace:
                try:
                    await self.context.tracing.stop(path=trace_out_path)
                except Exception as e:
                    logger.warning("browser_session: tracing stop failed: %s", e)
            await self.context.close()
        except Exception as e:
            logger.warning("browser_session: context close failed: %s", e)
