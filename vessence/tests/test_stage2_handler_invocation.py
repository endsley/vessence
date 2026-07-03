from jane_web.jane_v2 import stage2_dispatcher
from jane_web.jane_v2.stage2_handler_invocation import (
    accepted_handler_params,
    build_handler_kwargs,
)


def basic_handler(prompt):
    return {"text": prompt}


def context_pending_params_handler(prompt, *, context="", pending=None, params=None):
    return {"text": prompt, "context": context, "pending": pending, "params": params}


def pending_handler(prompt, *, pending=None):
    return {"text": prompt, "pending": pending}


def test_dispatcher_uses_extracted_handler_kwargs_helper() -> None:
    assert stage2_dispatcher._build_handler_kwargs is build_handler_kwargs


def test_accepted_handler_params_only_reports_supported_dispatch_kwargs() -> None:
    assert accepted_handler_params(basic_handler) == set()
    assert accepted_handler_params(context_pending_params_handler) == {
        "context",
        "pending",
        "params",
    }


def test_build_handler_kwargs_filters_by_signature_and_strips_internal_question() -> None:
    pending = {"awaiting": "category", "question": "Which category?"}
    params = {"day": "today"}

    kwargs = build_handler_kwargs(
        context_pending_params_handler,
        context="Recent turns",
        pending=pending,
        params=params,
    )

    assert kwargs == {
        "context": "Recent turns",
        "pending": {"awaiting": "category"},
        "params": params,
    }
    assert pending == {"awaiting": "category", "question": "Which category?"}


def test_build_handler_kwargs_preserves_pending_none_for_pending_handlers() -> None:
    assert build_handler_kwargs(
        pending_handler,
        context="ignored",
        pending=None,
        params={"ignored": True},
    ) == {"pending": None}


def test_build_handler_kwargs_returns_empty_for_uninspectable_handler() -> None:
    class Uninspectable:
        def __call__(self, prompt):
            return {"text": prompt}

        @property
        def __signature__(self):
            raise ValueError("no signature")

    assert build_handler_kwargs(
        Uninspectable(),
        context="ignored",
        pending={"x": 1},
        params={"y": 2},
    ) == {}
