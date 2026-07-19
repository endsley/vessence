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
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright
from agent_skills.nationalgrid_bill_helpers import (
    MONTH_RE,
    aggregate_fetch_totals as _aggregate_fetch_totals,
    infer_year_from_prompt as infer_year,
    extractor_config as _extractor_config,
    money_text as _money_text,
    money_to_decimal as _money_to_decimal,
    months_for_year as _months_for_year,
    resolve_accounts_from_map as _resolve_accounts_from_map,
    slug as _slug,
    split_months as _split_months,
    summarize_account as _summarize_account,
)
from agent_skills.web_ui_change import (
    ExtractionContractError,
    recover_website_ui_change,
    require_extraction_values,
)


EXTRACTOR_PATH = Path(
    "/home/chieh/.codex/skills/waterlily-playwright-extractor/scripts/playwright_extract.py"
)
START_URL = "https://www.nationalgridus.com/MA-Home/Default.aspx"
DEFAULT_DOWNLOAD_DIR = Path.home() / "ambient/vessence-data/waterlily/nationalgrid-bills"
DEFAULT_CACHE_DIR = Path.home() / "ambient/vessence-data/waterlily/bill-cache/nationalgrid"


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
    return _resolve_accounts_from_map(
        ACCOUNTS,
        prompt=prompt,
        account=account,
        utility=utility,
    )


def _build_config(
    account: NationalGridAccount,
    target_months: list[str],
    cache_dir: Path,
    cache_enabled: bool,
    timeout_ms: int,
) -> dict[str, Any]:
    return _extractor_config(
        account,
        target_months,
        start_url=START_URL,
        cache_dir=cache_dir,
        cache_enabled=cache_enabled,
        timeout_ms=timeout_ms,
    )


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

    totals = _aggregate_fetch_totals(account_summaries, warnings)

    result = {
        "meta": {
            "status": totals["status"],
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
        "total_amount": totals["total_amount"],
        "total_amount_text": totals["total_amount_text"],
    }
    if result["meta"]["status"] == "missing":
        raise ExtractionContractError(["accounts.monthly_amounts"])
    require_extraction_values(result, ["meta.final_url", "accounts"])
    return result


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
    try:
        result = fetch_bills(
            prompt=prompt,
            account=args.account,
            utility=args.utility,
            year=year,
            target_months=target_months,
            include_future_months=args.include_future_months,
            headful=args.headful,
        )
    except Exception as exc:  # noqa: BLE001
        recover_website_ui_change(
            skill="waterlily-nationalgrid-bills",
            intent="Read the requested National Grid bill-history amounts and bill PDFs for the selected known utility account without changing the account.",
            operation="National Grid bill-history extraction",
            exc=exc,
            project_root=Path(__file__).resolve().parents[1],
            retry_safe=True,
        )
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(result, indent=2)
    print(text)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
