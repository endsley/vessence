import pytest

from agent_skills import check_continuation
from agent_skills.continuation_policy import (
    CONTINUE_PROMPT_TEXT,
    active_queue_not_empty_result,
    continue_job_result,
    idle_state_is_idle,
    no_pending_jobs_result,
    queue_payload_is_empty,
    user_active_result,
)


def test_check_continuation_uses_extracted_policy_helpers():
    assert check_continuation._queue_payload_is_empty is queue_payload_is_empty
    assert check_continuation._idle_state_is_idle is idle_state_is_idle
    assert check_continuation._active_queue_not_empty_result is active_queue_not_empty_result
    assert check_continuation._no_pending_jobs_result is no_pending_jobs_result
    assert check_continuation._user_active_result is user_active_result
    assert check_continuation._continue_job_result is continue_job_result


def test_queue_payload_is_empty_preserves_items_rule():
    assert queue_payload_is_empty({}) is True
    assert queue_payload_is_empty({"items": []}) is True
    assert queue_payload_is_empty({"items": ["one"]}) is False


def test_queue_payload_is_empty_preserves_non_dict_failure_behavior():
    with pytest.raises(AttributeError):
        queue_payload_is_empty([])


def test_idle_state_is_idle_uses_missing_timestamp_as_idle():
    assert idle_state_is_idle({}, now=1000, threshold_seconds=300)
    assert idle_state_is_idle({"last_active_ts": 0}, now=1000, threshold_seconds=300)
    assert idle_state_is_idle({"last_active_ts": 700}, now=1000, threshold_seconds=300)
    assert not idle_state_is_idle({"last_active_ts": 701}, now=1000, threshold_seconds=300)


def test_continuation_result_shapes_match_script_contract():
    assert active_queue_not_empty_result() == {
        "should_continue": False,
        "prompt_index": None,
        "prompt_text": None,
        "reason": "Active queue not empty",
    }
    assert no_pending_jobs_result() == {
        "should_continue": False,
        "prompt_index": None,
        "prompt_text": None,
        "reason": "No pending jobs",
    }
    assert user_active_result() == {
        "should_continue": False,
        "prompt_index": None,
        "prompt_text": None,
        "reason": "user is active",
    }
    assert CONTINUE_PROMPT_TEXT == "[new]\nrun job queue:"
    assert continue_job_result(7) == {
        "should_continue": True,
        "prompt_index": 7,
        "prompt_text": "[new]\nrun job queue:",
        "reason": "All conditions met",
    }
