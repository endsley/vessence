"""Pure receipt parsing helpers for Google Cloud Billing downloads."""
from __future__ import annotations

import re
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable


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
DOCUMENT_NAME_RE = re.compile(r"\b(statement|invoice|receipt)\b", re.IGNORECASE)


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


def billing_account_from_gcloud_row(row: dict) -> BillingAccount | None:
    account_id = str(row.get("name") or "").strip()
    if account_id.startswith("billingAccounts/"):
        account_id = account_id.split("/", 1)[1]
    if not account_id:
        return None
    return BillingAccount(
        account_id=account_id,
        name=str(row.get("displayName") or account_id),
        open=bool(row.get("open", False)),
    )


def select_open_billing_accounts(
    accounts: Iterable[BillingAccount],
    billing_account_ids: Iterable[str] | None = None,
) -> tuple[list[BillingAccount], list[str]]:
    open_accounts = [account for account in accounts if account.open]
    if not billing_account_ids:
        return open_accounts, []
    wanted = {account_id.strip() for account_id in billing_account_ids if account_id.strip()}
    filtered = [account for account in open_accounts if account.account_id in wanted]
    missing = sorted(wanted.difference({account.account_id for account in filtered}))
    return filtered, missing


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


def receipt_candidate_from_control(
    account: BillingAccount,
    *,
    source_kind: str,
    source_index: int,
    source_name: str,
    row_text: str,
    discovered_at: int,
    href: str | None = None,
) -> ReceiptCandidate:
    parsed_date = parse_receipt_date(row_text or source_name)
    amount = parse_receipt_amount(row_text)
    return ReceiptCandidate(
        account_id=account.account_id,
        account_name=account.name,
        source_kind=source_kind,
        source_index=source_index,
        source_name=source_name,
        row_text=row_text,
        discovered_at=discovered_at,
        receipt_date=parsed_date.isoformat() if parsed_date else None,
        amount=amount,
        href=href,
        document_token=None,
    )


def document_candidate_from_row(
    account: BillingAccount,
    *,
    source_index: int,
    row_text: str,
    discovered_at: int,
    document_token: str | None,
) -> ReceiptCandidate | None:
    if not row_text or not document_token:
        return None
    match = DOCUMENT_NAME_RE.search(row_text)
    if not match:
        return None
    parsed_date = parse_receipt_date(row_text)
    amount = parse_receipt_amount(row_text)
    return ReceiptCandidate(
        account_id=account.account_id,
        account_name=account.name,
        source_kind="document_row",
        source_index=source_index,
        source_name=match.group(1).title(),
        row_text=row_text,
        discovered_at=discovered_at,
        receipt_date=parsed_date.isoformat() if parsed_date else None,
        amount=amount,
        href=None,
        document_token=document_token,
    )


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


def validate_receipt_request(
    *,
    count: int | None,
    start_date: date | None,
    end_date: date | None,
) -> None:
    if count is not None and count < 1:
        raise ValueError("count must be >= 1")
    if count is None and start_date is None and end_date is None:
        raise ValueError("Provide either count or a date range.")
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ValueError("start_date must be <= end_date")


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


def unique_dest_path(out_dir: Path, filename: str) -> Path:
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


def final_download_path(dest: Path, suggested_filename: str | None) -> Path:
    suffix = dest.suffix
    if suggested_filename:
        sfx = Path(suggested_filename).suffix.lower()
        if sfx:
            suffix = sfx
    return dest.with_suffix(suffix)


def downloaded_receipt_from_candidate(
    candidate: ReceiptCandidate,
    saved_path: Path | str,
    *,
    receipt_date: date | None = None,
) -> DownloadedReceipt:
    parsed_date = receipt_date if receipt_date is not None else candidate_date(candidate)
    return DownloadedReceipt(
        account_id=candidate.account_id,
        account_name=candidate.account_name,
        receipt_date=parsed_date.isoformat() if parsed_date else None,
        amount=candidate.amount,
        source_name=candidate.source_name,
        row_text=candidate.row_text,
        path=str(saved_path),
    )


def manifest_path(out_dir: Path) -> Path:
    return out_dir / "manifest.json"


def downloaded_receipts_json(downloads: Iterable[DownloadedReceipt]) -> str:
    return json.dumps([asdict(download) for download in downloads], indent=2)
