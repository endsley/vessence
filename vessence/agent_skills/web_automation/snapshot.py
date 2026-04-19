"""Accessibility-tree snapshots with compact element refs.

Phase 1 snapshot format (per spec sections 2 and 10.5):

    URL: https://example.com/login
    Title: Log in — Example
    Elements:
      e01 [role=heading level=1] "Log in to Example"
      e02 [role=textbox name="Email"] value=""
      e03 [role=textbox name="Password"] value="" (password)
      e04 [role=button name="Sign in"]
      e05 [role=link name="Forgot password?"] href="/reset"

Refs (``e01``...) are opaque short strings, stable **within** a single
snapshot; regenerated on every new snapshot. Callers pass refs back to
``actions.click(ref)`` / ``actions.fill(ref, text)`` and the action
resolver looks them up from the most recent snapshot on the page.

Design notes:
  - Uses Playwright's accessibility API (``page.accessibility.snapshot()``)
    — returns Chrome's a11y tree which is what Stagehand / Playwright MCP
    both settled on. 80–90% smaller than raw DOM.
  - Interactive elements only: button, link, textbox, checkbox, radio,
    combobox, listbox, switch, menuitem, tab, heading (for anchoring).
  - ARIA hidden / display:none elements pruned.
  - IFrame content is NOT stitched in Phase 1 (deferred — spec 10.1 notes
    the Stagehand EncodedId stitching pattern for later).

Storage: a per-page ``_SnapshotStore`` keeps the most recent snapshot's
ref→node map keyed by the Playwright ``Page`` object id. Refs resolve to
either an accessibility node (role+name tuple) or a concrete selector
candidate.
"""

from __future__ import annotations

import logging
import weakref
from dataclasses import dataclass, field
from typing import Any, Iterable

logger = logging.getLogger(__name__)


# Roles we consider "interactive" — worth an element ref in snapshots.
# Heading/textitem included as anchors so the LLM can describe location.
_INTERACTIVE_ROLES = {
    "button", "link", "textbox", "checkbox", "radio", "combobox",
    "listbox", "menuitem", "switch", "tab", "slider", "spinbutton",
    "searchbox",
    # Anchors / structural
    "heading", "option",
}

# Hard cap so a pathological page doesn't flood the LLM context.
_MAX_REFS_PER_SNAPSHOT = 200


@dataclass
class ElementRef:
    """One interactive element captured from the a11y tree."""

    ref: str
    role: str
    name: str
    value: str | None = None
    checked: bool | None = None
    disabled: bool | None = None
    href: str | None = None
    # Extra Playwright metadata used by the resolver — NOT surfaced to users.
    level: int | None = None
    haspopup: str | None = None
    expanded: bool | None = None


@dataclass
class PageSnapshot:
    """A snapshot of interactive elements on the page."""

    url: str
    title: str
    elements: list[ElementRef] = field(default_factory=list)

    def render(self) -> str:
        """Human-readable (and LLM-readable) rendering."""
        lines = [
            f"URL: {self.url}",
            f"Title: {self.title}",
            "Elements:",
        ]
        for e in self.elements:
            parts = [f"  {e.ref}", f"[role={e.role}"]
            if e.level is not None:
                parts[-1] += f" level={e.level}"
            parts[-1] += "]"
            if e.name:
                parts.append(f'"{e.name}"')
            if e.value is not None and e.role in {"textbox", "searchbox", "combobox", "spinbutton"}:
                v = (e.value or "")[:40]
                parts.append(f'value="{v}"')
            if e.checked is not None:
                parts.append("checked" if e.checked else "unchecked")
            if e.disabled:
                parts.append("(disabled)")
            if e.href:
                parts.append(f"href={e.href}")
            lines.append(" ".join(parts))
        return "\n".join(lines)

    def find(self, ref: str) -> ElementRef | None:
        for e in self.elements:
            if e.ref == ref:
                return e
        return None


