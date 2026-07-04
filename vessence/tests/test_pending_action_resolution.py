from jane_web.jane_v2 import pending_action_resolver
from jane_web.jane_v2.pending_action_resolution import (
    _cancel_kind,
    _followup_pivot_kind,
    _pending_awaiting,
    _pending_data,
    _resolution,
    _send_message_confirmation_resolution,
    _send_message_draft_resolution,
    _stage2_followup_resolution,
    _stage3_followup_resolution,
    resolve_pending_action_response,
)


def test_pending_action_resolver_uses_extracted_resolution_helper():
    assert pending_action_resolver._resolve_pending_action_response is resolve_pending_action_response


def test_pending_action_resolver_blank_reply_guard_preserves_stt_debounce_rule():
    assert pending_action_resolver._is_blank_pending_reply("")
    assert pending_action_resolver._is_blank_pending_reply(" ")
    assert pending_action_resolver._is_blank_pending_reply("a")
    assert not pending_action_resolver._is_blank_pending_reply("ok")


def test_pending_resolution_helpers_preserve_common_payload_shape():
    pending = {"type": "STAGE2_FOLLOWUP", "data": {"awaiting": "duration"}}

    assert _resolution("followup", pending, "turn", handler_class="timer") == {
        "action": "followup",
        "handler_class": "timer",
        "pending": pending,
        "pending_turn_id": "turn",
    }
    assert _pending_data(pending) == {"awaiting": "duration"}
    assert _pending_data({"data": "bad"}) == {}
    assert _pending_awaiting(pending) == "duration"
    assert _pending_awaiting({"awaiting": "category", "data": "bad"}) == "category"


def test_followup_pivot_kind_preserves_followup_only_interrupt_routing():
    assert _followup_pivot_kind("STAGE2_FOLLOWUP", "what time is it") == "high_precision_interrupt"
    assert _followup_pivot_kind("STAGE3_FOLLOWUP", "no, different issue") == "topic_pivot"
    assert _followup_pivot_kind("SEND_MESSAGE_CONFIRMATION", "what time is it") is None
    assert _followup_pivot_kind("STAGE2_FOLLOWUP", "the answer is blue") is None


def test_cancel_kind_preserves_soft_strong_and_global_cancel_routing():
    assert _cancel_kind("STAGE3_FOLLOWUP", "no") == "soft_ignored"
    assert _cancel_kind("SEND_MESSAGE_DRAFT_OPEN", "no") == "soft_ignored"
    assert _cancel_kind("STAGE3_FOLLOWUP", "cancel that") == "strong_cancel"
    assert _cancel_kind("STAGE2_FOLLOWUP", "no") == "global_cancel"
    assert _cancel_kind("SEND_MESSAGE_CONFIRMATION", "maybe") is None


def test_pending_type_resolution_helpers_preserve_action_payloads():
    confirmation = {"type": "SEND_MESSAGE_CONFIRMATION"}
    draft = {"type": "SEND_MESSAGE_DRAFT_OPEN"}
    stage3 = {"type": "STAGE3_FOLLOWUP", "awaiting": "details", "data": {"topic": "x"}}
    stage2 = {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "timer",
        "data": {"awaiting": "duration"},
    }

    assert _send_message_confirmation_resolution(confirmation, "yes", "t1") == {
        "action": "confirm",
        "pending": confirmation,
        "pending_turn_id": "t1",
    }
    assert _send_message_confirmation_resolution(confirmation, "maybe", "t1") is None
    assert _send_message_draft_resolution(draft, "send it", "t2") == {
        "action": "sms_draft_send",
        "pending": draft,
        "pending_turn_id": "t2",
    }
    assert _send_message_draft_resolution(draft, "make it shorter", "t2") == {
        "action": "sms_draft_edit",
        "pending": draft,
        "pending_turn_id": "t2",
    }
    assert _stage3_followup_resolution(stage3, "t3") == {
        "action": "stage3_followup",
        "pending": stage3,
        "pending_data": {"topic": "x"},
        "pending_turn_id": "t3",
    }
    assert _stage2_followup_resolution(stage2, "t4") == {
        "action": "followup",
        "handler_class": "timer",
        "pending": stage2,
        "pending_data": {"awaiting": "duration"},
        "pending_turn_id": "t4",
    }
    assert _stage2_followup_resolution({"type": "STAGE2_FOLLOWUP"}, "t5") is None


