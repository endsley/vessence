#!/usr/bin/env python3
"""Anthropic / Claude receipt downloader.

One-time setup:

    /home/chieh/google-adk-env/adk-venv/bin/python \
        agent_skills/anthropic_receipts.py capture-profile

Download recent Claude billing receipts:

    /home/chieh/google-adk-env/adk-venv/bin/python \
        agent_skills/anthropic_receipts.py download --count 10

The downloader uses a saved Claude browser profile, opens Claude Billing
settings, extracts visible invoice controls, and saves Stripe invoice pages as
PDFs. Password and 2FA prompts stay in the visible browser during capture.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from agent_skills.google_cloud_receipt_utils import (
    BillingAccount,
    DownloadedReceipt,
    ReceiptCandidate,
    build_receipt_filename,
    downloaded_receipt_from_candidate,
    downloaded_receipts_json,
    manifest_path as _manifest_path,
    parse_iso_date,
    parse_receipt_amount,
    parse_receipt_date,
    select_requested_receipt_candidates,
    unique_dest_path as _unique_dest_path,
    validate_receipt_request,
)
from agent_skills.web_automation.browser_session import (
    BrowserSessionManager,
    SessionOptions,
)
from agent_skills.web_automation.profiles import (
    ProfileMeta,
    ProfileNotFound,
    bind_check,
    capture_after_login,
    create as create_profile,
    get as get_profile,
    storage_state_path,
    touch_last_used,
)


CLAUDE_DOMAIN = "claude.ai"
DEFAULT_PROFILE_ID = "anthropic_claude"
DEFAULT_PROFILE_NAME = "Anthropic Claude"
DEFAULT_LOGIN_EMAIL = "Chieh.t.wu@gmail.com"
CLAUDE_URL = "https://claude.ai/"
CLAUDE_BILLING_URL = "https://claude.ai/settings/billing"
CLAUDE_SETTINGS_URL = "https://claude.ai/settings"
PROVIDER_FILENAME_PREFIX = "anthropic"
CLAUDE_ACCOUNT = BillingAccount(account_id="claude", name="Claude", open=True)

_LOGIN_BUTTON_RE = re.compile(r"^(log in|sign in|continue|continue with google|sign up|get started)$", re.IGNORECASE)
_GOOGLE_RE = re.compile(r"continue with google|sign in with google", re.IGNORECASE)
_BILLING_RE = re.compile(r"^billing$", re.IGNORECASE)
_VIEW_ALL_RE = re.compile(r"view all|show all|invoice history|invoices", re.IGNORECASE)
_STRIPE_INVOICE_RE = re.compile(r"^https://invoice\.stripe\.com/", re.IGNORECASE)
_DOWNLOAD_RE = re.compile(r"\b(download|pdf|invoice|receipt)\b", re.IGNORECASE)
_VIEW_OR_DOWNLOAD_RE = re.compile(r"\b(view|download|invoice|receipt)\b", re.IGNORECASE)
_INVOICE_CONTEXT_RE = re.compile(r"\b(invoice|receipt|paid|payment|billing|subscription|pro|max)\b", re.IGNORECASE)

_BLOCKED_LOGIN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "Google rejected the automated browser as insecure.",
        re.compile(r"browser or app may not be secure|couldn'?t sign you in", re.IGNORECASE),
    ),
    (
        "Claude or Google is asking for an anti-automation challenge.",
        re.compile(r"captcha|robot|automated|automation|unusual traffic|suspicious", re.IGNORECASE),
    ),
    (
        "Claude login is blocked in this browser session.",
        re.compile(r"access denied|blocked|not supported|temporarily unavailable", re.IGNORECASE),
    ),
)


def _default_out_dir() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path.home() / "Downloads" / f"anthropic_receipts_{ts}"


def ensure_anthropic_profile(profile_id: str = DEFAULT_PROFILE_ID) -> ProfileMeta:
    try:
        meta = get_profile(profile_id)
        if meta.domain != CLAUDE_DOMAIN:
            raise RuntimeError(
                f"Profile {profile_id!r} is bound to {meta.domain!r}, expected {CLAUDE_DOMAIN!r}."
            )
        return meta
    except ProfileNotFound:
        meta = create_profile(DEFAULT_PROFILE_NAME, CLAUDE_DOMAIN)
        if meta.profile_id != profile_id:
            raise RuntimeError(
                f"Expected profile id {profile_id!r}, but created {meta.profile_id!r}. "
                "Delete the conflicting profile and retry."
            )
        return meta


def require_captured_anthropic_profile(profile_id: str = DEFAULT_PROFILE_ID) -> ProfileMeta:
    try:
        meta = get_profile(profile_id)
    except ProfileNotFound as e:
        raise RuntimeError(
            "Anthropic Claude profile not found. Run "
            "`python agent_skills/anthropic_receipts.py capture-profile` first."
        ) from e
    if meta.domain != CLAUDE_DOMAIN:
        raise RuntimeError(
            f"Profile {profile_id!r} is bound to {meta.domain!r}, expected {CLAUDE_DOMAIN!r}."
        )
    if not meta.last_used:
        raise RuntimeError(
            "Anthropic Claude profile exists but has no captured login state. "
            "Run `python agent_skills/anthropic_receipts.py capture-profile` first. "
            "If Claude blocks the automated login, capture must be retried from a browser session it accepts."
        )
    return meta


def blocked_login_reason_from_text(text: str) -> str | None:
    for reason, pattern in _BLOCKED_LOGIN_PATTERNS:
        if pattern.search(text or ""):
            return reason
    return None


async def _body_text(page: Any, *, timeout: int = 2000) -> str:
    try:
        return await page.locator("body").inner_text(timeout=timeout)
    except Exception:
        return ""


async def _visible_count(locator: Any) -> int:
    try:
        count = await locator.count()
    except Exception:
        return 0
    total = 0
    for idx in range(min(count, 12)):
        try:
            if await locator.nth(idx).is_visible(timeout=500):
                total += 1
        except Exception:
            pass
    return total


async def _click_first_visible(locator: Any) -> bool:
    try:
        count = await locator.count()
    except Exception:
        return False
    for idx in range(min(count, 10)):
        item = locator.nth(idx)
        try:
            if await item.is_visible(timeout=500):
                await item.click(timeout=5000)
                return True
        except Exception:
            continue
    return False


async def _claude_block_reason(page: Any) -> str | None:
    text = await _body_text(page)
    return blocked_login_reason_from_text(text)


async def _is_claude_logged_in(page: Any) -> bool:
    url = page.url or ""
    if "claude.ai" not in url:
        return False
    if "/login" in url or "/auth" in url:
        return False

    text = (await _body_text(page)).lower()
    login_controls = await _visible_count(page.get_by_role("button", name=_LOGIN_BUTTON_RE))
    if login_controls and any(phrase in text for phrase in ("continue with google", "sign in", "log in", "email address")):
        return False
    if blocked_login_reason_from_text(text):
        return False

    composer = await _visible_count(
        page.locator(
            'textarea, [contenteditable="true"], [data-testid*="composer"], '
            '[aria-label*="message" i], [placeholder*="message" i]'
        )
    )
    account_controls = await _visible_count(
        page.locator(
            '[data-testid*="profile"], [aria-label*="profile" i], '
            '[aria-label*="account" i], [aria-label*="menu" i]'
        )
    )
    billing_page = "billing" in text and any(word in text for word in ("invoice", "payment", "subscription", "plan"))
    app_text = any(phrase in text for phrase in ("new chat", "recents", "projects", "what can i help", "how can i help"))
    return bool((composer or account_controls) and app_text) or billing_page


async def _start_google_login(page: Any, email: str) -> None:
    await _click_first_visible(page.get_by_role("button", name=re.compile(r"^(log in|sign in)$", re.IGNORECASE)))
    await _click_first_visible(page.get_by_role("link", name=re.compile(r"^(log in|sign in)$", re.IGNORECASE)))
    await page.wait_for_timeout(1500)

    clicked = await _click_first_visible(page.get_by_role("button", name=_GOOGLE_RE))
    if not clicked:
        await _click_first_visible(page.get_by_text(_GOOGLE_RE))
    await page.wait_for_timeout(1500)

    if "accounts.google.com" in (page.url or ""):
        if await _click_first_visible(page.get_by_text(email, exact=False)):
            return
        for locator in (
            page.locator('input[type="email"]'),
            page.get_by_label(re.compile(r"email", re.IGNORECASE)),
            page.get_by_placeholder(re.compile(r"email", re.IGNORECASE)),
        ):
            try:
                if await locator.count():
                    await locator.first.fill(email, timeout=3000)
                    await page.keyboard.press("Enter")
                    return
            except Exception:
                continue


async def capture_anthropic_profile(
    *,
    profile_id: str = DEFAULT_PROFILE_ID,
    email: str = DEFAULT_LOGIN_EMAIL,
    timeout_s: int = 900,
) -> ProfileMeta:
    meta = ensure_anthropic_profile(profile_id)
    bind_check(meta.profile_id, CLAUDE_URL)
    mgr = BrowserSessionManager.instance()
    async with mgr.session(
        run_id=f"capture_{meta.profile_id}",
        options=SessionOptions(headless=False, storage_state_path=storage_state_path(meta.profile_id)),
    ) as sess:
        page = sess.page
        print("Visible browser opened. Log in to Claude with Google and complete any 2FA prompts.", flush=True)
        await page.goto(CLAUDE_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2500)
        if not await _is_claude_logged_in(page):
            await _start_google_login(page, email)
        print(f"Waiting up to {timeout_s // 60} minutes for authenticated Claude...", flush=True)
        deadline = asyncio.get_running_loop().time() + timeout_s
        while asyncio.get_running_loop().time() < deadline:
            reason = await _claude_block_reason(page)
            if reason:
                raise RuntimeError(
                    f"{reason} Claude auth was not captured. "
                    "Retry later from a browser session Claude accepts, or use emailed receipts as the fallback source."
                )
            if await _is_claude_logged_in(page):
                await capture_after_login(page, meta.profile_id)
                return get_profile(meta.profile_id)
            await page.wait_for_timeout(2000)
    raise TimeoutError("Timed out waiting for authenticated Claude; profile was not saved.")


async def verify_anthropic_profile(profile_id: str = DEFAULT_PROFILE_ID) -> dict[str, Any]:
    meta = require_captured_anthropic_profile(profile_id)
    mgr = BrowserSessionManager.instance()
    async with mgr.session(
        run_id=f"verify_{meta.profile_id}",
        options=SessionOptions(storage_state_path=storage_state_path(meta.profile_id)),
    ) as sess:
        page = sess.page
        await page.goto(CLAUDE_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)
        logged_in = await _is_claude_logged_in(page)
        if logged_in:
            touch_last_used(meta.profile_id)
        return {
            "profile_id": meta.profile_id,
            "logged_in": logged_in,
            "blocked_reason": await _claude_block_reason(page),
            "url": page.url,
            "title": await page.title(),
        }


def receipt_candidate_from_invoice_control(payload: dict[str, Any], source_index: int) -> ReceiptCandidate | None:
    href = str(payload.get("href") or "").strip()
    aria = str(payload.get("aria") or "")
    text = str(payload.get("text") or "")
    row_text = str(payload.get("row_text") or "").strip()
    control_text = "\n".join(part for part in (text, aria) if part)
    combined = "\n".join(part for part in (row_text, control_text) if part)
    is_stripe = bool(_STRIPE_INVOICE_RE.search(href))

    if not is_stripe:
        if not _VIEW_OR_DOWNLOAD_RE.search(control_text):
            return None
        if not _INVOICE_CONTEXT_RE.search(combined):
            return None

    parsed_date = parse_receipt_date(combined)
    if parsed_date is None:
        return None

    amount = parse_receipt_amount(combined)
    source_name = "Stripe Invoice" if is_stripe else (text.strip() or aria.strip() or "Invoice")
    return ReceiptCandidate(
        account_id=CLAUDE_ACCOUNT.account_id,
        account_name=CLAUDE_ACCOUNT.name,
        source_kind="stripe_invoice_link" if is_stripe else "invoice_control",
        source_index=source_index,
        source_name=source_name,
        row_text=combined,
        discovered_at=source_index + 1,
        receipt_date=parsed_date.isoformat(),
        amount=amount,
        href=href or None,
        document_token=None,
    )


async def _page_has_billing_content(page: Any) -> bool:
    text = (await _body_text(page)).lower()
    return "billing" in text and any(word in text for word in ("invoice", "receipt", "payment", "subscription", "plan"))


async def _open_settings_from_app(page: Any) -> bool:
    for locator in (
        page.get_by_role("button", name=re.compile(r"(account|profile|menu|settings|initials)", re.IGNORECASE)),
        page.locator('[data-testid*="profile"], [aria-label*="profile" i], [aria-label*="account" i], [aria-label*="menu" i]'),
    ):
        if await _click_first_visible(locator):
            await page.wait_for_timeout(1000)
            break
    clicked_settings = await _click_first_visible(page.get_by_role("menuitem", name=re.compile(r"settings", re.IGNORECASE)))
    if not clicked_settings:
        clicked_settings = await _click_first_visible(page.get_by_role("button", name=re.compile(r"settings", re.IGNORECASE)))
    if not clicked_settings:
        clicked_settings = await _click_first_visible(page.get_by_text(re.compile(r"settings", re.IGNORECASE)))
    if clicked_settings:
        await page.wait_for_timeout(2000)
    return clicked_settings


async def _click_billing_tab(page: Any) -> None:
    for locator in (
        page.get_by_role("tab", name=_BILLING_RE),
        page.get_by_role("link", name=_BILLING_RE),
        page.get_by_role("button", name=_BILLING_RE),
        page.get_by_text(_BILLING_RE),
    ):
        if await _click_first_visible(locator):
            await page.wait_for_timeout(3000)
            return


async def _expand_invoice_history(page: Any) -> None:
    for locator in (
        page.get_by_role("button", name=_VIEW_ALL_RE),
        page.get_by_role("link", name=_VIEW_ALL_RE),
    ):
        try:
            count = await locator.count()
        except Exception:
            continue
        for idx in range(min(count, 4)):
            item = locator.nth(idx)
            try:
                if await item.is_visible(timeout=500):
                    await item.click(timeout=5000)
                    await page.wait_for_timeout(2000)
            except Exception:
                continue


async def _open_billing_page(page: Any) -> None:
    for url in (CLAUDE_BILLING_URL, CLAUDE_SETTINGS_URL, CLAUDE_URL):
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)
        reason = await _claude_block_reason(page)
        if reason:
            raise RuntimeError(f"Claude login is blocked: {reason}")
        if not await _is_claude_logged_in(page):
            continue
        if await _page_has_billing_content(page):
            await _expand_invoice_history(page)
            return
        await _click_billing_tab(page)
        if await _page_has_billing_content(page):
            await _expand_invoice_history(page)
            return
        if url == CLAUDE_URL and await _open_settings_from_app(page):
            await _click_billing_tab(page)
            if await _page_has_billing_content(page):
                await _expand_invoice_history(page)
                return
    raise RuntimeError(
        "Could not open Claude Billing settings. The saved Anthropic profile may be logged out, "
        "or Claude changed the Settings > Billing UI."
    )


async def _discover_receipt_candidates(page: Any) -> list[ReceiptCandidate]:
    payloads = await page.evaluate(
        """
        () => Array.from(document.querySelectorAll('a, button')).map((el) => {
          const text = (el.innerText || el.textContent || '').trim();
          const aria = el.getAttribute('aria-label') || '';
          const href = el.href || el.getAttribute('href') || '';
          const row = el.closest('tr, [role="row"], li, [data-testid*="invoice"], [data-testid*="receipt"]')
            || el.parentElement;
          return {
            href,
            aria,
            text,
            row_text: row ? (row.innerText || row.textContent || '').trim() : text,
          };
        })
        """
    )
    candidates: list[ReceiptCandidate] = []
    seen: set[tuple[str | None, str, str | None]] = set()
    for payload in payloads:
        candidate = receipt_candidate_from_invoice_control(payload, len(candidates))
        if candidate is None:
            continue
        key = (candidate.href, candidate.receipt_date or "", candidate.amount)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
    return candidates


async def list_receipts(profile_id: str = DEFAULT_PROFILE_ID) -> list[ReceiptCandidate]:
    meta = require_captured_anthropic_profile(profile_id)
    touch_last_used(meta.profile_id)
    mgr = BrowserSessionManager.instance()
    async with mgr.session(
        run_id=f"anthropic_receipts_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        options=SessionOptions(storage_state_path=storage_state_path(meta.profile_id)),
    ) as sess:
        page = sess.page
        await _open_billing_page(page)
        return await _discover_receipt_candidates(page)


async def _save_invoice_url(context: Any, url: str, dest: Path) -> Path:
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)

        for role in ("link", "button"):
            locator = page.get_by_role(role, name=_DOWNLOAD_RE)
            try:
                count = await locator.count()
            except Exception:
                continue
            for idx in range(min(count, 6)):
                item = locator.nth(idx)
                try:
                    if not await item.is_visible(timeout=500):
                        continue
                    async with page.expect_download(timeout=7000) as dl_info:
                        await item.click(timeout=7000)
                    download = await dl_info.value
                    suffix = Path(download.suggested_filename or "").suffix or ".pdf"
                    final_path = dest.with_suffix(suffix)
                    await download.save_as(str(final_path))
                    return final_path
                except Exception:
                    continue

        pdf_path = dest.with_suffix(".pdf")
        await page.pdf(path=str(pdf_path), print_background=True, format="Letter")
        return pdf_path
    finally:
        try:
            await page.close()
        except Exception:
            pass


async def _download_candidate(
    page: Any,
    candidate: ReceiptCandidate,
    *,
    out_dir: Path,
) -> DownloadedReceipt:
    if not candidate.href:
        raise RuntimeError(
            "Anthropic receipt candidate has no direct invoice URL. Use the Claude Billing 'View' "
            "control when available so the page exposes a Stripe invoice link."
        )
    parsed_date = date.fromisoformat(candidate.receipt_date) if candidate.receipt_date else None
    filename = build_receipt_filename(
        provider=PROVIDER_FILENAME_PREFIX,
        receipt_date=parsed_date,
        amount=candidate.amount,
    )
    dest = _unique_dest_path(out_dir, filename)
    saved = await _save_invoice_url(page.context, candidate.href, dest)
    return downloaded_receipt_from_candidate(candidate, saved, receipt_date=parsed_date)


async def download_receipts(
    *,
    count: int | None = None,
    profile_id: str = DEFAULT_PROFILE_ID,
    out_dir: Path | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[DownloadedReceipt]:
    if count is None and start_date is None and end_date is None:
        count = 10
    validate_receipt_request(count=count, start_date=start_date, end_date=end_date)

    meta = require_captured_anthropic_profile(profile_id)
    touch_last_used(meta.profile_id)
    out_root = out_dir or _default_out_dir()
    out_root.mkdir(parents=True, exist_ok=True)

    mgr = BrowserSessionManager.instance()
    async with mgr.session(
        run_id=f"anthropic_receipts_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        options=SessionOptions(storage_state_path=storage_state_path(meta.profile_id)),
    ) as sess:
        page = sess.page
        await _open_billing_page(page)
        candidates = await _discover_receipt_candidates(page)
        if not candidates:
            raise RuntimeError("No Claude invoice controls were found in Billing settings.")
        ranked = select_requested_receipt_candidates(
            candidates,
            count=count,
            start_date=start_date,
            end_date=end_date,
        )
        downloads: list[DownloadedReceipt] = []
        for idx, candidate in enumerate(ranked, start=1):
            print(f"Downloading Anthropic receipt {idx}/{len(ranked)}...", flush=True)
            downloads.append(await _download_candidate(page, candidate, out_dir=out_root))

    _manifest_path(out_root).write_text(downloaded_receipts_json(downloads), encoding="utf-8")
    return downloads


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Anthropic / Claude receipt downloader")
    sub = parser.add_subparsers(dest="cmd", required=True)

    cap = sub.add_parser("capture-profile", help="Launch visible browser and save Claude login state")
    cap.add_argument("--profile", default=DEFAULT_PROFILE_ID)
    cap.add_argument("--email", default=DEFAULT_LOGIN_EMAIL)
    cap.add_argument("--timeout", type=int, default=900)

    verify = sub.add_parser("verify-profile", help="Verify saved Claude login state")
    verify.add_argument("--profile", default=DEFAULT_PROFILE_ID)

    list_cmd = sub.add_parser("list", help="List visible Claude billing receipts without downloading")
    list_cmd.add_argument("--profile", default=DEFAULT_PROFILE_ID)

    dl = sub.add_parser("download", help="Download Claude billing receipts")
    dl.add_argument("--profile", default=DEFAULT_PROFILE_ID)
    dl.add_argument("--count", type=int, default=None, help="Number of newest receipts to download. Default: 10.")
    dl.add_argument("--start-date", default="", help="Inclusive lower bound in YYYY-MM-DD")
    dl.add_argument("--end-date", default="", help="Inclusive upper bound in YYYY-MM-DD")
    dl.add_argument("--out-dir", default="", help="Directory to write receipts into.")

    return parser


async def _run(args: argparse.Namespace) -> int:
    if args.cmd == "capture-profile":
        meta = await capture_anthropic_profile(profile_id=args.profile, email=args.email, timeout_s=args.timeout)
        print(json.dumps(meta.to_dict(), indent=2))
        return 0

    if args.cmd == "verify-profile":
        result = await verify_anthropic_profile(profile_id=args.profile)
        print(json.dumps(result, indent=2))
        return 0 if result["logged_in"] else 1

    if args.cmd == "list":
        candidates = await list_receipts(profile_id=args.profile)
        print(json.dumps([asdict(candidate) for candidate in candidates], indent=2))
        return 0

    if args.cmd == "download":
        out_dir = Path(args.out_dir).expanduser() if args.out_dir else None
        start_date = parse_iso_date(args.start_date) if args.start_date else None
        end_date = parse_iso_date(args.end_date) if args.end_date else None
        downloads = await download_receipts(
            count=args.count,
            profile_id=args.profile,
            out_dir=out_dir,
            start_date=start_date,
            end_date=end_date,
        )
        print(downloaded_receipts_json(downloads))
        return 0

    raise RuntimeError(f"Unknown command: {args.cmd}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
