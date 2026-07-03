import datetime as dt
from decimal import Decimal

import pytest

from agent_skills import nationalgrid_bills
from agent_skills.nationalgrid_bill_helpers import (
    aggregate_fetch_totals,
    current_bill_downloaded_entry,
    downloaded_month_entry,
    extractor_config,
    inferred_current_bill_entry,
    infer_year_from_prompt,
    latest_discovered_month_index,
    missing_month_entry,
    month_key_from_index,
    money_text,
    money_to_decimal,
    monthly_amounts_for_targets,
    months_for_year,
    resolve_accounts_from_map,
    slug,
    split_months,
    summarize_account,
    total_from_monthly_amounts,
)


def test_nationalgrid_bills_uses_extracted_helpers():
    assert nationalgrid_bills._slug is slug
    assert nationalgrid_bills._money_to_decimal is money_to_decimal
    assert nationalgrid_bills._money_text is money_text
    assert nationalgrid_bills._months_for_year is months_for_year
    assert nationalgrid_bills._split_months is split_months
    assert nationalgrid_bills._summarize_account is summarize_account
    assert nationalgrid_bills._extractor_config is extractor_config
    assert nationalgrid_bills._aggregate_fetch_totals is aggregate_fetch_totals
    assert nationalgrid_bills.infer_year is infer_year_from_prompt


def test_slug_money_and_month_parsing_helpers():
    assert slug("Air Temple Electric") == "Air_Temple_Electric"
    assert slug("!!!") == "account"
    assert money_to_decimal("$1,234.5") == Decimal("1234.50")
    assert money_to_decimal("bad") is None
    assert money_text(Decimal("1234.50")) == "$1,234.50"
    assert money_text(None) == ""
    assert split_months(["2026-01, 2026-02", "2026-01"]) == ["2026-01", "2026-02"]
    with pytest.raises(ValueError, match="target month"):
        split_months(["2026/01"])


def test_months_for_year_respects_current_year_and_future_flag():
    now = dt.datetime(2026, 7, 2)

    assert months_for_year(2026, now=now) == [f"2026-{month:02d}" for month in range(1, 8)]
    assert len(months_for_year(2026, include_future_months=True, now=now)) == 12
    assert months_for_year(2027, now=now) == []
    with pytest.raises(ValueError, match="unsupported year"):
        months_for_year(1999, now=now)


def test_resolve_accounts_from_map_preserves_prompt_account_and_utility_rules():
    accounts = nationalgrid_bills.ACCOUNTS

    assert [acct.key for acct in resolve_accounts_from_map(accounts, account="air temple electric")] == [
        "air_temple_electric"
    ]
    assert [acct.key for acct in resolve_accounts_from_map(accounts, prompt="Air Temple bills")] == [
        "air_temple_electric",
        "air_temple_gas",
    ]
    assert [acct.key for acct in resolve_accounts_from_map(accounts, prompt="Air Temple gas")] == [
        "air_temple_gas"
    ]
    assert [acct.key for acct in resolve_accounts_from_map(accounts, prompt="Earth King's Gas")] == [
        "earth_kingdom_gas"
    ]
    assert [acct.key for acct in resolve_accounts_from_map(accounts, utility="electric")] == [
        "air_temple_electric"
    ]


def test_infer_year_from_prompt_preserves_explicit_and_ytd_rules():
    now = dt.datetime(2026, 7, 2)

    assert infer_year_from_prompt("download 2025 bills", now=now) == 2025
    assert infer_year_from_prompt("year to date gas", now=now) == 2026
    assert infer_year_from_prompt("current bill", now=now) is None


def test_extractor_config_preserves_playwright_billing_contract(tmp_path):
    account = nationalgrid_bills.ACCOUNTS["air_temple_electric"]

    assert extractor_config(
        account,
        ["2026-01", "2026-02"],
        start_url="https://example.test/start",
        cache_dir=tmp_path / "cache",
        cache_enabled=False,
        timeout_ms=12345,
    ) == {
        "start_url": "https://example.test/start",
        "timeout_ms": 12345,
        "billing": {
            "enabled": True,
            "email": {"env": "NATIONALGRID_EMAIL"},
            "password": {"env": "NATIONALGRID_PASSWORD"},
            "accounts": ["Air Temple Electric"],
            "account_links": {"Air Temple Electric": "ce5cc1e"},
            "target_months": ["2026-01", "2026-02"],
            "filename_template": "Air_Temple_Electric_{month}.pdf",
            "cache_enabled": False,
            "cache_dir": str(tmp_path / "cache"),
        },
        "actions": [],
        "extract": {"fields": {}, "rows": []},
        "downloads": [],
    }


