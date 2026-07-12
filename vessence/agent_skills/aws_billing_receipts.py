#!/usr/bin/env python3
"""AWS Billing invoice downloader for Northeastern Concur receipts.

This script uses a saved Playwright storage state for the AWS console. It is
intended for AWS card expenses where Concur has transaction dates on the first
of the month and AWS Billing has invoices for the previous billing period.

Typical use:

    python agent_skills/aws_billing_receipts.py capture-profile
    python agent_skills/aws_billing_receipts.py download \
        --period 2026-06=18.14 --period 2026-05=18.67 \
        --out-dir /home/chieh/Desktop/Receipts/payment_receipts_2026-04_to_latest/aws_downloaded

If AWS changes the UI, the script writes screenshot/html/text diagnostics and
exits. Those artifacts are meant for an LLM repair pass against this file.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from agent_skills.web_automation.browser_session import (
    BrowserSessionManager,
    SessionOptions,
)
from agent_skills.web_automation.profiles import (
    ProfileMeta,
    ProfileNotFound,
    capture_after_login,
    create as create_profile,
    get as get_profile,
    storage_state_path,
    touch_last_used,
)

AWS_PROFILE_ID = "aws_billing"
AWS_PROFILE_NAME = "AWS Billing"
AWS_PROFILE_DOMAIN = "console.aws.amazon.com"
AWS_BILLS_URL = "https://us-east-1.console.aws.amazon.com/billing/home?region=us-east-1#/bills"
AWS_BILLS_PERIOD_URL = AWS_BILLS_URL + "?year={year}&month={month}"
DEFAULT_OUT_DIR = Path.home() / "Desktop" / "Receipts" / "aws_billing_downloaded"
DEFAULT_DIAGNOSTICS_DIR = Path.home() / "Desktop" / "Receipts" / "automation_diagnostics" / "aws_billing"

_AMOUNT_RE = re.compile(r"USD\s+([0-9][0-9,]*\.\d{2})")
_INVOICE_ID_RE = re.compile(r"\b(\d{10})\b")
_ACCOUNT_ID_RE = re.compile(r"\b(\d{12})\b")
_DATE_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")


@dataclass(frozen=True)
class PeriodRequest:
    year: int
    month: int
    expected_amount: str | None = None

    @property
    def label(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


@dataclass
class DownloadedAwsInvoice:
    billing_period: str
    account_id: str | None
    invoice_id: str
    invoice_date: str | None
    amount: str
    source_download_path: str
    saved_path: str
    verified: bool
    evidence: list[str]


def ensure_aws_profile(profile_id: str = AWS_PROFILE_ID) -> ProfileMeta:
    try:
        meta = get_profile(profile_id)
        if meta.domain != AWS_PROFILE_DOMAIN:
            raise RuntimeError(
                f"Profile {profile_id!r} is bound to {meta.domain!r}, expected {AWS_PROFILE_DOMAIN!r}."
            )
        return meta
    except ProfileNotFound:
        meta = create_profile(AWS_PROFILE_NAME, AWS_PROFILE_DOMAIN)
        if meta.profile_id != profile_id:
            raise RuntimeError(
                f"Expected profile id {profile_id!r}, created {meta.profile_id!r}."
            )
        return meta


def require_aws_profile(profile_id: str = AWS_PROFILE_ID) -> ProfileMeta:
    try:
        meta = get_profile(profile_id)
    except ProfileNotFound as e:
        raise RuntimeError(
            "AWS Billing profile not found. Run `python agent_skills/aws_billing_receipts.py capture-profile` first."
        ) from e
    if meta.domain != AWS_PROFILE_DOMAIN:
        raise RuntimeError(
            f"Profile {profile_id!r} is bound to {meta.domain!r}, expected {AWS_PROFILE_DOMAIN!r}."
        )
    if not meta.last_used:
        raise RuntimeError(
            "AWS Billing profile exists but has no captured login state. Run capture-profile first."
        )
    return meta


def parse_period(value: str) -> PeriodRequest:
    raw = value.strip()
    expected_amount: str | None = None
    if "=" in raw:
        raw, expected_amount = raw.split("=", 1)
        expected_amount = normalize_amount(expected_amount)
    m = re.fullmatch(r"(\d{4})-(\d{2})", raw)
    if not m:
        raise argparse.ArgumentTypeError("period must be YYYY-MM or YYYY-MM=amount")
    year = int(m.group(1))
    month = int(m.group(2))
    if not 1 <= month <= 12:
        raise argparse.ArgumentTypeError("month must be 01-12")
    return PeriodRequest(year=year, month=month, expected_amount=expected_amount)


def normalize_amount(value: str | float | int) -> str:
    text = str(value).strip().replace("$", "").replace(",", "")
    return f"{float(text):.2f}"


def invoice_charge_date(year: int, month: int) -> date:
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


def safe_piece(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("_") or "unknown"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    i = 2
    while True:
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


async def capture_aws_profile(*, timeout_s: int, profile_id: str = AWS_PROFILE_ID) -> ProfileMeta:
    meta = ensure_aws_profile(profile_id)
    mgr = BrowserSessionManager.instance()
    async with mgr.session(
        run_id=f"capture_{meta.profile_id}",
        options=SessionOptions(headless=False, storage_state_path=storage_state_path(meta.profile_id)),
    ) as sess:
        page = sess.page
        print("Visible browser opened. Log in to AWS Billing if prompted.", flush=True)
        await page.goto(AWS_BILLS_URL, wait_until="domcontentloaded", timeout=90000)
        await wait_for_aws_billing_ready(page, timeout_s=timeout_s)
        await capture_after_login(page, meta.profile_id)
    return get_profile(meta.profile_id)


async def wait_for_aws_billing_ready(page: Any, *, timeout_s: int) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while asyncio.get_running_loop().time() < deadline:
        url = page.url or ""
        text = await page_text(page)
        if "signin.aws.amazon.com" not in url and (
            "Billing and Cost Management" in text or "AWS bill summary" in text or "AWS estimated bill summary" in text
        ):
            return
        await page.wait_for_timeout(1500)
    raise TimeoutError(f"Timed out after {timeout_s}s waiting for AWS Billing.")


async def page_text(page: Any) -> str:
    try:
        return await page.locator("body").inner_text(timeout=5000)
    except Exception:
        return ""


async def write_diagnostics(page: Any, diagnostics_dir: Path, label: str) -> Path:
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    base = diagnostics_dir / safe_piece(label)
    try:
        await page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
    except Exception:
        pass
    try:
        base.with_suffix(".html").write_text(await page.content(), encoding="utf-8")
    except Exception:
        pass
    try:
        base.with_suffix(".txt").write_text(await page_text(page), encoding="utf-8")
    except Exception:
        pass
    return base


def parse_invoice_summary(text: str, request: PeriodRequest) -> tuple[str | None, str, str | None, str]:
    account_id = None
    for match in _ACCOUNT_ID_RE.finditer(text):
        value = match.group(1)
        if len(value) == 12:
            account_id = value
            break

    invoice_ids = [m.group(1) for m in _INVOICE_ID_RE.finditer(text)]
    if not invoice_ids:
        raise RuntimeError(f"No invoice ID found for billing period {request.label}.")
    invoice_id = invoice_ids[0]

    invoice_date = None
    issued = re.search(r"Issued\s+(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
    if issued:
        invoice_date = issued.group(1)
    else:
        dates = [m.group(1) for m in _DATE_RE.finditer(text)]
        if dates:
            invoice_date = dates[0]

    grand_total = re.search(r"Grand total:\s*USD\s*([0-9][0-9,]*\.\d{2})", text, re.IGNORECASE)
    if grand_total:
        amount = normalize_amount(grand_total.group(1))
    else:
        amounts = [normalize_amount(m.group(1)) for m in _AMOUNT_RE.finditer(text)]
        if not amounts:
            raise RuntimeError(f"No USD amount found for billing period {request.label}.")
        amount = amounts[-1]

    if request.expected_amount and normalize_amount(amount) != request.expected_amount:
        raise RuntimeError(
            f"Amount mismatch for {request.label}: page has {amount}, expected {request.expected_amount}."
        )
    return account_id, invoice_id, invoice_date, amount


async def click_invoice_download(page: Any, invoice_id: str) -> Any:
    locators = [
        page.get_by_role("link", name=re.compile(re.escape(invoice_id))),
        page.get_by_text(invoice_id, exact=True),
    ]
    last_error: Exception | None = None
    for locator in locators:
        try:
            if await locator.count() == 0:
                continue
            async with page.expect_download(timeout=90000) as download_info:
                await locator.first.click(timeout=15000)
            return await download_info.value
        except Exception as e:
            last_error = e
            continue
    if last_error:
        raise RuntimeError(f"Could not download invoice {invoice_id}: {last_error}") from last_error
    raise RuntimeError(f"Could not find clickable invoice {invoice_id}.")


def pdf_text(path: Path) -> str:
    proc = subprocess.run(
        ["pdftotext", str(path), "-"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout


def verify_pdf(path: Path, invoice_id: str, amount: str, account_id: str | None) -> tuple[bool, list[str]]:
    text = pdf_text(path)
    evidence: list[str] = []
    for line in text.splitlines():
        if any(token in line for token in ("Amazon Web Services", invoice_id, f"USD {amount}", "billing period")):
            evidence.append(line.strip())
        if len(evidence) >= 10:
            break
    ok = "Amazon Web Services" in text and invoice_id in text and f"USD {amount}" in text
    if account_id:
        ok = ok and account_id in text
    return ok, evidence


async def download_period(
    page: Any,
    request: PeriodRequest,
    *,
    out_dir: Path,
    diagnostics_dir: Path,
) -> DownloadedAwsInvoice:
    url = AWS_BILLS_PERIOD_URL.format(year=request.year, month=request.month)
    await page.goto(url, wait_until="domcontentloaded", timeout=90000)
    await page.wait_for_timeout(4000)
    text = await page_text(page)
    if "Sign in" in text and "AWS" in text and "Billing" not in text:
        await write_diagnostics(page, diagnostics_dir, f"aws_signed_out_{request.label}")
        raise RuntimeError("AWS session is signed out. Run capture-profile again.")
    try:
        account_id, invoice_id, invoice_date, amount = parse_invoice_summary(text, request)
    except Exception:
        await write_diagnostics(page, diagnostics_dir, f"aws_parse_failed_{request.label}")
        raise

    try:
        download = await click_invoice_download(page, invoice_id)
    except Exception:
        await write_diagnostics(page, diagnostics_dir, f"aws_download_failed_{request.label}_{invoice_id}")
        raise

    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = out_dir / f"_download_{invoice_id}.pdf"
    await download.save_as(str(tmp_path))

    charge_date = invoice_charge_date(request.year, request.month).isoformat()
    account_piece = account_id or "unknown_account"
    final_name = (
        f"aws_{charge_date}_{amount}_{account_piece}_invoice_{invoice_id}.pdf"
        .replace("-", "_")
    )
    final_path = unique_path(out_dir / final_name)
    tmp_path.replace(final_path)

    verified, evidence = verify_pdf(final_path, invoice_id, amount, account_id)
    if not verified:
        await write_diagnostics(page, diagnostics_dir, f"aws_pdf_verify_failed_{request.label}_{invoice_id}")
        raise RuntimeError(f"Downloaded invoice {invoice_id}, but PDF verification failed: {final_path}")

    return DownloadedAwsInvoice(
        billing_period=request.label,
        account_id=account_id,
        invoice_id=invoice_id,
        invoice_date=invoice_date,
        amount=amount,
        source_download_path=str(download.suggested_filename),
        saved_path=str(final_path),
        verified=verified,
        evidence=evidence,
    )


async def run_download(args: argparse.Namespace) -> int:
    meta = require_aws_profile(args.profile_id)
    out_dir = Path(args.out_dir).expanduser()
    diagnostics_dir = Path(args.diagnostics_dir).expanduser()
    mgr = BrowserSessionManager.instance()
    results: list[DownloadedAwsInvoice] = []
    async with mgr.session(
        run_id="aws_billing_download",
        options=SessionOptions(
            headless=not args.visible,
            storage_state_path=storage_state_path(meta.profile_id),
            record_trace=args.trace,
        ),
    ) as sess:
        page = sess.page
        page.set_default_timeout(30000)
        for request in args.period:
            result = await download_period(
                page,
                request,
                out_dir=out_dir,
                diagnostics_dir=diagnostics_dir,
            )
            results.append(result)
        touch_last_used(meta.profile_id)

    manifest = out_dir / "aws_invoices_manifest.json"
    manifest.write_text(json.dumps([asdict(r) for r in results], indent=2), encoding="utf-8")
    print(json.dumps([asdict(r) for r in results], indent=2))
    print(f"Manifest: {manifest}")
    return 0


async def run_capture(args: argparse.Namespace) -> int:
    meta = await capture_aws_profile(timeout_s=args.timeout, profile_id=args.profile_id)
    print(json.dumps(meta.to_dict(), indent=2))
    return 0


async def run_verify(args: argparse.Namespace) -> int:
    meta = require_aws_profile(args.profile_id)
    mgr = BrowserSessionManager.instance()
    async with mgr.session(
        run_id="aws_billing_verify",
        options=SessionOptions(headless=not args.visible, storage_state_path=storage_state_path(meta.profile_id)),
    ) as sess:
        page = sess.page
        await page.goto(AWS_BILLS_URL, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(4000)
        text = await page_text(page)
        ok = "Billing and Cost Management" in text or "AWS bill" in text
        if ok:
            touch_last_used(meta.profile_id)
        print(json.dumps({"profile_id": meta.profile_id, "logged_in": ok, "url": page.url}, indent=2))
        return 0 if ok else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-id", default=AWS_PROFILE_ID)
    sub = parser.add_subparsers(dest="cmd", required=True)

    capture = sub.add_parser("capture-profile")
    capture.add_argument("--timeout", type=int, default=600)
    capture.set_defaults(func=run_capture)

    verify = sub.add_parser("verify-profile")
    verify.add_argument("--visible", action="store_true")
    verify.set_defaults(func=run_verify)

    download = sub.add_parser("download")
    download.add_argument("--period", action="append", type=parse_period, required=True, help="YYYY-MM or YYYY-MM=amount")
    download.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    download.add_argument("--diagnostics-dir", default=str(DEFAULT_DIAGNOSTICS_DIR))
    download.add_argument("--visible", action="store_true")
    download.add_argument("--trace", action="store_true")
    download.set_defaults(func=run_download)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(args.func(args))
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
