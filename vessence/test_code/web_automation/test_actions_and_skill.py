"""Integration-style tests for actions.py + skill.dispatch_action.

These exercise the full ActionResult / safety gate / run-logging pipe
with a fake Playwright Page. Real browser tests are separate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from agent_skills.web_automation import actions, artifacts, skill
from agent_skills.web_automation import snapshot as snap_mod


@pytest.fixture
def run_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VESSENCE_DATA_HOME", str(tmp_path))
    rid = artifacts.new_run_id(label="test")
    return artifacts.RunDir(rid)


def _page_with_snapshot(a11y_children):
    page = MagicMock()
    page.url = "https://example.com/login"
    page.title = AsyncMock(return_value="Login")
    page.accessibility.snapshot = AsyncMock(return_value={
        "role": "WebArea",
        "children": a11y_children,
    })
    page.eval_on_selector_all = AsyncMock(return_value=[])
    return page


# ── navigate ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_navigate_accepts_http(run_dir):
    page = MagicMock()
    page.goto = AsyncMock(return_value=None)
    page.url = "https://example.com/"
    page.title = AsyncMock(return_value="Example")
    res = await skill.dispatch_action(
        page, action="navigate", args={"url": "https://example.com"}, run=run_dir,
    )
    assert res.ok, res.message
    page.goto.assert_awaited_once()


@pytest.mark.asyncio
async def test_navigate_rejects_file_url(run_dir):
    page = MagicMock()
    res = await skill.dispatch_action(
        page, action="navigate", args={"url": "file:///etc/passwd"}, run=run_dir,
    )
    assert not res.ok
    assert "non-http" in res.message.lower()


@pytest.mark.asyncio
async def test_navigate_rejects_blocked_domain(run_dir):
    from agent_skills.web_automation import safety
    safety.BLOCKED_DOMAINS.add("phishing.test")
    page = MagicMock()
    try:
        res = await skill.dispatch_action(
            page, action="navigate", args={"url": "https://phishing.test/login"}, run=run_dir,
        )
        assert not res.ok
        assert "block" in res.message.lower()
    finally:
        safety.BLOCKED_DOMAINS.discard("phishing.test")


# ── safety gates ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_blocks_high_risk_without_confirmation(run_dir):
    page = MagicMock()
    page.goto = AsyncMock(return_value=None)
    res = await skill.dispatch_action(
        page, action="navigate", args={"url": "https://site.example/checkout"}, run=run_dir,
    )
    assert not res.ok
    assert res.data.get("needs_confirmation") is True
    assert res.data.get("risk") == "high"


@pytest.mark.asyncio
async def test_dispatch_allows_high_risk_when_confirmed(run_dir):
    page = MagicMock()
    page.goto = AsyncMock(return_value=None)
    page.url = "https://site.example/checkout"
    page.title = AsyncMock(return_value="Checkout")
    res = await skill.dispatch_action(
        page, action="navigate", args={"url": "https://site.example/checkout"},
        run=run_dir, confirmed=True,
    )
    assert res.ok, res.message


# ── missing-arg validation ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_rejects_missing_required_arg(run_dir):
    page = MagicMock()
    res = await skill.dispatch_action(
        page, action="fill", args={"ref": "e01"}, run=run_dir,
    )
    assert not res.ok
    assert "missing" in res.message.lower() or "arg" in res.message.lower()


@pytest.mark.asyncio
async def test_dispatch_unknown_action(run_dir):
    page = MagicMock()
    res = await skill.dispatch_action(
        page, action="hack", args={}, run=run_dir,
    )
    assert not res.ok
    assert "unknown action" in res.message.lower()


# ── click via snapshot ref ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_click_resolves_ref_after_snapshot(run_dir):
    page = _page_with_snapshot([
        {"role": "button", "name": "Sign in", "children": []},
    ])
    click_locator = MagicMock()
    click_locator.click = AsyncMock(return_value=None)
    page.get_by_role = MagicMock(return_value=click_locator)

    # First, snapshot populates the store.
    res = await skill.dispatch_action(page, action="snapshot", args={}, run=run_dir)
    assert res.ok
    # Then click by the ref we got.
    res = await skill.dispatch_action(page, action="click", args={"ref": "e01"}, run=run_dir)
    assert res.ok, res.message
    click_locator.click.assert_awaited_once()


@pytest.mark.asyncio
async def test_click_unknown_ref_fails_cleanly(run_dir):
    page = _page_with_snapshot([
        {"role": "button", "name": "Sign in", "children": []},
    ])
    await skill.dispatch_action(page, action="snapshot", args={}, run=run_dir)
    res = await skill.dispatch_action(page, action="click", args={"ref": "e99"}, run=run_dir)
    assert not res.ok
    assert "e99" in res.message


# ── fill scrubs text from message (defense in depth) ─────────────────────────

@pytest.mark.asyncio
async def test_fill_does_not_echo_text_in_message(run_dir):
    page = _page_with_snapshot([
        {"role": "textbox", "name": "Password", "children": []},
    ])
    locator = MagicMock()
    locator.fill = AsyncMock(return_value=None)
    page.get_by_role = MagicMock(return_value=locator)
    await skill.dispatch_action(page, action="snapshot", args={}, run=run_dir)
    secret = "hunter2"
    res = await skill.dispatch_action(
        page, action="fill", args={"ref": "e01", "text": secret}, run=run_dir,
    )
    assert res.ok, res.message
    assert secret not in res.message


# ── run.json accumulates step history ───────────────────────────────────────

@pytest.mark.asyncio
async def test_run_json_gets_written_with_step_entries(run_dir):
    page = MagicMock()
    page.goto = AsyncMock(return_value=None)
    page.url = "https://example.com/"
    page.title = AsyncMock(return_value="Example")
    await skill.dispatch_action(
        page, action="navigate", args={"url": "https://example.com"}, run=run_dir,
    )
    data = json.loads((run_dir.dir / "run.json").read_text())
    assert len(data["steps"]) == 1
    assert data["steps"][0]["action"] == "navigate"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
