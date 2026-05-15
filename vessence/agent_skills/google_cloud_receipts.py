#!/usr/bin/env python3
"""Google Cloud Billing receipt downloader.

One-time setup:

1. Capture a browser profile bound to ``console.cloud.google.com``:

   /home/chieh/google-adk-env/adk-venv/bin/python \
       agent_skills/google_cloud_receipts.py capture-profile

2. Download the most recent receipts:

   /home/chieh/google-adk-env/adk-venv/bin/python \
       agent_skills/google_cloud_receipts.py download --count 5

The downloader automates the Google Cloud Billing console using the saved
browser session. It does not depend on undocumented billing APIs.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

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


GOOGLE_CLOUD_DOMAIN = "console.cloud.google.com"
DEFAULT_PROFILE_ID = "google_cloud_billing"
DEFAULT_PROFILE_NAME = "Google Cloud Billing"
MANAGE_BILLING_URL = "https://console.cloud.google.com/billing"
HISTORY_URL_TMPL = "https://console.cloud.google.com/billing/{account_id}/history"
DOCUMENTS_URL_TMPL = "https://console.cloud.google.com/billing/{account_id}/invoices"
PROVIDER_FILENAME_PREFIX = "google"

_RECEIPT_RE = re.compile(r"\breceipt\b", re.IGNORECASE)
_DOCUMENT_RE = re.compile(r"\b(statement|invoice|receipt)\b", re.IGNORECASE)
_AMOUNT_PATTERNS = (
    re.compile(r"\$\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{2}))"),
    re.compile(r"\bUSD\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{2}))\b", re.IGNORECASE),
    re.compile(r"\b([0-9]+(?:,[0-9]{3})*\.[0-9]{2})\b"),
)
_DATE_PATTERNS = (
    ("%B %d, %Y", re.compile(r"\b([A-Z][a-z]+ \d{1,2}, \d{4})\b")),
    ("%b %d, %Y", re.compile(r"\b([A-Z][a-z]{2} \d{1,2}, \d{4})\b")),
    ("%Y-%m-%d", re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")),
    ("%m/%d/%Y", re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b")),
)


@dataclass(frozen=True)
class BillingAccount:
    account_id: str
    name: str
    open: bool


@dataclass(frozen=True)
class ReceiptCandidate:
    account_id: str
    account_name: str
    source_kind: str
    source_index: int
    source_name: str
    row_text: str
    discovered_at: int
    receipt_date: str | None = None
    amount: str | None = None
    href: str | None = None
    document_token: str | None = None


@dataclass(frozen=True)
class DownloadedReceipt:
    account_id: str
    account_name: str
    receipt_date: str | None
    amount: str | None
    source_name: str
    row_text: str
    path: str


def parse_receipt_date(text: str) -> date | None:
    for fmt, pat in _DATE_PATTERNS:
        m = pat.search(text or "")
        if not m:
            continue
        try:
            return datetime.strptime(m.group(1), fmt).date()
        except ValueError:
            continue
    return None


def parse_receipt_amount(text: str) -> str | None:
    for pat in _AMOUNT_PATTERNS:
        m = pat.search(text or "")
        if not m:
            continue
        return m.group(1).replace(",", "")
    return None


def sanitize_filename_piece(text: str, *, fallback: str = "receipt") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (text or "").strip())
    cleaned = cleaned.strip("._-")
    return cleaned[:80] or fallback


def build_receipt_filename(
    *,
    provider: str,
    receipt_date: date | None,
    amount: str | None,
    fallback: str = "receipt",
) -> str:
    pieces = [sanitize_filename_piece(provider, fallback=provider)]
    if receipt_date is not None:
        pieces.extend([
            str(receipt_date.month),
            str(receipt_date.day),
            str(receipt_date.year),
        ])
    else:
        pieces.append("undated")
    pieces.append(sanitize_filename_piece(amount or "unknown_amount", fallback="unknown_amount"))
    return "_".join(pieces) + ".pdf"


def parse_iso_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as e:
        raise ValueError(f"Invalid date {text!r}. Expected YYYY-MM-DD.") from e


def candidate_date(candidate: ReceiptCandidate) -> date | None:
    if candidate.receipt_date:
        try:
            return date.fromisoformat(candidate.receipt_date)
        except ValueError:
            pass
    return parse_receipt_date(candidate.row_text)


def sort_receipt_candidates(candidates: Iterable[ReceiptCandidate]) -> list[ReceiptCandidate]:
    def _key(candidate: ReceiptCandidate) -> tuple[date, int]:
        parsed = candidate_date(candidate) or date.min
        return (parsed, -candidate.discovered_at)

    return sorted(list(candidates), key=_key, reverse=True)


def filter_receipt_candidates_by_date(
    candidates: Iterable[ReceiptCandidate],
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[ReceiptCandidate]:
    out: list[ReceiptCandidate] = []
    for candidate in candidates:
        parsed = candidate_date(candidate)
        if parsed is None:
            continue
        if start_date is not None and parsed < start_date:
            continue
        if end_date is not None and parsed > end_date:
            continue
        out.append(candidate)
    return out


def _manifest_path(out_dir: Path) -> Path:
    return out_dir / "manifest.json"


def _default_out_dir() -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path.home() / "Downloads" / f"google_cloud_receipts_{ts}"


def _run_json(cmd: list[str]) -> Any:
    proc = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{stderr}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Command returned invalid JSON: {' '.join(cmd)}\n{e}") from e


def list_billing_accounts() -> list[BillingAccount]:
    data = _run_json(["gcloud", "billing", "accounts", "list", "--format=json"])
    out: list[BillingAccount] = []
    for row in data:
        account_id = str(row.get("name") or "").strip()
        if account_id.startswith("billingAccounts/"):
            account_id = account_id.split("/", 1)[1]
        if not account_id:
            continue
        out.append(BillingAccount(
            account_id=account_id,
            name=str(row.get("displayName") or account_id),
            open=bool(row.get("open", False)),
        ))
    return out


def ensure_google_profile(profile_id: str = DEFAULT_PROFILE_ID) -> ProfileMeta:
    try:
        meta = get_profile(profile_id)
        if meta.domain != GOOGLE_CLOUD_DOMAIN:
            raise RuntimeError(
                f"Profile {profile_id!r} is bound to {meta.domain!r}, expected {GOOGLE_CLOUD_DOMAIN!r}."
            )
        return meta
    except ProfileNotFound:
        meta = create_profile(DEFAULT_PROFILE_NAME, GOOGLE_CLOUD_DOMAIN)
        if meta.profile_id != profile_id:
            raise RuntimeError(
                f"Expected profile id {profile_id!r}, but created {meta.profile_id!r}. "
                "Delete the conflicting profile and retry."
            )
        return meta


def require_captured_google_profile(profile_id: str = DEFAULT_PROFILE_ID) -> ProfileMeta:
    try:
        meta = get_profile(profile_id)
    except ProfileNotFound as e:
        raise RuntimeError(
            "Google Cloud Billing profile not found. Run "
            "`python agent_skills/google_cloud_receipts.py capture-profile` first."
        ) from e
    if meta.domain != GOOGLE_CLOUD_DOMAIN:
        raise RuntimeError(
            f"Profile {profile_id!r} is bound to {meta.domain!r}, expected {GOOGLE_CLOUD_DOMAIN!r}."
        )
    if not meta.last_used:
        raise RuntimeError(
            "Google Cloud Billing profile exists but has no captured login state. "
            "Run `python agent_skills/google_cloud_receipts.py capture-profile` first."
        )
    return meta


async def capture_google_profile(
    *,
    profile_id: str = DEFAULT_PROFILE_ID,
    timeout_s: int = 300,
) -> ProfileMeta:
    meta = ensure_google_profile(profile_id)
    bind_check(meta.profile_id, MANAGE_BILLING_URL)
    mgr = BrowserSessionManager.instance()
    async with mgr.session(
        run_id=f"capture_{meta.profile_id}",
        options=SessionOptions(headless=False),
    ) as sess:
        page = sess.page
        print(
            "Visible browser opened. Log in to Google Cloud Billing and land on any billing page.",
            flush=True,
        )
        await page.goto(MANAGE_BILLING_URL, wait_until="domcontentloaded")
        await _wait_for_billing_console_ready(page, timeout_s=timeout_s)
        await capture_after_login(page, meta.profile_id)
    return get_profile(meta.profile_id)


async def _wait_for_billing_console_ready(page: Any, *, timeout_s: int) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while True:
        if asyncio.get_running_loop().time() > deadline:
            raise TimeoutError(
                f"Timed out after {timeout_s}s waiting for a logged-in Google Cloud Billing page."
            )
        url = page.url or ""
        if "accounts.google.com" not in url and "console.cloud.google.com" in url and "/billing" in url:
            for text in ("Manage billing accounts", "Transactions", "Documents", "Overview"):
                try:
                    if await page.get_by_text(text, exact=False).count():
                        return
                except Exception:
                    pass
        await page.wait_for_timeout(1000)


def _select_accounts(billing_account_ids: list[str] | None) -> list[BillingAccount]:
    accounts = [a for a in list_billing_accounts() if a.open]
    if not billing_account_ids:
        return accounts
    wanted = {x.strip() for x in billing_account_ids if x.strip()}
    filtered = [a for a in accounts if a.account_id in wanted]
    missing = wanted.difference({a.account_id for a in filtered})
    if missing:
        raise RuntimeError(f"Billing account(s) not found or not open: {', '.join(sorted(missing))}")
    return filtered


async def _open_history_page(page: Any, account_id: str, profile_id: str) -> None:
    url = HISTORY_URL_TMPL.format(account_id=account_id)
    bind_check(profile_id, url)
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_timeout(1500)


async def _open_documents_page(page: Any, account_id: str, profile_id: str) -> None:
    url = DOCUMENTS_URL_TMPL.format(account_id=account_id)
    bind_check(profile_id, url)
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_timeout(1500)


async def _maybe_expand_date_range(page: Any) -> None:
    triggers = [
        page.get_by_role("button", name=re.compile(r"(last 3 months|date range|this year)", re.I)),
        page.get_by_role("combobox", name=re.compile(r"date range", re.I)),
    ]
    for trigger in triggers:
        try:
            if await trigger.count():
                await trigger.first.click(timeout=3000)
                await page.wait_for_timeout(500)
                for role in ("option", "menuitem"):
                    locator = page.get_by_role(role, name=re.compile(r"this year", re.I))
                    if await locator.count():
                        await locator.first.click(timeout=3000)
                        await page.wait_for_timeout(1000)
                        return
        except Exception:
            continue


async def _locator_row_text(locator: Any) -> str:
    script = """
        (el) => {
          const row = el.closest('tr,[role="row"],[data-row-index]');
          const box = row || el.closest('section,article,div,li') || el;
          return (box.innerText || el.innerText || '').trim();
        }
    """
    try:
        return ((await locator.evaluate(script)) or "").strip()
    except Exception:
        try:
            return ((await locator.text_content()) or "").strip()
        except Exception:
            return ""


async def _discover_receipt_candidates(page: Any, account: BillingAccount) -> list[ReceiptCandidate]:
    queries = (
        ("link", page.get_by_role("link", name=_RECEIPT_RE)),
        ("button", page.get_by_role("button", name=_RECEIPT_RE)),
    )
    candidates: list[ReceiptCandidate] = []
    discovered_at = 0
    for source_kind, locator in queries:
        try:
            count = await locator.count()
        except Exception:
            continue
        for idx in range(count):
            item = locator.nth(idx)
            try:
                if not await item.is_visible():
                    continue
            except Exception:
                continue
            row_text = await _locator_row_text(item)
            source_name = ((await item.inner_text()) or "").strip() or "Receipt"
            href = None
            if source_kind == "link":
                try:
                    href = await item.get_attribute("href")
                except Exception:
                    href = None
            discovered_at += 1
            parsed_date = parse_receipt_date(row_text or source_name)
            amount = parse_receipt_amount(row_text)
            candidates.append(
                ReceiptCandidate(
                    account_id=account.account_id,
                    account_name=account.name,
                    source_kind=source_kind,
                    source_index=idx,
                    source_name=source_name,
                    row_text=row_text,
                    discovered_at=discovered_at,
                    receipt_date=parsed_date.isoformat() if parsed_date else None,
                    amount=amount,
                    href=href,
                    document_token=None,
                )
            )
    return candidates


async def _wait_for_frame_url(page: Any, url_fragment: str, *, timeout_ms: int = 20000) -> Any:
    deadline = asyncio.get_running_loop().time() + (timeout_ms / 1000.0)
    while True:
        for frame in page.frames:
            if url_fragment in (frame.url or ""):
                return frame
        if asyncio.get_running_loop().time() > deadline:
            raise RuntimeError(f"Timed out waiting for frame containing {url_fragment!r}.")
        await page.wait_for_timeout(250)


async def _discover_document_candidates(page: Any, account: BillingAccount) -> list[ReceiptCandidate]:
    frame = await _wait_for_frame_url(page, "/documentcenter")
    rows = frame.locator("[data-data-token]")
    try:
        count = await rows.count()
    except Exception:
        return []
    candidates: list[ReceiptCandidate] = []
    discovered_at = 0
    for idx in range(count):
        row = rows.nth(idx)
        try:
            text = ((await row.inner_text()) or "").strip()
        except Exception:
            continue
        if not text or not _DOCUMENT_RE.search(text):
            continue
        parsed_date = parse_receipt_date(text)
        amount = parse_receipt_amount(text)
        token = await row.get_attribute("data-data-token")
        if not token:
            continue
        discovered_at += 1
        match = _DOCUMENT_RE.search(text)
        source_name = match.group(1).title() if match else "Document"
        candidates.append(
            ReceiptCandidate(
                account_id=account.account_id,
                account_name=account.name,
                source_kind="document_row",
                source_index=idx,
                source_name=source_name,
                row_text=text,
                discovered_at=discovered_at,
                receipt_date=parsed_date.isoformat() if parsed_date else None,
                amount=amount,
                href=None,
                document_token=token,
            )
        )
    return candidates


def _unique_dest_path(out_dir: Path, filename: str) -> Path:
    base = out_dir / filename
    if not base.exists():
        return base
    stem = base.stem
    suffix = base.suffix
    i = 2
    while True:
        candidate = out_dir / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def _final_download_path(dest: Path, suggested_filename: str | None) -> Path:
    suffix = dest.suffix
    if suggested_filename:
        sfx = Path(suggested_filename).suffix.lower()
        if sfx:
            suffix = sfx
    return dest.with_suffix(suffix)


async def _try_direct_cookie_download(context: Any, url: str, dest: Path) -> Path | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    cookies = await context.cookies([url])
    cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
    }
    if cookie_header:
        headers["Cookie"] = cookie_header

    def _fetch() -> tuple[bytes, str]:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read(), resp.headers.get("Content-Type", "")

    try:
        body, content_type = await asyncio.to_thread(_fetch)
    except Exception:
        return None
    if not body:
        return None
    if "pdf" in content_type.lower() or body.lstrip().startswith(b"%PDF"):
        out = dest.with_suffix(".pdf")
        out.write_bytes(body)
        return out
    return None


async def _embedded_document_url(page: Any) -> str | None:
    selectors = (
        ("iframe[src]", "src"),
        ("embed[src]", "src"),
        ("object[data]", "data"),
        ("a[href$='.pdf']", "href"),
    )
    for selector, attr in selectors:
        locator = page.locator(selector)
        try:
            if await locator.count():
                value = await locator.first.get_attribute(attr)
                if value:
                    return urllib.parse.urljoin(page.url, value)
        except Exception:
            continue
    return None


async def _save_receipt_page(
    context: Any,
    url: str,
    dest: Path,
    *,
    existing_page: Any | None = None,
) -> Path | None:
    page = existing_page
    owns_page = False
    if page is None:
        page = await context.new_page()
        owns_page = True
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)

    try:
        direct = await _try_direct_cookie_download(context, url, dest)
        if direct:
            return direct

        embedded = await _embedded_document_url(page)
        if embedded:
            direct = await _try_direct_cookie_download(context, embedded, dest)
            if direct:
                return direct

        for role in ("button", "link"):
            locator = page.get_by_role(role, name=re.compile(r"download", re.I))
            try:
                if await locator.count():
                    async with page.expect_download(timeout=6000) as dl_info:
                        await locator.first.click(timeout=6000)
                    dl = await dl_info.value
                    final_path = _final_download_path(dest, dl.suggested_filename)
                    await dl.save_as(str(final_path))
                    return final_path
            except Exception:
                continue

        pdf_path = dest.with_suffix(".pdf")
        await page.pdf(path=str(pdf_path), print_background=True)
        return pdf_path
    finally:
        if owns_page:
            try:
                await page.close()
            except Exception:
                pass


async def _resolve_candidate_locator(page: Any, candidate: ReceiptCandidate) -> Any:
    locator = (
        page.get_by_role("button", name=_RECEIPT_RE)
        if candidate.source_kind == "button"
        else page.get_by_role("link", name=_RECEIPT_RE)
    )
    count = await locator.count()
    if candidate.source_index >= count:
        raise RuntimeError(
            f"Receipt locator index {candidate.source_index} no longer exists for billing account "
            f"{candidate.account_id}. The Transactions page layout may have changed."
        )
    return locator.nth(candidate.source_index)


async def _click_for_download(page: Any, locator: Any, dest: Path) -> Path:
    before_pages = set(page.context.pages)
    try:
        await locator.scroll_into_view_if_needed(timeout=5000)
    except Exception:
        pass

    try:
        async with page.expect_download(timeout=8000) as dl_info:
            await locator.click(timeout=8000)
        download = await dl_info.value
        final_path = _final_download_path(dest, download.suggested_filename)
        await download.save_as(str(final_path))
        return final_path
    except Exception:
        pass

    await page.wait_for_timeout(2000)
    new_pages = [p for p in page.context.pages if p not in before_pages]
    if new_pages:
        receipt_page = new_pages[-1]
        try:
            saved = await _save_receipt_page(page.context, receipt_page.url, dest, existing_page=receipt_page)
            if saved:
                return saved
        finally:
            try:
                await receipt_page.close()
            except Exception:
                pass

    if page.url and "billing" not in page.url.lower():
        saved = await _save_receipt_page(page.context, page.url, dest, existing_page=page)
        if saved:
            return saved

    raise RuntimeError("Receipt click did not yield a downloadable document or printable receipt page.")


async def _download_document_candidate(page: Any, candidate: ReceiptCandidate, dest: Path) -> Path:
    if not candidate.document_token:
        raise RuntimeError("Document candidate is missing its Google Payments token.")
    frame = await _wait_for_frame_url(page, "/documentcenter")
    row = frame.locator(f'[data-data-token="{candidate.document_token}"]').first
    if not await row.count():
        raise RuntimeError(
            f"Document token {candidate.document_token!r} no longer exists for billing account "
            f"{candidate.account_id}. The Documents page layout may have changed."
        )
    checkbox = row.get_by_role("checkbox").first
    if not await checkbox.count():
        raise RuntimeError("Could not find the document selection checkbox.")
    await checkbox.evaluate("(el) => el.click()")
    button = frame.get_by_role("button", name=re.compile(r"download selected", re.I)).first
    if not await button.count():
        raise RuntimeError("Could not find the Download selected button.")
    async with page.context.expect_page(timeout=10000) as popup_info:
        await button.click(timeout=10000)
    popup = await popup_info.value
    try:
        download = await popup.wait_for_event("download", timeout=15000)
        final_path = _final_download_path(dest, download.suggested_filename)
        await download.save_as(str(final_path))
        return final_path
    finally:
        try:
            await popup.close()
        except Exception:
            pass


async def _download_candidate(
    page: Any,
    candidate: ReceiptCandidate,
    *,
    out_dir: Path,
    profile_id: str,
) -> DownloadedReceipt:
    parsed_date = (
        date.fromisoformat(candidate.receipt_date)
        if candidate.receipt_date
        else parse_receipt_date(candidate.row_text)
    )
    filename = build_receipt_filename(
        provider=PROVIDER_FILENAME_PREFIX,
        receipt_date=parsed_date,
        amount=candidate.amount,
    )
    dest = _unique_dest_path(out_dir, filename)

    if candidate.source_kind == "document_row":
        await _open_documents_page(page, candidate.account_id, profile_id)
        saved = await _download_document_candidate(page, candidate, dest)
        return DownloadedReceipt(
            account_id=candidate.account_id,
            account_name=candidate.account_name,
            receipt_date=parsed_date.isoformat() if parsed_date else None,
            amount=candidate.amount,
            source_name=candidate.source_name,
            row_text=candidate.row_text,
            path=str(saved),
        )

    await _open_history_page(page, candidate.account_id, profile_id)
    await _maybe_expand_date_range(page)

    if candidate.href:
        href = urllib.parse.urljoin(page.url, candidate.href)
        saved = await _save_receipt_page(page.context, href, dest)
        if saved:
            return DownloadedReceipt(
                account_id=candidate.account_id,
                account_name=candidate.account_name,
                receipt_date=parsed_date.isoformat() if parsed_date else None,
                amount=candidate.amount,
                source_name=candidate.source_name,
                row_text=candidate.row_text,
                path=str(saved),
            )

    locator = await _resolve_candidate_locator(page, candidate)
    saved = await _click_for_download(page, locator, dest)
    return DownloadedReceipt(
        account_id=candidate.account_id,
        account_name=candidate.account_name,
        receipt_date=parsed_date.isoformat() if parsed_date else None,
        amount=candidate.amount,
        source_name=candidate.source_name,
        row_text=candidate.row_text,
        path=str(saved),
    )


async def download_recent_receipts(
    *,
    count: int | None = None,
    profile_id: str = DEFAULT_PROFILE_ID,
    billing_account_ids: list[str] | None = None,
    out_dir: Path | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[DownloadedReceipt]:
    if count is not None and count < 1:
        raise ValueError("count must be >= 1")
    if count is None and start_date is None and end_date is None:
        raise ValueError("Provide either count or a date range.")
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ValueError("start_date must be <= end_date")
    meta = require_captured_google_profile(profile_id)
    touch_last_used(meta.profile_id)

    out_root = out_dir or _default_out_dir()
    out_root.mkdir(parents=True, exist_ok=True)
    accounts = _select_accounts(billing_account_ids)
    all_candidates: list[ReceiptCandidate] = []

    mgr = BrowserSessionManager.instance()
    async with mgr.session(
        run_id=f"gcp_receipts_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        options=SessionOptions(storage_state_path=storage_state_path(meta.profile_id)),
    ) as sess:
        page = sess.page
        for account in accounts:
            print(f"Scanning {account.account_id} ({account.name})...", flush=True)
            await _open_history_page(page, account.account_id, meta.profile_id)
            await _maybe_expand_date_range(page)
            all_candidates.extend(await _discover_receipt_candidates(page, account))
            await _open_documents_page(page, account.account_id, meta.profile_id)
            all_candidates.extend(await _discover_document_candidates(page, account))

        if not all_candidates:
            raise RuntimeError(
                "No receipt controls were found in Google Cloud Billing. "
                "Refresh the profile or inspect the Transactions page manually."
            )

        ranked = sort_receipt_candidates(all_candidates)
        if start_date is not None or end_date is not None:
            ranked = filter_receipt_candidates_by_date(
                ranked,
                start_date=start_date,
                end_date=end_date,
            )
        if count is not None:
            ranked = ranked[:count]
        if not ranked:
            start_label = start_date.isoformat() if start_date else "the beginning"
            end_label = end_date.isoformat() if end_date else "today"
            raise RuntimeError(
                f"No receipts matched the requested date range ({start_label} to {end_label})."
            )
        downloads: list[DownloadedReceipt] = []
        for idx, candidate in enumerate(ranked, start=1):
            print(f"Downloading receipt {idx}/{len(ranked)}...", flush=True)
            downloads.append(
                await _download_candidate(
                    page,
                    candidate,
                    out_dir=out_root,
                    profile_id=meta.profile_id,
                )
            )

    _manifest_path(out_root).write_text(
        json.dumps([asdict(d) for d in downloads], indent=2),
        encoding="utf-8",
    )
    return downloads


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Google Cloud Billing receipt downloader")
    sub = parser.add_subparsers(dest="cmd", required=True)

    cap = sub.add_parser("capture-profile", help="Launch visible browser and save Google Billing login state")
    cap.add_argument("--profile", default=DEFAULT_PROFILE_ID)
    cap.add_argument("--timeout", type=int, default=300)

    dl = sub.add_parser("download", help="Download the last N recent Google Cloud payment receipts")
    dl.add_argument("--profile", default=DEFAULT_PROFILE_ID)
    dl.add_argument("--count", type=int, default=None)
    dl.add_argument(
        "--billing-account",
        action="append",
        dest="billing_accounts",
        default=[],
        help="Billing account ID to target. Repeat to target multiple accounts. Default: all open accounts.",
    )
    dl.add_argument("--start-date", default="", help="Inclusive lower bound in YYYY-MM-DD")
    dl.add_argument("--end-date", default="", help="Inclusive upper bound in YYYY-MM-DD")
    dl.add_argument(
        "--out-dir",
        default="",
        help="Directory to write receipts into. Default: ~/Downloads/google_cloud_receipts_<timestamp>",
    )

    sub.add_parser("list-accounts", help="List open Google Cloud billing accounts visible to gcloud")
    return parser


async def _run(args: argparse.Namespace) -> int:
    if args.cmd == "list-accounts":
        rows = [a for a in list_billing_accounts() if a.open]
        print(json.dumps([asdict(a) for a in rows], indent=2))
        return 0

    if args.cmd == "capture-profile":
        meta = await capture_google_profile(profile_id=args.profile, timeout_s=args.timeout)
        print(json.dumps(meta.to_dict(), indent=2))
        return 0

    if args.cmd == "download":
        out_dir = Path(args.out_dir).expanduser() if args.out_dir else None
        start_date = parse_iso_date(args.start_date) if args.start_date else None
        end_date = parse_iso_date(args.end_date) if args.end_date else None
        downloads = await download_recent_receipts(
            count=args.count,
            profile_id=args.profile,
            billing_account_ids=args.billing_accounts,
            out_dir=out_dir,
            start_date=start_date,
            end_date=end_date,
        )
        print(json.dumps([asdict(d) for d in downloads], indent=2))
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
