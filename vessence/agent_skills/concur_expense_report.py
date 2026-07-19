#!/usr/bin/env python3
"""Northeastern Concur report inspector and receipt uploader.

This script automates the repeatable Concur UI steps that previously required
manual browser work: launch Concur, open an existing report, inspect expense
rows, and attach receipt PDFs from a JSON plan.

It intentionally does not submit reports.

Plan schema:

{
  "report_name": "from_may_to_july_report",
  "items": [
    {
      "date": "07/01/2026",
      "vendor": "AMAZON WEB SERVICES",
      "amount": "18.14",
      "receipt_path": "/home/chieh/Desktop/Receipts/.../aws_2026_07_01_18.14_...pdf"
    }
  ]
}

If Concur changes slightly, failures write diagnostics under
`~/Desktop/Receipts/automation_diagnostics/concur`. Those artifacts are meant
for an LLM repair pass against this file.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import asdict, dataclass
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
from agent_skills.web_ui_change import recover_website_ui_change

CONCUR_PROFILE_ID = "northeastern_concur"
CONCUR_PROFILE_NAME = "Northeastern Concur"
CONCUR_PROFILE_DOMAIN = "concursolutions.com"
CONCUR_HOME_URL = "https://us2.concursolutions.com/home"
EMPLOYEE_HUB_URL = "https://employee.me.northeastern.edu/"
DEFAULT_DIAGNOSTICS_DIR = Path.home() / "Desktop" / "Receipts" / "automation_diagnostics" / "concur"


@dataclass
class ExpenseRow:
    index: int
    date: str | None
    vendor: str | None
    amount: str | None
    text: str
    cells: list[str]


@dataclass(frozen=True)
class ReceiptPlanItem:
    date: str
    vendor: str
    amount: str
    receipt_path: str
    replace: bool = False


@dataclass
class AttachResult:
    item: dict[str, Any]
    status: str
    message: str


def ensure_concur_profile(profile_id: str = CONCUR_PROFILE_ID) -> ProfileMeta:
    try:
        meta = get_profile(profile_id)
        if meta.domain != CONCUR_PROFILE_DOMAIN:
            raise RuntimeError(
                f"Profile {profile_id!r} is bound to {meta.domain!r}, expected {CONCUR_PROFILE_DOMAIN!r}."
            )
        return meta
    except ProfileNotFound:
        meta = create_profile(CONCUR_PROFILE_NAME, CONCUR_PROFILE_DOMAIN)
        if meta.profile_id != profile_id:
            raise RuntimeError(
                f"Expected profile id {profile_id!r}, created {meta.profile_id!r}."
            )
        return meta


def require_concur_profile(profile_id: str = CONCUR_PROFILE_ID) -> ProfileMeta:
    try:
        meta = get_profile(profile_id)
    except ProfileNotFound as e:
        raise RuntimeError(
            "Concur profile not found. Run `python agent_skills/concur_expense_report.py capture-profile` first."
        ) from e
    if meta.domain != CONCUR_PROFILE_DOMAIN:
        raise RuntimeError(
            f"Profile {profile_id!r} is bound to {meta.domain!r}, expected {CONCUR_PROFILE_DOMAIN!r}."
        )
    if not meta.last_used:
        raise RuntimeError("Concur profile exists but has no captured login state. Run capture-profile first.")
    return meta


def normalize_amount(value: str | float | int) -> str:
    return f"{float(str(value).replace('$', '').replace(',', '').strip()):.2f}"


def amount_variants(amount: str | float | int) -> set[str]:
    norm = normalize_amount(amount)
    return {norm, f"${norm}", f"USD {norm}"}


def safe_piece(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("_") or "unknown"


def parse_plan(path: Path) -> tuple[str, list[ReceiptPlanItem]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    report_name = data.get("report_name")
    if not report_name:
        raise ValueError("plan JSON requires report_name")
    items: list[ReceiptPlanItem] = []
    for raw in data.get("items", []):
        item = ReceiptPlanItem(
            date=str(raw["date"]),
            vendor=str(raw["vendor"]),
            amount=normalize_amount(raw["amount"]),
            receipt_path=str(raw["receipt_path"]),
            replace=bool(raw.get("replace", False)),
        )
        if not Path(item.receipt_path).expanduser().exists():
            raise FileNotFoundError(item.receipt_path)
        items.append(item)
    if not items:
        raise ValueError("plan JSON has no items")
    return report_name, items


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


async def click_first_visible(locator: Any, *, timeout: int = 5000) -> bool:
    try:
        count = await locator.count()
    except Exception:
        return False
    for idx in range(min(count, 12)):
        item = locator.nth(idx)
        try:
            if await item.is_visible(timeout=800):
                await item.click(timeout=timeout)
                return True
        except Exception:
            continue
    return False


async def is_concur_ready(page: Any) -> bool:
    text = await page_text(page)
    return any(token in text for token in ("Create Expense Report", "Expense Reports", "Available Expenses"))


async def is_concur_signin(page: Any) -> bool:
    text = await page_text(page)
    url = page.url or ""
    return "Sign In" in text and ("concursolutions" in url or "SAP Concur" in text)


async def launch_concur(page: Any, *, use_employee_hub: bool) -> None:
    await page.goto(CONCUR_HOME_URL, wait_until="domcontentloaded", timeout=90000)
    await page.wait_for_timeout(5000)
    if await is_concur_ready(page):
        return
    if not use_employee_hub:
        return
    if await is_concur_signin(page):
        await page.goto(EMPLOYEE_HUB_URL, wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(4000)
        clicked = await click_first_visible(page.get_by_text("Concur", exact=True))
        if not clicked:
            clicked = await click_first_visible(page.get_by_text(re.compile(r"\bConcur\b", re.IGNORECASE)))
        if clicked:
            await page.wait_for_timeout(8000)


async def capture_concur_profile(
    *,
    profile_id: str = CONCUR_PROFILE_ID,
    timeout_s: int = 900,
    use_employee_hub: bool = True,
) -> ProfileMeta:
    meta = ensure_concur_profile(profile_id)
    mgr = BrowserSessionManager.instance()
    async with mgr.session(
        run_id=f"capture_{meta.profile_id}",
        options=SessionOptions(headless=False, storage_state_path=storage_state_path(meta.profile_id)),
    ) as sess:
        page = sess.page
        print("Visible browser opened. Complete Northeastern/Concur login if prompted.", flush=True)
        deadline = asyncio.get_running_loop().time() + timeout_s
        await launch_concur(page, use_employee_hub=use_employee_hub)
        while asyncio.get_running_loop().time() < deadline:
            if await is_concur_ready(page):
                await capture_after_login(page, meta.profile_id)
                return get_profile(meta.profile_id)
            await page.wait_for_timeout(2000)
    raise TimeoutError("Timed out waiting for authenticated Concur.")


async def open_report(page: Any, report_name: str, *, use_employee_hub: bool, diagnostics_dir: Path) -> None:
    await launch_concur(page, use_employee_hub=use_employee_hub)
    if not await is_concur_ready(page):
        await write_diagnostics(page, diagnostics_dir, "concur_not_ready")
        raise RuntimeError("Concur is not ready or is signed out. Run capture-profile again.")
    if await page.get_by_text(report_name, exact=True).count():
        await page.get_by_text(report_name, exact=True).first.click(timeout=15000)
    else:
        # Try the sidebar/report page, then the report name again.
        await click_first_visible(page.get_by_text(re.compile(r"Expense Reports", re.IGNORECASE)))
        await page.wait_for_timeout(3000)
        if await page.get_by_text(report_name, exact=True).count():
            await page.get_by_text(report_name, exact=True).first.click(timeout=15000)
        else:
            await write_diagnostics(page, diagnostics_dir, f"report_not_found_{report_name}")
            raise RuntimeError(f"Report not found: {report_name}")
    await page.wait_for_timeout(5000)
    text = await page_text(page)
    if report_name not in text or "Expenses" not in text:
        await write_diagnostics(page, diagnostics_dir, f"report_open_failed_{report_name}")
        raise RuntimeError(f"Could not open report: {report_name}")


async def extract_expense_rows(page: Any) -> list[ExpenseRow]:
    rows_data = await page.evaluate(
        """
        () => {
          const seen = new Set();
          const nodes = Array.from(document.querySelectorAll('tr,[role="row"]'));
          return nodes.map((row, index) => {
            const text = (row.innerText || '').trim();
            const cells = Array.from(row.querySelectorAll('th,td,[role="gridcell"],[role="columnheader"]'))
              .map(cell => (cell.innerText || '').trim())
              .filter(Boolean);
            return {index, text, cells};
          }).filter(row => {
            if (!row.text || seen.has(row.text)) return false;
            seen.add(row.text);
            return /\d{2}\/\d{2}\/\d{4}/.test(row.text) && /\$?\d+\.\d{2}/.test(row.text);
          });
        }
        """
    )
    out: list[ExpenseRow] = []
    for raw in rows_data:
        text = raw.get("text", "")
        date_match = re.search(r"\b\d{2}/\d{2}/\d{4}\b", text)
        amount_match = re.search(r"\$?([0-9][0-9,]*\.\d{2})", text)
        vendor = None
        for candidate in ("OPENAI OPCO", "GOOGLE SERVICES", "AMAZON WEB SERVICES", "ANTHROPIC"):
            if candidate in text.upper():
                vendor = candidate
                break
        out.append(
            ExpenseRow(
                index=int(raw.get("index", 0)),
                date=date_match.group(0) if date_match else None,
                vendor=vendor,
                amount=normalize_amount(amount_match.group(1)) if amount_match else None,
                text=text,
                cells=list(raw.get("cells", [])),
            )
        )
    return out


async def find_row_locator(page: Any, item: ReceiptPlanItem) -> Any:
    vendor = item.vendor.upper()
    amounts = amount_variants(item.amount)
    for selector in ("tr", '[role="row"]'):
        rows = page.locator(selector)
        count = await rows.count()
        for idx in range(count):
            row = rows.nth(idx)
            try:
                text = await row.inner_text(timeout=1000)
            except Exception:
                continue
            text_upper = text.upper()
            if item.date in text and vendor in text_upper and any(amount in text for amount in amounts):
                return row
    raise RuntimeError(f"No matching row for {item.date} {item.vendor} {item.amount}")


async def open_row_editor(page: Any, row: Any, item: ReceiptPlanItem) -> None:
    buttons = row.locator("button")
    if await buttons.count():
        await buttons.last.click(timeout=10000)
        await page.wait_for_timeout(700)
        if await click_first_visible(page.get_by_role("menuitem", name=re.compile(r"^Edit$", re.IGNORECASE))):
            pass
        elif await click_first_visible(page.get_by_text("Edit", exact=True)):
            pass
        else:
            await row.dblclick(timeout=10000)
    else:
        await row.dblclick(timeout=10000)
    await page.wait_for_timeout(4000)
    text = await page_text(page)
    if "Save Expense" not in text:
        raise RuntimeError(f"Editor did not open for {item.date} {item.vendor} {item.amount}")
    if item.vendor.upper() not in text.upper() or normalize_amount(item.amount) not in text:
        raise RuntimeError(f"Editor content does not match selected row for {item.date} {item.vendor} {item.amount}")


async def receipt_already_attached(page: Any) -> bool:
    text = await page_text(page)
    return "Remove" in text and "Upload New Receipt" not in text


async def remove_existing_receipt(page: Any) -> None:
    clicked = await click_first_visible(page.get_by_text("Remove", exact=True))
    if not clicked:
        raise RuntimeError("Could not find existing receipt Remove control.")
    await page.wait_for_timeout(1000)
    await click_first_visible(page.get_by_role("button", name=re.compile(r"Remove Receipt", re.IGNORECASE)))
    await page.wait_for_timeout(2500)


async def attach_receipt_file(page: Any, receipt_path: Path) -> None:
    upload = page.get_by_role("button", name=re.compile(r"Upload New Receipt", re.IGNORECASE))
    if await upload.count():
        async with page.expect_file_chooser(timeout=15000) as chooser_info:
            await upload.first.click(timeout=10000)
        chooser = await chooser_info.value
        await chooser.set_files(str(receipt_path))
    else:
        file_input = page.locator('input[type="file"]')
        if await file_input.count() == 0:
            raise RuntimeError("No Upload New Receipt button or file input found.")
        await file_input.first.set_input_files(str(receipt_path))
    try:
        await page.get_by_text(re.compile(r"Receipt attached", re.IGNORECASE)).wait_for(timeout=20000)
    except Exception:
        await page.wait_for_timeout(3000)
    text = await page_text(page)
    if "Remove" not in text and "Receipt attached" not in text:
        raise RuntimeError(f"Receipt upload did not appear to complete: {receipt_path}")


async def save_expense(page: Any) -> None:
    save = page.get_by_role("button", name=re.compile(r"Save Expense", re.IGNORECASE))
    if await save.count() == 0:
        raise RuntimeError("Save Expense button not found.")
    await save.first.click(timeout=15000)
    await page.wait_for_timeout(5000)
    text = await page_text(page)
    if "Expenses" not in text:
        await page.wait_for_timeout(5000)


async def attach_plan_items(
    page: Any,
    items: list[ReceiptPlanItem],
    *,
    diagnostics_dir: Path,
) -> list[AttachResult]:
    results: list[AttachResult] = []
    for item in items:
        try:
            row = await find_row_locator(page, item)
            await open_row_editor(page, row, item)
            if await receipt_already_attached(page):
                if item.replace:
                    await remove_existing_receipt(page)
                else:
                    results.append(AttachResult(asdict(item), "skipped", "receipt already attached"))
                    await click_first_visible(page.get_by_text(re.compile(r"from_.*_report", re.IGNORECASE)))
                    await page.wait_for_timeout(3000)
                    continue
            await attach_receipt_file(page, Path(item.receipt_path).expanduser())
            await save_expense(page)
            results.append(AttachResult(asdict(item), "attached", "receipt attached and expense saved"))
        except Exception as e:
            await write_diagnostics(page, diagnostics_dir, f"attach_failed_{item.date}_{item.vendor}_{item.amount}")
            results.append(AttachResult(asdict(item), "failed", str(e)))
            break
    return results


async def run_capture(args: argparse.Namespace) -> int:
    meta = await capture_concur_profile(
        profile_id=args.profile_id,
        timeout_s=args.timeout,
        use_employee_hub=not args.no_employee_hub,
    )
    print(json.dumps(meta.to_dict(), indent=2))
    return 0


async def run_inspect(args: argparse.Namespace) -> int:
    meta = require_concur_profile(args.profile_id)
    diagnostics_dir = Path(args.diagnostics_dir).expanduser()
    mgr = BrowserSessionManager.instance()
    async with mgr.session(
        run_id="concur_inspect_report",
        options=SessionOptions(
            headless=not args.visible,
            storage_state_path=storage_state_path(meta.profile_id),
            record_trace=args.trace,
        ),
    ) as sess:
        page = sess.page
        page.set_default_timeout(30000)
        await open_report(page, args.report_name, use_employee_hub=not args.no_employee_hub, diagnostics_dir=diagnostics_dir)
        rows = await extract_expense_rows(page)
        touch_last_used(meta.profile_id)
    print(json.dumps([asdict(row) for row in rows], indent=2))
    return 0


async def run_attach(args: argparse.Namespace) -> int:
    meta = require_concur_profile(args.profile_id)
    diagnostics_dir = Path(args.diagnostics_dir).expanduser()
    report_name, items = parse_plan(Path(args.plan).expanduser())
    if args.report_name:
        report_name = args.report_name
    mgr = BrowserSessionManager.instance()
    async with mgr.session(
        run_id="concur_attach_receipts",
        options=SessionOptions(
            headless=not args.visible,
            storage_state_path=storage_state_path(meta.profile_id),
            record_trace=args.trace,
        ),
    ) as sess:
        page = sess.page
        page.set_default_timeout(30000)
        await open_report(page, report_name, use_employee_hub=not args.no_employee_hub, diagnostics_dir=diagnostics_dir)
        results = await attach_plan_items(page, items, diagnostics_dir=diagnostics_dir)
        touch_last_used(meta.profile_id)
    print(json.dumps([asdict(result) for result in results], indent=2))
    return 0 if all(r.status != "failed" for r in results) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-id", default=CONCUR_PROFILE_ID)
    sub = parser.add_subparsers(dest="cmd", required=True)

    capture = sub.add_parser("capture-profile")
    capture.add_argument("--timeout", type=int, default=900)
    capture.add_argument("--no-employee-hub", action="store_true")
    capture.set_defaults(func=run_capture)

    inspect = sub.add_parser("inspect-report")
    inspect.add_argument("--report-name", required=True)
    inspect.add_argument("--diagnostics-dir", default=str(DEFAULT_DIAGNOSTICS_DIR))
    inspect.add_argument("--visible", action="store_true")
    inspect.add_argument("--trace", action="store_true")
    inspect.add_argument("--no-employee-hub", action="store_true")
    inspect.set_defaults(func=run_inspect)

    attach = sub.add_parser("attach-receipts")
    attach.add_argument("--plan", required=True)
    attach.add_argument("--report-name")
    attach.add_argument("--diagnostics-dir", default=str(DEFAULT_DIAGNOSTICS_DIR))
    attach.add_argument("--visible", action="store_true")
    attach.add_argument("--trace", action="store_true")
    attach.add_argument("--no-employee-hub", action="store_true")
    attach.set_defaults(func=run_attach)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(args.func(args))
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        recover_website_ui_change(
            skill="northeastern-concur-expense-report",
            intent="Open the named Concur expense report and extract its visible expense rows; attachment changes must never be replayed automatically.",
            operation=args.cmd,
            exc=e,
            project_root=Path(__file__).resolve().parents[1],
            retry_safe=args.cmd == "inspect-report",
        )
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
