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


def test_task_prompt_context_uses_built_context(monkeypatch):
    monkeypatch.setattr(
        task_offloader,
        "_automation_prompt_context",
        lambda message, ctx: (f"prompt:{message}:{ctx.transcript}", ctx.system_prompt),
    )

    prompt_text, system_prompt = task_offloader._task_prompt_context(
        "implement this",
        [{"role": "assistant", "content": "prior"}],
        "task-1",
        build_context_fn=lambda message, history: SimpleNamespace(
            system_prompt=f"system:{message}",
            transcript=f"history:{len(history)}",
        ),
    )

    assert prompt_text == "prompt:implement this:history:1"
    assert system_prompt == "system:implement this"


def test_task_prompt_context_falls_back_when_context_build_fails():
    def fail_build(_message, _history):
        raise RuntimeError("boom")

    assert task_offloader._task_prompt_context(
        "raw message",
        [{"role": "assistant", "content": "prior"}],
        "task-1",
        build_context_fn=fail_build,
    ) == ("raw message", "")


def test_task_progress_heartbeat_tracks_latest_delta_without_real_thread():
    starts = []
    writes = []

    class FakeThread:
        def __init__(self, *, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            starts.append((self.target, self.daemon))

    heartbeat = task_offloader._TaskProgressHeartbeat(
        "task-1",
        interval=99,
        write_progress_fn=lambda task_id, message: writes.append((task_id, message)),
        heartbeat_message_fn=lambda delta: f"latest:{delta}" if delta else None,
        thread_factory=FakeThread,
    )

    assert heartbeat._latest_message() is None
    heartbeat.on_progress("first chunk")
    assert heartbeat._latest_message() == "latest:first chunk"
    heartbeat.start()
    assert starts == [(heartbeat._loop, True)]
    heartbeat.stop()
    assert heartbeat._stop_event.is_set()

    class OneTickStop:
        def __init__(self):
            self.calls = 0

        def wait(self, _interval):
            self.calls += 1
            return self.calls > 1

    heartbeat._stop_event = OneTickStop()
    heartbeat._loop()

    assert writes == [("task-1", "latest:first chunk")]


def test_run_automation_with_retries_retries_empty_response():
    class FakeAutomationError(Exception):
        pass

    attempts = []
    announcements = []
    sleeps = []

    def runner(prompt_text, *, system_prompt, workdir, on_progress):
        attempts.append((prompt_text, system_prompt, workdir, on_progress))
        if len(attempts) == 1:
            raise FakeAutomationError("empty response")
        return "done"

    result = task_offloader._run_automation_with_retries(
        "task-1",
        "prompt",
        "system",
        lambda chunk: None,
        runner=runner,
        automation_error_cls=FakeAutomationError,
        sleep_fn=sleeps.append,
        write_progress_fn=lambda task_id, message: announcements.append((task_id, message)),
    )

    assert result == "done"
    assert len(attempts) == 2
    assert attempts[0][0:3] == ("prompt", "system", task_offloader.VESSENCE_HOME)
    assert sleeps == [2]
    assert announcements == [("task-1", "⏳ Got an empty response — retrying…")]


def test_run_automation_with_retries_raises_non_retryable_error():
    class FakeAutomationError(Exception):
        pass

    def runner(*_args, **_kwargs):
        raise FakeAutomationError("backend not found")

    try:
        task_offloader._run_automation_with_retries(
            "task-1",
            "prompt",
            "system",
            lambda chunk: None,
            runner=runner,
            automation_error_cls=FakeAutomationError,
            sleep_fn=lambda _seconds: None,
            write_progress_fn=lambda _task_id, _message: None,
        )
    except FakeAutomationError as exc:
        assert str(exc) == "backend not found"
    else:
        raise AssertionError("expected FakeAutomationError")
