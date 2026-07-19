#!/usr/bin/env python3
"""OpenAI / ChatGPT receipt downloader.

One-time setup:

    /home/chieh/google-adk-env/adk-venv/bin/python \
        agent_skills/openai_receipts.py capture-profile

Download recent ChatGPT billing receipts:

    /home/chieh/google-adk-env/adk-venv/bin/python \
        agent_skills/openai_receipts.py download --count 10

The downloader uses the saved ChatGPT browser profile, opens the ChatGPT
Billing settings modal, extracts Stripe invoice links, and saves invoice pages
as PDFs. Password and 2FA prompts stay in the visible browser during capture.
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
from agent_skills.web_ui_change import recover_website_ui_change


CHATGPT_DOMAIN = "chatgpt.com"
DEFAULT_PROFILE_ID = "openai_chatgpt"
DEFAULT_PROFILE_NAME = "OpenAI ChatGPT"
DEFAULT_LOGIN_EMAIL = "Chieh.t.wu@gmail.com"
CHATGPT_URL = "https://chatgpt.com/"
CHATGPT_BILLING_URL = "https://chatgpt.com/#settings/Billing"
PROVIDER_FILENAME_PREFIX = "openai"
CHATGPT_ACCOUNT = BillingAccount(account_id="chatgpt", name="ChatGPT", open=True)

_LOGIN_BUTTON_RE = re.compile(r"^(log in|sign up|sign up for free)$", re.IGNORECASE)
_GOOGLE_RE = re.compile(r"continue with google|sign in with google", re.IGNORECASE)
_VIEW_ALL_RE = re.compile(r"^view all$", re.IGNORECASE)
_DATE_FROM_ARIA_RE = re.compile(r"\binvoice from\s+(.+)$", re.IGNORECASE)
_STRIPE_INVOICE_RE = re.compile(r"^https://invoice\.stripe\.com/", re.IGNORECASE)
_DOWNLOAD_RE = re.compile(r"\b(download|pdf|invoice|receipt)\b", re.IGNORECASE)


def _default_out_dir() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path.home() / "Downloads" / f"openai_receipts_{ts}"


def ensure_openai_profile(profile_id: str = DEFAULT_PROFILE_ID) -> ProfileMeta:
    try:
        meta = get_profile(profile_id)
        if meta.domain != CHATGPT_DOMAIN:
            raise RuntimeError(
                f"Profile {profile_id!r} is bound to {meta.domain!r}, expected {CHATGPT_DOMAIN!r}."
            )
        return meta
    except ProfileNotFound:
        meta = create_profile(DEFAULT_PROFILE_NAME, CHATGPT_DOMAIN)
        if meta.profile_id != profile_id:
            raise RuntimeError(
                f"Expected profile id {profile_id!r}, but created {meta.profile_id!r}. "
                "Delete the conflicting profile and retry."
            )
        return meta


def require_captured_openai_profile(profile_id: str = DEFAULT_PROFILE_ID) -> ProfileMeta:
    try:
        meta = get_profile(profile_id)
    except ProfileNotFound as e:
        raise RuntimeError(
            "OpenAI ChatGPT profile not found. Run "
            "`python agent_skills/openai_receipts.py capture-profile` first."
        ) from e
    if meta.domain != CHATGPT_DOMAIN:
        raise RuntimeError(
            f"Profile {profile_id!r} is bound to {meta.domain!r}, expected {CHATGPT_DOMAIN!r}."
        )
    if not meta.last_used:
        raise RuntimeError(
            "OpenAI ChatGPT profile exists but has no captured login state. "
            "Run `python agent_skills/openai_receipts.py capture-profile` first."
        )
    return meta


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


async def _is_chatgpt_logged_in(page: Any) -> bool:
    if "chatgpt.com" not in (page.url or ""):
        return False
    if "/auth/" in (page.url or ""):
        return False
    login_buttons = await _visible_count(page.get_by_role("button", name=_LOGIN_BUTTON_RE))
    login_links = await _visible_count(page.get_by_role("link", name=_LOGIN_BUTTON_RE))
    tailored_prompt = await _visible_count(page.get_by_text("Get responses tailored to you", exact=False))
    if login_buttons or login_links or tailored_prompt:
        return False
    profile_controls = await _visible_count(
        page.locator('[data-testid*="profile"], [aria-label*="profile" i], [aria-label*="account" i]')
    )
    composer = await _visible_count(page.locator('textarea, [contenteditable="true"], [data-testid*="composer"]'))
    return bool(profile_controls or composer)


async def _click_first_visible(locator: Any) -> bool:
    try:
        count = await locator.count()
    except Exception:
        return False
    for idx in range(min(count, 8)):
        item = locator.nth(idx)
        try:
            if await item.is_visible(timeout=500):
                await item.click(timeout=5000)
                return True
        except Exception:
            continue
    return False


async def _start_google_login(page: Any, email: str) -> None:
    clicked = await _click_first_visible(page.get_by_role("button", name=re.compile(r"^log in$", re.IGNORECASE)))
    if not clicked:
        await _click_first_visible(page.get_by_role("link", name=re.compile(r"^log in$", re.IGNORECASE)))
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


async def capture_openai_profile(
    *,
    profile_id: str = DEFAULT_PROFILE_ID,
    email: str = DEFAULT_LOGIN_EMAIL,
    timeout_s: int = 900,
) -> ProfileMeta:
    meta = ensure_openai_profile(profile_id)
    bind_check(meta.profile_id, CHATGPT_URL)
    mgr = BrowserSessionManager.instance()
    async with mgr.session(
        run_id=f"capture_{meta.profile_id}",
        options=SessionOptions(headless=False, storage_state_path=storage_state_path(meta.profile_id)),
    ) as sess:
        page = sess.page
        print("Visible browser opened. Log in to ChatGPT with Google and complete any 2FA prompts.", flush=True)
        await page.goto(CHATGPT_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        if not await _is_chatgpt_logged_in(page):
            await _start_google_login(page, email)
        print(f"Waiting up to {timeout_s // 60} minutes for authenticated ChatGPT...", flush=True)
        deadline = asyncio.get_running_loop().time() + timeout_s
        while asyncio.get_running_loop().time() < deadline:
            if await _is_chatgpt_logged_in(page):
                await capture_after_login(page, meta.profile_id)
                return get_profile(meta.profile_id)
            await page.wait_for_timeout(2000)
    raise TimeoutError("Timed out waiting for authenticated ChatGPT; profile was not saved.")


async def verify_openai_profile(profile_id: str = DEFAULT_PROFILE_ID) -> dict[str, Any]:
    meta = require_captured_openai_profile(profile_id)
    mgr = BrowserSessionManager.instance()
    async with mgr.session(
        run_id=f"verify_{meta.profile_id}",
        options=SessionOptions(storage_state_path=storage_state_path(meta.profile_id)),
    ) as sess:
        page = sess.page
        await page.goto(CHATGPT_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)
        logged_in = await _is_chatgpt_logged_in(page)
        if logged_in:
            touch_last_used(meta.profile_id)
        return {
            "profile_id": meta.profile_id,
            "logged_in": logged_in,
            "url": page.url,
            "title": await page.title(),
        }


def receipt_candidate_from_invoice_link(payload: dict[str, Any], source_index: int) -> ReceiptCandidate | None:
    href = str(payload.get("href") or "").strip()
    if not _STRIPE_INVOICE_RE.search(href):
        return None

    aria = str(payload.get("aria") or "")
    date_text = str(payload.get("date_text") or "").strip()
    amount_text = str(payload.get("amount_text") or "").strip()
    status_text = str(payload.get("status_text") or "").strip()

    aria_match = _DATE_FROM_ARIA_RE.search(aria)
    parsed_date = parse_receipt_date(date_text)
    if parsed_date is None and aria_match:
        parsed_date = parse_receipt_date(aria_match.group(1))
    if parsed_date is None:
        parsed_date = parse_receipt_date(str(payload.get("row_text") or ""))
    if parsed_date is None:
        return None

    amount = parse_receipt_amount(amount_text) or parse_receipt_amount(str(payload.get("row_text") or ""))
    row_text = "\n".join(part for part in (date_text, amount_text, status_text, "View") if part)
    return ReceiptCandidate(
        account_id=CHATGPT_ACCOUNT.account_id,
        account_name=CHATGPT_ACCOUNT.name,
        source_kind="stripe_invoice_link",
        source_index=source_index,
        source_name="Invoice",
        row_text=row_text,
        discovered_at=source_index + 1,
        receipt_date=parsed_date.isoformat(),
        amount=amount,
        href=href,
        document_token=None,
    )


async def _open_billing_page(page: Any) -> None:
    await page.goto(CHATGPT_BILLING_URL, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(8000)
    if not await _is_chatgpt_logged_in(page):
        raise RuntimeError(
            "Saved OpenAI ChatGPT profile is not logged in. Run "
            "`python agent_skills/openai_receipts.py capture-profile` again."
        )
    try:
        await page.get_by_text("Billing history", exact=False).first.wait_for(timeout=15000)
    except Exception as e:
        raise RuntimeError("Could not find ChatGPT Billing history in settings.") from e
    try:
        button = page.get_by_role("button", name=_VIEW_ALL_RE).first
        if await button.count() and await button.is_visible(timeout=1000):
            await button.click(timeout=5000)
            await page.wait_for_timeout(3000)
    except Exception:
        pass


async def _discover_receipt_candidates(page: Any) -> list[ReceiptCandidate]:
    payloads = await page.evaluate(
        """
        () => Array.from(document.querySelectorAll('a[href*="invoice.stripe.com"]')).map((a) => {
          const parent = a.parentElement;
          const children = parent ? Array.from(parent.children) : [];
          const idx = children.indexOf(a);
          const textAt = (offset) => {
            const el = idx >= offset ? children[idx - offset] : null;
            return (el && (el.innerText || el.textContent) || '').trim();
          };
          return {
            href: a.href || a.getAttribute('href') || '',
            aria: a.getAttribute('aria-label') || '',
            text: (a.innerText || a.textContent || '').trim(),
            date_text: textAt(3),
            amount_text: textAt(2),
            status_text: textAt(1),
            row_text: [textAt(3), textAt(2), textAt(1), (a.innerText || a.textContent || '').trim()]
              .filter(Boolean).join('\\n'),
          };
        })
        """
    )
    candidates: list[ReceiptCandidate] = []
    seen: set[str] = set()
    for payload in payloads:
        candidate = receipt_candidate_from_invoice_link(payload, len(candidates))
        if candidate is None or not candidate.href or candidate.href in seen:
            continue
        seen.add(candidate.href)
        candidates.append(candidate)
    return candidates


async def list_receipts(profile_id: str = DEFAULT_PROFILE_ID) -> list[ReceiptCandidate]:
    meta = require_captured_openai_profile(profile_id)
    touch_last_used(meta.profile_id)
    mgr = BrowserSessionManager.instance()
    async with mgr.session(
        run_id=f"openai_receipts_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
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
        raise RuntimeError("OpenAI receipt candidate is missing its Stripe invoice URL.")
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

    meta = require_captured_openai_profile(profile_id)
    touch_last_used(meta.profile_id)
    out_root = out_dir or _default_out_dir()
    out_root.mkdir(parents=True, exist_ok=True)

    mgr = BrowserSessionManager.instance()
    async with mgr.session(
        run_id=f"openai_receipts_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        options=SessionOptions(storage_state_path=storage_state_path(meta.profile_id)),
    ) as sess:
        page = sess.page
        await _open_billing_page(page)
        candidates = await _discover_receipt_candidates(page)
        if not candidates:
            raise RuntimeError("No ChatGPT Stripe invoice links were found in Billing history.")
        ranked = select_requested_receipt_candidates(
            candidates,
            count=count,
            start_date=start_date,
            end_date=end_date,
        )
        downloads: list[DownloadedReceipt] = []
        for idx, candidate in enumerate(ranked, start=1):
            print(f"Downloading OpenAI receipt {idx}/{len(ranked)}...", flush=True)
            downloads.append(await _download_candidate(page, candidate, out_dir=out_root))

    _manifest_path(out_root).write_text(downloaded_receipts_json(downloads), encoding="utf-8")
    return downloads


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OpenAI / ChatGPT receipt downloader")
    sub = parser.add_subparsers(dest="cmd", required=True)

    cap = sub.add_parser("capture-profile", help="Launch visible browser and save ChatGPT login state")
    cap.add_argument("--profile", default=DEFAULT_PROFILE_ID)
    cap.add_argument("--email", default=DEFAULT_LOGIN_EMAIL)
    cap.add_argument("--timeout", type=int, default=900)

    sub.add_parser("verify-profile", help="Verify saved ChatGPT login state")

    list_cmd = sub.add_parser("list", help="List visible ChatGPT billing receipts without downloading")
    list_cmd.add_argument("--profile", default=DEFAULT_PROFILE_ID)

    dl = sub.add_parser("download", help="Download ChatGPT billing receipts")
    dl.add_argument("--profile", default=DEFAULT_PROFILE_ID)
    dl.add_argument("--count", type=int, default=None, help="Number of newest receipts to download. Default: 10.")
    dl.add_argument("--start-date", default="", help="Inclusive lower bound in YYYY-MM-DD")
    dl.add_argument("--end-date", default="", help="Inclusive upper bound in YYYY-MM-DD")
    dl.add_argument("--out-dir", default="", help="Directory to write receipts into.")

    return parser


async def _run(args: argparse.Namespace) -> int:
    if args.cmd == "capture-profile":
        meta = await capture_openai_profile(profile_id=args.profile, email=args.email, timeout_s=args.timeout)
        print(json.dumps(meta.to_dict(), indent=2))
        return 0

    if args.cmd == "verify-profile":
        result = await verify_openai_profile()
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
        recover_website_ui_change(
            skill="openai-receipts",
            intent="Open ChatGPT Billing and extract or download the requested invoice receipts without changing billing settings.",
            operation=args.cmd,
            exc=e,
            project_root=Path(__file__).resolve().parents[1],
            retry_safe=args.cmd in {"list", "download", "verify-profile"},
        )
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
