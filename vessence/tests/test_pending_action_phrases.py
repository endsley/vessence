from jane_web.jane_v2 import pending_action_resolver as resolver
from jane_web.jane_v2.pending_action_phrases import (
    STAGE3_CANCEL_STRONG,
    is_cancel,
    is_confirm,
    is_edit_intent,
    is_high_precision_interrupt,
    is_topic_pivot,
    normalize_reply,
)


def test_pending_action_resolver_reexports_phrase_helpers_for_existing_callers():
    assert resolver._normalize is normalize_reply
    assert resolver._is_confirm is is_confirm
    assert resolver._is_cancel is is_cancel
    assert resolver._is_edit_intent is is_edit_intent
    assert resolver._is_high_precision_interrupt is is_high_precision_interrupt
    assert resolver._is_topic_pivot is is_topic_pivot
    assert resolver._STAGE3_CANCEL_STRONG is STAGE3_CANCEL_STRONG


def test_confirm_cancel_and_edit_phrase_policy_preserves_precedence():
    assert normalize_reply(" Yes,  ") == "yes"
    assert is_confirm("send it please")
    assert is_cancel("don't send it")

    assert not is_edit_intent("yes")
    assert not is_edit_intent("no")
    assert is_edit_intent("make it shorter")
    assert is_edit_intent("actually say I will be late")


def test_pivot_and_interrupt_detectors_preserve_high_precision_cases():
    assert is_high_precision_interrupt("what time is it")
    assert is_high_precision_interrupt("tell mom hi")
    assert is_high_precision_interrupt("set a timer for five minutes")
    assert not is_high_precision_interrupt("five minutes")

    assert is_topic_pivot("no, different issue")
    assert is_topic_pivot("forget that, let's talk about another thing")
    assert not is_topic_pivot("no")
