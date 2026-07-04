from jane_web.jane_v2 import stage3_escalate
from jane_web.jane_v2.body_message_updates import copy_body_with_message as shared_copy_body_with_message
from jane_web.jane_v2.stage3_body_injections import (
    copy_body_with_message,
    inject_extracted_params,
    maybe_voice_wrap,
)
from jane_web.jane_v2.stage3_escalate import _copy_body_with_message, _inject_extracted_params, _maybe_voice_wrap


class FakeToolExtractor:
    def __init__(self):
        self.feed_calls = []
        self.flush_called = False

    def feed(self, text):
        self.feed_calls.append(text)
        return "visible", [{"name": "send_sms", "args": {"draft_id": "d1"}}]

    def flush(self):
        self.flush_called = True
        return "tail", [{"name": "timer", "args": {"seconds": 30}}]


class ModelCopyBody:
    def __init__(self, message, platform=None):
        self.message = message
        self.platform = platform

    def model_copy(self, update):
        clone = ModelCopyBody(self.message, self.platform)
        clone.message = update["message"]
        return clone


class CopyBody:
    def __init__(self, message, platform=None):
        self.message = message
        self.platform = platform

    def copy(self, update):
        clone = CopyBody(self.message, self.platform)
        clone.message = update["message"]
        return clone


def test_stage3_escalate_reexports_body_injection_helpers():
    assert copy_body_with_message is shared_copy_body_with_message
    assert stage3_escalate._copy_body_with_message is copy_body_with_message
    assert stage3_escalate._maybe_voice_wrap is maybe_voice_wrap
    assert stage3_escalate._inject_extracted_params is inject_extracted_params


def test_class_protocol_status_reports_loaded_missing_and_not_applicable(monkeypatch):
    monkeypatch.setattr(stage3_escalate, "_reason_to_class", lambda reason: None)
    assert stage3_escalate._class_protocol_status("others") == "n/a"

    monkeypatch.setattr(stage3_escalate, "_reason_to_class", lambda reason: "weather")
    monkeypatch.setattr(stage3_escalate, "_load_class_protocol", lambda class_name: "protocol")
    assert stage3_escalate._class_protocol_status("weather") == "loaded:weather"

    monkeypatch.setattr(stage3_escalate, "_load_class_protocol", lambda class_name: "")
    assert stage3_escalate._class_protocol_status("weather") == "missing:weather"


def test_copy_body_with_message_prefers_model_copy_without_mutating_original():
    body = ModelCopyBody("old")

    copied = _copy_body_with_message(body, "new")

    assert copied is not body
    assert copied.message == "new"
    assert body.message == "old"


def test_copy_body_with_message_preserves_copy_fallback():
    body = CopyBody("old")

    copied = _copy_body_with_message(body, "new")

    assert copied is not body
    assert copied.message == "new"
    assert body.message == "old"


def test_maybe_voice_wrap_only_wraps_voice_platform():
    body = ModelCopyBody("hello", platform="web")

    assert _maybe_voice_wrap(body) is body
    wrapped = _maybe_voice_wrap(ModelCopyBody("hello", platform="voice"))
    assert wrapped.message.endswith("hello")
    assert wrapped.message.startswith("(voice request")


def test_inject_extracted_params_filters_empty_values_and_prepends_block():
    body = ModelCopyBody("hello")

    injected = _inject_extracted_params(body, {"name": "Chieh", "empty": "", "none": None})

    assert injected.message.startswith("[EXTRACTED PARAMS]")
    assert "- name: 'Chieh'" in injected.message
    assert "empty" not in injected.message
    assert injected.message.endswith("\n\nhello")


def test_v1_ack_chunk_detection_preserves_existing_prefix_match():
    assert stage3_escalate._is_v1_ack_chunk('{"type": "ack", "data": "On it"}')
    assert stage3_escalate._is_v1_ack_chunk('{"type":"ack","data":"On it"}')
    assert not stage3_escalate._is_v1_ack_chunk('{"type": "model", "data": "qwen"}')


def test_stage3_delta_events_emit_tool_use_before_clean_delta():
    extractor = FakeToolExtractor()

    events = stage3_escalate._stage3_delta_events(
        {"type": "delta", "data": "raw", "meta": "keep"},
        extractor,
    )

    assert extractor.feed_calls == ["raw"]
    assert events == [
        '{"type": "tool_use", "data": "{\\"name\\": \\"send_sms\\", \\"args\\": {\\"draft_id\\": \\"d1\\"}}"}\n',
        '{"type": "delta", "data": "visible", "meta": "keep"}\n',
    ]


def test_stage3_delta_events_return_none_for_non_delta_payloads():
    assert stage3_escalate._stage3_delta_events({"type": "model", "data": "qwen"}, FakeToolExtractor()) is None
    assert stage3_escalate._stage3_delta_events({"type": "delta", "data": 1}, FakeToolExtractor()) is None


def test_stage3_tool_flush_events_emit_tool_use_before_tail_delta():
    extractor = FakeToolExtractor()

    events = stage3_escalate._stage3_tool_flush_events(extractor)

    assert extractor.flush_called
    assert events == [
        '{"type": "tool_use", "data": "{\\"name\\": \\"timer\\", \\"args\\": {\\"seconds\\": 30}}"}\n',
        '{"type": "delta", "data": "tail"}\n',
    ]
