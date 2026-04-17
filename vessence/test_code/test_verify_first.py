"""Tests for verify_first_policy + the Claude Code hook script.

Covers:
  - Classifier accuracy (needs_verification)
  - ToolUseCounter behavior
  - summarize_verification_status output shape
  - Hook's user_prompt_submit / post_tool_use / stop decisions
  - Pipeline injection happens for code prompts, not chat prompts
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, "/home/chieh/ambient/vessence")

from jane_web.verify_first_policy import (  # noqa: E402
    STRONGER_VERIFY_INSTRUCTION,
    ToolUseCounter,
    needs_verification,
    summarize_verification_status,
)

HOOK_SCRIPT = Path("/home/chieh/.claude/hooks/verify_first_hook.py")
PYTHON = "/home/chieh/google-adk-env/adk-venv/bin/python"


class ClassifierTest(unittest.TestCase):
    """needs_verification should fire on code/debug/system prompts only."""

    CODE_PROMPTS = [
        "why is the timer handler returning 5 seconds instead of 20",
        "check the logs for the stage3 crash",
        "trace how the pending_action is cleared",
        "show me the send_message handler",
        "where is the v2 class registry loaded",
        "how does the awaiting marker stripper work",
        "debug this bug where Opus ignores tool markers",
        "what's in configs/CRON_JOBS.md",
        "read configs/SELF_IMPROVE.md",
        "grep the codebase for TimerHandler",
        "tail the logs for the last timer turn",
        "root cause for the STT button bug",
        "which file has the wake word detector",
        "what's happening with the shopping list handler",
    ]

    NON_CODE_PROMPTS = [
        "hey jane how are you",
        "set a timer for 20 seconds",
        "what's the weather",
        "remind me to call my wife",
        "send a message to Kathia saying I love her",
        "what did I do yesterday",
        "play some music",
        "read my messages",
        "write me a poem about oak trees",
        "yes",
        "cancel that",
        "what did you fix last night",
    ]

    def test_code_prompts_trigger(self) -> None:
        for p in self.CODE_PROMPTS:
            with self.subTest(prompt=p):
                self.assertTrue(
                    needs_verification(p),
                    f"expected verification for: {p!r}",
                )

    def test_non_code_prompts_skip(self) -> None:
        for p in self.NON_CODE_PROMPTS:
            with self.subTest(prompt=p):
                self.assertFalse(
                    needs_verification(p),
                    f"unexpected verification trigger for: {p!r}",
                )

    def test_empty_prompt_is_false(self) -> None:
        self.assertFalse(needs_verification(""))
        self.assertFalse(needs_verification(None))  # type: ignore[arg-type]


class ToolUseCounterTest(unittest.TestCase):
    def test_counts_invocations(self) -> None:
        c = ToolUseCounter()
        c("Read", {"path": "x"})
        c("Grep", {"pattern": "y"})
        self.assertEqual(c.count, 2)
        self.assertIn("Read", c.names)
        self.assertIn("Grep", c.names)

    def test_passthrough_called(self) -> None:
        seen = []

        def original(name, args):
            seen.append((name, args))

        c = ToolUseCounter(original)
        c("Read", {"path": "x"})
        self.assertEqual(c.count, 1)
        self.assertEqual(seen, [("Read", {"path": "x"})])

    def test_passthrough_exception_swallowed(self) -> None:
        def broken(*_a, **_kw):
            raise RuntimeError("boom")

        c = ToolUseCounter(broken)
        # Must not raise.
        c("Read", {"path": "x"})
        self.assertEqual(c.count, 1)

    def test_name_list_capped(self) -> None:
        c = ToolUseCounter()
        for i in range(25):
            c(f"Tool{i}", {})
        self.assertEqual(c.count, 25)
        self.assertEqual(len(c.names), 10)  # capped


class SummarizeStatusTest(unittest.TestCase):
    def test_verified_when_tools_used_on_code_prompt(self) -> None:
        c = ToolUseCounter()
        c("Read", {"path": "x"})
        status = summarize_verification_status(
            "why does the timer fail", c,
        )
        self.assertTrue(status["needed"])
        self.assertTrue(status["verified"])
        self.assertFalse(status["flagged"])
        self.assertEqual(status["tool_calls"], 1)

    def test_flagged_when_no_tools_on_code_prompt(self) -> None:
        c = ToolUseCounter()
        status = summarize_verification_status(
            "why does the timer fail", c,
        )
        self.assertTrue(status["needed"])
        self.assertFalse(status["verified"])
        self.assertTrue(status["flagged"])

    def test_not_needed_for_chat_prompt(self) -> None:
        c = ToolUseCounter()
        status = summarize_verification_status("hey jane", c)
        self.assertFalse(status["needed"])
        self.assertFalse(status["flagged"])
        self.assertFalse(status["verified"])


def _run_hook(mode: str, payload: dict, state_dir: str) -> dict:
    env = os.environ.copy()
    env["HOME"] = os.environ["HOME"]
    # Monkey-patch the STATE_DIR via env hack: the hook defaults to
    # /tmp/claude-verify-first, which is fine for tests as long as we
    # use unique session ids.
    result = subprocess.run(
        [PYTHON, str(HOOK_SCRIPT), mode],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"Hook output not JSON: {result.stdout!r} (stderr: {result.stderr!r})"
        ) from e


class HookDispatcherTest(unittest.TestCase):
    """End-to-end hook script tests via subprocess."""

    def setUp(self) -> None:
        self.session_id = f"test-verify-{os.getpid()}-{id(self)}"

    def tearDown(self) -> None:
        # Clean up state file for this test run.
        state_path = Path("/tmp/claude-verify-first") / f"{self.session_id}.json"
        if state_path.exists():
            state_path.unlink()

    def test_user_prompt_submit_code_question_injects_instruction(self) -> None:
        result = _run_hook(
            "user_prompt_submit",
            {
                "session_id": self.session_id,
                "prompt": "why is the timer handler returning 5 seconds",
            },
            state_dir="/tmp/claude-verify-first",
        )
        self.assertEqual(result["decision"], "approve")
        self.assertIn("additionalContext", result)
        self.assertIn("VERIFY FIRST", result["additionalContext"])

    def test_user_prompt_submit_chat_question_no_injection(self) -> None:
        result = _run_hook(
            "user_prompt_submit",
            {
                "session_id": self.session_id,
                "prompt": "hey jane how are you",
            },
            state_dir="/tmp/claude-verify-first",
        )
        self.assertEqual(result["decision"], "approve")
        self.assertNotIn("additionalContext", result)

    def test_stop_blocks_code_question_without_tools(self) -> None:
        _run_hook(
            "user_prompt_submit",
            {
                "session_id": self.session_id,
                "prompt": "why does the timer fail",
            },
            state_dir="/tmp/claude-verify-first",
        )
        # No tool use recorded.
        result = _run_hook(
            "stop",
            {"session_id": self.session_id, "stop_hook_active": False},
            state_dir="/tmp/claude-verify-first",
        )
        self.assertEqual(result["decision"], "block")
        self.assertIn("verify-first", result["reason"].lower())

    def test_stop_approves_after_tool_use(self) -> None:
        _run_hook(
            "user_prompt_submit",
            {
                "session_id": self.session_id,
                "prompt": "why does the timer fail",
            },
            state_dir="/tmp/claude-verify-first",
        )
        # Record one tool invocation (Read).
        _run_hook(
            "post_tool_use",
            {"session_id": self.session_id, "tool_name": "Read"},
            state_dir="/tmp/claude-verify-first",
        )
        result = _run_hook(
            "stop",
            {"session_id": self.session_id},
            state_dir="/tmp/claude-verify-first",
        )
        self.assertEqual(result["decision"], "approve")

    def test_stop_approves_non_code_prompt(self) -> None:
        _run_hook(
            "user_prompt_submit",
            {"session_id": self.session_id, "prompt": "hey jane"},
            state_dir="/tmp/claude-verify-first",
        )
        result = _run_hook(
            "stop",
            {"session_id": self.session_id},
            state_dir="/tmp/claude-verify-first",
        )
        self.assertEqual(result["decision"], "approve")

    def test_stop_does_not_loop(self) -> None:
        """If stop_hook_active is True, approve even without tools to
        avoid infinite block loops."""
        _run_hook(
            "user_prompt_submit",
            {
                "session_id": self.session_id,
                "prompt": "why does the bug happen",
            },
            state_dir="/tmp/claude-verify-first",
        )
        result = _run_hook(
            "stop",
            {
                "session_id": self.session_id,
                "stop_hook_active": True,  # we've already nudged once
            },
            state_dir="/tmp/claude-verify-first",
        )
        self.assertEqual(result["decision"], "approve")

    def test_non_qualifying_tools_dont_count(self) -> None:
        _run_hook(
            "user_prompt_submit",
            {
                "session_id": self.session_id,
                "prompt": "why does the timer fail",
            },
            state_dir="/tmp/claude-verify-first",
        )
        # Edit/Write aren't evidence-gathering.
        _run_hook(
            "post_tool_use",
            {"session_id": self.session_id, "tool_name": "Edit"},
            state_dir="/tmp/claude-verify-first",
        )
        _run_hook(
            "post_tool_use",
            {"session_id": self.session_id, "tool_name": "TaskUpdate"},
            state_dir="/tmp/claude-verify-first",
        )
        # Still should block — no Read/Grep/Bash.
        result = _run_hook(
            "stop",
            {"session_id": self.session_id},
            state_dir="/tmp/claude-verify-first",
        )
        self.assertEqual(result["decision"], "block")


class PipelineInjectionTest(unittest.TestCase):
    """Verify the pipeline appends the instruction for code prompts."""

    def test_instruction_content_looks_right(self) -> None:
        self.assertIn("VERIFY FIRST", STRONGER_VERIFY_INSTRUCTION)
        self.assertIn("most likely", STRONGER_VERIFY_INSTRUCTION.lower())
        self.assertIn("evidence", STRONGER_VERIFY_INSTRUCTION.lower())

    def test_pipeline_imports_verify_first(self) -> None:
        src = Path(
            "/home/chieh/ambient/vessence/jane_web/jane_v2/pipeline.py"
        ).read_text()
        # Both streaming + non-streaming Stage 3 paths should import + use it.
        self.assertGreaterEqual(
            src.count("from jane_web.verify_first_policy import"),
            2,
            "verify_first_policy not imported in both pipeline paths",
        )
        self.assertIn("verify-first instruction injected", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
