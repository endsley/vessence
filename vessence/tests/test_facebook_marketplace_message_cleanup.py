import datetime as dt
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_skills import facebook_marketplace_message_cleanup as cleanup  # noqa: E402


def test_protected_honda_fit_title_matches_colon_and_middle_dot_variants():
    assert cleanup.is_protected_title(
        "Rickey \u00b7 2015 Honda Fit",
        ["Rickey : 2015 Honda Fit"],
    )
    assert cleanup.is_protected_title(
        "Group chat: Rickey : 2015 Honda Fit",
        ["Rickey \u00b7 2015 Honda Fit"],
    )


def test_parse_relative_age_days_from_facebook_labels():
    now = dt.datetime(2026, 6, 30, 12, 0)

    assert cleanup.parse_relative_age_days("Buyer: ok  \u00b7  4d", now=now) == 4
    assert cleanup.parse_relative_age_days("You: yea  \u00b7  1w", now=now) == 7
    assert cleanup.parse_relative_age_days("New message  \u00b7  13m", now=now) == 0
    assert cleanup.parse_relative_age_days("Jun 25", now=now) == 5
    assert cleanup.parse_relative_age_days("Sat", now=now) == 3


def test_sold_signal_deletes_but_sold_question_does_not():
    sold = cleanup.Conversation(
        href="/messages/t/1/",
        title="Eddy \u00b7 2021 Honda HR-V",
        raw_text="Eddy sold 2021 Honda HR-V.",
    )
    question = cleanup.Conversation(
        href="/messages/t/2/",
        title="Buyer \u00b7 Bike",
        raw_text="Is this sold?",
    )

    assert cleanup.classify_conversation(sold, keep_titles=[]).reason == "sold_or_gone_signal"
    assert cleanup.classify_conversation(question, keep_titles=[]).action == "keep"


def test_stale_conversations_delete_after_threshold():
    stale = cleanup.Conversation(
        href="/messages/t/1/",
        title="James \u00b7 Camping and back up battery",
        raw_text="You: I bought a bigger battery  \u00b7  4d",
        age_days=4,
    )
    recent = cleanup.Conversation(
        href="/messages/t/2/",
        title="Buyer \u00b7 Camping and back up battery",
        raw_text="Buyer: still available?  \u00b7  1d",
        age_days=1,
    )

    assert cleanup.classify_conversation(stale, keep_titles=[], stale_days=3).action == "delete"
    assert cleanup.classify_conversation(recent, keep_titles=[], stale_days=3).action == "keep"


def test_protected_title_wins_over_sold_and_stale_signals():
    protected = cleanup.Conversation(
        href="/messages/t/3/",
        title="Rickey \u00b7 2015 Honda Fit",
        raw_text="Rickey sold 2015 Honda Fit.  \u00b7  1w",
        age_days=7,
    )

    decision = cleanup.classify_conversation(
        protected,
        keep_titles=["Rickey : 2015 Honda Fit"],
        stale_days=3,
    )

    assert decision.action == "keep"
    assert decision.reason == "protected_title"
