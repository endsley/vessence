#!/usr/bin/env python3
"""Wait for a logged-in Citizens Bank session and click account ending 4495."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


TARGET = "4495"
BASE = "https://www.citizensbank.com/homepage.aspx"
SCRIPT_DIR = Path(__file__).resolve().parent
STATE_FILE_DEFAULT = str(SCRIPT_DIR / "citizensbank_auth_state.json")
TIMEOUT_SCREENSHOT_PATH = str(SCRIPT_DIR / "citizensbank_4495_timeout.png")


def find_and_click_target(scope, target: str) -> bool:
    selectors = [
        "a",
        "button",
        "[role='button']",
        "[role='link']",
        "td",
        "div",
        "span",
        "li",
    ]

    for selector in selectors:
        try:
            locator = scope.locator(f'{selector}:has-text(\"{target}\")')
            for i in range(locator.count()):
                node = locator.nth(i)
                if not node.is_visible():
                    continue
                text = (node.inner_text() or "").replace("\xa0", " ").strip()
                if target not in text.replace(" ", ""):
                    continue
                try:
                    node.scroll_into_view_if_needed()
                    node.click(timeout=3000)
                    print(f"CLICKED {selector} index={i}: {text[:180]}")
                    return True
                except Exception as exc:
                    print(f"CLICK_REJECTED {selector} index={i}: {type(exc).__name__}")
                    continue
        except Exception as exc:
            print(f"QUERY_FAIL {selector}: {type(exc).__name__}")
            continue
    return False


def collect_status_text(page):
    try:
        return (page.locator("body").inner_text(timeout=4000) or "").lower()
    except Exception:
        return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Open Citizens Bank and open account ending in 4495.")
    parser.add_argument("--state-file", default=STATE_FILE_DEFAULT)
    parser.add_argument("--timeout-ms", type=int, default=600000, help="Max runtime in milliseconds")
    parser.add_argument("--poll-ms", type=int, default=2500, help="Poll interval in milliseconds")
    args = parser.parse_args()

    state_file = Path(args.state_file)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=str(state_file) if state_file.exists() else None)
        page = context.new_page()
        page.goto(BASE, wait_until="domcontentloaded", timeout=60000)

        print(f"Opened {page.url}")
        if state_file.exists():
            print(f"Loaded state from {state_file}")
        else:
            print("No saved state file found; continuing from browser defaults.")

        print("Ready. You can log in manually if needed; script will click account 4495 when visible.")

        deadline = time.time() + args.timeout_ms / 1000.0
        attempts = 0

        while time.time() < deadline:
            attempts += 1
            if find_and_click_target(page, TARGET):
                print("SUCCESS: clicked account ending 4495.")
                page.wait_for_timeout(3000)
                context.storage_state(path=str(state_file))
                print("Saved updated state.")
                print("CURRENT_URL", page.url)
                browser.close()
                return

            for frame in page.frames:
                if frame == page.main_frame:
                    continue
                if find_and_click_target(frame, TARGET):
                    print("SUCCESS: clicked account ending 4495 in an embedded frame.")
                    page.wait_for_timeout(3000)
                    context.storage_state(path=str(state_file))
                    print("Saved updated state.")
                    print("CURRENT_URL", page.url)
                    browser.close()
                    return

            if attempts % 4 == 0:
                status = collect_status_text(page)
                print(
                    "CHECKPOINT",
                    attempts,
                    "len_text=",
                    len(status),
                    "login_hint=",
                    "log in" in status,
                    "logged_in_hint=",
                    "log out" in status or "sign out" in status,
                    "url=",
                    page.url,
                )

            page.wait_for_timeout(args.poll_ms)

        print("TIMEOUT: account ending 4495 not found or not clickable.")
        context.storage_state(path=str(state_file))
        page.screenshot(path=TIMEOUT_SCREENSHOT_PATH)
        print(f"Saved timeout screenshot: {TIMEOUT_SCREENSHOT_PATH}")
        browser.close()


if __name__ == "__main__":
    main()
