import asyncio
import importlib
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock


fake_conversation_manager = types.ModuleType("agent_skills.conversation_manager")


class StubConversationManager:
    def __init__(self, session_id):
        self.session_id = session_id


fake_conversation_manager.ConversationManager = StubConversationManager
sys.modules.setdefault("agent_skills.conversation_manager", fake_conversation_manager)

wrapper_module = importlib.import_module("jane.jane_session_wrapper")
JaneSessionWrapper = wrapper_module.JaneSessionWrapper


def _make_wrapper(loop):
    wrapper = JaneSessionWrapper.__new__(JaneSessionWrapper)
    wrapper.debug = False
    wrapper.session_id = "test-session"
    wrapper.conv_manager = None
    wrapper.process = None
    wrapper.master_fd = None
    wrapper.loop = loop
    wrapper.exiting = False
    wrapper.last_sigint_time = 0.0
    wrapper.reader_task = None
    wrapper.memory_lock = asyncio.Lock()
    wrapper.restart_lock = asyncio.Lock()
    wrapper.signal_lock = asyncio.Lock()
    wrapper.ready_event = asyncio.Event()
    wrapper.process_generation = 0
    wrapper.pending_summary = None
    wrapper.pending_commit_tasks = set()
    wrapper.shutdown_task = None
    wrapper.log_queue = asyncio.Queue()
    wrapper.log_writer_task = None
    wrapper.raw_log_path = "/tmp/jane-wrapper-test.log"
    return wrapper


def test_extract_prompt_split_accepts_known_variants():
    wrapper = JaneSessionWrapper.__new__(JaneSessionWrapper)

    before, after, matched = wrapper._extract_prompt_split(
        "assistant reply\nType your message or @path/to/file\n"
    )
    assert before == "assistant reply\n"
    assert after == "\n"
    assert matched == "Type your message or @path/to/file"

    before, after, matched = wrapper._extract_prompt_split(
        "assistant reply\nPress / for commands\n"
    )
    assert before == "assistant reply\n"
    assert after == "\n"
    assert matched == "Press / for commands"


def test_normalize_output_strips_ansi_and_crlf():
    wrapper = JaneSessionWrapper.__new__(JaneSessionWrapper)
    text = "\x1b[32mhello\r\nworld\x1b[0m\r"
    assert wrapper._normalize_output(text) == "hello\nworld"


def test_schedule_commit_tracks_background_task():
    async def run():
        loop = asyncio.get_running_loop()
        wrapper = _make_wrapper(loop)
        calls = []

        async def fake_commit(role, content):
            calls.append((role, content))

        wrapper._commit_message = fake_commit

        wrapper._schedule_commit("user", "hello")
        assert len(wrapper.pending_commit_tasks) == 1

        await asyncio.gather(*list(wrapper.pending_commit_tasks))
        assert calls == [("user", "hello")]
        assert wrapper.pending_commit_tasks == set()

    asyncio.run(run())


def test_log_raw_queues_text_without_blocking():
    async def run():
        loop = asyncio.get_running_loop()
        wrapper = _make_wrapper(loop)

        wrapper._log_raw("hello")
        wrapper._log_raw(" world")

        assert await wrapper.log_queue.get() == "hello"
        assert await wrapper.log_queue.get() == " world"

    asyncio.run(run())


def test_shutdown_waits_for_pending_commit_tasks_before_close():
    async def run():
        loop = asyncio.get_running_loop()
        wrapper = _make_wrapper(loop)
        events = []

        async def pending_commit():
            await asyncio.sleep(0.01)
            events.append("commit")

        def close_manager():
            events.append("close")

        wrapper.conv_manager = types.SimpleNamespace(close=close_manager)
        wrapper.close_process = AsyncMock(side_effect=lambda: events.append("close_process"))
        wrapper.log_writer_task = asyncio.create_task(asyncio.sleep(0))
        task = asyncio.create_task(pending_commit())
        wrapper.pending_commit_tasks.add(task)

        await wrapper.shutdown()

        assert events == ["commit", "close", "close_process"]
        assert wrapper.exiting is True

    asyncio.run(run())


def test_wrapper_help_runs_as_script():
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(repo_root / "jane" / "jane_session_wrapper.py"), "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Jane Pro-Wrapper" in result.stdout