def test_followup_interrupts_and_topic_pivots_return_pivot_action():
    pending = {"type": "STAGE2_FOLLOWUP", "data": {"awaiting": "duration"}}

    assert resolve_pending_action_response(pending, "what time is it", "turn-1") == {
        "action": "pivot",
        "pending": pending,
        "pending_turn_id": "turn-1",
    }
    assert resolve_pending_action_response(pending, "no, different issue", "turn-1") == {
        "action": "pivot",
        "pending": pending,
        "pending_turn_id": "turn-1",
    }


def test_cancel_strength_preserves_stage3_and_draft_semantics():
    stage3 = {"type": "STAGE3_FOLLOWUP", "awaiting": "details", "data": {"x": 1}}
    draft = {"type": "SEND_MESSAGE_DRAFT_OPEN"}
    stage2 = {"type": "STAGE2_FOLLOWUP", "handler_class": "timer"}

    assert resolve_pending_action_response(stage3, "no", "t1") == {
        "action": "stage3_followup",
        "pending": stage3,
        "pending_data": {"x": 1},
        "pending_turn_id": "t1",
    }
    assert resolve_pending_action_response(stage3, "cancel that", "t1") == {
        "action": "cancel",
        "pending": stage3,
        "pending_turn_id": "t1",
    }
    assert resolve_pending_action_response(draft, "no", "t2") is None
    assert resolve_pending_action_response(stage2, "no", "t3") == {
        "action": "cancel",
        "pending": stage2,
        "pending_turn_id": "t3",
    }


def test_sms_confirmation_and_draft_routing():
    confirmation = {"type": "SEND_MESSAGE_CONFIRMATION"}
    draft = {"type": "SEND_MESSAGE_DRAFT_OPEN"}

    assert resolve_pending_action_response(confirmation, "yes", "turn") == {
        "action": "confirm",
        "pending": confirmation,
        "pending_turn_id": "turn",
    }
    assert resolve_pending_action_response(confirmation, "maybe", "turn") is None
    assert resolve_pending_action_response(draft, "send it please", "turn") == {
        "action": "sms_draft_send",
        "pending": draft,
        "pending_turn_id": "turn",
    }
    assert resolve_pending_action_response(draft, "actually make it shorter", "turn") == {
        "action": "sms_draft_edit",
        "pending": draft,
        "pending_turn_id": "turn",
    }


def test_stage2_and_stage3_followup_payloads():
    stage3 = {"type": "STAGE3_FOLLOWUP", "awaiting": "details", "data": {"topic": "x"}}
    stage2 = {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "todo_list",
        "data": {"awaiting": "category"},
    }

    assert resolve_pending_action_response(stage3, "the answer", "turn-3") == {
        "action": "stage3_followup",
        "pending": stage3,
        "pending_data": {"topic": "x"},
        "pending_turn_id": "turn-3",
    }
    assert resolve_pending_action_response(stage2, "personal", "turn-4") == {
        "action": "followup",
        "handler_class": "todo_list",
        "pending": stage2,
        "pending_data": {"awaiting": "category"},
        "pending_turn_id": "turn-4",
    }
    assert resolve_pending_action_response({"type": "STAGE2_FOLLOWUP"}, "personal") is None


def test_stage_followup_malformed_data_falls_back_to_empty_pending_data():
    stage3 = {"type": "STAGE3_FOLLOWUP", "data": "bad"}
    stage2 = {"type": "STAGE2_FOLLOWUP", "handler_class": "timer", "data": "bad"}

    assert resolve_pending_action_response(stage3, "answer", "t1")["pending_data"] == {}
    assert resolve_pending_action_response(stage2, "answer", "t2")["pending_data"] == {}
