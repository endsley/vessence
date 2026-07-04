import asyncio

from llm_brain.v1 import persistent_codex


class FakeStdout:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    async def read(self, _size):
        if self._chunks:
            return self._chunks.pop(0)
        return b""


class FakeStderr:
    async def read(self):
        return b""


class FakeProcess:
    def __init__(self):
        self.stdout = FakeStdout([
            (
                b'{"type":"thread.started","thread_id":"thread-1"}\n'
                b'{"type":"item.completed","item":{"type":"agent_message","text":"done"}}\n'
                b'{"type":"turn.completed"}\n'
            ),
            b"",
        ])
        self.stderr = FakeStderr()
        self.returncode = None
        self.pid = 12345

    async def wait(self):
        self.returncode = 0
        return 0


def test_codex_session_key_matches_manager_storage_key():
    assert persistent_codex._codex_session_key("user", "session") == "user:session"


def test_codex_event_error_message_preserves_stream_event_shapes():
    assert persistent_codex._codex_event_error_message({
        "type": "error",
        "message": "  top-level failure  ",
    }) == "top-level failure"
    assert persistent_codex._codex_event_error_message({
        "type": "turn.failed",
        "error": {"message": "  turn failed  "},
    }) == "turn failed"
    assert persistent_codex._codex_event_error_message({
        "type": "turn.failed",
        "error": "bad shape",
    }) == ""
    assert persistent_codex._codex_event_error_message({"type": "item.failed"}) == ""


def test_persistent_codex_failed_command_result_uses_command_formatter():
    manager = persistent_codex.CodexPersistentManager()
    long_message = "x" * 350

    assert manager._format_failed_command_result(
        "/bin/bash -lc 'pytest tests -q'",
        long_message,
    ) == f"pytest tests -q failed\n↳ {'x' * 300}"


def test_persistent_codex_execute_streaming_cleans_active_proc(monkeypatch):
    fake_proc = FakeProcess()

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return fake_proc

    monkeypatch.setattr(
        persistent_codex.asyncio,
        "create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    manager = persistent_codex.CodexPersistentManager()

    response, thread_id = asyncio.run(
        manager._execute_streaming(
            ["codex", "exec"],
            on_delta=None,
            on_status=None,
            on_thought=None,
            on_tool_use=None,
            on_tool_result=None,
            timeout_seconds=5,
            session_id="session",
            user_id="user",
        )
    )

    assert response == "done"
    assert thread_id == "thread-1"
    assert manager._active_procs == {}
