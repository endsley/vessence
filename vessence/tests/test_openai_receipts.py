import unittest
from datetime import date

from agent_skills import openai_receipts
from agent_skills.google_cloud_receipt_utils import (
    ReceiptCandidate,
    build_receipt_filename,
    select_requested_receipt_candidates,
)


class OpenAIReceiptsTests(unittest.TestCase):
    def test_receipt_candidate_from_invoice_link_parses_chatgpt_grid_payload(self):
        candidate = openai_receipts.receipt_candidate_from_invoice_link(
            {
                "href": "https://invoice.stripe.com/i/acct_123/live_invoice?s=ap",
                "aria": "Open invoice from July 9, 2026",
                "date_text": "Jul 9, 2026",
                "amount_text": "$85.90",
                "status_text": "Paid",
                "row_text": "Jul 9, 2026\n$85.90\nPaid\nView",
            },
            3,
        )

        self.assertEqual(
            candidate,
            ReceiptCandidate(
                account_id="chatgpt",
                account_name="ChatGPT",
                source_kind="stripe_invoice_link",
                source_index=3,
                source_name="Invoice",
                row_text="Jul 9, 2026\n$85.90\nPaid\nView",
                discovered_at=4,
                receipt_date="2026-07-09",
                amount="85.90",
                href="https://invoice.stripe.com/i/acct_123/live_invoice?s=ap",
                document_token=None,
            ),
        )

    def test_receipt_candidate_uses_aria_date_when_grid_date_is_missing(self):
        candidate = openai_receipts.receipt_candidate_from_invoice_link(
            {
                "href": "https://invoice.stripe.com/i/acct_123/live_invoice?s=ap",
                "aria": "Open invoice from April 16, 2026",
                "amount_text": "$21.25",
                "status_text": "Paid",
            },
            0,
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.receipt_date, "2026-04-16")
        self.assertEqual(candidate.amount, "21.25")

    def test_receipt_candidate_rejects_non_stripe_links_and_missing_dates(self):
        self.assertIsNone(openai_receipts.receipt_candidate_from_invoice_link({
            "href": "https://example.com/invoice",
            "aria": "Open invoice from July 9, 2026",
        }, 0))
        self.assertIsNone(openai_receipts.receipt_candidate_from_invoice_link({
            "href": "https://invoice.stripe.com/i/acct_123/live_invoice?s=ap",
            "aria": "Open invoice",
        }, 0))

    def test_openai_filename_contract_reuses_receipt_helpers(self):
        self.assertEqual(
            build_receipt_filename(
                provider=openai_receipts.PROVIDER_FILENAME_PREFIX,
                receipt_date=date(2026, 7, 9),
                amount="85.90",
            ),
            "openai_7_9_2026_85.90.pdf",
        )

    def test_date_range_selection_covers_work_report_window(self):
        april = openai_receipts.receipt_candidate_from_invoice_link(
            {
                "href": "https://invoice.stripe.com/i/acct_123/april?s=ap",
                "aria": "Open invoice from April 16, 2026",
                "amount_text": "$21.25",
            },
            0,
        )
        july = openai_receipts.receipt_candidate_from_invoice_link(
            {
                "href": "https://invoice.stripe.com/i/acct_123/july?s=ap",
                "aria": "Open invoice from July 9, 2026",
                "amount_text": "$85.90",
            },
            1,
        )
        december = openai_receipts.receipt_candidate_from_invoice_link(
            {
                "href": "https://invoice.stripe.com/i/acct_123/december?s=ap",
                "aria": "Open invoice from December 16, 2025",
                "amount_text": "$21.25",
            },
            2,
        )

        selected = select_requested_receipt_candidates(
            [candidate for candidate in (april, july, december) if candidate],
            start_date=date(2026, 4, 1),
            end_date=date(2026, 7, 10),
        )

        self.assertEqual([candidate.receipt_date for candidate in selected], ["2026-07-09", "2026-04-16"])


if __name__ == "__main__":
    unittest.main()
