from jane_web.proxy_ack import pick_ack


def first(options):
    return options[0]


def test_pick_ack_question_category_has_priority_over_status_keywords():
    assert pick_ack("What is the current status?", chooser=first) == "Let me check."


def test_pick_ack_matches_core_action_categories_with_deterministic_chooser():
    assert pick_ack("status update please", chooser=first) == "Let me check on that."
    assert pick_ack("fix this failing job", chooser=first) == "On it — let me investigate."
    assert pick_ack("what do you recommend?", chooser=first) == "Let me check."
    assert pick_ack("please suggest a better option", chooser=first) == "Let me think about that."
    assert pick_ack("explain the cache", chooser=first) == "Sure, let me explain."
    assert pick_ack("hey Jane", chooser=first) == "Hey!"
    assert pick_ack("thanks for helping", chooser=first) == "Glad to help!"
    assert pick_ack("show me the report", chooser=first) == "Sure, pulling that up."
    assert pick_ack("implement the helper", chooser=first) == "On it."
    assert pick_ack("delete the stale file", chooser=first) == "Got it — cleaning that up."
    assert pick_ack("ugh it still fails", chooser=first) == "I hear you. Let me take another look."


def test_pick_ack_returns_none_for_uncategorized_messages():
    assert pick_ack("blue square moonlight", chooser=first) is None
