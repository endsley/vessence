from types import SimpleNamespace

from jane_web import task_offloader
from jane_web.task_offloader_context import automation_prompt_context


def test_task_offloader_uses_context_selection_helper():
    assert task_offloader._automation_prompt_context is automation_prompt_context


def test_automation_prompt_context_uses_transcript_when_available():
    prompt_text, system_prompt = automation_prompt_context(
        "raw message",
        SimpleNamespace(system_prompt="system", transcript="User: prior\nJane: done"),
    )

    assert prompt_text == "User: prior\nJane: done"
    assert system_prompt == "system"


def test_automation_prompt_context_falls_back_to_raw_message():
    prompt_text, system_prompt = automation_prompt_context(
        "raw message",
        SimpleNamespace(system_prompt=None, transcript=""),
    )

    assert prompt_text == "raw message"
    assert system_prompt == ""
