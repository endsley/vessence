from jane_web.jane_v2.classes.timer import handler
from jane_web.jane_v2.classes.timer.intent_rules import (
    CANCEL_WORDS,
    COUNT_PHRASES,
    CREATE_TIMER_WORDS,
    CREATE_VERBS,
    LIST_WORDS,
    SET_TRIGGERS,
    STRICT_LIST_PHRASES,
    TIMER_NOUNS,
    has_timer_set_trigger,
    is_cancel_query,
    is_count_query,
    is_list_query,
    wants_timer_creation,
)
from jane_web.jane_v2.classes.timer.parsing import (
    extract_delete_target,
    extract_label,
    label_from_reply,
    looks_like_new_timer,
    parse_delete_phrase,
    parse_duration_ms,
    parse_followup_duration_ms,
    pretty_duration,
)
from jane_web.jane_v2.classes.timer.responses import (
    build_ask_duration_response,
    build_ask_label_response,
    build_cancel_response,
    build_count_response,
    build_delete_response,
    build_duration_retry_response,
    build_list_response,
    build_set_marker,
    build_set_response,
    delete_target_description,
    spoken_set_confirmation,
)


def test_timer_handler_uses_extracted_parsing_helpers():
    assert handler._parse_duration_ms is parse_duration_ms
    assert handler._parse_followup_duration_ms is parse_followup_duration_ms
    assert handler._CANCEL_WORDS is CANCEL_WORDS
    assert handler._LIST_WORDS is LIST_WORDS
    assert handler._COUNT_PHRASES is COUNT_PHRASES
    assert handler._TIMER_NOUNS is TIMER_NOUNS
    assert handler._STRICT_LIST_PHRASES is STRICT_LIST_PHRASES
    assert handler._CREATE_TIMER_WORDS is CREATE_TIMER_WORDS
    assert handler._CREATE_VERBS is CREATE_VERBS
    assert handler._SET_TRIGGERS is SET_TRIGGERS
    assert handler._is_count_query is is_count_query
    assert handler._is_cancel_query is is_cancel_query
    assert handler._is_list_query is is_list_query
    assert handler._wants_timer_creation is wants_timer_creation
    assert handler._has_timer_set_trigger is has_timer_set_trigger


def test_timer_legacy_intent_rules_preserve_inline_phrase_checks() -> None:
    assert is_count_query("how many timers do i have")
    assert is_cancel_query("cancel my timer")
    assert not is_cancel_query("cancel that")
    assert is_list_query("how much time is left on my timer")
    assert is_list_query("show me my timer")
    assert not is_list_query("show me my list")
    assert wants_timer_creation("start a countdown")
    assert wants_timer_creation("i need another")
    assert has_timer_set_trigger("ten minutes", "ten minutes")
    assert has_timer_set_trigger("let me know in ten minutes", "let me know in ten minutes")
    assert not has_timer_set_trigger(
        "let me rest for ten minutes",
        "let me rest for ten minutes",
    )
    assert handler._extract_label is extract_label
    assert handler._ask_duration is build_ask_duration_response
    assert handler._ask_label is build_ask_label_response


def test_parse_duration_ms_handles_common_timer_phrases():
    assert parse_duration_ms("half an hour") == 30 * 60 * 1000
    assert parse_duration_ms("2 and a half hours") == int(2.5 * 3600 * 1000)
    assert parse_duration_ms("one hour 30 minutes") == 90 * 60 * 1000
    assert parse_duration_ms("an hour") == 3600 * 1000
    assert parse_duration_ms("no duration here") == 0


def test_parse_followup_duration_ms_allows_bare_minutes() -> None:
    assert parse_followup_duration_ms("five") == 5 * 60 * 1000
    assert parse_followup_duration_ms("2.5") == int(2.5 * 60 * 1000)
    assert parse_followup_duration_ms("30 seconds") == 30 * 1000
    assert parse_followup_duration_ms("later") == 0


def test_extract_label_and_pretty_duration():
    assert extract_label("set a 5 minute pizza timer") == "pizza"
    assert extract_label("set a timer for the pasta") == "pasta"
    assert extract_label("set a timer to stretch") == "stretch"
    assert pretty_duration(45 * 1000) == "45 seconds"
    assert pretty_duration(90 * 1000) == "1 minute 30 sec"
    assert pretty_duration(90 * 60 * 1000) == "1 hour 30 minutes"


