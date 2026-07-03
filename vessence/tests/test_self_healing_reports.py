from types import SimpleNamespace

from jane_web.self_healing_reports import normalize_self_healing_report, self_healing_report_authorized


def _request(headers=None):
    return SimpleNamespace(headers=headers or {})


def test_self_healing_report_authorized_allows_local_requests_without_token():
    assert self_healing_report_authorized(
        _request(),
        expected_token="",
        is_local_request_fn=lambda request: True,
    )


def test_self_healing_report_authorized_requires_matching_token_for_external_requests():
    assert self_healing_report_authorized(
        _request({"x-jane-self-heal-token": "secret"}),
        expected_token=" secret ",
        is_local_request_fn=lambda request: False,
    )
    assert not self_healing_report_authorized(
        _request({"x-jane-self-heal-token": "wrong"}),
        expected_token="secret",
        is_local_request_fn=lambda request: False,
    )
    assert not self_healing_report_authorized(
        _request({"x-jane-self-heal-token": "secret"}),
        expected_token="",
        is_local_request_fn=lambda request: False,
    )


def test_normalize_self_healing_report_preserves_fields_and_truncates_message():
    payload = {"detail": "broken"}
    report = normalize_self_healing_report(
        {
            "source": "app",
            "category": "crash",
            "message": "x" * 2100,
            "project_root": "/repo",
            "tags": ["android"],
            "payload": payload,
        },
        default_project_root="/default",
    )

    assert report == {
        "source": "app",
        "category": "crash",
        "message": "x" * 2000,
        "project_root": "/repo",
        "tags": ["android"],
        "payload": payload,
    }


def test_normalize_self_healing_report_uses_defaults_and_body_as_payload():
    body = {"message": None, "tags": "not-a-list", "payload": "not-a-dict"}

    assert normalize_self_healing_report(body, default_project_root="/default") == {
        "source": "external_app",
        "category": "error",
        "message": "",
        "project_root": "/default",
        "tags": ["external"],
        "payload": body,
    }
