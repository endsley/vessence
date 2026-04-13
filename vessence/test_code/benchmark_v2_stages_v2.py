"""30-prompt v2 benchmark — captures per-stage timing and the ack line.

Reads the new response fields added to v2 handle_chat:
  - ack              — what Stage 2 would have said right away
  - classification   — Stage 1 output (e.g. "weather:High")
  - stage            — "stage2" or "stage3"
  - stage1_ms        — classifier time
  - stage2_ms        — stage 2 time (0 if skipped)
  - stage3_ms        — stage 3 (v1 brain) time (0 if skipped)

30 prompts spanning weather / music play / others — FRESH set, no overlap
with benchmark_v2_stages_table.py's prompts.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

ENDPOINT = "http://localhost:8081/api/jane/chat"
RESULTS_PATH = Path(__file__).parent / "benchmark_v2_stages_v2_results.json"

PROMPTS: list[str] = [
    # --- weather (10 NEW prompts) ---
    "Does the forecast show rain this weekend?",
    "Is it going to be sunny tomorrow?",
    "What's the lowest temperature this week?",
    "Is tonight going to be windy?",
    "How humid is it right now?",
    "When's the warmest day this week?",
    "Should I wear shorts on Tuesday?",
    "Will it freeze overnight?",
    "Is Saturday going to be cloudy?",
    "What's the weather like on Thursday?",

    # --- music play (10 NEW prompts) ---
    "Play Clocks",
    "Play some jazz music",
    "Start my sleep playlist",
    "Put on the piano folder",
    "Play Yesterday",
    "I want to listen to sleep sounds",
    "Shuffle my music library",
    "Play the Scientist",
    "Queue up Viva La Vida",
    "Play Fix You",

    # --- others (10 NEW prompts, should go to Stage 3) ---
    "What's the capital of France?",
    "How do I make pancakes?",
    "Tell me a joke",
    "What day of the week is April 15?",
    "How old is the universe?",
    "What's 125 divided by 5?",
    "Recommend a good science fiction novel",
    "How does a car engine work?",
    "What's the tallest mountain in the world?",
    "Write a short limerick about cats",
]


def main() -> None:
    print(f"Running {len(PROMPTS)} prompts against {ENDPOINT}\n")
    results = []
    started = time.perf_counter()

    for i, prompt in enumerate(PROMPTS, 1):
        t0 = time.perf_counter()
        try:
            r = httpx.post(
                ENDPOINT,
                json={"message": prompt, "session_id": "bench-stages-v2", "platform": "voice"},
                timeout=300.0,
            )
            elapsed = time.perf_counter() - t0
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            elapsed = time.perf_counter() - t0
            data = {"response": f"[error: {type(e).__name__}: {e}]", "ack": "", "classification": "?",
                    "stage": "?", "stage1_ms": 0, "stage2_ms": 0, "stage3_ms": 0, "files": []}

        row = {
            "i": i,
            "prompt": prompt,
            "classification": data.get("classification", "?"),
            "stage": data.get("stage", "?"),
            "ack": data.get("ack", ""),
            "response": data.get("response", ""),
            "stage1_ms": int(data.get("stage1_ms", 0) or 0),
            "stage2_ms": int(data.get("stage2_ms", 0) or 0),
            "stage3_ms": int(data.get("stage3_ms", 0) or 0),
            "total_ms": int(elapsed * 1000),
            "playlist_id": data.get("playlist_id"),
        }
        results.append(row)

        short = row["response"].replace("\n", " ")[:70]
        print(
            f"[{i:2d}] total={row['total_ms']:>6}ms "
            f"s1={row['stage1_ms']:>5}ms s2={row['stage2_ms']:>5}ms s3={row['stage3_ms']:>6}ms  "
            f"{row['stage']:<6} {row['classification']:<16}  {short}"
        )

    total_elapsed = time.perf_counter() - started
    print(f"\nDone in {total_elapsed:.1f}s")

    RESULTS_PATH.write_text(json.dumps({
        "endpoint": ENDPOINT,
        "total_elapsed_s": round(total_elapsed, 2),
        "results": results,
    }, indent=2))
    print(f"saved: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
