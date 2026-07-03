from jane_web.jane_v2 import stage1_classifier
from jane_web.jane_v2.stage1_prompt_cleaning import strip_stage1_system_markers


def test_stage1_classifier_uses_prompt_cleaning_helper():
    assert stage1_classifier._strip_system_markers is strip_stage1_system_markers


def test_strip_stage1_system_markers_removes_nested_tool_result_prefix():
    prompt = '[TOOL_RESULT:{"tool":"x","data":{"body":"hello"}}] what is the weather?'

    assert strip_stage1_system_markers(prompt) == "what is the weather?"


def test_strip_stage1_system_markers_removes_complete_sms_blocks():
    prompt = (
        "[SMS SEND REQUEST — Stage 2 could not resolve recipient]\n"
        '[[CLIENT_TOOL:contacts.sms_send_direct:{"phone_number":"<number>","body":"<message>"}]]\n'
        "[END SMS SEND REQUEST]\n"
        "tell Mia I am late"
    )

    assert strip_stage1_system_markers(prompt) == "tell Mia I am late"


def test_strip_stage1_system_markers_removes_truncated_tail_blocks():
    prompt = "tell Mia I am late\n[SMS SEND REQUEST missing end marker"

    assert strip_stage1_system_markers(prompt) == "tell Mia I am late"


def test_strip_stage1_system_markers_normalizes_subject_change_and_weather_plural():
    assert strip_stage1_system_markers("can we change the subject to weather") == "weather"
    assert strip_stage1_system_markers("show me the weathers") == "show me the weather"
