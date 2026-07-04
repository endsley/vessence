import unittest
from datetime import date
from pathlib import Path

from agent_skills import google_cloud_receipts
from agent_skills.google_cloud_receipt_utils import (
    BillingAccount,
    ReceiptCandidate,
    billing_account_from_gcloud_row,
    build_receipt_filename,
    document_candidate_from_row,
    downloaded_receipt_from_candidate,
    downloaded_receipts_json,
    filter_receipt_candidates_by_date,
    final_download_path,
    manifest_path,
    parse_iso_date,
    parse_receipt_amount,
    parse_receipt_date,
    receipt_candidate_from_control,
    sanitize_filename_piece,
    select_requested_receipt_candidates,
    select_open_billing_accounts,
    sort_receipt_candidates,
    unique_dest_path,
    validate_receipt_request,
)


class GoogleCloudReceiptsTests(unittest.TestCase):
    def test_google_cloud_receipts_reexports_receipt_helpers(self):
        self.assertIs(google_cloud_receipts.ReceiptCandidate, ReceiptCandidate)
        self.assertIs(google_cloud_receipts.billing_account_from_gcloud_row, billing_account_from_gcloud_row)
        self.assertIs(google_cloud_receipts.select_open_billing_accounts, select_open_billing_accounts)
        self.assertIs(google_cloud_receipts.parse_receipt_date, parse_receipt_date)
        self.assertIs(google_cloud_receipts.receipt_candidate_from_control, receipt_candidate_from_control)
        self.assertIs(google_cloud_receipts.document_candidate_from_row, document_candidate_from_row)
        self.assertIs(google_cloud_receipts.downloaded_receipt_from_candidate, downloaded_receipt_from_candidate)
        self.assertIs(google_cloud_receipts.downloaded_receipts_json, downloaded_receipts_json)
        self.assertIs(google_cloud_receipts.select_requested_receipt_candidates, select_requested_receipt_candidates)
        self.assertIs(google_cloud_receipts._manifest_path, manifest_path)
        self.assertIs(google_cloud_receipts._unique_dest_path, unique_dest_path)
        self.assertIs(google_cloud_receipts._final_download_path, final_download_path)
        self.assertIs(google_cloud_receipts.validate_receipt_request, validate_receipt_request)

    def test_parse_receipt_date_supports_multiple_formats(self):
        self.assertEqual(parse_receipt_date("Payment receipt for May 14, 2026"), date(2026, 5, 14))
        self.assertEqual(parse_receipt_date("Issued 2026-05-14"), date(2026, 5, 14))
        self.assertEqual(parse_receipt_date("Paid on 05/14/2026"), date(2026, 5, 14))

    def test_billing_account_from_gcloud_row_normalizes_account_id_and_defaults_name(self):
        self.assertEqual(
            billing_account_from_gcloud_row({
                "name": "billingAccounts/ABC-123",
                "displayName": "Primary",
                "open": True,
            }),
            BillingAccount(account_id="ABC-123", name="Primary", open=True),
        )
        self.assertEqual(
            billing_account_from_gcloud_row({"name": "XYZ-789"}),
            BillingAccount(account_id="XYZ-789", name="XYZ-789", open=False),
        )
        self.assertIsNone(billing_account_from_gcloud_row({"displayName": "missing"}))

    def test_select_open_billing_accounts_filters_requested_ids_and_reports_missing(self):
        accounts = [
            BillingAccount(account_id="open-1", name="Open 1", open=True),
            BillingAccount(account_id="closed-1", name="Closed", open=False),
            BillingAccount(account_id="open-2", name="Open 2", open=True),
        ]

        self.assertEqual(select_open_billing_accounts(accounts), (accounts[0:1] + accounts[2:3], []))
        self.assertEqual(
            select_open_billing_accounts(accounts, [" open-2 ", "closed-1", "missing", ""]),
            ([accounts[2]], ["closed-1", "missing"]),
        )

    def test_parse_receipt_amount_prefers_currency_formats(self):
        self.assertEqual(parse_receipt_amount("Receipt total $23.34"), "23.34")
        self.assertEqual(parse_receipt_amount("Amount USD 1,023.45"), "1023.45")

    def test_filename_contract(self):
        self.assertEqual(
            build_receipt_filename(
                provider="google",
                receipt_date=date(2025, 3, 4),
                amount="23.34",
            ),
            "google_3_4_2025_23.34.pdf",
        )

    def test_parse_iso_date(self):
        self.assertEqual(parse_iso_date("2026-03-01"), date(2026, 3, 1))

    def test_validate_receipt_request_preserves_download_argument_errors(self):
        validate_receipt_request(count=1, start_date=None, end_date=None)
        validate_receipt_request(count=None, start_date=date(2026, 3, 1), end_date=None)

        with self.assertRaisesRegex(ValueError, "count must be >= 1"):
            validate_receipt_request(count=0, start_date=None, end_date=None)
        with self.assertRaisesRegex(ValueError, "Provide either count or a date range"):
            validate_receipt_request(count=None, start_date=None, end_date=None)
        with self.assertRaisesRegex(ValueError, "start_date must be <= end_date"):
            validate_receipt_request(
                count=None,
                start_date=date(2026, 3, 2),
                end_date=date(2026, 3, 1),
            )

    def test_sanitize_filename_piece(self):
        self.assertEqual(
            sanitize_filename_piece("My Billing Account / March receipt"),
            "My_Billing_Account_March_receipt",
        )

    def test_sort_receipt_candidates_prefers_newer_dates(self):
        older = ReceiptCandidate(
            account_id="A",
            account_name="one",
            source_kind="link",
            source_index=0,
            source_name="Receipt",
            row_text="Payment receipt for May 01, 2026 amount $10.00",
            discovered_at=1,
            receipt_date="2026-05-01",
            amount="10.00",
            href=None,
        )
        newer = ReceiptCandidate(
            account_id="B",
            account_name="two",
            source_kind="link",
            source_index=0,
            source_name="Receipt",
            row_text="Payment receipt for May 14, 2026 amount $11.00",
            discovered_at=2,
            receipt_date="2026-05-14",
            amount="11.00",
            href=None,
        )
        ordered = sort_receipt_candidates([older, newer])
        self.assertEqual([c.account_id for c in ordered], ["B", "A"])

    def test_filter_receipt_candidates_by_date(self):
        older = ReceiptCandidate(
            account_id="A",
            account_name="one",
            source_kind="link",
            source_index=0,
            source_name="Receipt",
            row_text="Payment receipt for February 28, 2026 amount $10.00",
            discovered_at=1,
            receipt_date="2026-02-28",
            amount="10.00",
            href=None,
        )
        in_range = ReceiptCandidate(
            account_id="B",
            account_name="two",
            source_kind="link",
            source_index=0,
            source_name="Receipt",
            row_text="Payment receipt for March 14, 2026 amount $11.00",
            discovered_at=2,
            receipt_date="2026-03-14",
            amount="11.00",
            href=None,
        )
        filtered = filter_receipt_candidates_by_date(
            [older, in_range],
            start_date=date(2026, 3, 1),
            end_date=date(2026, 5, 14),
        )
        self.assertEqual([c.account_id for c in filtered], ["B"])

    def test_select_requested_receipt_candidates_sorts_filters_and_limits(self):
        older = ReceiptCandidate(
            account_id="A",
            account_name="one",
            source_kind="link",
            source_index=0,
            source_name="Receipt",
            row_text="Payment receipt for February 28, 2026 amount $10.00",
            discovered_at=1,
            receipt_date="2026-02-28",
            amount="10.00",
            href=None,
        )
        in_range = ReceiptCandidate(
            account_id="B",
            account_name="two",
            source_kind="link",
            source_index=0,
            source_name="Receipt",
            row_text="Payment receipt for March 14, 2026 amount $11.00",
            discovered_at=2,
            receipt_date="2026-03-14",
            amount="11.00",
            href=None,
        )
        newer = ReceiptCandidate(
            account_id="C",
            account_name="three",
            source_kind="link",
            source_index=0,
            source_name="Receipt",
            row_text="Payment receipt for March 31, 2026 amount $12.00",
            discovered_at=3,
            receipt_date="2026-03-31",
            amount="12.00",
            href=None,
        )

        selected = select_requested_receipt_candidates(
            [older, in_range, newer],
            count=1,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )

        self.assertEqual([c.account_id for c in selected], ["C"])

    def test_select_requested_receipt_candidates_reports_empty_date_range(self):
        candidate = ReceiptCandidate(
            account_id="A",
            account_name="one",
            source_kind="link",
            source_index=0,
            source_name="Receipt",
            row_text="Payment receipt for February 28, 2026 amount $10.00",
            discovered_at=1,
            receipt_date="2026-02-28",
            amount="10.00",
            href=None,
        )

        with self.assertRaisesRegex(RuntimeError, r"No receipts matched .*2026-03-01 to 2026-03-31"):
            select_requested_receipt_candidates(
                [candidate],
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 31),
            )

    def test_receipt_candidate_from_control_parses_date_amount_and_href(self):
        account = BillingAccount(account_id="acct-1", name="Primary", open=True)

        self.assertEqual(
            receipt_candidate_from_control(
                account,
                source_kind="link",
                source_index=3,
                source_name="Receipt",
                row_text="Payment receipt for May 14, 2026 total $23.34",
                discovered_at=2,
                href="/billing/receipt",
            ),
            ReceiptCandidate(
                account_id="acct-1",
                account_name="Primary",
                source_kind="link",
                source_index=3,
                source_name="Receipt",
                row_text="Payment receipt for May 14, 2026 total $23.34",
                discovered_at=2,
                receipt_date="2026-05-14",
                amount="23.34",
                href="/billing/receipt",
                document_token=None,
            ),
        )

    def test_document_candidate_from_row_parses_document_type_and_rejects_non_documents(self):
        account = BillingAccount(account_id="acct-1", name="Primary", open=True)

        self.assertEqual(
            document_candidate_from_row(
                account,
                source_index=4,
                row_text="Invoice issued 2026-05-14 USD 1,023.45",
                discovered_at=1,
                document_token="token-1",
            ),
            ReceiptCandidate(
                account_id="acct-1",
                account_name="Primary",
                source_kind="document_row",
                source_index=4,
                source_name="Invoice",
                row_text="Invoice issued 2026-05-14 USD 1,023.45",
                discovered_at=1,
                receipt_date="2026-05-14",
                amount="1023.45",
                href=None,
                document_token="token-1",
            ),
        )
        self.assertIsNone(document_candidate_from_row(
            account,
            source_index=5,
            row_text="Payment method updated",
            discovered_at=2,
            document_token="token-2",
        ))
        self.assertIsNone(document_candidate_from_row(
            account,
            source_index=6,
            row_text="Receipt issued 2026-05-14",
            discovered_at=3,
            document_token=None,
        ))

    def test_unique_dest_path_adds_numeric_suffix(self):
        out_dir = self.tmp_path
        (out_dir / "receipt.pdf").write_text("one")
        (out_dir / "receipt_2.pdf").write_text("two")

        self.assertEqual(unique_dest_path(out_dir, "receipt.pdf"), out_dir / "receipt_3.pdf")

    def test_final_download_path_prefers_suggested_suffix(self):
        dest = self.tmp_path / "receipt.pdf"

        self.assertEqual(final_download_path(dest, None), dest)
        self.assertEqual(final_download_path(dest, "download.PDF"), dest)
        self.assertEqual(final_download_path(dest, "download.html"), self.tmp_path / "receipt.html")

    def test_downloaded_receipt_from_candidate_preserves_manifest_shape(self):
        candidate = ReceiptCandidate(
            account_id="acct-1",
            account_name="Primary",
            source_kind="document_row",
            source_index=2,
            source_name="Invoice",
            row_text="Invoice issued 2026-05-14 USD 1,023.45",
            discovered_at=1,
            receipt_date="2026-05-14",
            amount="1023.45",
            href=None,
            document_token="token-1",
        )

        self.assertEqual(
            downloaded_receipt_from_candidate(candidate, self.tmp_path / "receipt.pdf"),
            google_cloud_receipts.DownloadedReceipt(
                account_id="acct-1",
                account_name="Primary",
                receipt_date="2026-05-14",
                amount="1023.45",
                source_name="Invoice",
                row_text="Invoice issued 2026-05-14 USD 1,023.45",
                path=str(self.tmp_path / "receipt.pdf"),
            ),
        )

    def test_manifest_helpers_preserve_path_and_json_shape(self):
        receipt = google_cloud_receipts.DownloadedReceipt(
            account_id="acct-1",
            account_name="Primary",
            receipt_date="2026-05-14",
            amount="1023.45",
            source_name="Invoice",
            row_text="Invoice issued 2026-05-14 USD 1,023.45",
            path="/tmp/receipt.pdf",
        )

        self.assertEqual(manifest_path(self.tmp_path), self.tmp_path / "manifest.json")
        self.assertEqual(
            downloaded_receipts_json([receipt]),
            (
                "[\n"
                "  {\n"
                '    "account_id": "acct-1",\n'
                '    "account_name": "Primary",\n'
                '    "receipt_date": "2026-05-14",\n'
                '    "amount": "1023.45",\n'
                '    "source_name": "Invoice",\n'
                '    "row_text": "Invoice issued 2026-05-14 USD 1,023.45",\n'
                '    "path": "/tmp/receipt.pdf"\n'
                "  }\n"
                "]"
            ),
        )

    def setUp(self):
        import tempfile

        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()


if __name__ == "__main__":
    unittest.main()
