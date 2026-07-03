import datetime as dt
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_skills import facebook_marketplace_message_cleanup as cleanup  # noqa: E402
from agent_skills.facebook_marketplace_rules import (  # noqa: E402
    Conversation,
    classify_conversation,
    classify_conversations,
    conversation_from_row,
    is_protected_title,
    parse_relative_age_days,
    select_delete_candidates,
)


def test_cleanup_script_reexports_classification_rules():
    assert cleanup.Conversation is Conversation
    assert cleanup.classify_conversation is classify_conversation
    assert cleanup.conversation_from_row is conversation_from_row
    assert cleanup.classify_conversations is classify_conversations
    assert cleanup.select_delete_candidates is select_delete_candidates


def test_conversation_from_row_cleans_text_extracts_title_and_age():
    conversation = conversation_from_row({
        "href": "/messages/t/123/",
        "label": "Group chat: Buyer \u00b7 Bike",
        "text": "Buyer \u00a0\u00a0 Bike  \u00b7  4d",
    })

    assert conversation == Conversation(
        href="/messages/t/123/",
        title="Buyer \u00b7 Bike",
        raw_text="Buyer Bike \u00b7 4d",
        label="Group chat: Buyer \u00b7 Bike",
        age_days=4,
    )
    assert conversation_from_row({"href": "", "label": "Missing href"}) is None
    assert conversation_from_row({"href": "/messages/t/1/", "label": "", "text": ""}) is None


def test_protected_honda_fit_title_matches_colon_and_middle_dot_variants():
    assert is_protected_title(
        "Rickey \u00b7 2015 Honda Fit",
        ["Rickey : 2015 Honda Fit"],
    )
    assert is_protected_title(
        "Group chat: Rickey : 2015 Honda Fit",
        ["Rickey \u00b7 2015 Honda Fit"],
    )


def test_parse_relative_age_days_from_facebook_labels():
    now = dt.datetime(2026, 6, 30, 12, 0)

    assert parse_relative_age_days("Buyer: ok  \u00b7  4d", now=now) == 4
    assert parse_relative_age_days("You: yea  \u00b7  1w", now=now) == 7
    assert parse_relative_age_days("New message  \u00b7  13m", now=now) == 0
    assert parse_relative_age_days("Jun 25", now=now) == 5
    assert parse_relative_age_days("Sat", now=now) == 3


def test_sold_signal_deletes_but_sold_question_does_not():
    sold = Conversation(
        href="/messages/t/1/",
        title="Eddy \u00b7 2021 Honda HR-V",
        raw_text="Eddy sold 2021 Honda HR-V.",
    )
    question = Conversation(
        href="/messages/t/2/",
        title="Buyer \u00b7 Bike",
        raw_text="Is this sold?",
    )

    assert classify_conversation(sold, keep_titles=[]).reason == "sold_or_gone_signal"
    assert classify_conversation(question, keep_titles=[]).action == "keep"


def test_stale_conversations_delete_after_threshold():
    stale = Conversation(
        href="/messages/t/1/",
        title="James \u00b7 Camping and back up battery",
        raw_text="You: I bought a bigger battery  \u00b7  4d",
        age_days=4,
    )
    recent = Conversation(
        href="/messages/t/2/",
        title="Buyer \u00b7 Camping and back up battery",
        raw_text="Buyer: still available?  \u00b7  1d",
        age_days=1,
    )

    assert classify_conversation(stale, keep_titles=[], stale_days=3).action == "delete"
    assert classify_conversation(recent, keep_titles=[], stale_days=3).action == "keep"


def test_protected_title_wins_over_sold_and_stale_signals():
    protected = Conversation(
        href="/messages/t/3/",
        title="Rickey \u00b7 2015 Honda Fit",
        raw_text="Rickey sold 2015 Honda Fit.  \u00b7  1w",
        age_days=7,
    )

    decision = classify_conversation(
        protected,
        keep_titles=["Rickey : 2015 Honda Fit"],
        stale_days=3,
    )

    assert decision.action == "keep"
    assert decision.reason == "protected_title"


def test_classify_conversations_and_select_delete_candidates_preserve_order_and_limit():
    protected = Conversation(
        href="/messages/t/1/",
        title="Rickey \u00b7 2015 Honda Fit",
        raw_text="Rickey sold 2015 Honda Fit.  \u00b7  1w",
        age_days=7,
    )
    stale = Conversation(
        href="/messages/t/2/",
        title="Buyer \u00b7 Bike",
        raw_text="Buyer: ok  \u00b7  4d",
        age_days=4,
    )
    sold = Conversation(
        href="/messages/t/3/",
        title="Eddy \u00b7 2021 Honda HR-V",
        raw_text="Eddy sold 2021 Honda HR-V.",
    )

    classified = classify_conversations(
        [protected, stale, sold],
        keep_titles=["Rickey : 2015 Honda Fit"],
        stale_days=3,
    )

    assert [decision.reason for _conversation, decision in classified] == [
        "protected_title",
        "stale_4d",
        "sold_or_gone_signal",
    ]
    assert select_delete_candidates(classified, max_delete=1) == [classified[1]]
    assert select_delete_candidates(classified, max_delete=0) == []
