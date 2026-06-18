#!/usr/bin/env python3
"""National Grid bill summaries for Jane.

This module is shared by Jane web/Android handlers and Codex skills. It avoids
LLM guessing by using a small account map plus the existing National Grid
Playwright extractor.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


EXTRACTOR_PATH = Path(
    "/home/chieh/.codex/skills/waterlily-playwright-extractor/scripts/playwright_extract.py"
)
START_URL = "https://www.nationalgridus.com/MA-Home/Default.aspx"
DEFAULT_DOWNLOAD_DIR = Path.home() / "ambient/vessence-data/waterlily/nationalgrid-bills"
DEFAULT_CACHE_DIR = Path.home() / "ambient/vessence-data/waterlily/bill-cache/nationalgrid"
MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


@dataclass(frozen=True)
class NationalGridAccount:
    key: str
    label: str
    property_name: str
    utility: str
    account_number: str
    account_link: str
    address: str


ACCOUNTS: dict[str, NationalGridAccount] = {
    "air_temple_electric": NationalGridAccount(
        key="air_temple_electric",
        label="Air Temple Electric",
        property_name="Air Temple",
        utility="electric",
        account_number="0179768079",
        account_link="ce5cc1e",
        address="80 GOVERNORS AVE, MEDFORD, MA 02155",
    ),
    "air_temple_gas": NationalGridAccount(
        key="air_temple_gas",
        label="Air Temple Gas",
        property_name="Air Temple",
        utility="gas",
        account_number="8075631004",
        account_link="decfe96",
        address="80 GOVERNORS AVE, UNIT HSE, GAS, MEDFORD, MA 02155",
    ),
    "earth_kingdom_gas": NationalGridAccount(
        key="earth_kingdom_gas",
        label="Earth Kingdom Gas",
        property_name="Earth Kingdom",
        utility="gas",
        account_number="4442308003",
        account_link="d442706",
        address="5 HIGH ST, UNIT S1, GAS, MALDEN, MA 02148",
    ),
}


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_") or "account"


def _money_to_decimal(value: Any) -> Decimal | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("$", "").replace(",", "").replace(" ", "")
    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _money_text(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"${value:,.2f}"


def _months_for_year(year: int, include_future_months: bool = False) -> list[str]:
    now = datetime.now()
    if year < 2000 or year > 2100:
        raise ValueError(f"unsupported year: {year}")
    end_month = 12
    if year == now.year and not include_future_months:
        end_month = now.month
    if year > now.year and not include_future_months:
        return []
    return [f"{year:04d}-{month:02d}" for month in range(1, end_month + 1)]


def _split_months(raw_values: list[str]) -> list[str]:
    months: list[str] = []
    for raw in raw_values:
        for part in str(raw).split(","):
            value = part.strip()
            if not value:
                continue
            if not MONTH_RE.match(value):
                raise ValueError(f"target month must be YYYY-MM: {value}")
            months.append(value)
    return list(dict.fromkeys(months))


def _load_extractor():
    if not EXTRACTOR_PATH.exists():
        raise RuntimeError(f"National Grid extractor not found: {EXTRACTOR_PATH}")
    spec = importlib.util.spec_from_file_location("waterlily_playwright_extract", EXTRACTOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load extractor module: {EXTRACTOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_accounts(prompt: str = "", account: str | None = None, utility: str | None = None) -> list[NationalGridAccount]:
    text = " ".join(x for x in (prompt, account or "", utility or "") if x).lower()
    explicit = (account or "").strip().lower().replace(" ", "_").replace("-", "_")
    if explicit in ACCOUNTS:
        candidates = [ACCOUNTS[explicit]]
    elif "air temple" in text:
        candidates = [ACCOUNTS["air_temple_electric"], ACCOUNTS["air_temple_gas"]]
    elif "earth kingdom" in text or "earth king" in text:
        candidates = [ACCOUNTS["earth_kingdom_gas"]]
    else:
        candidates = []

    if "electric" in text or "electricity" in text:
        candidates = [acct for acct in candidates if acct.utility == "electric"]
    elif re.search(r"\bgas\b", text):
        candidates = [acct for acct in candidates if acct.utility == "gas"]

    if not candidates and utility:
        normalized_utility = utility.strip().lower()
        candidates = [acct for acct in ACCOUNTS.values() if acct.utility == normalized_utility]

    return candidates


def _build_config(
    account: NationalGridAccount,
    target_months: list[str],
    cache_dir: Path,
    cache_enabled: bool,
    timeout_ms: int,
) -> dict[str, Any]:
    return {
        "start_url": START_URL,
        "timeout_ms": timeout_ms,
        "billing": {
            "enabled": True,
            "email": {"env": "NATIONALGRID_EMAIL"},
            "password": {"env": "NATIONALGRID_PASSWORD"},
            "accounts": [account.label],
            "account_links": {account.label: account.account_link},
            "target_months": target_months,
            "filename_template": f"{_slug(account.label)}_{{month}}.pdf",
            "cache_enabled": cache_enabled,
            "cache_dir": str(cache_dir),
        },
        "actions": [],
        "extract": {"fields": {}, "rows": []},
        "downloads": [],
    }


def _summarize_account(
    account: NationalGridAccount,
    record: dict[str, Any],
    target_months: list[str],
) -> dict[str, Any]:
    by_month: dict[str, dict[str, Any]] = {}
    for bill in record.get("bills") or []:
        month = str(bill.get("target") or "").strip()
        if not month or not MONTH_RE.match(month):
            continue
        amount = _money_to_decimal(bill.get("amount"))
        by_month[month] = {
            "month": month,
            "status": "downloaded",
            "amount": float(amount) if amount is not None else None,
            "amount_text": _money_text(amount),
            "path": bill.get("path"),
            "file_url": bill.get("file_url"),
            "cached": bool(bill.get("cached")),
            "billing_period": bill.get("billing_period"),
            "issue_date": bill.get("issue_date"),
            "sha256": bill.get("sha256"),
        }

    discovered_rows = record.get("discovered_rows") or []
    discovered_current = [
        row for row in discovered_rows
        if row.get("is_current") and row.get("amount")
    ]
    current_bills = [
        bill for bill in (record.get("bills") or [])
        if str(bill.get("match_type") or "").endswith("_from_current")
    ]
    for bill in current_bills:
        month = str(bill.get("target") or "")
        amount = _money_to_decimal(bill.get("amount"))
        if month and MONTH_RE.match(month) and amount is not None:
            by_month[month] = {
                "month": month,
                "status": "downloaded",
                "amount": float(amount),
                "amount_text": _money_text(amount),
                "path": bill.get("path"),
                "file_url": bill.get("file_url"),
                "cached": bool(bill.get("cached")),
                "billing_period": bill.get("billing_period"),
                "issue_date": bill.get("issue_date"),
                "sha256": bill.get("sha256"),
                "source": "current_bill",
                "row_text": discovered_current[0].get("row_text") if discovered_current else None,
            }

    latest_history_index = None
    for row in discovered_rows:
        month = str(row.get("month_key") or "")
        if not MONTH_RE.match(month):
            continue
        year_s, month_s = month.split("-")
        month_index = int(year_s) * 12 + int(month_s)
        if latest_history_index is None or month_index > latest_history_index:
            latest_history_index = month_index
    if latest_history_index is not None and discovered_current:
        next_index = latest_history_index + 1
        inferred_year = (next_index - 1) // 12
        inferred_month = ((next_index - 1) % 12) + 1
        inferred_key = f"{inferred_year:04d}-{inferred_month:02d}"
        amount = _money_to_decimal(discovered_current[0].get("amount"))
        if inferred_key in target_months and inferred_key not in by_month and amount is not None:
            by_month[inferred_key] = {
                "month": inferred_key,
                "status": "amount_found_pdf_missing",
                "amount": float(amount),
                "amount_text": _money_text(amount),
                "path": None,
                "file_url": None,
                "cached": False,
                "billing_period": None,
                "issue_date": None,
                "sha256": None,
                "source": "current_bill_row",
                "row_text": discovered_current[0].get("row_text"),
            }

    monthly_amounts = [
        by_month.get(
            month,
            {
                "month": month,
                "status": "missing",
                "amount": None,
                "amount_text": "",
                "path": None,
                "file_url": None,
                "cached": False,
                "billing_period": None,
                "issue_date": None,
                "sha256": None,
            },
        )
        for month in target_months
    ]
    total = Decimal("0.00")
    for item in monthly_amounts:
        amount = _money_to_decimal(item.get("amount_text"))
        if amount is not None:
            total += amount

    return {
        "account": account.label,
        "account_key": account.key,
        "property": account.property_name,
        "utility": account.utility,
        "account_number": account.account_number,
        "account_link": account.account_link,
        "monthly_amounts": monthly_amounts,
        "downloaded_count": sum(1 for item in monthly_amounts if item["status"] == "downloaded"),
        "missing_count": sum(1 for item in monthly_amounts if item["status"] == "missing"),
        "amount_found_count": sum(1 for item in monthly_amounts if item.get("amount_text")),
        "total_amount": float(total),
        "total_amount_text": _money_text(total),
        "record_status": record.get("status"),
        "record_error": record.get("error"),
    }


def fetch_bills(
    *,
    prompt: str = "",
    account: str | None = None,
    utility: str | None = None,
    year: int | None = None,
    target_months: list[str] | None = None,
    include_future_months: bool = False,
    download_dir: Path = DEFAULT_DOWNLOAD_DIR,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    cache_enabled: bool = True,
    headful: bool = False,
    timeout_ms: int = 60000,
) -> dict[str, Any]:
    accounts = resolve_accounts(prompt=prompt, account=account, utility=utility)
    if not accounts:
        raise ValueError("Could not resolve a National Grid account from the request")

    months = list(target_months or [])
    if year is not None:
        months = _months_for_year(year, include_future_months)
    if not months:
        months = ["current"]
    months = list(dict.fromkeys(months))

    extractor = _load_extractor()
    email = extractor._resolve_secret({"env": "NATIONALGRID_EMAIL"})
    password = extractor._resolve_secret({"env": "NATIONALGRID_PASSWORD"})
    if not email or not password:
        raise RuntimeError("Missing NATIONALGRID_EMAIL or NATIONALGRID_PASSWORD in env/SecretStore")

    download_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    account_summaries: list[dict[str, Any]] = []
    raw_records: list[dict[str, Any]] = []
    final_url = ""
    warnings: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headful)
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 1400})
            page = context.new_page()
            page.set_default_timeout(timeout_ms)
            page.goto(START_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            for acct in accounts:
                cfg = _build_config(
                    acct,
                    months,
                    cache_dir / acct.key,
                    cache_enabled,
                    timeout_ms,
                )
                records = extractor._run_billing_downloads(
                    page,
                    cfg,
                    download_dir / acct.key,
                    timeout_ms,
                )
                raw_records.extend(records)
                record = records[0] if records else {"status": "error", "error": "no record returned"}
                if record.get("status") not in {"ok", None}:
                    warnings.append(f"{acct.label}: {record.get('status')} - {record.get('error')}")
                account_summaries.append(_summarize_account(acct, record, months))
                final_url = page.url
        finally:
            browser.close()

    total = Decimal("0.00")
    for summary in account_summaries:
        total += _money_to_decimal(summary.get("total_amount_text")) or Decimal("0.00")

    status = "ok"
    if warnings:
        status = "partial"
    if all(summary.get("downloaded_count") == 0 for summary in account_summaries):
        status = "missing"

    return {
        "meta": {
            "status": status,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "prompt": prompt,
            "year": year,
            "target_months": months,
            "final_url": final_url,
            "download_dir": str(download_dir),
            "cache_dir": str(cache_dir),
            "cache_enabled": cache_enabled,
            "warnings": warnings,
        },
        "accounts": account_summaries,
        "bill_downloads": raw_records,
        "total_amount": float(total),
        "total_amount_text": _money_text(total),
    }


def format_answer(result: dict[str, Any]) -> str:
    lines: list[str] = []
    for account in result.get("accounts") or []:
        title = f"{account['property']} {account['utility'].title()} ({account['account']})"
        lines.append(f"{title}:")
        for item in account.get("monthly_amounts") or []:
            amount = item.get("amount_text") or "not found"
            lines.append(f"- {item['month']}: {amount}")
        lines.append(f"Total: {account.get('total_amount_text', '$0.00')}")
    if len(result.get("accounts") or []) > 1:
        lines.append(f"Combined total: {result.get('total_amount_text', '$0.00')}")
    warnings = result.get("meta", {}).get("warnings") or []
    if warnings:
        lines.append("Warnings: " + " | ".join(warnings))
    return "\n".join(lines)


def infer_year(prompt: str) -> int | None:
    match = re.search(r"\b(20\d{2})\b", prompt)
    if match:
        return int(match.group(1))
    if re.search(r"\bthis year\b|\byear to date\b|\bytd\b|so far\b", prompt, re.I):
        return datetime.now().year
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch National Grid bill summaries for Jane.")
    parser.add_argument("prompt", nargs="*", help="Natural-language request")
    parser.add_argument("--account")
    parser.add_argument("--utility", choices=["gas", "electric"])
    parser.add_argument("--year", type=int)
    parser.add_argument("--target-month", action="append", default=[])
    parser.add_argument("--include-future-months", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--headful", action="store_true")
    args = parser.parse_args()

    prompt = " ".join(args.prompt).strip()
    target_months = _split_months(args.target_month)
    year = args.year if args.year is not None else infer_year(prompt)
    result = fetch_bills(
        prompt=prompt,
        account=args.account,
        utility=args.utility,
        year=year,
        target_months=target_months,
        include_future_months=args.include_future_months,
        headful=args.headful,
    )
    text = json.dumps(result, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