def test_delete_target_parsers_handle_id_index_label_and_all():
    assert extract_delete_target("delete timer 3") == {"id": 3}
    assert extract_delete_target("delete the third timer") == {"index": 3}
    assert extract_delete_target("delete the pasta timer") == {"label": "pasta"}
    assert extract_delete_target("delete all timers") is None

    assert parse_delete_phrase("timer #42") == {"id": 42}
    assert parse_delete_phrase("third") == {"index": 3}
    assert parse_delete_phrase("the oven timer") == {"label": "oven"}


def test_label_reply_and_new_timer_restart_detection():
    assert label_from_reply("no thanks") == ""
    assert label_from_reply("call it bread please") == "bread"
    assert looks_like_new_timer("set a 5 minute timer")
    assert not looks_like_new_timer("five minutes")


def test_timer_set_response_preserves_marker_spoken_text_and_resolution():
    response = build_set_response(5 * 60 * 1000, "pasta")

    assert build_set_marker(5 * 60 * 1000, "pasta") == (
        '[[CLIENT_TOOL:timer.set:{"duration_ms":300000,"label":"pasta"}]]'
    )
    assert spoken_set_confirmation(5 * 60 * 1000, "pasta") == (
        "Timer set — I'll let you know when the pasta is ready in 5 minutes."
    )
    assert response["text"] == (
        "Timer set — I'll let you know when the pasta is ready in 5 minutes. "
        '[[CLIENT_TOOL:timer.set:{"duration_ms":300000,"label":"pasta"}]]'
    )
    assert response["conversation_end"] is True
    assert response["structured"] == {
        "intent": "timer",
        "entities": {"action": "set", "duration_ms": 300000, "label": "pasta"},
    }

    followup = build_set_response(30 * 1000, "", from_followup=True)
    assert followup["text"] == (
        'Timer set for 30 seconds. [[CLIENT_TOOL:timer.set:{"duration_ms":30000,"label":""}]]'
    )
    assert followup["structured"]["pending_action"] == {
        "type": "STAGE2_FOLLOWUP",
        "handler_class": "timer",
        "status": "resolved",
    }


def test_timer_pending_question_responses_preserve_shapes():
    duration = build_ask_duration_response({"label": "tea"})
    pending = duration["structured"]["pending_action"]
    assert duration["text"] == "Sure — how long should the timer run?"
    assert pending["handler_class"] == "timer"
    assert pending["awaiting"] == "duration"
    assert pending["question"] == duration["text"]
    assert pending["data"] == {"label": "tea", "awaiting": "duration"}

    label = build_ask_label_response({"duration_ms": 90 * 1000})
    pending = label["structured"]["pending_action"]
    assert label["text"] == "Got it, 1 minute 30 sec. What should I call this timer? Or say 'no label'."
    assert label["structured"]["entities"] == {
        "action": "set",
        "stage": "await_label",
        "duration_ms": 90000,
    }
    assert pending["data"] == {"duration_ms": 90000, "awaiting": "label"}

    retry = build_duration_retry_response({})
    assert retry["text"] == "I didn't catch that. How long should the timer run? Like '5 minutes'."
    assert retry["structured"]["pending_action"]["awaiting"] == "duration"


def test_timer_simple_action_responses_preserve_markers_and_entities():
    assert build_count_response() == {
        "text": "Let me check. [[CLIENT_TOOL:timer.list:{}]]",
        "structured": {"intent": "timer", "entities": {"action": "count"}},
    }
    assert build_list_response() == {
        "text": "Checking your timers. [[CLIENT_TOOL:timer.list:{}]]",
        "structured": {"intent": "timer", "entities": {"action": "list"}},
    }
    assert build_cancel_response() == {
        "text": "Cancelling your timer. [[CLIENT_TOOL:timer.cancel:{}]]",
        "structured": {"intent": "timer", "entities": {"action": "cancel"}},
    }


def test_timer_delete_response_describes_target_and_preserves_marker():
    assert delete_target_description({"id": 7}) == "timer #7"
    assert delete_target_description({"label": "pasta"}) == "the pasta timer"
    assert delete_target_description({"index": 2}) == "the #2 timer"

    response = build_delete_response({"label": "pasta"})
    assert response == {
        "text": 'Deleting the pasta timer. [[CLIENT_TOOL:timer.delete:{"label":"pasta"}]]',
        "structured": {
            "intent": "timer",
            "entities": {"action": "delete", "label": "pasta"},
        },
    }
