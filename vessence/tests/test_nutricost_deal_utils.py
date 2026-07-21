import base64
import datetime as dt
from zoneinfo import ZoneInfo

from agent_skills import nutricost_deal_monitor
from agent_skills.nutricost_deal_utils import (
    NUTRICOST_FROM,
    alerted_message_ids,
    best_detected_discount,
    build_deal_alert_content,
    clean_url,
    deal_alerted_within,
    deal_key,
    default_monitor_state,
    extract_deal_links,
    extract_discounts,
    is_marketing_message,
    nutricost_message_text,
    record_deal_alert,
    record_alerted_message,
)


NY = ZoneInfo("America/New_York")


def _message(sender: str, *, headers: dict[str, str] | None = None) -> dict:
    all_headers = {"From": sender, **(headers or {})}
    return {
        "payload": {
            "headers": [
                {"name": name, "value": value}
                for name, value in all_headers.items()
            ],
        },
    }


class _Request:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class _Messages:
    def __init__(self, service):
        self.service = service

    def get(self, userId, id, format):  # noqa: N803
        return _Request(self.service.messages[id])

    def trash(self, userId, id):  # noqa: N803
        self.service.trashed.append(id)
        return _Request({})


class _Users:
    def __init__(self, service):
        self.service = service

    def messages(self):
        return _Messages(self.service)


class _Service:
    def __init__(self, messages):
        self.messages = messages
        self.trashed = []

    def users(self):
        return _Users(self)


def _nutricost_message(
    message_dt: dt.datetime,
    subject: str,
    *,
    snippet: str = "",
    body: str = "",
) -> dict:
    return {
        "internalDate": str(int(message_dt.timestamp() * 1000)),
        "snippet": snippet,
        "payload": {
            "headers": [
                {"name": "From", "value": "Nutricost <support@nutricost.com>"},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": "Mon, 29 Jun 2026 09:00:00 -0400"},
                {"name": "List-Unsubscribe", "value": "<https://manage.kmail-lists.com/unsubscribe>"},
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": base64.urlsafe_b64encode(body.encode()).decode()},
                }
            ],
        },
    }


def test_nutricost_helpers_are_reexported_from_monitor():
    assert nutricost_deal_monitor.NUTRICOST_FROM == NUTRICOST_FROM
    assert nutricost_deal_monitor.extract_discounts is extract_discounts
    assert nutricost_deal_monitor.extract_deal_links is extract_deal_links
    assert nutricost_deal_monitor.default_monitor_state is default_monitor_state
    assert nutricost_deal_monitor.alerted_message_ids is alerted_message_ids
    assert nutricost_deal_monitor.record_deal_alert is record_deal_alert
    assert nutricost_deal_monitor.record_alerted_message is record_alerted_message


def test_alert_state_helpers_preserve_default_and_sorted_alerted_ids():
    state = default_monitor_state()
    assert state == {"alerted_message_ids": [], "recent_deal_alerts": []}
    assert alerted_message_ids(state) == set()

    record_alerted_message(state, "msg-b")
    record_alerted_message(state, "msg-a")
    record_alerted_message(state, "msg-b")

    assert alerted_message_ids(state) == {"msg-a", "msg-b"}
    assert state == {"alerted_message_ids": ["msg-a", "msg-b"], "recent_deal_alerts": []}


def test_deal_alert_deduplication_uses_promo_code_and_three_day_window():
    now = dt.datetime(2026, 7, 20, 9, 0, tzinfo=NY)
    state = default_monitor_state()
    summer_key = deal_key(35, "Use code SUMMER35 for 35% off")

    assert summer_key == "discount:35;code:SUMMER35"
    assert deal_key(35, "35% off sitewide") == "discount:35"
    record_deal_alert(state, message_id="summer", key=summer_key, alerted_at=now)

    assert deal_alerted_within(state, summer_key, now=now + dt.timedelta(days=3))
    assert not deal_alerted_within(state, summer_key, now=now + dt.timedelta(days=3, seconds=1))
    assert not deal_alerted_within(state, deal_key(35, "Use code FALL35 for 35% off"), now=now)
    assert state["alerted_message_ids"] == ["summer"]


def test_is_marketing_message_requires_nutricost_sender_and_bulk_signal():
    marketing = _message(
        "Nutricost <support@nutricost.com>",
        headers={"List-Unsubscribe": "<https://manage.kmail-lists.com/unsubscribe>"},
    )
    no_signal = _message("Nutricost <support@nutricost.com>")
    wrong_sender = _message(
        "Someone <sender@example.com>",
        headers={"List-Unsubscribe": "<https://manage.kmail-lists.com/unsubscribe>"},
    )

    assert is_marketing_message(marketing, "Save 30% today")
    assert not is_marketing_message(no_signal, "Save 30% today")
    assert not is_marketing_message(wrong_sender, "Save 30% today")


def test_extract_discounts_keeps_percent_deals_in_supported_range():
    assert extract_discounts("30% off plus 40 percent sitewide, 0% and 99% ignored") == [
        30,
        40,
    ]
    assert best_detected_discount("30% off plus 40 percent sitewide") == 40


