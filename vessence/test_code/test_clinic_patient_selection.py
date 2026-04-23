"""Regression tests for clinic patient-selection follow-ups."""

from __future__ import annotations

import asyncio

from jane_web.jane_v2.classes.clinic_schedules_info import handler


def test_patient_selection_uses_semantic_fallback(monkeypatch):
    calls: list[str] = []

    async def fake_semantic_selection_id(prompt, patient_list):
        calls.append(prompt)
        return 1

    def fake_patient_detail(prompt, patient_name, appointment_time=None):
        return {
            "text": f"selected {patient_name} at {appointment_time}",
        }

    monkeypatch.setattr(handler, "_semantic_selection_id", fake_semantic_selection_id)
    monkeypatch.setattr(handler, "_patient_detail", fake_patient_detail)

    pending = {
        "patient_list": [
            {"name": "Caile Hanlon", "time": "8:00am", "db_time": "8:00a"},
            {"name": "Julie Hannon", "time": "9:00am", "db_time": "9:00a"},
        ]
    }

    result = asyncio.run(handler._resume_patient_selection("yeah the first patient", pending))

    assert calls == ["yeah the first patient"]
    assert result == {"text": "selected Caile Hanlon at 8:00a"}


def test_patient_selection_keeps_deterministic_fast_path(monkeypatch):
    async def fail_semantic_selection_id(prompt, patient_list):
        raise AssertionError("semantic parser should not run for explicit IDs")

    def fake_patient_detail(prompt, patient_name, appointment_time=None):
        return {
            "text": f"selected {patient_name} at {appointment_time}",
        }

    monkeypatch.setattr(handler, "_semantic_selection_id", fail_semantic_selection_id)
    monkeypatch.setattr(handler, "_patient_detail", fake_patient_detail)

    pending = {
        "patient_list": [
            {"name": "Caile Hanlon", "time": "8:00am", "db_time": "8:00a"},
            {"name": "Julie Hannon", "time": "9:00am", "db_time": "9:00a"},
        ]
    }

    result = asyncio.run(handler._resume_patient_selection("patient 2", pending))

    assert result == {"text": "selected Julie Hannon at 9:00a"}


def test_patient_selection_keeps_visible_name_fast_path(monkeypatch):
    async def fail_semantic_selection_id(prompt, patient_list):
        raise AssertionError("semantic parser should not run for visible patient names")

    def fake_patient_detail(prompt, patient_name, appointment_time=None):
        return {
            "text": f"selected {patient_name} at {appointment_time}",
        }

    monkeypatch.setattr(handler, "_semantic_selection_id", fail_semantic_selection_id)
    monkeypatch.setattr(handler, "_patient_detail", fake_patient_detail)

    pending = {
        "patient_list": [
            {"name": "Caile Hanlon", "time": "8:00am", "db_time": "8:00a"},
            {"name": "Julie Hannon", "time": "9:00am", "db_time": "9:00a"},
        ]
    }

    result = asyncio.run(handler._resume_patient_selection("Caile Hanlon", pending))

    assert result == {"text": "selected Caile Hanlon at 8:00a"}


def test_another_patient_followup_accepts_ordinal_selection(monkeypatch):
    async def fake_semantic_selection_id(prompt, patient_list):
        assert prompt == "the fourth patient"
        return 4

    def fake_selection_cache_get(session_id):
        return [
            {"name": "Caile Hanlon", "time": "8:00am", "db_time": "8:00a"},
            {"name": "Mock Patient", "time": "8:30am", "db_time": "8:30a"},
            {"name": "Julie Hannon", "time": "9:00am", "db_time": "9:00a"},
            {"name": "Jenna Kauffman", "time": "9:30am", "db_time": "9:30a"},
        ]

    def fake_current_session_id():
        return "test-session"

    def fake_patient_detail(prompt, patient_name, appointment_time=None):
        return {
            "text": f"{prompt}|{patient_name}|{appointment_time}",
        }

    monkeypatch.setattr(handler, "_semantic_selection_id", fake_semantic_selection_id)
    monkeypatch.setattr(handler, "_selection_cache_get", fake_selection_cache_get)
    monkeypatch.setattr(handler, "_patient_detail", fake_patient_detail)
    monkeypatch.setattr(
        "jane_web.session_context.get_current_session_id",
        fake_current_session_id,
    )

    pending = {"last_detail_type": "Visit Summary"}
    result = asyncio.run(handler._resume_another_patient("the fourth patient", pending))

    assert result == {"text": "visit summary for jenna kauffman|Jenna Kauffman|9:30a"}


def test_patient_detail_prints_summary_once(monkeypatch):
    class FakeConn:
        def execute(self, *_args, **_kwargs):
            return self

        def fetchone(self):
            return ("2026-04-20",)

        def fetchall(self):
            return [("Mock Patient", "health", "recs", "summary body")]

        def close(self):
            pass

    monkeypatch.setattr(handler, "_db_conn", lambda: FakeConn())

    result = handler._patient_detail("visit summary for mock patient", "Mock Patient")

    assert result["text"] == (
        "I have printed the patient summary in the chat. "
        "Any other patients you want to know more about, or would you like me "
        "to read the full summary so you can hear it?"
    )
    assert result["print"] == "**Mock Patient — Visit Summary**\n\nsummary body"
    assert "summary body" not in result["text"]


def test_another_patient_followup_can_read_last_summary(monkeypatch):
    calls = []

    def fake_patient_detail(prompt, patient_name, appointment_time=None, *, speak_summary=False):
        calls.append((prompt, patient_name, appointment_time, speak_summary))
        return {"text": "spoken summary"}

    monkeypatch.setattr(handler, "_patient_detail", fake_patient_detail)

    pending = {
        "last_detail_type": "Visit Summary",
        "last_patient": "Mock Patient",
        "last_appointment_time": "8:30a",
    }

    result = asyncio.run(handler._resume_another_patient("read it out loud", pending))

    assert result == {"text": "spoken summary"}
    assert calls == [("visit summary for mock patient", "Mock Patient", "8:30a", True)]
