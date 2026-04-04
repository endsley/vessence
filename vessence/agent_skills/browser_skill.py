import asyncio
from playwright.async_api import async_playwright
import json
import logging

logger = logging.getLogger('amber.browser_skill')

class BrowserContextManager:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def start(self):
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=False) # Headless=False to see what's happening if needed
            self.context = await self.browser.new_context()
            self.page = await self.context.new_page()

    async def stop(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def get_compact_context(self):
        """Returns AXTree (Accessibility Tree) which is a compact, semantic representation of the page."""
        if not self.page:
            return "No active page."
        
        # Capture AXTree
        snapshot = await self.page.accessibility.snapshot()
        
        # Simplify the snapshot to keep it compact
        def simplify(node):
            res = {
                "role": node.get("role"),
                "name": node.get("name"),
            }
            if "description" in node: res["description"] = node["description"]
            if "value" in node: res["value"] = node["value"]
            if "children" in node:
                res["children"] = [simplify(c) for k, c in enumerate(node["children"]) if k < 20] # Limit children
            return res

        compact_html = json.dumps(snapshot, indent=2) # Using raw snapshot for now as it's already quite structured
        return compact_html

    async def navigate(self, url):
        await self.start()
        await self.page.goto(url)
        return await self.page.screenshot()

    async def get_screenshot(self):
        if self.page:
            return await self.page.screenshot()
        return None
