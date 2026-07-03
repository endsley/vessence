#!/usr/bin/env python3
"""Clean up stale or completed Facebook Marketplace Messenger threads.

The cron path uses Chieh's already-authenticated Chromium profile. It scans the
Marketplace inbox, keeps the protected Honda Fit conversation, and deletes
threads that either look sold/gone or have had no visible activity for the
configured stale window.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
import os
import re
from dataclasses import asdict
from pathlib import Path

from agent_skills.facebook_marketplace_rules import (
    Conversation,
    Decision,
    classify_conversations,
    classify_conversation,
    conversation_from_row,
    extract_title,
    is_protected_title,
    looks_sold_or_gone,
    normalize_title,
    parse_relative_age_days,
    select_delete_candidates,
)


LOGGER = logging.getLogger("facebook_marketplace_message_cleanup")

VESSENCE_DATA_HOME = Path(
    os.environ.get("VESSENCE_DATA_HOME", "/home/chieh/ambient/vessence-data")
)
DEFAULT_PROFILE_DIR = (
    VESSENCE_DATA_HOME / "browser-profiles" / "facebook-messenger-playwright"
)
DEFAULT_AUDIT_LOG = (
    VESSENCE_DATA_HOME / "logs" / "facebook_marketplace_message_cleanup.jsonl"
)
DEFAULT_KEEP_TITLES = ("Rickey : 2015 Honda Fit", "Rickey \u00b7 2015 Honda Fit")
MESSENGER_URL = "https://www.facebook.com/messages/t/"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


VISIBLE_CONVERSATIONS_JS = r"""
(() => {
  const out = [];
  const seen = new Set();
  const viewportHeight = window.innerHeight || 1000;
  for (const link of Array.from(document.querySelectorAll('a[href*="/messages/t/"]'))) {
    const href = (link.getAttribute('href') || '').split('?')[0];
    if (!/\/messages\/t\/\d+\/?$/.test(href) || seen.has(href)) continue;
    const rect = link.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0 || rect.x < 0 || rect.y < 60 || rect.y > viewportHeight - 40) continue;
    seen.add(href);
    const label = link.getAttribute('aria-label') || '';
    let node = link;
    for (let i = 0; i < 9 && node.parentElement; i += 1) {
      const text = (node.innerText || '').trim();
      if (text.length > 20 && text.length < 800) break;
      node = node.parentElement;
    }
    out.push({
      href,
      label,
      text: (node.innerText || link.innerText || '').slice(0, 900),
      rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height}
    });
  }
  return out;
})()
"""


async def click_marketplace_folder(page) -> None:
    await page.goto(MESSENGER_URL, wait_until="domcontentloaded", timeout=60_000)
    await page.wait_for_timeout(8_000)
    clicked = await page.evaluate(
        r"""
        (() => {
          const candidates = Array.from(document.querySelectorAll('span,div,button,a'));
          for (const el of candidates) {
            const text = (el.innerText || '').trim();
            if (text !== 'Marketplace') continue;
            const rect = el.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0 || rect.x > 380 || rect.y < 50 || rect.y > 650) continue;
            let node = el;
            for (let i = 0; i < 8 && node; i += 1, node = node.parentElement) {
              const role = node.getAttribute && node.getAttribute('role');
              const nodeRect = node.getBoundingClientRect();
              if (role === 'button' || role === 'row' || role === 'link' || nodeRect.height >= 40) {
                node.click();
                return true;
              }
            }
            el.click();
            return true;
          }
          return false;
        })()
        """
    )
    if not clicked:
        await page.mouse.click(172, 397)
    await page.wait_for_timeout(8_000)


async def scan_conversations(page, *, max_scrolls: int) -> list[Conversation]:
    await click_marketplace_folder(page)
    await page.mouse.move(170, 600)
    for _ in range(8):
        await page.mouse.wheel(0, -1000)
        await page.wait_for_timeout(150)

    conversations: list[Conversation] = []
    seen_hrefs: set[str] = set()
    idle_scrolls = 0
    for _ in range(max_scrolls):
        rows = await page.evaluate(VISIBLE_CONVERSATIONS_JS)
        new_count = 0
        for row in rows:
            conversation = conversation_from_row(row)
            if not conversation or conversation.href in seen_hrefs:
                continue
            seen_hrefs.add(conversation.href)
            conversations.append(conversation)
            new_count += 1
        if new_count == 0:
            idle_scrolls += 1
        else:
            idle_scrolls = 0
        if idle_scrolls >= 6:
            break
        await page.mouse.move(170, 600)
        await page.mouse.wheel(0, 760)
        await page.wait_for_timeout(900)
    return conversations


async def click_delete_menu_item(page, *, allow_bare_delete: bool = False) -> bool:
    patterns = [r"^Delete chat$", r"^Delete conversation$"]
    if allow_bare_delete:
        patterns.append(r"^Delete$")
    for pattern in patterns:
        for role in ("menuitem", "button", "link"):
            locator = page.get_by_role(role, name=re.compile(pattern, re.I)).first
            try:
                if await locator.count():
                    await locator.click(timeout=4_000)
                    await page.wait_for_timeout(1_000)
                    return True
            except Exception as exc:  # pragma: no cover - live UI fallback
                LOGGER.debug("delete locator failed for %s/%s: %s", role, pattern, exc)
    return False


async def confirm_delete(page) -> bool:
    for pattern in (r"^Delete chat$", r"^Delete conversation$", r"^Delete$"):
        button = page.get_by_role("button", name=re.compile(pattern, re.I)).first
        try:
            if await button.count():
                await button.click(timeout=5_000)
                await page.wait_for_timeout(2_000)
                return True
        except Exception as exc:  # pragma: no cover - live UI fallback
            LOGGER.debug("confirm delete failed for %s: %s", pattern, exc)
    return False


async def click_right_panel_button_text(page, text_pattern: str) -> bool:
    clicked = await page.evaluate(
        r"""
        (pattern) => {
          const regex = new RegExp(pattern, 'i');
          const candidates = Array.from(document.querySelectorAll('span,div,button,a'));
          for (const el of candidates) {
            const text = (el.innerText || el.getAttribute('aria-label') || '').trim();
            if (!regex.test(text)) continue;
            const rect = el.getBoundingClientRect();
            if (rect.width <= 0 || rect.height <= 0 || rect.x < 900 || rect.y < 60 || rect.y > 930) continue;
            let node = el;
            for (let i = 0; i < 8 && node; i += 1, node = node.parentElement) {
              const role = node.getAttribute && node.getAttribute('role');
              const nodeRect = node.getBoundingClientRect();
              if (role === 'button' || role === 'menuitem' || (nodeRect.width > 80 && nodeRect.height > 24)) {
                node.click();
                return true;
              }
            }
            el.click();
            return true;
          }
          return false;
        }
        """,
        text_pattern,
    )
    if clicked:
        await page.wait_for_timeout(1_000)
    return bool(clicked)


async def try_delete_from_open_chat(page, conversation: Conversation) -> bool:
    href = conversation.href
    url = href if href.startswith("http") else f"https://www.facebook.com{href}"
    await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    await page.wait_for_timeout(7_000)

    if await click_delete_menu_item(page):
        return await confirm_delete(page)

    info = page.get_by_role(
        "button",
        name=re.compile(r"^(Conversation information|Chat information|Chat info)$", re.I),
    ).first
    try:
        if await info.count():
            await info.click(timeout=4_000)
            await page.wait_for_timeout(1_000)
    except Exception as exc:  # pragma: no cover - live UI fallback
        LOGGER.debug("conversation information click failed: %s", exc)

    for panel_label in (r"^More options$", r"^Privacy (&|and) support$"):
        if await click_right_panel_button_text(page, panel_label):
            if await click_delete_menu_item(page, allow_bare_delete=False):
                return await confirm_delete(page)
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(400)

    return False


async def scroll_to_visible_conversation(page, href: str, *, max_scrolls: int = 80) -> bool:
    await click_marketplace_folder(page)
    await page.mouse.move(170, 600)
    for _ in range(8):
        await page.mouse.wheel(0, -1000)
        await page.wait_for_timeout(150)

    for _ in range(max_scrolls):
        rows = await page.evaluate(VISIBLE_CONVERSATIONS_JS)
        if any(row.get("href") == href for row in rows):
            return True
        await page.mouse.move(170, 600)
        await page.mouse.wheel(0, 760)
        await page.wait_for_timeout(650)
    return False


async def try_delete_from_visible_row(page, conversation: Conversation) -> bool:
    if not await scroll_to_visible_conversation(page, conversation.href):
        return False

    link = page.locator(f'a[href="{conversation.href}"]').first
    try:
        await link.hover(timeout=5_000)
        await page.wait_for_timeout(600)
    except Exception as exc:  # pragma: no cover - live UI fallback
        LOGGER.debug("hover failed for %s: %s", conversation.title, exc)

    menu_button = page.get_by_role(
        "button",
        name=re.compile(rf"^More options for {re.escape(conversation.title)}$", re.I),
    ).first
    try:
        if await menu_button.count():
            await menu_button.click(timeout=5_000)
            await page.wait_for_timeout(1_000)
            if await click_delete_menu_item(page):
                return await confirm_delete(page)
    except Exception as exc:  # pragma: no cover - live UI fallback
        LOGGER.debug("row menu delete failed for %s: %s", conversation.title, exc)
    return False


async def delete_conversation(page, conversation: Conversation) -> bool:
    if await try_delete_from_open_chat(page, conversation):
        return True
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(500)
    return await try_delete_from_visible_row(page, conversation)


def append_audit(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


async def run_cleanup(args: argparse.Namespace) -> int:
    from playwright.async_api import async_playwright

    keep_titles = tuple(DEFAULT_KEEP_TITLES) + tuple(args.keep_title or ())
    audit_path = Path(args.audit_log)
    profile_dir = Path(args.profile_dir)
    effective_delete = bool(args.delete and not args.dry_run)
    headless = not args.headed and os.environ.get("FB_MARKETPLACE_MESSAGE_HEADFUL_DEBUG", "").lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }

    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            str(profile_dir),
            headless=headless,
            viewport={"width": 1500, "height": 1000},
            user_agent=USER_AGENT,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else await context.new_page()
        try:
            conversations = await scan_conversations(page, max_scrolls=args.max_scrolls)
            LOGGER.info("scanned %d Marketplace conversations", len(conversations))

            classified = classify_conversations(
                conversations,
                keep_titles=keep_titles,
                stale_days=args.stale_days,
            )
            for conversation, decision in classified:
                append_audit(
                    audit_path,
                    {
                        "ts": dt.datetime.now(dt.UTC).isoformat(),
                        "mode": "scan",
                        "decision": asdict(decision),
                        "conversation": asdict(conversation),
                    },
                )

            candidates = select_delete_candidates(classified, max_delete=args.max_delete)

            LOGGER.info(
                "%d delete candidates selected (delete=%s, limit=%d)",
                len(candidates),
                effective_delete,
                args.max_delete,
            )

            for conversation, decision in candidates:
                if is_protected_title(conversation.title, keep_titles):
                    status = "kept_protected"
                elif not effective_delete:
                    status = "dry_run"
                else:
                    LOGGER.info("deleting %s (%s)", conversation.title, decision.reason)
                    status = "deleted" if await delete_conversation(page, conversation) else "delete_failed"
                append_audit(
                    audit_path,
                    {
                        "ts": dt.datetime.now(dt.UTC).isoformat(),
                        "mode": "delete" if effective_delete else "dry_run",
                        "status": status,
                        "decision": asdict(decision),
                        "conversation": asdict(conversation),
                    },
                )
                LOGGER.info("%s: %s (%s)", status, conversation.title, decision.reason)
        finally:
            await context.close()

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Clean sold/gone/stale Facebook Marketplace Messenger chats."
    )
    parser.add_argument("--delete", action="store_true", help="Actually delete matching chats.")
    parser.add_argument("--dry-run", action="store_true", help="Scan and log without deleting.")
    parser.add_argument("--headed", action="store_true", help="Show Chromium for debugging.")
    parser.add_argument("--max-scrolls", type=int, default=80)
    parser.add_argument("--max-delete", type=int, default=25)
    parser.add_argument("--stale-days", type=int, default=3)
    parser.add_argument("--keep-title", action="append", default=[])
    parser.add_argument(
        "--profile-dir",
        default=os.environ.get("FB_MARKETPLACE_MESSAGE_PROFILE", str(DEFAULT_PROFILE_DIR)),
    )
    parser.add_argument("--audit-log", default=str(DEFAULT_AUDIT_LOG))
    return parser


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args()
    return asyncio.run(run_cleanup(args))


if __name__ == "__main__":
    raise SystemExit(main())
