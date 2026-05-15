import unittest
from datetime import date

from agent_skills.google_cloud_receipts import (
    ReceiptCandidate,
    build_receipt_filename,
    filter_receipt_candidates_by_date,
    parse_iso_date,
    parse_receipt_amount,
    parse_receipt_date,
    sanitize_filename_piece,
    sort_receipt_candidates,
)


class GoogleCloudReceiptsTests(unittest.TestCase):
    def test_parse_receipt_date_supports_multiple_formats(self):
        self.assertEqual(parse_receipt_date("Payment receipt for May 14, 2026"), date(2026, 5, 14))
        self.assertEqual(parse_receipt_date("Issued 2026-05-14"), date(2026, 5, 14))
        self.assertEqual(parse_receipt_date("Paid on 05/14/2026"), date(2026, 5, 14))

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


if __name__ == "__main__":
    unittest.main()
