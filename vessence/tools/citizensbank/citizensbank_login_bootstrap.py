#!/usr/bin/env python3
"""Bootstrap script for Citizens Bank workflows using manual login.

This script opens Citizens Bank and gives you time to sign in interactively.
It then saves Playwright storage state for reuse in later automation steps.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = "https://www.citizensbank.com/"
LOGIN_URL = "https://www.citizensbank.com/login"
SCRIPT_DIR = Path(__file__).resolve().parent
STATE_FILE_DEFAULT = str(SCRIPT_DIR / "citizensbank_auth_state.json")


def is_blocked_page(page) -> bool:
    """Best-effort check for anti-bot / denied pages."""
    try:
        title = (page.title() or "").lower()
        body = (page.locator("body").inner_text(timeout=3000) or "").lower()
        return "access denied" in title or "access denied" in body
    except Exception:
        return False


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Open Citizens Bank and capture an authenticated Playwright session state."
    )
    parser.add_argument(
        "--url",
        default=BASE_URL,
        help="Citizens Bank URL to open.",
    )
    parser.add_argument(
        "--login-url",
        default=LOGIN_URL,
        help="Direct Citizens Bank login URL (often less blocked than homepage).",
    )
    parser.add_argument(
        "--use-login-url",
        action="store_true",
        help="Open --login-url instead of --url.",
    )
    parser.add_argument(
        "--state-file",
        default=STATE_FILE_DEFAULT,
        help="Path where authenticated Playwright storage state will be stored.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser headless after opening the site.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Load an existing state file and continue from that session.",
    )
    parser.add_argument(
        "--pause-note",
        default="When you finish logging in, return here and press Enter.",
        help="Prompt text shown while waiting for manual login.",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=600000,
        help="Maximum milliseconds to wait for manual login completion.",
    )
    parser.add_argument(
        "--channel",
        default="",
        help="Browser channel (e.g., chrome or msedge) when available.",
    )
    parser.add_argument(
        "--persistent-profile",
        default="",
        help="Optional persistent browser profile directory path.",
    )
    parser.add_argument(
        "--disable-automation-flags",
        action="store_true",
        help="Add launch args commonly used to reduce bot-detection signals.",
    )
    args = parser.parse_args()

    state_path = Path(args.state_file)
    target_url = args.login_url if args.use_login_url else args.url

    with sync_playwright() as p:
        launch_kwargs: dict[str, object] = {"headless": args.headless}
        if args.channel:
            launch_kwargs["channel"] = args.channel
        if args.disable_automation_flags:
            launch_kwargs["args"] = [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]

        if args.persistent_profile:
            context = p.chromium.launch_persistent_context(
                user_data_dir=args.persistent_profile,
                **launch_kwargs,
            )
            browser = None
        else:
            browser = p.chromium.launch(**launch_kwargs)
            if args.resume and state_path.exists():
                context = browser.new_context(storage_state=str(state_path))
                print(f"Loaded existing auth state from: {state_path}")
            else:
                context = browser.new_context()

        page = context.new_page()
        page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        if is_blocked_page(page):
            print("Detected blocked/denied page immediately after navigation.")
        print(f"Opened {page.url}")
        print(f"Page title: {page.title()}")
        print(args.pause_note)

        if args.resume and state_path.exists():
            print("Resume mode: keep session open briefly for inspection.")
            page.wait_for_timeout(min(args.timeout_ms, 15000))
        else:
            try:
                input(f"Press Enter to continue after login (max {args.timeout_ms // 1000}s): ")
            except EOFError:
                page.wait_for_timeout(args.timeout_ms)

        context.storage_state(path=str(state_path))
        print(f"Saved auth state to: {state_path}")
        print("Next step: reuse with --resume to continue automation from authenticated session.")

        context.close()
        if browser is not None:
            browser.close()


if __name__ == "__main__":
    main()
