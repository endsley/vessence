import asyncio

from jane_web.jane_v2.classes.delete_messages import handler
from jane_web.jane_v2.classes.message_guard_helpers import (
    contains_architecture_phrase,
)


def run(coro):
    return asyncio.run(coro)


def test_delete_messages_handler_uses_shared_architecture_guard() -> None:
    assert handler.contains_architecture_phrase is contains_architecture_phrase
    assert handler._ARCH_WORDS == (
        "architecture",
        "infrastructure",
        "pipeline",
        "handler",
        "classifier",
        "stage",
    )


def test_delete_messages_handler_rejects_architecture_prompts_and_escalates_deletes() -> None:
    assert run(handler.handle("show me the classifier pipeline")) == {"wrong_class": True}
    assert run(handler.handle("delete the spam texts")) is None
