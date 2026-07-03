from jane_web.jane_v2 import pending_action_resolver
from jane_web.jane_v2.pending_action_resolution import resolve_pending_action_response


def test_pending_action_resolver_uses_extracted_resolution_helper():
    assert pending_action_resolver._resolve_pending_action_response is resolve_pending_action_response


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
