from types import SimpleNamespace

import pytest

from jane_web.web_automation_helpers import (
    automation_result_payload,
    web_plan_headless,
    web_plan_label,
    web_plan_profile_id,
    web_plan_raw_steps,
    web_plan_record_trace,
    web_plan_storage_state_path,
    web_plan_step_specs,
    web_profile_capture_values,
    web_profile_create_values,
    web_secret_create_values,
    web_secret_public_entry,
)


def test_web_plan_raw_steps_requires_non_empty_list():
    steps = [{"action": "snapshot"}]

    assert web_plan_raw_steps({"steps": steps}) is steps
    with pytest.raises(ValueError, match="'steps' must be a non-empty array"):
        web_plan_raw_steps({"steps": []})
    with pytest.raises(ValueError, match="'steps' must be a non-empty array"):
        web_plan_raw_steps({"steps": "navigate"})


def test_web_plan_step_specs_normalizes_action_args_and_confirm():
    assert web_plan_step_specs(
        [
            {"action": 123, "args": None, "confirm": 1},
            {"action": "click", "args": {"selector": "#go"}},
        ]
    ) == [
        {"action": "123", "args": {}, "confirm": True},
        {"action": "click", "args": {"selector": "#go"}, "confirm": False},
    ]


def test_web_plan_step_specs_reports_malformed_index():
    with pytest.raises(ValueError, match="step 1 malformed"):
        web_plan_step_specs([{"action": "snapshot"}, {"args": {}}])


def test_web_plan_options_preserve_route_coercion():
    assert web_plan_label({"label": "x" * 50}) == "x" * 40
    assert web_plan_label({}) == "adhoc"
    assert web_plan_headless({"headless": True}) is True
    assert web_plan_headless({"headless": "true"}) is None
    assert web_plan_record_trace({"record_trace": "yes"}) is True
    assert web_plan_profile_id({"profile_id": "  prof  "}) == "  prof  "
    assert web_plan_profile_id({"profile_id": "   "}) is None


def test_automation_result_payload_shape():
    result = SimpleNamespace(ok=True, run_id="run-1", summary="done", data={"x": 1})

    assert automation_result_payload(result) == {
        "ok": True,
        "run_id": "run-1",
        "summary": "done",
        "data": {"x": 1},
    }


def test_web_plan_storage_state_path_checks_every_navigate_step_and_touches_profile():
    class Profiles:
        def __init__(self):
            self.checked = []
            self.touched = []

        def bind_check(self, profile_id, url):
            self.checked.append((profile_id, url))

        def storage_state_path(self, profile_id):
            return f"/profiles/{profile_id}.json"

        def touch_last_used(self, profile_id):
            self.touched.append(profile_id)

    profiles = Profiles()
    steps = [
        SimpleNamespace(action="navigate", args={"url": "https://bank.example"}),
        SimpleNamespace(action="click", args={"selector": "#go"}),
        SimpleNamespace(action="navigate", args={"url": "https://bank.example/accounts"}),
    ]

    assert web_plan_storage_state_path("prof-1", steps, profiles) == "/profiles/prof-1.json"
    assert profiles.checked == [
        ("prof-1", "https://bank.example"),
        ("prof-1", "https://bank.example/accounts"),
    ]
    assert profiles.touched == ["prof-1"]
    assert web_plan_storage_state_path(None, steps, profiles) is None


def test_web_profile_create_values_strip_required_fields():
    assert web_profile_create_values({"display_name": "  Bank  ", "domain": "  bank.example  "}) == (
        "Bank",
        "bank.example",
    )
    assert web_profile_create_values({}) == ("", "")


def test_web_profile_capture_values_strip_urls_and_coerce_timeout():
    assert web_profile_capture_values(
        {
            "login_url": "  https://bank.example/login  ",
            "success_url_pattern": "  bank.example/dashboard  ",
            "timeout_s": "120",
        }
    ) == ("https://bank.example/login", "bank.example/dashboard", 120)
    assert web_profile_capture_values({}) == ("", "", 300)


def test_web_secret_create_values_strip_only_domain_and_label():
    assert web_secret_create_values(
        {
            "domain": "  bank.example  ",
            "label": "  Bank  ",
            "username": "  user  ",
            "password": "  pass  ",
            "notes": "  note  ",
        }
    ) == ("bank.example", "Bank", "  user  ", "  pass  ", "  note  ")
    assert web_secret_create_values({}) == ("", "", "", "", "")


def test_web_secret_public_entry_shape():
    entry = SimpleNamespace(
        secret_id="s1",
        domain="bank.example",
        label="Bank",
        created_at="2026-07-02",
        last_used=None,
    )

    assert web_secret_public_entry(entry) == {
        "secret_id": "s1",
        "domain": "bank.example",
        "label": "Bank",
        "created_at": "2026-07-02",
        "last_used": None,
    }
