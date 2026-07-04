import asyncio

from jane_web.jane_v2.classes.message_guard_helpers import (
    contains_architecture_phrase,
)
from jane_web.jane_v2.classes.read_messages import handler


def run(coro):
    return asyncio.run(coro)


def test_read_messages_guard_predicates_preserve_misclassification_rules() -> None:
    assert handler.contains_architecture_phrase is contains_architecture_phrase
    assert handler.contains_architecture_phrase("why is the classifier stage slow?")
    assert handler.contains_meta_self_reference("why did your last reply take so long?")
    assert handler.should_reject_read_messages_prompt("explain why your previous message was slow")
    assert not handler.should_reject_read_messages_prompt("read my latest texts from Mia")


def test_read_messages_handler_rejects_meta_prompts_and_escalates_real_reads() -> None:
    assert run(handler.handle("show me the handler architecture")) == {"wrong_class": True}
    assert run(handler.handle("why was your last message slow?")) == {"wrong_class": True}
    assert run(handler.handle("read my latest texts from Mia")) is None
