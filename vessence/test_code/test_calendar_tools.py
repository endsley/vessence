"""Unit tests for agent_skills/calendar_tools.py

Mocks refresh_token_if_needed and the googleapiclient service so tests run
offline without valid Google credentials.
"""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/home/chieh/ambient/vessence")

from agent_skills import calendar_tools  # noqa: E402


def _token(scope: str) -> dict:
    return {
        "access_token": "AT",
        "refresh_token": "RT",
        "expires_at": 9999999999,
        "scope": scope,
        "user_id": "u@example.com",
    }


class ScopeValidationTest(unittest.TestCase):
    def test_rejects_missing_scope(self) -> None:
        with patch.object(calendar_tools, "refresh_token_if_needed",
                          return_value=_token("openid email profile")):
            with self.assertRaises(RuntimeError) as ctx:
                calendar_tools._service()
            self.assertIn("scope", str(ctx.exception).lower())

    def test_rejects_readonly_scope(self) -> None:
        with patch.object(calendar_tools, "refresh_token_if_needed",
                          return_value=_token(
                              "https://www.googleapis.com/auth/calendar.readonly")):
            with self.assertRaises(RuntimeError):
                calendar_tools._service()

    def test_accepts_events_scope(self) -> None:
        with patch.object(calendar_tools, "refresh_token_if_needed",
                          return_value=_token(
                              "https://www.googleapis.com/auth/calendar.events")), \
             patch.object(calendar_tools, "build", return_value=MagicMock()):
            svc = calendar_tools._service()
            self.assertIsNotNone(svc)

    def test_accepts_full_calendar_scope(self) -> None:
        with patch.object(calendar_tools, "refresh_token_if_needed",
                          return_value=_token(
                              "openid https://www.googleapis.com/auth/calendar")), \
             patch.object(calendar_tools, "build", return_value=MagicMock()):
            self.assertIsNotNone(calendar_tools._service())

    def test_no_token_raises(self) -> None:
        with patch.object(calendar_tools, "refresh_token_if_needed",
                          return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                calendar_tools._service()
            self.assertIn("sign in", str(ctx.exception).lower())


def _svc_with(method_chain_return: dict | list) -> MagicMock:
    """Build a fake Calendar service where events().<anything>().execute()
    returns the given value."""
    svc = MagicMock()
    events = svc.events.return_value
    for call in ("list", "insert", "patch", "delete", "quickAdd"):
        getattr(events, call).return_value.execute.return_value = method_chain_return
    return svc


class CreateEventTest(unittest.TestCase):
    def _patched_service(self, return_value):
        svc = _svc_with(return_value)
        return patch.object(calendar_tools, "_service", return_value=svc), svc

    def test_happy_path(self) -> None:
        fake_event = {
            "id": "evt_123",
            "summary": "Dinner",
            "start": {"dateTime": "2026-04-15T19:00:00-04:00"},
            "end": {"dateTime": "2026-04-15T20:00:00-04:00"},
            "htmlLink": "http://cal.example/evt_123",
        }
        p, svc = self._patched_service(fake_event)
        with p:
            out = calendar_tools.create_event(
                "Dinner",
                "2026-04-15T19:00:00-04:00",
                "2026-04-15T20:00:00-04:00",
            )
            self.assertEqual(out["id"], "evt_123")
            self.assertEqual(out["summary"], "Dinner")
            svc.events.return_value.insert.assert_called_once()
            body = svc.events.return_value.insert.call_args.kwargs["body"]
            self.assertEqual(body["summary"], "Dinner")
            self.assertEqual(body["start"]["dateTime"],
                             "2026-04-15T19:00:00-04:00")
            self.assertNotIn("reminders", body)

    def test_reminders_too_many(self) -> None:
        p, _ = self._patched_service({})
        with p, self.assertRaises(ValueError) as ctx:
            calendar_tools.create_event(
                "x", "2026-04-15T10:00:00-04:00", "2026-04-15T11:00:00-04:00",
                reminders_minutes=[1, 2, 3, 4, 5, 6],
            )
        self.assertIn("5", str(ctx.exception))

    def test_reminders_negative(self) -> None:
        p, _ = self._patched_service({})
        with p, self.assertRaises(ValueError):
            calendar_tools.create_event(
                "x", "2026-04-15T10:00:00-04:00", "2026-04-15T11:00:00-04:00",
                reminders_minutes=[-1],
            )

    def test_reminders_too_large(self) -> None:
        p, _ = self._patched_service({})
        with p, self.assertRaises(ValueError):
            calendar_tools.create_event(
                "x", "2026-04-15T10:00:00-04:00", "2026-04-15T11:00:00-04:00",
                reminders_minutes=[40321],
            )

    def test_reminders_non_int(self) -> None:
        p, _ = self._patched_service({})
        with p, self.assertRaises(ValueError):
            calendar_tools.create_event(
                "x", "2026-04-15T10:00:00-04:00", "2026-04-15T11:00:00-04:00",
                reminders_minutes=["30"],  # type: ignore[list-item]
            )

    def test_reminders_valid(self) -> None:
        fake = {"id": "e", "summary": "x",
                "start": {"dateTime": "a"}, "end": {"dateTime": "b"}}
        p, svc = self._patched_service(fake)
        with p:
            calendar_tools.create_event(
                "x", "2026-04-15T10:00:00-04:00", "2026-04-15T11:00:00-04:00",
                reminders_minutes=[10, 30, 60],
            )
            body = svc.events.return_value.insert.call_args.kwargs["body"]
            self.assertEqual(len(body["reminders"]["overrides"]), 3)
            self.assertFalse(body["reminders"]["useDefault"])


class UpdateEventTest(unittest.TestCase):
    def test_empty_patch_rejected(self) -> None:
        with patch.object(calendar_tools, "_service",
                          return_value=_svc_with({})), \
             self.assertRaises(ValueError) as ctx:
            calendar_tools.update_event("evt_123")
        self.assertIn("no fields", str(ctx.exception).lower())

    def test_single_field_update(self) -> None:
        fake = {"id": "evt_123", "summary": "New",
                "start": {"dateTime": "a"}, "end": {"dateTime": "b"}}
        svc = _svc_with(fake)
        with patch.object(calendar_tools, "_service", return_value=svc):
            out = calendar_tools.update_event("evt_123", summary="New")
            self.assertEqual(out["summary"], "New")
            body = svc.events.return_value.patch.call_args.kwargs["body"]
            self.assertEqual(body, {"summary": "New"})

    def test_multi_field_update(self) -> None:
        fake = {"id": "e", "summary": "s",
                "start": {"dateTime": "a"}, "end": {"dateTime": "b"}}
        svc = _svc_with(fake)
        with patch.object(calendar_tools, "_service", return_value=svc):
            calendar_tools.update_event(
                "e", summary="S", start_iso="2026-04-15T10:00:00-04:00",
                end_iso="2026-04-15T11:00:00-04:00",
                description="d",
            )
            body = svc.events.return_value.patch.call_args.kwargs["body"]
            self.assertEqual(set(body.keys()),
                             {"summary", "start", "end", "description"})


class ListEventsTest(unittest.TestCase):
    def test_returns_slim_dicts(self) -> None:
        svc = _svc_with({"items": [
            {"id": "1", "summary": "A",
             "start": {"dateTime": "2026-04-15T10:00:00-04:00"},
             "end": {"dateTime": "2026-04-15T11:00:00-04:00"},
             "htmlLink": "h1", "extra_field": "ignored"},
            {"id": "2", "summary": "B",
             "start": {"date": "2026-04-16"},  # all-day event
             "end": {"date": "2026-04-17"},
             "htmlLink": "h2"},
        ]})
        with patch.object(calendar_tools, "_service", return_value=svc):
            out = calendar_tools.list_events("2026-04-15T00:00:00-04:00")
            self.assertEqual(len(out), 2)
            self.assertEqual(out[0]["id"], "1")
            self.assertNotIn("extra_field", out[0])
            # all-day event falls back to "date"
            self.assertEqual(out[1]["start"], "2026-04-16")

    def test_passes_time_bounds(self) -> None:
        svc = _svc_with({"items": []})
        with patch.object(calendar_tools, "_service", return_value=svc):
            calendar_tools.list_events(
                "2026-04-15T00:00:00-04:00",
                "2026-04-16T00:00:00-04:00",
                max_results=5,
            )
            kwargs = svc.events.return_value.list.call_args.kwargs
            self.assertEqual(kwargs["timeMin"], "2026-04-15T00:00:00-04:00")
            self.assertEqual(kwargs["timeMax"], "2026-04-16T00:00:00-04:00")
            self.assertEqual(kwargs["maxResults"], 5)
            self.assertTrue(kwargs["singleEvents"])


class QuickAddTest(unittest.TestCase):
    def test_quick_add(self) -> None:
        fake = {"id": "qa1", "summary": "Dinner Saturday",
                "start": {"dateTime": "x"}, "end": {"dateTime": "y"}}
        svc = _svc_with(fake)
        with patch.object(calendar_tools, "_service", return_value=svc):
            out = calendar_tools.quick_add("Dinner Saturday 7pm")
            self.assertEqual(out["id"], "qa1")
            kwargs = svc.events.return_value.quickAdd.call_args.kwargs
            self.assertEqual(kwargs["text"], "Dinner Saturday 7pm")
            self.assertEqual(kwargs["calendarId"], "primary")


class DeleteEventTest(unittest.TestCase):
    def test_delete_returns_true(self) -> None:
        svc = _svc_with({})
        with patch.object(calendar_tools, "_service", return_value=svc):
            self.assertTrue(calendar_tools.delete_event("evt_123"))
            kwargs = svc.events.return_value.delete.call_args.kwargs
            self.assertEqual(kwargs["eventId"], "evt_123")
            self.assertEqual(kwargs["calendarId"], "primary")


class SlimHelperTest(unittest.TestCase):
    def test_handles_missing_fields(self) -> None:
        out = calendar_tools._slim({"id": "x"})
        self.assertEqual(out["id"], "x")
        self.assertEqual(out["summary"], "")
        self.assertIsNone(out["start"])
        self.assertIsNone(out["end"])

    def test_prefers_datetime_over_date(self) -> None:
        out = calendar_tools._slim({
            "id": "x",
            "start": {"dateTime": "DT", "date": "D"},
            "end": {"dateTime": "DT2", "date": "D2"},
        })
        self.assertEqual(out["start"], "DT")
        self.assertEqual(out["end"], "DT2")


class ManifestIntegrityTest(unittest.TestCase):
    """Make sure the Android manifest edits actually landed as intended."""

    MANIFEST = ("/home/chieh/ambient/vessence/android/app/src/main/"
                "AndroidManifest.xml")

    def setUp(self) -> None:
        with open(self.MANIFEST) as f:
            self.xml = f.read()

    def test_calendar_perms_declared(self) -> None:
        for perm in ("READ_CALENDAR", "WRITE_CALENDAR",
                     "USE_EXACT_ALARM", "SCHEDULE_EXACT_ALARM",
                     "RECEIVE_BOOT_COMPLETED"):
            with self.subTest(perm=perm):
                self.assertIn(f"android.permission.{perm}", self.xml)

    def test_timer_receiver_registered(self) -> None:
        self.assertIn(".tools.TimerFireReceiver", self.xml)
        self.assertIn("com.vessences.android.TIMER_FIRE", self.xml)

    def test_xml_parses(self) -> None:
        import xml.etree.ElementTree as ET
        # Raises on malformed XML.
        ET.parse(self.MANIFEST)


class OAuthScopeTest(unittest.TestCase):
    def test_calendar_scope_in_oauth_config(self) -> None:
        with open("/home/chieh/ambient/vessence/vault_web/oauth.py") as f:
            src = f.read()
        self.assertIn("auth/calendar.events", src)
        self.assertIn("auth/gmail.modify", src)  # didn't clobber gmail


if __name__ == "__main__":
    unittest.main(verbosity=2)
