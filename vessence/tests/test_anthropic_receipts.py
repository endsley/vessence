import unittest
from datetime import date

from agent_skills import anthropic_receipts
from agent_skills.google_cloud_receipt_utils import (
    ReceiptCandidate,
    build_receipt_filename,
    select_requested_receipt_candidates,
)


class AnthropicReceiptsTests(unittest.TestCase):
    def test_receipt_candidate_from_stripe_link_parses_claude_invoice_row(self):
        candidate = anthropic_receipts.receipt_candidate_from_invoice_control(
            {
                "href": "https://invoice.stripe.com/i/acct_123/live_invoice?s=ap",
                "aria": "View invoice",
                "text": "View",
                "row_text": "July 9, 2026\n$85.81\nPaid\nView",
            },
            2,
        )

        self.assertEqual(
            candidate,
            ReceiptCandidate(
                account_id="claude",
                account_name="Claude",
                source_kind="stripe_invoice_link",
                source_index=2,
                source_name="Stripe Invoice",
                row_text="July 9, 2026\n$85.81\nPaid\nView\nView\nView invoice",
                discovered_at=3,
                receipt_date="2026-07-09",
                amount="85.81",
                href="https://invoice.stripe.com/i/acct_123/live_invoice?s=ap",
                document_token=None,
            ),
        )

    def test_receipt_candidate_accepts_invoice_context_without_href_for_listing(self):
        candidate = anthropic_receipts.receipt_candidate_from_invoice_control(
            {
                "href": "",
                "aria": "Download invoice",
                "text": "Download",
                "row_text": "Invoice\nApr 16, 2026\nUSD 21.25\nPaid",
            },
            0,
        )

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(candidate.source_kind, "invoice_control")
        self.assertEqual(candidate.receipt_date, "2026-04-16")
        self.assertEqual(candidate.amount, "21.25")
        self.assertIsNone(candidate.href)

    def test_receipt_candidate_rejects_random_controls_and_missing_dates(self):
        self.assertIsNone(anthropic_receipts.receipt_candidate_from_invoice_control({
            "href": "https://example.com/",
            "text": "View",
            "row_text": "Project settings",
        }, 0))
        self.assertIsNone(anthropic_receipts.receipt_candidate_from_invoice_control({
            "href": "https://invoice.stripe.com/i/acct_123/live_invoice?s=ap",
            "text": "View",
            "row_text": "Invoice\nPaid\n$21.25",
        }, 0))

    def test_anthropic_filename_contract_reuses_receipt_helpers(self):
        self.assertEqual(
            build_receipt_filename(
                provider=anthropic_receipts.PROVIDER_FILENAME_PREFIX,
                receipt_date=date(2026, 4, 16),
                amount="21.25",
            ),
            "anthropic_4_16_2026_21.25.pdf",
        )

    def test_date_range_selection_covers_work_report_window(self):
        april = anthropic_receipts.receipt_candidate_from_invoice_control(
            {
                "href": "https://invoice.stripe.com/i/acct_123/april?s=ap",
                "text": "View",
                "row_text": "Invoice\nApril 16, 2026\n$21.25\nPaid",
            },
            0,
        )
        july = anthropic_receipts.receipt_candidate_from_invoice_control(
            {
                "href": "https://invoice.stripe.com/i/acct_123/july?s=ap",
                "text": "View",
                "row_text": "Invoice\nJuly 9, 2026\n$85.81\nPaid",
            },
            1,
        )
        december = anthropic_receipts.receipt_candidate_from_invoice_control(
            {
                "href": "https://invoice.stripe.com/i/acct_123/december?s=ap",
                "text": "View",
                "row_text": "Invoice\nDecember 16, 2025\n$21.25\nPaid",
            },
            2,
        )

        selected = select_requested_receipt_candidates(
            [candidate for candidate in (april, july, december) if candidate],
            start_date=date(2026, 4, 1),
            end_date=date(2026, 7, 10),
        )

        self.assertEqual([candidate.receipt_date for candidate in selected], ["2026-07-09", "2026-04-16"])

    def test_blocked_login_reason_matches_google_automation_rejection(self):
        reason = anthropic_receipts.blocked_login_reason_from_text(
            "Couldn't sign you in. This browser or app may not be secure."
        )

        self.assertEqual(reason, "Google rejected the automated browser as insecure.")


if __name__ == "__main__":
    unittest.main()
