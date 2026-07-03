from jane_web.jane_v2.body_message_updates import append_body_message, prepend_body_message
from jane_web.jane_v2.pipeline import _copy_body_with_appended_message, _copy_body_with_prepended_message


class CopyBody:
    def __init__(self, message):
        self.message = message

    def copy(self, update):
        clone = CopyBody(self.message)
        clone.message = update["message"]
        return clone


class MutableBody:
    def __init__(self, message):
        self.message = message


def test_copy_body_with_appended_message_uses_existing_body_when_extra_empty():
    body = MutableBody("hello")

    assert _copy_body_with_appended_message is append_body_message
    assert _copy_body_with_prepended_message is prepend_body_message
    assert _copy_body_with_appended_message(body, "") is body


def test_copy_body_with_appended_message_preserves_copy_fallback():
    body = CopyBody("hello")

    copied = _copy_body_with_appended_message(body, " world")

    assert copied is not body
    assert copied.message == "hello world"
    assert body.message == "hello"


def test_copy_body_with_appended_message_mutates_when_no_copy_api_exists():
    body = MutableBody("hello")

    copied = _copy_body_with_appended_message(body, " world")

    assert copied is body
    assert body.message == "hello world"


def test_copy_body_with_prepended_message_adds_separator_only_when_needed():
    body = MutableBody("body")

    copied = _copy_body_with_prepended_message(body, "prefix")

    assert copied.message == "prefix\n\nbody"


def test_copy_body_with_prepended_message_preserves_double_newline_suffix():
    body = MutableBody("body")

    copied = _copy_body_with_prepended_message(body, "prefix\n\n")

    assert copied.message == "prefix\n\nbody"
