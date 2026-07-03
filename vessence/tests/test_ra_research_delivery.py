import datetime as dt

from agent_skills.ra_research_delivery import (
    app_report_message,
    build_email_report_body,
    build_app_report_payload,
    email_report_subject,
    mark_email_report_sent,
    mark_app_report_sent,
    normalize_report_channel,
    parse_iso_datetime,
    should_send_report,
)


NOW = dt.datetime(2026, 7, 2, 12, 0, tzinfo=dt.timezone.utc)


def test_parse_iso_datetime_normalizes_naive_and_aware_values():
    assert parse_iso_datetime(None) is None
    assert parse_iso_datetime("not a date") is None
    assert parse_iso_datetime("2026-07-02T12:00:00") == NOW
    assert parse_iso_datetime("2026-07-02T08:00:00-04:00") == NOW


def test_should_send_report_preserves_force_initial_and_interval_rules():
    assert should_send_report({}, True, now=NOW, initial_report_after_runs=4, report_interval_hours=72)
    assert not should_send_report(
        {"run_count": 3, "initial_report_sent": False},
        False,
        now=NOW,
        initial_report_after_runs=4,
        report_interval_hours=72,
    )
    assert should_send_report(
        {"run_count": 4, "initial_report_sent": False},
        False,
        now=NOW,
        initial_report_after_runs=4,
        report_interval_hours=72,
    )
    assert not should_send_report(
        {"run_count": 10, "initial_report_sent": True, "last_report_sent_at": "2026-07-01T12:00:00+00:00"},
        False,
        now=NOW,
        initial_report_after_runs=4,
        report_interval_hours=72,
    )
    assert should_send_report(
        {"run_count": 10, "initial_report_sent": True, "last_report_sent_at": "2026-06-28T12:00:00+00:00"},
        False,
        now=NOW,
        initial_report_after_runs=4,
        report_interval_hours=72,
    )
    assert should_send_report(
        {"run_count": 4, "initial_report_sent": True, "last_report_sent_at": "bad"},
        False,
        now=NOW,
        initial_report_after_runs=4,
        report_interval_hours=72,
    )


def test_app_report_payload_preserves_shape_and_message_pluralization():
    assert app_report_message(1, 8) == "1 new/upgraded source summary; 8 cached sources total. Tap to read the HTML report."
    assert app_report_message(2, 9) == "2 new/upgraded source summaries; 9 cached sources total. Tap to read the HTML report."

    payload = build_app_report_payload(
        report_id="20260702_120000",
        report_path="/vault/report.md",
        html_report_path="/vault/report.html",
        new_count=2,
        total_sources=9,
        created_at="2026-07-02T12:00:00+00:00",
    )

    assert payload == {
        "id": "ra_report_20260702_120000",
        "type": "report_ready",
        "report_kind": "ra_research",
        "title": "RA research update ready",
        "message": "2 new/upgraded source summaries; 9 cached sources total. Tap to read the HTML report.",
        "created_at": "2026-07-02T12:00:00+00:00",
        "timestamp": "2026-07-02T12:00:00+00:00",
        "final": True,
        "report_id": "20260702_120000",
        "report_url": "/api/research/ra/reports/20260702_120000.html",
        "web_url": "/research/ra/reports/20260702_120000",
        "markdown_path": "/vault/report.md",
        "html_path": "/vault/report.html",
        "new_sources": 2,
        "total_sources": 9,
    }


def test_normalize_report_channel_preserves_existing_aliases_and_defaults():
    assert normalize_report_channel("email") == "email"
    assert normalize_report_channel("GMAIL") == "email"
    assert normalize_report_channel("none") == "disabled"
    assert normalize_report_channel("off") == "disabled"
    assert normalize_report_channel("disabled") == "disabled"
    assert normalize_report_channel("") == "app"
    assert normalize_report_channel(None) == "app"
    assert normalize_report_channel("web") == "app"


def test_mark_app_report_sent_updates_existing_state_in_place():
    state = {"last_report_error": "old"}

    mark_app_report_sent(
        state,
        created_at="2026-07-02T12:00:00+00:00",
        total_sources=9,
        html_report_path="/vault/report.html",
    )

    assert state == {
        "last_report_sent_at": "2026-07-02T12:00:00+00:00",
        "last_report_source_count": 9,
        "initial_report_sent": True,
        "last_report_error": None,
        "last_report_channel": "app",
        "last_html_report_path": "/vault/report.html",
    }


def test_email_report_subject_and_body_preserve_snapshot_limits():
    body = build_email_report_body(
        processed_count=12,
        report_path="/vault/report.md",
        recommendation_path="/vault/scheme.md",
        action_plan_path="/vault/action.md",
        action_plan_text="A" * 12005,
        recommendation_text="R" * 6005,
    )

    assert email_report_subject("2026-07-02") == "RA research update: remission/asymptomatic evidence (2026-07-02)"
    assert body.startswith("Chieh,\n\nThe RA remission research cron is still running.")
    assert "It has processed and cached 12 sources so far." in body
    assert "Latest report:\n/vault/report.md" in body
    assert "Latest living recommendation scheme:\n/vault/scheme.md" in body
    assert "Latest action plan:\n/vault/action.md" in body
    assert ("A" * 12000) in body
    assert ("A" * 12001) not in body
    assert ("R" * 6000) in body
    assert ("R" * 6001) not in body
    assert body.endswith("Medication, supplement, or treatment changes should not be made from this report alone.")


def test_mark_email_report_sent_updates_state_without_channel_side_effects():
    state = {"last_report_error": "old", "last_report_channel": "email"}

    mark_email_report_sent(state, sent_at="2026-07-02T12:00:00+00:00", processed_count=12)

    assert state == {
        "last_report_error": None,
        "last_report_channel": "email",
        "last_report_sent_at": "2026-07-02T12:00:00+00:00",
        "last_report_source_count": 12,
        "initial_report_sent": True,
    }
