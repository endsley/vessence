from __future__ import annotations

import pytest

from agent_skills.web_ui_change import (
    ExtractionContractError,
    VESSENCE_HOME,
    recover_website_ui_change,
    require_record_values,
    require_extraction_values,
    suspected_ui_change,
)


def test_required_extraction_values_accepts_zero_and_false() -> None:
    require_extraction_values({"count": 0, "complete": False, "meta": {"url": "https://example.test"}}, ["count", "complete", "meta.url"])


def test_required_extraction_values_reports_all_missing_paths() -> None:
    with pytest.raises(ExtractionContractError) as caught:
        require_extraction_values({"meta": {"url": ""}, "rows": []}, ["meta.url", "rows", "missing"])
    assert caught.value.missing_paths == ("meta.url", "rows", "missing")


def test_record_contract_reports_only_structural_missing_field_paths() -> None:
    with pytest.raises(ExtractionContractError) as caught:
        require_record_values(
            [{"account": "kept-private", "amount": ""}],
            ["account", "amount", "date"],
            label="payment_history",
        )
    assert caught.value.missing_paths == ("payment_history[0].amount", "payment_history[0].date")


@pytest.mark.parametrize(
    "exc",
    [
        ExtractionContractError(["downloads"]),
        RuntimeError("Could not locate Download button"),
        RuntimeError("Could not locate sign-in password field"),
        RuntimeError("No ChatGPT Stripe invoice links were found in Billing history."),
        RuntimeError("locator timed out while waiting for the bill table"),
    ],
)
def test_suspected_ui_change_accepts_selector_failures(exc: BaseException) -> None:
    assert suspected_ui_change(exc)


@pytest.mark.parametrize(
    "message",
    [
        "Missing NATIONALGRID_PASSWORD in SecretStore",
        "MFA code required",
        "CAPTCHA challenge displayed",
        "connection refused by remote host",
    ],
)
def test_suspected_ui_change_excludes_non_ui_blockers(message: str) -> None:
    assert not suspected_ui_change(RuntimeError(message))


def test_recovery_captures_contract_and_intent_without_raw_error(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_capture_report(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return {"incident_path": "/tmp/website-ui-incident.json"}

    import agent_skills.self_healing as self_healing

    monkeypatch.setattr(self_healing, "capture_report", fake_capture_report)
    monkeypatch.setenv("JANE_WEB_UI_AUTO_REPAIR", "0")
    incident = recover_website_ui_change(
        skill="example-skill",
        intent="Read the current invoice total from the billing page.",
        operation="invoice extraction",
        exc=RuntimeError("Could not locate Invoice total selector"),
        project_root=VESSENCE_HOME,
        retry_safe=True,
    )

    assert incident is not None
    assert incident.reason == "selector_missing"
    assert captured["source"] == "website_ui_example-skill"
    assert captured["auto_repair"] is False
    assert captured["payload"]["intent"] == "Read the current invoice total from the billing page."
    assert "Could not locate" not in captured["message"]