def test_extract_deal_links_prefers_nutricost_and_filters_noise():
    text = """
    https://manage.kmail-lists.com/unsubscribe
    https://www.nutricost.com/products/creatine?utm=1
    https://www.instagram.com/nutricost
    https://example.com/fallback
    https://www.nutricost.com/products/creatine?utm=1
    """

    assert extract_deal_links(text) == [
        "https://www.nutricost.com/products/creatine?utm=1",
        "https://example.com/fallback",
    ]


def test_clean_url_decodes_entities_and_strips_trailing_punctuation():
    assert clean_url(" https://example.com?a=1&amp;b=2). ") == "https://example.com?a=1&b=2"


def test_nutricost_message_text_combines_subject_snippet_and_body():
    message = _nutricost_message(
        dt.datetime(2026, 6, 29, 9, 0, tzinfo=NY),
        "40% off",
        snippet="Creatine sale",
        body="https://www.nutricost.com/products/creatine",
    )

    assert nutricost_message_text(message, "40% off") == (
        "40% off\n\n"
        "Creatine sale\n\n"
        "https://www.nutricost.com/products/creatine"
    )


def test_build_deal_alert_content_formats_subject_body_and_no_link_fallback():
    content = build_deal_alert_content(
        subject="40% off",
        message_date="2026-06-29T09:00:00-04:00",
        discount=40,
        links=[],
        message_id="abc123",
    )

    assert content.subject == "Nutricost 40% deal"
    assert content.body == (
        "Nutricost deal found.\n\n"
        "Discount detected: 40%\n"
        "Original subject: 40% off\n"
        "Original date: 2026-06-29T09:00:00-04:00\n"
        "Gmail message ID: abc123\n\n"
        "Links:\n"
        "- No deal link found in the message body.\n"
    )


def test_process_message_trashes_below_threshold_marketing_message():
    day = dt.date(2026, 6, 29)
    service = _Service({
        "low-deal": _nutricost_message(
            dt.datetime(2026, 6, 29, 9, 0, tzinfo=NY),
            "15% off",
            snippet="15% off today",
        )
    })

    outcome = nutricost_deal_monitor.process_message(
        service,
        "low-deal",
        day,
        threshold=30,
        dry_run=False,
        state={},
    )

    assert outcome == "trashed"
    assert service.trashed == ["low-deal"]


def test_process_message_dry_run_alert_does_not_mutate_state_or_trash():
    day = dt.date(2026, 6, 29)
    state = {"alerted_message_ids": []}
    service = _Service({
        "high-deal": _nutricost_message(
            dt.datetime(2026, 6, 29, 9, 0, tzinfo=NY),
            "40% off",
            snippet="40% off https://www.nutricost.com/products/creatine",
        )
    })

    outcome = nutricost_deal_monitor.process_message(
        service,
        "high-deal",
        day,
        threshold=30,
        dry_run=True,
        state=state,
    )

    assert outcome == "would_alert"
    assert service.trashed == []
    assert state == {"alerted_message_ids": []}


def test_process_message_suppresses_same_deal_alerted_within_three_days(monkeypatch):
    day = dt.date(2026, 6, 29)
    now = dt.datetime(2026, 6, 30, 9, 0, tzinfo=NY)
    state = default_monitor_state()
    record_deal_alert(
        state,
        message_id="prior-deal",
        key=deal_key(40, "40% off"),
        alerted_at=now - dt.timedelta(days=2, hours=23),
    )
    service = _Service({
        "same-deal": _nutricost_message(
            dt.datetime(2026, 6, 29, 9, 0, tzinfo=NY),
            "40% off",
            snippet="40% off https://www.nutricost.com/products/creatine",
        )
    })
    monkeypatch.setattr(nutricost_deal_monitor, "send_deal_alert", lambda **kwargs: None)

    outcome = nutricost_deal_monitor.process_message(
        service,
        "same-deal",
        day,
        threshold=35,
        dry_run=False,
        state=state,
        now=now,
    )

    assert outcome == "duplicate_deal"
    assert service.trashed == []
    assert state["alerted_message_ids"] == ["prior-deal"]


def test_parse_args_defaults_nutricost_alert_threshold_to_35(monkeypatch):
    monkeypatch.setattr("sys.argv", ["nutricost_deal_monitor.py"])

    assert nutricost_deal_monitor.parse_args().threshold == 35


def test_count_nutricost_messages_uses_threshold_state_and_failure_outcome():
    day = dt.date(2026, 6, 29)
    state = {"alerted_message_ids": []}
    service = _Service({
        "low-deal": _nutricost_message(
            dt.datetime(2026, 6, 29, 9, 0, tzinfo=NY),
            "15% off",
            snippet="15% off today",
        ),
        "high-deal": _nutricost_message(
            dt.datetime(2026, 6, 29, 9, 0, tzinfo=NY),
            "40% off",
            snippet="40% off https://www.nutricost.com/products/creatine",
        ),
    })
    failures = []

    counts = nutricost_deal_monitor.count_nutricost_messages(
        service,
        ["low-deal", "high-deal", "missing"],
        day,
        threshold=30,
        dry_run=True,
        state=state,
        log_failure=lambda message_id, exc: failures.append((message_id, type(exc).__name__)),
    )

    assert counts == {"would_trash": 1, "would_alert": 1, "failed": 1}
    assert failures == [("missing", "KeyError")]
    assert service.trashed == []
    assert state == {"alerted_message_ids": []}
