from types import SimpleNamespace

import pytest

from jane_web.permission_helpers import (
    permission_pending_entry,
    permission_request_args,
    permission_response_args,
    permission_wait_payload,
)


def test_permission_request_args_preserve_required_indexing_and_defaults():
    assert permission_request_args(
        {
            "request_id": "r1",
            "tool_name": "shell",
        }
    ) == {
        "request_id": "r1",
        "tool_name": "shell",
        "tool_input": {},
        "session_id": "",
    }
    with pytest.raises(KeyError):
        permission_request_args({"request_id": "r1"})


def test_permission_response_args_preserve_defaults():
    assert permission_response_args({"request_id": "r1"}) == {
        "request_id": "r1",
        "approved": False,
        "reason": "",
    }
    assert permission_response_args({"request_id": "r1", "approved": "yes", "reason": "ok"}) == {
        "request_id": "r1",
        "approved": "yes",
        "reason": "ok",
    }


def test_permission_wait_and_pending_payload_shapes():
    request = SimpleNamespace(
        request_id="r1",
        tool_name="shell",
        tool_input={"cmd": "date"},
        created_at=123.0,
        reason="approved",
    )

    assert permission_wait_payload(True, request) == {"approved": True, "reason": "approved"}
    assert permission_pending_entry(request) == {
        "request_id": "r1",
        "tool_name": "shell",
        "tool_input": {"cmd": "date"},
        "created_at": 123.0,
    }
