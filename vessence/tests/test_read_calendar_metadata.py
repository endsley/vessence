from jane_web.jane_v2.classes.read_calendar import metadata


def test_calendar_metadata_event_and_block_formatting() -> None:
    assert metadata._format_event_line(
        1,
        {
            "summary": "Dentist",
            "start": "2026-07-02T09:00:00",
            "end": "2026-07-02T10:30:00",
        },
    ) == "1. Dentist — Thu Jul 2, 9:00am–10:30am"
    assert metadata._format_event_line(
        2,
        {"summary": "", "start": "2026-07-03", "description": "Bring card"},
    ) == "2. Untitled — 2026-07-03 (all day)"
    assert metadata._format_event_line(3, {"summary": "Loose event"}) == "3. Loose event"

    block = metadata._format_calendar_block(
        "[CALENDAR — today]",
        [{"summary": "Dentist", "start": "2026-07-03", "description": "Bring card"}],
    )
    assert block == (
        "[CALENDAR — today]\n"
        "1. Dentist — 2026-07-03 (all day)\n"
        "   Notes: Bring card\n"
        "[END]"
    )
    assert metadata._format_calendar_block("[CALENDAR — today]", []) == (
        "[CALENDAR — today]\nNothing scheduled.\n[END]"
    )


def test_calendar_bucket_block_formats_success_and_preserves_bucket_specs() -> None:
    calls = []

    def list_events_in_range(range_hint, *, max_results):
        calls.append((range_hint, max_results))
        return [{"summary": "Dentist", "start": "2026-07-03"}]

    block, creds_failed = metadata._calendar_bucket_block(
        list_events_in_range,
        label="[CALENDAR — today]",
        range_hint="today",
        max_results=25,
    )

    assert metadata.CALENDAR_BUCKETS == (
        ("[CALENDAR — today]", "today", 25),
        ("[CALENDAR — tomorrow]", "tomorrow", 25),
        ("[CALENDAR — next 90 days]", "next_90_days", 200),
    )
    assert calls == [("today", 25)]
    assert creds_failed is False
    assert "1. Dentist — 2026-07-03 (all day)" in block


def test_calendar_bucket_block_reports_credential_and_general_failures() -> None:
    def fail_runtime(*_args, **_kwargs):
        raise RuntimeError("missing token")

    def fail_general(*_args, **_kwargs):
        raise ValueError("api down")

    block, creds_failed = metadata._calendar_bucket_block(
        fail_runtime,
        label="[CALENDAR — today]",
        range_hint="today",
        max_results=25,
    )
    assert creds_failed is True
    assert "Google Calendar not set up: missing token" in block
    assert "sign in with Google" in block

    block, creds_failed = metadata._calendar_bucket_block(
        fail_general,
        label="[CALENDAR — tomorrow]",
        range_hint="tomorrow",
        max_results=25,
    )
    assert creds_failed is False
    assert block == "[CALENDAR — tomorrow]\nFetch failed: api down\n[END]"
