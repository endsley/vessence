import asyncio

from jane_web.jane_v2.classes.nationalgrid_bills import handler


def run(coro):
    return asyncio.run(coro)


def test_nationalgrid_bill_response_helpers_preserve_shapes(monkeypatch) -> None:
    monkeypatch.setattr(handler, "format_answer", lambda result: f"answer: {result['total']}")

    result = {"total": "$42.00"}
    assert handler.bill_fetch_success_response(result) == {
        "text": "answer: $42.00",
        "data": result,
    }
    assert handler.bill_fetch_error_response(RuntimeError("login failed")) == {
        "text": "I could not fetch the National Grid bills yet: login failed",
        "error": "login failed",
    }


def test_nationalgrid_handler_requires_year_before_fetch(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(handler, "infer_year", lambda prompt: None)
    monkeypatch.setattr(handler, "fetch_bills", lambda **kwargs: calls.append(kwargs))

    assert run(handler.handle("show my bills")) is None
    assert calls == []


def test_nationalgrid_handler_wraps_success_and_fetch_errors(monkeypatch) -> None:
    monkeypatch.setattr(handler, "infer_year", lambda prompt: 2026)
    monkeypatch.setattr(handler, "format_answer", lambda result: f"{result['year']} total")
    monkeypatch.setattr(handler, "fetch_bills", lambda **kwargs: {"year": kwargs["year"]})

    assert run(handler.handle("show my 2026 bills")) == {
        "text": "2026 total",
        "data": {"year": 2026},
    }

    def fail_fetch(**kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(handler, "fetch_bills", fail_fetch)
    assert run(handler.handle("show my 2026 bills")) == {
        "text": "I could not fetch the National Grid bills yet: network down",
        "error": "network down",
    }
