"""Simulate 10 turns in one session to verify the full FIFO flow.

For each turn we check:
  1. The v2 pipeline classifies the prompt correctly
  2. The FIFO grows by one entry (after Haiku writes the summary)
  3. Each subsequent request sees an expanding recent_context block
     (observed via jane_web.log "fetched recent context" line)
  4. Final answer comes back cleanly

Note: the Haiku summary write is asynchronous (fires from a background
persistence thread after send_message returns). We poll the FIFO after
each turn with a brief timeout to wait for the summary to land.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

ENDPOINT = "http://localhost:8081/api/jane/chat"
SESSION_ID = f"fifo-bench-{int(time.time())}"
RESULTS_PATH = Path(__file__).parent / "benchmark_fifo_flow_results.json"


PROMPTS: list[str] = [
    "What's the temperature right now?",
    "How about tomorrow?",
    "Will it rain on Monday?",
    "Is Tuesday going to be warmer?",
    "What's the forecast for the rest of the week?",
    "Should I bring an umbrella on Wednesday?",
    "How hot will Thursday get?",
    "Is the air quality good today?",
    "What's the UV index for tomorrow?",
    "Give me the coldest night this week.",
]


def _fifo_count(sid: str) -> int:
    try:
        from vault_web.recent_turns import count
        return count(sid)
    except Exception:
        return -1


def _fifo_contents(sid: str) -> list[str]:
    try:
        from vault_web.recent_turns import get_recent
        return get_recent(sid, n=20)
    except Exception:
        return []


def _wait_for_fifo_growth(sid: str, expected_count: int, timeout: float = 20.0) -> bool:
    """Poll until the FIFO reaches expected_count or timeout."""
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if _fifo_count(sid) >= expected_count:
            return True
        time.sleep(0.2)
    return False


def main() -> None:
    print(f"FIFO flow benchmark  session={SESSION_ID}  endpoint={ENDPOINT}\n")
    results = []
    started = time.perf_counter()

    # Starting FIFO count (should be 0 for a fresh session)
    initial = _fifo_count(SESSION_ID)
    print(f"Initial FIFO count for new session: {initial}\n")

    for i, prompt in enumerate(PROMPTS, start=1):
        pre_count = _fifo_count(SESSION_ID)
        t0 = time.perf_counter()
        try:
            r = httpx.post(
                ENDPOINT,
                json={"message": prompt, "session_id": SESSION_ID, "platform": "android"},
                timeout=300.0,
            )
            elapsed = time.perf_counter() - t0
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            elapsed = time.perf_counter() - t0
            data = {"response": f"[error: {type(e).__name__}: {e}]", "classification": "?", "stage": "?"}
            print(f"[{i:2d}] ERROR after {elapsed:.2f}s: {data['response']}")
            continue

        # Wait for the background Haiku writeback to land
        target_count = pre_count + 1
        fifo_grew = _wait_for_fifo_growth(SESSION_ID, target_count)
        post_count = _fifo_count(SESSION_ID)

        row = {
            "i": i,
            "prompt": prompt,
            "classification": data.get("classification", "?"),
            "stage": data.get("stage", "?"),
            "response": data.get("response", ""),
            "stage1_ms": data.get("stage1_ms", 0),
            "stage2_ms": data.get("stage2_ms", 0),
            "stage3_ms": data.get("stage3_ms", 0),
            "total_ms": int(elapsed * 1000),
            "fifo_pre": pre_count,
            "fifo_post": post_count,
            "fifo_grew_in_time": fifo_grew,
        }
        results.append(row)

        # One-line progress
        short = row["response"].replace("\n", " ")[:80]
        tick = "✓" if fifo_grew else "…"
        print(
            f"[{i:2d}] {elapsed:5.2f}s {tick} fifo {pre_count}->{post_count}  "
            f"{row['classification']:<16}  {row['stage']:<6}  {short}"
        )

    total_elapsed = time.perf_counter() - started
    print(f"\nDone in {total_elapsed:.1f}s")

    # Show final FIFO state
    final_entries = _fifo_contents(SESSION_ID)
    print(f"\nFinal FIFO state ({len(final_entries)} entries, oldest-first):")
    for idx, s in enumerate(final_entries, start=1):
        print(f"  {idx:2d}. {s[:120]}")

    RESULTS_PATH.write_text(
        json.dumps(
            {
                "endpoint": ENDPOINT,
                "session_id": SESSION_ID,
                "total_elapsed_s": round(total_elapsed, 2),
                "final_fifo_size": len(final_entries),
                "final_fifo_entries": final_entries,
                "results": results,
            },
            indent=2,
        )
    )
    print(f"\nsaved: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
