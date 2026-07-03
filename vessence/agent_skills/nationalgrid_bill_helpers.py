"""Pure helpers for National Grid bill summaries."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_") or "account"


def money_to_decimal(value: Any) -> Decimal | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("$", "").replace(",", "").replace(" ", "")
    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def money_text(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"${value:,.2f}"


def months_for_year(
    year: int,
    include_future_months: bool = False,
    *,
    now: datetime | None = None,
) -> list[str]:
    current = now or datetime.now()
    if year < 2000 or year > 2100:
        raise ValueError(f"unsupported year: {year}")
    end_month = 12
    if year == current.year and not include_future_months:
        end_month = current.month
    if year > current.year and not include_future_months:
        return []
    return [f"{year:04d}-{month:02d}" for month in range(1, end_month + 1)]


def split_months(raw_values: list[str]) -> list[str]:
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


def resolve_accounts_from_map(
    accounts: Mapping[str, Any],
    *,
    prompt: str = "",
    account: str | None = None,
    utility: str | None = None,
) -> list[Any]:
    text = " ".join(value for value in (prompt, account or "", utility or "") if value).lower()
    explicit = (account or "").strip().lower().replace(" ", "_").replace("-", "_")
    if explicit in accounts:
        candidates = [accounts[explicit]]
    elif "air temple" in text:
        candidates = [accounts["air_temple_electric"], accounts["air_temple_gas"]]
    elif "earth kingdom" in text or "earth king" in text:
        candidates = [accounts["earth_kingdom_gas"]]
    else:
        candidates = []

    if "electric" in text or "electricity" in text:
        candidates = [acct for acct in candidates if acct.utility == "electric"]
    elif re.search(r"\bgas\b", text):
        candidates = [acct for acct in candidates if acct.utility == "gas"]

    if not candidates and utility:
        normalized_utility = utility.strip().lower()
        candidates = [acct for acct in accounts.values() if acct.utility == normalized_utility]

    return candidates


def extractor_config(
    account: Any,
    target_months: list[str],
    *,
    start_url: str,
    cache_dir: Any,
    cache_enabled: bool,
    timeout_ms: int,
) -> dict[str, Any]:
    return {
        "start_url": start_url,
        "timeout_ms": timeout_ms,
        "billing": {
            "enabled": True,
            "email": {"env": "NATIONALGRID_EMAIL"},
            "password": {"env": "NATIONALGRID_PASSWORD"},
            "accounts": [account.label],
            "account_links": {account.label: account.account_link},
            "target_months": target_months,
            "filename_template": f"{slug(account.label)}_{{month}}.pdf",
            "cache_enabled": cache_enabled,
            "cache_dir": str(cache_dir),
        },
        "actions": [],
        "extract": {"fields": {}, "rows": []},
        "downloads": [],
    }


def infer_year_from_prompt(prompt: str, *, now: datetime | None = None) -> int | None:
    match = re.search(r"\b(20\d{2})\b", prompt)
    if match:
        return int(match.group(1))
    if re.search(r"\bthis year\b|\byear to date\b|\bytd\b|so far\b", prompt, re.I):
        return (now or datetime.now()).year
    return None


def downloaded_month_entry(bill: dict[str, Any], month: str | None = None) -> dict[str, Any] | None:
    month = str(month or bill.get("target") or "").strip()
    if not month or not MONTH_RE.match(month):
        return None
    amount = money_to_decimal(bill.get("amount"))
    return {
        "month": month,
        "status": "downloaded",
        "amount": float(amount) if amount is not None else None,
        "amount_text": money_text(amount),
        "path": bill.get("path"),
        "file_url": bill.get("file_url"),
        "cached": bool(bill.get("cached")),
        "billing_period": bill.get("billing_period"),
        "issue_date": bill.get("issue_date"),
        "sha256": bill.get("sha256"),
    }


def current_bill_downloaded_entry(
    bill: dict[str, Any],
    discovered_current: list[dict[str, Any]],
) -> dict[str, Any] | None:
    month = str(bill.get("target") or "")
    entry = downloaded_month_entry(bill, month)
    if entry is None or entry["amount"] is None:
        return None
    entry["source"] = "current_bill"
    entry["row_text"] = discovered_current[0].get("row_text") if discovered_current else None
    return entry


def missing_month_entry(month: str) -> dict[str, Any]:
    return {
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
    }


def latest_discovered_month_index(discovered_rows: list[dict[str, Any]]) -> int | None:
    latest_history_index = None
    for row in discovered_rows:
        month = str(row.get("month_key") or "")
        if not MONTH_RE.match(month):
            continue
        year_s, month_s = month.split("-")
        month_index = int(year_s) * 12 + int(month_s)
        if latest_history_index is None or month_index > latest_history_index:
            latest_history_index = month_index
    return latest_history_index


def month_key_from_index(month_index: int) -> str:
    inferred_year = (month_index - 1) // 12
    inferred_month = ((month_index - 1) % 12) + 1
    return f"{inferred_year:04d}-{inferred_month:02d}"


def inferred_current_bill_entry(
    discovered_rows: list[dict[str, Any]],
    discovered_current: list[dict[str, Any]],
    target_months: list[str],
    by_month: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    latest_history_index = latest_discovered_month_index(discovered_rows)
    if latest_history_index is None or not discovered_current:
        return None
    inferred_key = month_key_from_index(latest_history_index + 1)
    amount = money_to_decimal(discovered_current[0].get("amount"))
    if inferred_key not in target_months or inferred_key in by_month or amount is None:
        return None
    return {
        "month": inferred_key,
        "status": "amount_found_pdf_missing",
        "amount": float(amount),
        "amount_text": money_text(amount),
        "path": None,
        "file_url": None,
        "cached": False,
        "billing_period": None,
        "issue_date": None,
        "sha256": None,
        "source": "current_bill_row",
        "row_text": discovered_current[0].get("row_text"),
    }


def monthly_amounts_for_targets(
    target_months: list[str],
    by_month: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [by_month.get(month, missing_month_entry(month)) for month in target_months]


def total_from_monthly_amounts(monthly_amounts: list[dict[str, Any]]) -> Decimal:
    total = Decimal("0.00")
    for item in monthly_amounts:
        amount = money_to_decimal(item.get("amount_text"))
        if amount is not None:
            total += amount
    return total


def summarize_account(account: Any, record: dict[str, Any], target_months: list[str]) -> dict[str, Any]:
    by_month: dict[str, dict[str, Any]] = {}
    for bill in record.get("bills") or []:
        entry = downloaded_month_entry(bill)
        if entry is not None:
            by_month[entry["month"]] = entry

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
        entry = current_bill_downloaded_entry(bill, discovered_current)
        if entry is not None:
            by_month[entry["month"]] = entry

    inferred_entry = inferred_current_bill_entry(discovered_rows, discovered_current, target_months, by_month)
    if inferred_entry is not None:
        by_month[inferred_entry["month"]] = inferred_entry

    monthly_amounts = monthly_amounts_for_targets(target_months, by_month)
    total = total_from_monthly_amounts(monthly_amounts)

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
        "total_amount_text": money_text(total),
        "record_status": record.get("status"),
        "record_error": record.get("error"),
    }


def aggregate_fetch_totals(
    account_summaries: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    total = Decimal("0.00")
    for summary in account_summaries:
        total += money_to_decimal(summary.get("total_amount_text")) or Decimal("0.00")

    status = "ok"
    if warnings:
        status = "partial"
    if all(summary.get("downloaded_count") == 0 for summary in account_summaries):
        status = "missing"

    return {
        "status": status,
        "total_amount": float(total),
        "total_amount_text": money_text(total),
    }
