from __future__ import annotations

from jane_web.jane_v2.classes.clinic_schedules_info import handler


def test_patient_index_forces_patient_detail_and_uses_requested_day(monkeypatch):
    monkeypatch.setattr(handler, "_current_week_start", lambda: "2026-04-27")
    monkeypatch.setattr(
        handler,
        "_now_meta",
        lambda: {"today": "Monday", "current_time": "9:20 AM"},
    )

    def fake_fetch_day_rows(week_start: str, day: str):
        assert week_start == "2026-04-27"
        assert day == "Tuesday"
        return [
            {
                "name": "Kamal Ahmed (matha)",
                "time": "8:00am",
                "db_time": "8:00a",
                "status": "scheduled",
                "health_concerns": "",
                "recommendations": "",
                "visit_summary": "",
            },
            {
                "name": "Second Patient",
                "time": "9:00am",
                "db_time": "9:00a",
                "status": "scheduled",
                "health_concerns": "concern",
                "recommendations": "recommendation",
                "visit_summary": "summary",
            },
        ]

    monkeypatch.setattr(handler, "_fetch_day_rows", fake_fetch_day_rows)

    facts = handler._build_facts(
        {
            "loader": "next_patient",
            "day": "Tuesday",
            "patient_name": None,
            "patient_index": 1,
        }
    )

    assert facts["loader"] == "patient_detail"
    assert facts["patient"] == {
        "name": "Kamal Ahmed (matha)",
        "day": "Tuesday",
        "time": "8:00am",
        "index": 1,
        "health_concerns": "",
        "recommendations": "",
        "visit_summary": "",
    }
