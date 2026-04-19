"""Typed deterministic action registry.

Each action is a small, well-typed wrapper around a Playwright method.
The LLM never constructs one directly — Jane's Stage 3 brain emits a
CLIENT_TOOL call (see ``skill.py``), which the handler maps to one of
these functions. Keeping the surface typed makes misuse loud.

Actions return a ``ActionResult`` with ``ok``, a human-readable
``message`` (what Jane says next), and optional ``data`` for things
like extracted text.

Tight docstrings on every function — they double as the spec Opus reads
when deciding which tool to emit.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from .snapshot import PageSnapshot, RefResolutionError, resolve_locator, take_snapshot

logger = logging.getLogger(__name__)

# Per-action timeouts in milliseconds. Tight enough that a hung page
# doesn't stall a whole turn; long enough that real sites finish.
_DEFAULT_NAV_TIMEOUT_MS = 30_000
_DEFAULT_ACTION_TIMEOUT_MS = 15_000


@dataclass
class ActionResult:
    ok: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)


# ── Navigation ────────────────────────────────────────────────────────────────

async def navigate(page: Any, url: str, *, wait: str = "load") -> ActionResult:
    """Navigate the page to ``url``.

    ``wait`` is one of ``"load"`` (default), ``"domcontentloaded"``,
    ``"networkidle"`` — passed straight through to Playwright.

    On success, returns the final URL (which may differ from the
    requested URL after redirects).
    """
    if not _is_http_url(url):
        return ActionResult(
            ok=False,
            message=f"Refused to navigate to non-http(s) URL: {url!r}",
        )
    try:
        await page.goto(url, wait_until=wait, timeout=_DEFAULT_NAV_TIMEOUT_MS)
    except Exception as e:
        return ActionResult(ok=False, message=f"Navigation failed: {e}")
    final_url = page.url
    try:
        title = await page.title()
    except Exception:
        title = ""
    return ActionResult(
        ok=True,
        message=f"Loaded {final_url}" + (f" — {title}" if title else ""),
        data={"url": final_url, "title": title},
    )


# ── Perception ────────────────────────────────────────────────────────────────

async def snapshot(page: Any) -> ActionResult:
    """Take an accessibility snapshot of the current page.

    Returns the rendered snapshot text as ``data["snapshot"]`` and as
    ``message`` so Jane's brain can reason over it immediately.
    """
    snap: PageSnapshot = await take_snapshot(page)
    rendered = snap.render()
    return ActionResult(
        ok=True,
        message=rendered,
        data={"snapshot": rendered, "url": snap.url, "title": snap.title},
    )


async def status(page: Any) -> ActionResult:
    """Report the current URL, title, and a health signal."""
    try:
        url = page.url
        title = await page.title()
    except Exception as e:
        return ActionResult(ok=False, message=f"Status read failed: {e}")
    return ActionResult(
        ok=True,
        message=f"{url} — {title}",
        data={"url": url, "title": title},
    )


# ── Interaction ───────────────────────────────────────────────────────────────

async def click(page: Any, ref: str) -> ActionResult:
    """Click the element identified by a snapshot ``ref`` (e.g. ``"e04"``)."""
    locator, err = await _locate(page, ref)
    if err is not None:
        return err
    try:
        await locator.click(timeout=_DEFAULT_ACTION_TIMEOUT_MS)
    except Exception as e:
        return ActionResult(ok=False, message=f"Click {ref} failed: {e}")
    return ActionResult(ok=True, message=f"Clicked {ref}")


async def fill(page: Any, ref: str, text: str) -> ActionResult:
    """Type ``text`` into a text input identified by ``ref``.

    Use ``fill_secret(ref, secret_id, field)`` for credentials — this
    plain version writes the literal text and it will appear in traces.
    """
    locator, err = await _locate(page, ref)
    if err is not None:
        return err
    try:
        await locator.fill(text, timeout=_DEFAULT_ACTION_TIMEOUT_MS)
    except Exception as e:
        return ActionResult(ok=False, message=f"Fill {ref} failed: {e}")
    # Don't echo the text back in the message — traces + LLM logs pick
    # it up downstream and we don't want secrets leaking even from non-
    # secret fills by mistake.
    return ActionResult(ok=True, message=f"Filled {ref}")


async def fill_secret(
    page: Any,
    ref: str,
    secret_id: str,
    *,
    field: str = "password",
) -> ActionResult:
    """Fill a credential field without ever surfacing the plaintext.

    Pulls the secret via :func:`secrets.get` — which enforces domain
    binding against the page's CURRENT URL. The only place the clear
    text exists is the locator.fill() call; it never hits the trace,
    never gets logged, and never appears in the returned message.

    ``field`` is one of ``"username"`` or ``"password"``.
    """
    from . import safety as _safety
    from . import secrets as _secrets_mod

    locator, err = await _locate(page, ref)
    if err is not None:
        return err

    # Resolve the element's OWN frame domain, not just the top-level
    # page URL. A cross-origin iframe (ad, overlay, embedded widget)
    # presents inputs whose containing frame can be on an attacker
    # domain even when the outer page is legitimate — typing a password
    # there would exfiltrate it.
    frame_url = ""
    try:
        handle = await locator.element_handle(timeout=_DEFAULT_ACTION_TIMEOUT_MS)
        if handle is not None:
            owning_frame = await handle.owner_frame()
            if owning_frame is not None:
                frame_url = owning_frame.url
    except Exception:
        frame_url = ""
    if not frame_url:
        # Fall back to page.url — will be validated below.
        try:
            frame_url = page.url
        except Exception:
            frame_url = ""
    target_domain = _safety.domain_of(frame_url)
    if not target_domain:
        return ActionResult(
            ok=False, message="Cannot read element's frame URL for domain binding",
        )
    try:
        value = _secrets_mod.get(
            secret_id,
            expected_domain=target_domain,
            caller="web_automation.fill_secret",
        )
    except _secrets_mod.SecretDomainMismatch as e:
        return ActionResult(ok=False, message=f"Secret refused: {e}")
    except _secrets_mod.SecretNotFound:
        return ActionResult(ok=False, message=f"Secret {secret_id!r} not found")
    except _secrets_mod.SecretStoreMisconfigured as e:
        return ActionResult(ok=False, message=f"Secret store unavailable: {e}")

    text = value.username if field == "username" else value.password
    if not text:
        return ActionResult(
            ok=False,
            message=f"Secret {secret_id!r} has no '{field}' field",
        )

    try:
        await locator.fill(text, timeout=_DEFAULT_ACTION_TIMEOUT_MS)
    except Exception as e:
        return ActionResult(ok=False, message=f"Fill secret {ref} failed: {e}")
    return ActionResult(
        ok=True,
        message=f"Filled {ref} from secret {secret_id[:6]}… ({field})",
    )


async def press(page: Any, key: str) -> ActionResult:
    """Fire a keyboard press (``Enter``, ``Escape``, ``Tab``, ``ArrowDown``…)."""
    try:
        await page.keyboard.press(key)
    except Exception as e:
        return ActionResult(ok=False, message=f"Press {key!r} failed: {e}")
    return ActionResult(ok=True, message=f"Pressed {key}")


async def select(page: Any, ref: str, value: str) -> ActionResult:
    """Select an option by ``value`` in the dropdown at ``ref``."""
    locator, err = await _locate(page, ref)
    if err is not None:
        return err
    try:
        await locator.select_option(value, timeout=_DEFAULT_ACTION_TIMEOUT_MS)
    except Exception as e:
        return ActionResult(ok=False, message=f"Select {ref}={value!r} failed: {e}")
    return ActionResult(ok=True, message=f"Selected {value!r} in {ref}")


# ── Waiting ───────────────────────────────────────────────────────────────────

async def wait(page: Any, *, for_: str = "load", timeout_ms: int = 15_000) -> ActionResult:
    """Wait for a named page condition.

    ``for_`` options:
      - ``"load"`` / ``"domcontentloaded"`` / ``"networkidle"``: standard Playwright load states
      - ``"url_contains:<pat>"``: wait until the current URL contains ``pat``
      - ``"text:<pat>"``: wait until any element with visible text ``pat`` is attached
    """
    try:
        if for_.startswith("url_contains:"):
            pat = for_.split(":", 1)[1]
            await page.wait_for_function(
                f"() => window.location.href.includes({pat!r})",
                timeout=timeout_ms,
            )
        elif for_.startswith("text:"):
            pat = for_.split(":", 1)[1]
            await page.get_by_text(pat, exact=False).first.wait_for(timeout=timeout_ms)
        else:
            await page.wait_for_load_state(for_, timeout=timeout_ms)
    except Exception as e:
        return ActionResult(ok=False, message=f"Wait {for_!r} failed: {e}")
    return ActionResult(ok=True, message=f"Wait {for_} satisfied")


# ── Extraction ────────────────────────────────────────────────────────────────

_TEXT_CLIP = 4000  # chars — keeps Opus context sane


async def extract(page: Any, *, ref: str | None = None) -> ActionResult:
    """Read text content from a ref or the whole page body.

    For form inputs (textbox, searchbox, textarea) we read the field's
    value via ``input_value()`` — ``inner_text()`` returns empty for
    unstyled inputs.
    """
    try:
        if ref:
            locator, err = await _locate(page, ref)
            if err is not None:
                return err
            # Look up role so we know whether to use input_value vs inner_text.
            from .snapshot import lookup_ref
            el = lookup_ref(page, ref)
            role = (el.role if el else "").lower()
            if role in {"textbox", "searchbox", "combobox", "spinbutton"}:
                text = await locator.input_value(timeout=_DEFAULT_ACTION_TIMEOUT_MS)
            else:
                text = await locator.inner_text(timeout=_DEFAULT_ACTION_TIMEOUT_MS)
        else:
            text = await page.locator("body").inner_text(timeout=_DEFAULT_ACTION_TIMEOUT_MS)
    except Exception as e:
        return ActionResult(ok=False, message=f"Extract failed: {e}")
    clipped = text[:_TEXT_CLIP]
    clipped_note = "" if len(text) <= _TEXT_CLIP else f" (clipped from {len(text)} chars)"
    return ActionResult(
        ok=True,
        message=clipped + clipped_note,
        data={"text": clipped, "length": len(text)},
    )


async def screenshot(page: Any, *, path: str, reason: str = "explicit") -> ActionResult:
    """Write a full-page PNG screenshot to ``path`` with a stated reason."""
    try:
        await page.screenshot(path=path, full_page=True)
    except Exception as e:
        return ActionResult(ok=False, message=f"Screenshot failed: {e}")
    return ActionResult(
        ok=True,
        message=f"Screenshot saved ({reason}) → {path}",
        data={"path": path, "reason": reason},
    )


# ── helpers ───────────────────────────────────────────────────────────────────

async def _locate(page: Any, ref: str) -> tuple[Any, ActionResult | None]:
    try:
        loc = await resolve_locator(page, ref)
        return loc, None
    except RefResolutionError as e:
        return None, ActionResult(ok=False, message=str(e))


_HTTP_RE = re.compile(r"^https?://", re.IGNORECASE)


def _is_http_url(url: str) -> bool:
    return bool(_HTTP_RE.match(url or ""))


# ── Action registry (for the skill handler) ───────────────────────────────────

# Maps the LLM-visible action name → async handler signature notes.
# Used by ``skill.dispatch_action`` to validate + route without a giant if/else.
REGISTRY: dict[str, dict[str, Any]] = {
    "navigate":   {"fn": navigate,   "args": {"url": str, "wait": str}, "required": ["url"]},
    "snapshot":   {"fn": snapshot,   "args": {}, "required": []},
    "status":     {"fn": status,     "args": {}, "required": []},
    "click":      {"fn": click,      "args": {"ref": str}, "required": ["ref"]},
    "fill":       {"fn": fill,       "args": {"ref": str, "text": str}, "required": ["ref", "text"]},
    "fill_secret":{"fn": fill_secret, "args": {"ref": str, "secret_id": str, "field": str}, "required": ["ref", "secret_id"]},
    "press":      {"fn": press,      "args": {"key": str}, "required": ["key"]},
    "select":     {"fn": select,     "args": {"ref": str, "value": str}, "required": ["ref", "value"]},
    "wait":       {"fn": wait,       "args": {"for_": str, "timeout_ms": int}, "required": []},
    "extract":    {"fn": extract,    "args": {"ref": str}, "required": []},
    "screenshot": {"fn": screenshot, "args": {"path": str, "reason": str}, "required": ["path"]},
}


__all__ = [
    "ActionResult",
    "REGISTRY",
    "click",
    "extract",
    "fill",
    "fill_secret",
    "navigate",
    "press",
    "screenshot",
    "select",
    "snapshot",
    "status",
    "wait",
]
