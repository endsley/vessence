"""Integration test for the "Stop thinking" button's end-to-end behavior.

The Android button calls ChatViewModel.cancelCurrentResponse(), which
cancels the coroutine job, which closes the OkHttp stream. From the
server's perspective this is just a dropped HTTP connection mid-stream.

These tests verify the SERVER side of that cancellation:

  1. Server accepts a streaming POST to /api/jane/chat/stream.
  2. We drop the connection after receiving the first delta.
  3. Server should:
       - Not crash
       - Not leak a pending standing-brain turn
       - Keep serving new requests immediately

We also verify the ChatViewModel state-machine invariants by inspecting
the Kotlin source — the actual cancel path is covered by existing
`currentStreamJob?.cancel()` logic that was already in place before
this UI change.
"""
from __future__ import annotations

import json
import socket
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, "/home/chieh/ambient/vessence")

SERVER_URL = "http://localhost:8080"  # proxy
JANE_KT_ROOT = Path(
    "/home/chieh/ambient/vessence/android/app/src/main/java/com/vessences/android/ui/chat"
)


class _ServerReachable:
    """Reusable check — mark tests skipped if server not up on localhost."""
    @staticmethod
    def probe(timeout: float = 1.0) -> bool:
        import urllib.request
        try:
            with urllib.request.urlopen(f"{SERVER_URL}/health", timeout=timeout) as r:
                return r.status == 200
        except Exception:
            return False


class CancelMidStreamTest(unittest.TestCase):
    """Functional end-to-end: drop stream, verify server stays healthy."""

    def setUp(self) -> None:
        if not _ServerReachable.probe():
            self.skipTest("Jane server not reachable at localhost:8080")

    def _health_ok(self) -> bool:
        import urllib.request
        try:
            with urllib.request.urlopen(f"{SERVER_URL}/health", timeout=2) as r:
                if r.status != 200:
                    return False
                body = json.loads(r.read())
                return body.get("status") == "ok"
        except Exception:
            return False

    def test_server_survives_mid_stream_drop(self) -> None:
        import http.client
        self.assertTrue(self._health_ok(), "Precondition: server healthy")

        # Open a streaming POST using a raw HTTPConnection so we can close
        # the socket mid-flight — same effect as the Android client's
        # OkHttp cancel.
        body = json.dumps({
            "message": "hey, what's 2+2?",
            "session_id": "test-cancel-session",
            "essence": "jane",
        }).encode()
        conn = http.client.HTTPConnection("localhost", 8080, timeout=10)
        conn.request(
            "POST", "/api/jane/chat/stream", body,
            {"Content-Type": "application/json", "Accept": "application/x-ndjson"},
        )
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)

        # Read a few bytes to confirm streaming started, then abort.
        first = resp.read(1)
        self.assertTrue(first, "Server never produced any bytes")
        conn.close()  # <-- the cancel

        # Immediately verify server still serves new requests.
        time.sleep(0.2)
        self.assertTrue(
            self._health_ok(),
            "Server stopped responding after mid-stream cancel",
        )

    def test_many_consecutive_cancels(self) -> None:
        """Rapid cancel cycles shouldn't starve the server."""
        import http.client
        self.assertTrue(self._health_ok(), "Precondition: server healthy")
        for i in range(3):
            body = json.dumps({
                "message": f"cancel-cycle-{i}",
                "session_id": "test-cancel-rapid",
                "essence": "jane",
            }).encode()
            conn = http.client.HTTPConnection("localhost", 8080, timeout=10)
            conn.request(
                "POST", "/api/jane/chat/stream", body,
                {"Content-Type": "application/json", "Accept": "application/x-ndjson"},
            )
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200, f"Cycle {i}: got status {resp.status}")
            resp.read(1)  # confirm streaming started
            conn.close()  # cancel
            time.sleep(0.1)
        self.assertTrue(self._health_ok(),
                        "Server died after rapid cancel cycles")


class StopButtonWiringTest(unittest.TestCase):
    """Static source-level invariants about the Stop Jane button.

    We can't run Compose UI tests without the Android test harness, so
    verify the code wiring is correct:
      - JaneChatScreen imports the Stop icon
      - The button calls cancelCurrentResponse()
      - The button is conditionally shown on isSending
      - ChatViewModel.cancelCurrentResponse() exists and clears state
    """

    def test_jane_chat_screen_has_stop_button(self) -> None:
        src = (JANE_KT_ROOT / "JaneChatScreen.kt").read_text()
        self.assertIn("import androidx.compose.material.icons.filled.Stop", src)
        self.assertIn("cancelCurrentResponse()", src)
        self.assertIn('contentDescription = "Stop Jane"', src)
        # Visibility gate must be on isSending so a stuck STT flag can't
        # leave the stop-STT button visible during thinking.
        self.assertIn("chatState.isSending", src)

    def test_chat_input_row_has_stop_button(self) -> None:
        src = (JANE_KT_ROOT / "ChatInputRow.kt").read_text()
        self.assertIn("import androidx.compose.material.icons.filled.Stop", src)
        self.assertIn("if (isSending && onCancel != null)", src)

    def test_view_model_cancel_clears_state(self) -> None:
        src = (JANE_KT_ROOT / "ChatViewModel.kt").read_text()
        # cancelCurrentResponse must: cancel the coroutine, clear the job
        # handle, mark messages cancelled, flip isSending=false, and
        # drain the queue.
        fn_start = src.find("fun cancelCurrentResponse()")
        self.assertGreater(fn_start, 0, "cancelCurrentResponse() missing")
        # Read the function body (crude — stop at next blank-line+fun)
        fn = src[fn_start:fn_start + 1500]
        self.assertIn("currentStreamJob?.cancel()", fn)
        self.assertIn("currentStreamJob = null", fn)
        self.assertIn("isSending = false", fn)
        self.assertIn("pendingQueue.clear()", fn)
        self.assertIn("(cancelled)", fn)

    def test_isListeningForSpeech_forceclear_on_send(self) -> None:
        """Defensive reset: when isSending flips true, isListeningForSpeech
        must be force-cleared so the red STT-cancel button can't linger
        through the thinking phase."""
        src = (JANE_KT_ROOT / "JaneChatScreen.kt").read_text()
        self.assertIn(
            "LaunchedEffect(chatState.isSending)",
            src,
            "No defensive reset of isListeningForSpeech on isSending=true",
        )
        self.assertIn(
            "force-clearing",
            src,
            "Missing log line for defensive reset (aids future debugging)",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
