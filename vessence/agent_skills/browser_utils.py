import asyncio
import json
import logging
from playwright.async_api import async_playwright

logger = logging.getLogger('amber.browser_utils')

async def get_ax_tree(url: str) -> str:
    """Uses Playwright to capture the Accessibility Tree of a page."""
    if not url or not url.startswith("http"):
        return "No valid URL provided."
        
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Capture Accessibility Tree
            snapshot = await page.accessibility.snapshot()
            await browser.close()
            
            if not snapshot:
                return "Empty AXTree."
                
            # Convert to a compact JSON string
            return json.dumps(snapshot, indent=2)[:3000] # Limit size
    except Exception as e:
        logger.error(f"Error getting AXTree: {e}")
        return f"Error capturing AXTree: {str(e)}"

async def get_compact_html(url: str) -> str:
    """Async wrapper for AXTree capture. Must be awaited inside an async context."""
    return await get_ax_tree(url)
