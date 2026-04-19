"""Unit tests for agent_skills.web_automation.snapshot."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from agent_skills.web_automation import snapshot as snap_mod


def _fake_page(a11y_root: dict, url: str = "https://example.com", title: str = "Example"):
    page = MagicMock()
    page.url = url
    page.title = AsyncMock(return_value=title)
    page.accessibility.snapshot = AsyncMock(return_value=a11y_root)
    page.eval_on_selector_all = AsyncMock(return_value=[])
    return page


@pytest.mark.asyncio
async def test_take_snapshot_extracts_interactive_elements():
    a11y = {
        "role": "WebArea",
        "name": "Example",
        "children": [
            {"role": "heading", "name": "Log in", "level": 1, "children": []},
            {"role": "textbox", "name": "Email", "value": "", "children": []},
            {"role": "textbox", "name": "Password", "value": "", "children": []},
            {"role": "button", "name": "Sign in", "children": []},
            {"role": "link", "name": "Forgot password?", "children": []},
            {"role": "paragraph", "name": "ignored prose", "children": []},
        ],
    }
    page = _fake_page(a11y)
    snap = await snap_mod.take_snapshot(page)
    refs = [e.ref for e in snap.elements]
    names = [e.name for e in snap.elements]
    roles = [e.role for e in snap.elements]
    assert "e01" in refs and "e05" in refs
    assert "Log in" in names
    assert "Sign in" in names
    assert "Forgot password?" in names
    assert "paragraph" not in roles
    rendered = snap.render()
    assert "URL: https://example.com" in rendered
    assert "role=button" in rendered


@pytest.mark.asyncio
async def test_take_snapshot_caps_at_200_elements():
    children = [
        {"role": "button", "name": f"b{i}", "children": []}
        for i in range(500)
    ]
    a11y = {"role": "WebArea", "children": children}
    page = _fake_page(a11y)
    snap = await snap_mod.take_snapshot(page)
    assert len(snap.elements) == 200


@pytest.mark.asyncio
async def test_find_returns_element_and_none():
    a11y = {
        "role": "WebArea",
        "children": [
            {"role": "button", "name": "OK", "children": []},
        ],
    }
    page = _fake_page(a11y)
    snap = await snap_mod.take_snapshot(page)
    assert snap.find("e01").name == "OK"
    assert snap.find("e42") is None


@pytest.mark.asyncio
async def test_resolve_locator_without_snapshot_raises():
    page = _fake_page({"role": "WebArea", "children": []})
    # page id uniqueness to avoid cross-test pollution
    snap_mod._SnapshotStore.clear(page)
    with pytest.raises(snap_mod.RefResolutionError):
        await snap_mod.resolve_locator(page, "e01")


@pytest.mark.asyncio
async def test_resolve_locator_uses_role_name_after_snapshot():
    a11y = {
        "role": "WebArea",
        "children": [
            {"role": "button", "name": "Submit", "children": []},
        ],
    }
    page = _fake_page(a11y)
    page.get_by_role = MagicMock(return_value="ROLE_LOCATOR")
    await snap_mod.take_snapshot(page)
    loc = await snap_mod.resolve_locator(page, "e01")
    assert loc == "ROLE_LOCATOR"
    page.get_by_role.assert_called_once_with("button", name="Submit")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
