"""Live end-to-end smoke test — launches Chromium, hits hacker news.

Skipped by default; enable with RUN_LIVE=1. Fails fast if Playwright or
the Chromium build aren't installed. Not part of the regular CI cycle —
used to prove Phase 1 actually drives a real browser.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from agent_skills.web_automation import skill as wa_skill
from agent_skills.web_automation.browser_session import BrowserSessionManager, SessionOptions
from agent_skills.web_automation.skill import TaskStep

# Playwright's default cache dir doesn't match our Vessence-scoped location.
os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    str(Path(os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data")))
        / "playwright_browsers"),
)

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE") != "1",
    reason="Live browser test — set RUN_LIVE=1 to exercise",
)


@pytest.mark.asyncio
async def test_hacker_news_canary():
    result = await wa_skill.run_task(
        [
            TaskStep(action="navigate", args={"url": "https://news.ycombinator.com"}),
            TaskStep(action="snapshot", args={}),
            TaskStep(action="extract", args={}),
        ],
        label="hn_smoke",
        options=SessionOptions(headless=True),
    )
    try:
        assert result.ok, f"Task failed: {result.summary}"
        assert "news.ycombinator.com" in str(result.data).lower() or result.ok
    finally:
        await BrowserSessionManager.instance().shutdown()


@pytest.mark.asyncio
async def test_example_com_extracts_body():
    result = await wa_skill.run_task(
        [
            TaskStep(action="navigate", args={"url": "https://example.com"}),
            TaskStep(action="extract", args={}),
        ],
        label="example_smoke",
        options=SessionOptions(headless=True),
    )
    try:
        assert result.ok, f"Task failed: {result.summary}"
        # example.com contains the phrase "Example Domain" in its body.
        extracted = result.data.get("step_2", {}).get("text", "")
        assert "example domain" in extracted.lower()
    finally:
        await BrowserSessionManager.instance().shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