async def take_snapshot(page: Any) -> PageSnapshot:
    """Capture an accessibility snapshot of the current page.

    ``page`` is a Playwright ``Page``. Keeps the call here (not on the
    Page via a plugin) so callers don't need to know about Playwright
    internals; also lets unit tests pass a fake page.
    """
    url = page.url
    try:
        title = await page.title()
    except Exception:
        title = ""

    # Playwright returns a nested dict: {role, name, children, ...}
    try:
        root = await page.accessibility.snapshot(interesting_only=False)
    except Exception as e:
        # Fail loud — returning an empty tree would make Opus hallucinate
        # a blank page and loop forever ("still loading?").
        raise SnapshotError(f"accessibility snapshot failed: {e}") from e
    if root is None:
        raise SnapshotError(
            "accessibility snapshot returned None — page may have been "
            "navigated or closed mid-snapshot"
        )

    elements: list[ElementRef] = []
    ref_counter = [1]  # mutable box for inner fn

    def walk(node: dict | None) -> None:
        if not isinstance(node, dict):
            return
        role = node.get("role") or ""
        name = (node.get("name") or "").strip()
        if role in _INTERACTIVE_ROLES and (name or role in {"textbox", "searchbox"}):
            if len(elements) < _MAX_REFS_PER_SNAPSHOT:
                elements.append(ElementRef(
                    ref=f"e{ref_counter[0]:02d}",
                    role=role,
                    name=name,
                    value=_as_str(node.get("value")),
                    checked=_as_bool(node.get("checked")),
                    disabled=_as_bool(node.get("disabled")),
                    level=_as_int(node.get("level")),
                    expanded=_as_bool(node.get("expanded")),
                    haspopup=_as_str(node.get("haspopup")),
                ))
                ref_counter[0] += 1
        for child in node.get("children") or []:
            walk(child)

    walk(root)

    # Resolve hrefs for links via DOM query — a11y tree doesn't include them.
    if any(e.role == "link" for e in elements):
        try:
            links = await page.eval_on_selector_all(
                "a[href]",
                "els => els.map(a => ({text: (a.innerText||'').trim(), href: a.href}))",
            )
            # Match by visible text; best-effort.
            for e in elements:
                if e.role != "link" or e.href is not None:
                    continue
                for link in links:
                    if link.get("text") and link["text"] == e.name:
                        e.href = link["href"]
                        break
        except Exception as e:
            logger.debug("snapshot: link href resolution skipped: %s", e)

    snap = PageSnapshot(url=url, title=title, elements=elements)
    _SnapshotStore.set(page, snap)
    return snap


class _SnapshotStore:
    """Stash the most recent snapshot keyed on the Page object.

    Uses a ``WeakKeyDictionary`` so snapshots evict automatically when
    the Page is garbage-collected — avoids the OOM Gemini flagged where
    stale ids accumulated forever.
    """

    _by_page: "weakref.WeakKeyDictionary[Any, PageSnapshot]" = weakref.WeakKeyDictionary()

    @classmethod
    def set(cls, page: Any, snap: PageSnapshot) -> None:
        try:
            cls._by_page[page] = snap
        except TypeError:
            # Object doesn't support weakref (e.g. a MagicMock in tests).
            # Fall back to a module-level dict keyed on id; best effort.
            _fallback_store[id(page)] = snap

    @classmethod
    def get(cls, page: Any) -> PageSnapshot | None:
        snap = cls._by_page.get(page)
        if snap is not None:
            return snap
        return _fallback_store.get(id(page))

    @classmethod
    def clear(cls, page: Any) -> None:
        try:
            cls._by_page.pop(page, None)
        except TypeError:
            pass
        _fallback_store.pop(id(page), None)


_fallback_store: dict[int, PageSnapshot] = {}


async def resolve_locator(page: Any, ref: str):
    """Translate a snapshot ref to a Playwright Locator.

    Re-queries the page via role+name — the snapshot ref is not a live
    handle, so the DOM can shift between snapshot and action. This is the
    canonical resolution path; tests mock at the Locator boundary.
    """
    snap = _SnapshotStore.get(page)
    if snap is None:
        raise RefResolutionError(
            "No snapshot on file for this page. Take a snapshot first."
        )
    el = snap.find(ref)
    if el is None:
        raise RefResolutionError(f"Unknown ref {ref!r} (not in current snapshot).")
    if el.role and el.name:
        return page.get_by_role(el.role, name=el.name)
    if el.name:
        return page.get_by_text(el.name, exact=False)
    # Role-only (e.g. a single textbox) — take the first match.
    return page.get_by_role(el.role).first


class RefResolutionError(RuntimeError):
    """Raised when a snapshot ref can't be mapped back to a Locator."""


class SnapshotError(RuntimeError):
    """Raised when the accessibility tree can't be retrieved."""


# ── tiny type coercion helpers ────────────────────────────────────────────────

def _as_bool(v: Any) -> bool | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() in ("true", "1", "yes")
    return bool(v)


def _as_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _as_str(v: Any) -> str | None:
    if v is None:
        return None
    return str(v)


__all__ = [
    "ElementRef",
    "PageSnapshot",
    "RefResolutionError",
    "SnapshotError",
    "resolve_locator",
    "take_snapshot",
]


def lookup_ref(page: Any, ref: str) -> ElementRef | None:
    """Resolve a ref to its stored ``ElementRef`` metadata (if any).

    Used by the safety classifier so ``click(e04)`` can see that ``e04``
    is a ``button name="Delete Account"`` and elevate the risk.
    """
    snap = _SnapshotStore.get(page)
    if snap is None:
        return None
    return snap.find(ref)