def test_nationalgrid_month_entry_helpers_preserve_row_shapes_and_totals():
    bill = {
        "target": "2026-01",
        "amount": "$100.50",
        "path": "/tmp/jan.pdf",
        "file_url": "file:///tmp/jan.pdf",
        "cached": True,
        "billing_period": "Jan 1-Feb 1",
        "issue_date": "2026-02-02",
        "sha256": "abc",
    }

    downloaded = downloaded_month_entry(bill)
    assert downloaded == {
        "month": "2026-01",
        "status": "downloaded",
        "amount": 100.5,
        "amount_text": "$100.50",
        "path": "/tmp/jan.pdf",
        "file_url": "file:///tmp/jan.pdf",
        "cached": True,
        "billing_period": "Jan 1-Feb 1",
        "issue_date": "2026-02-02",
        "sha256": "abc",
    }
    assert downloaded_month_entry({"target": "bad", "amount": "$999"}) is None
    assert missing_month_entry("2026-02") == {
        "month": "2026-02",
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
    monthly = monthly_amounts_for_targets(["2026-01", "2026-02"], {"2026-01": downloaded})
    assert [item["status"] for item in monthly] == ["downloaded", "missing"]
    assert total_from_monthly_amounts(monthly) == Decimal("100.50")


def test_nationalgrid_current_bill_helpers_infer_current_month_rows():
    discovered_rows = [
        {"month_key": "bad", "amount": "$1"},
        {"month_key": "2026-01", "amount": "$100.50"},
    ]
    discovered_current = [{"is_current": True, "amount": "$120", "row_text": "Current bill $120"}]

    assert latest_discovered_month_index(discovered_rows) == (2026 * 12 + 1)
    assert month_key_from_index(2026 * 12 + 2) == "2026-02"
    assert current_bill_downloaded_entry(
        {"target": "2026-03", "amount": "$120", "match_type": "download_from_current"},
        discovered_current,
    ) == {
        "month": "2026-03",
        "status": "downloaded",
        "amount": 120.0,
        "amount_text": "$120.00",
        "path": None,
        "file_url": None,
        "cached": False,
        "billing_period": None,
        "issue_date": None,
        "sha256": None,
        "source": "current_bill",
        "row_text": "Current bill $120",
    }
    assert inferred_current_bill_entry(
        discovered_rows,
        discovered_current,
        ["2026-02"],
        {},
    ) == {
        "month": "2026-02",
        "status": "amount_found_pdf_missing",
        "amount": 120.0,
        "amount_text": "$120.00",
        "path": None,
        "file_url": None,
        "cached": False,
        "billing_period": None,
        "issue_date": None,
        "sha256": None,
        "source": "current_bill_row",
        "row_text": "Current bill $120",
    }
    assert inferred_current_bill_entry(discovered_rows, discovered_current, ["2026-02"], {"2026-02": {}}) is None


def test_summarize_account_preserves_downloaded_missing_current_and_totals():
    account = nationalgrid_bills.ACCOUNTS["air_temple_electric"]
    record = {
        "status": "ok",
        "bills": [
            {
                "target": "2026-01",
                "amount": "$100.50",
                "path": "/tmp/jan.pdf",
                "file_url": "file:///tmp/jan.pdf",
                "cached": True,
                "billing_period": "Jan 1-Feb 1",
                "issue_date": "2026-02-02",
                "sha256": "abc",
            },
            {
                "target": "2026-03",
                "amount": "$120",
                "match_type": "download_from_current",
                "path": "/tmp/mar.pdf",
            },
            {"target": "bad", "amount": "$999"},
        ],
        "discovered_rows": [
            {"month_key": "2026-01", "amount": "$100.50"},
            {"is_current": True, "amount": "$120", "row_text": "Current bill $120"},
        ],
    }

    summary = summarize_account(account, record, ["2026-01", "2026-02", "2026-03"])

    assert summary["account"] == "Air Temple Electric"
    assert summary["downloaded_count"] == 2
    assert summary["missing_count"] == 0
    assert summary["amount_found_count"] == 3
    assert summary["total_amount_text"] == "$340.50"
    assert summary["monthly_amounts"][0]["amount_text"] == "$100.50"
    assert summary["monthly_amounts"][0]["cached"] is True
    assert summary["monthly_amounts"][1]["status"] == "amount_found_pdf_missing"
    assert summary["monthly_amounts"][1]["source"] == "current_bill_row"
    assert summary["monthly_amounts"][1]["row_text"] == "Current bill $120"
    assert summary["monthly_amounts"][2]["status"] == "downloaded"
    assert summary["monthly_amounts"][2]["source"] == "current_bill"


def test_summarize_account_fills_missing_months_and_preserves_record_error():
    account = nationalgrid_bills.ACCOUNTS["earth_kingdom_gas"]
    summary = summarize_account(
        account,
        {"status": "error", "error": "login failed", "bills": []},
        ["2026-01"],
    )

    assert summary["monthly_amounts"] == [
        {
            "month": "2026-01",
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
    ]
    assert summary["missing_count"] == 1
    assert summary["total_amount_text"] == "$0.00"
    assert summary["record_status"] == "error"
    assert summary["record_error"] == "login failed"


def test_aggregate_fetch_totals_preserves_status_precedence_and_total_text():
    summaries = [
        {"downloaded_count": 1, "total_amount_text": "$100.25"},
        {"downloaded_count": 0, "total_amount_text": "$20.00"},
    ]

    assert aggregate_fetch_totals(summaries, []) == {
        "status": "ok",
        "total_amount": 120.25,
        "total_amount_text": "$120.25",
    }
    assert aggregate_fetch_totals(summaries, ["one warning"])["status"] == "partial"
    assert aggregate_fetch_totals(
        [{"downloaded_count": 0, "total_amount_text": "$0.00"}],
        ["warning"],
    ) == {
        "status": "missing",
        "total_amount": 0.0,
        "total_amount_text": "$0.00",
    }
