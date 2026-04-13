"""30-prompt benchmark that captures Stage 1 / Stage 2 / Stage 3 outputs.

For each prompt, we record:
  - Stage 1 classification ("weather:High", "music play:High", "others:Low", ...)
  - Stage 2 output (if Stage 2 handled it; otherwise blank)
  - Stage 3 output (if Stage 3 handled it; otherwise blank)
  - Wall-clock latency

The column that ends up populated depends on routing. Weather and music
prompts usually fill the Stage 2 column; everything else fills Stage 3.

All requests hit /api/jane/chat (non-streaming) which is the voice-path
endpoint and is what the v2 pipeline replaces. Stage 2 weather is the
voice-friendly short variant installed in this session.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import httpx

ENDPOINT = "http://localhost:8081/api/jane/chat"
LOG_PATH = Path("/home/chieh/ambient/vessence-data/logs/jane_web.log")
RESULTS_PATH = Path(__file__).parent / "benchmark_v2_stages_table_results.json"

PROMPTS: list[str] = [
    # --- weather (expect Stage 2 weather) ---
    "What's the temperature right now?",
    "How cold is it outside?",
    "Will it rain tomorrow?",
    "What's the high on Monday?",
    "Is the air quality okay today?",
    "How windy is it right now?",
    "What's the forecast for this week?",
    "Should I bring an umbrella tomorrow?",
    "What's the UV index today?",
    "How warm will it be on Tuesday?",

    # --- music play (expect Stage 2 music) ---
    "Play my coldplay playlist",
    "Put on some music",
    "Play Bohemian Rhapsody",
    "I want to hear some Brazilian music",
    "Play something relaxing",
    "Start the encanto playlist",
    "Queue up some piano",
    "Play a random song",
    "Shuffle my coldplay playlist",
    "Put on some Chinese music",

    # --- others (expect Stage 3 escalation to Opus) ---
    "Hey, good morning!",
    "How does Python's asyncio event loop work?",
    "Nice weather we're having, huh.",
    "When was Bohemian Rhapsody released?",
    "What's 42 times 17?",
    "Explain the Pythagorean theorem simply",
    "Write a haiku about coffee",
    "How tall is the Eiffel Tower?",
    "Translate 'good night' to Japanese",
    "How does the weather cron job run in this codebase?",
]


_STAGE1_RE = re.compile(r"stage1_classifier:\s*([\w ]+?):(\w+)")


def _log_size() -> int:
    return LOG_PATH.stat().st_size if LOG_PATH.exists() else 0


def _new_log_text(since_size: int) -> str:
    if not LOG_PATH.exists():
        return ""
    with LOG_PATH.open("rb") as f:
        f.seek(since_size)
        return f.read().decode("utf-8", errors="ignore")


def _parse(log_slice: str, response_text: str) -> tuple[str, str, str]:
    """Return (classification, stage2_output, stage3_output)."""
    m = _STAGE1_RE.search(log_slice)
    classification = f"{m.group(1).strip()}:{m.group(2).strip()}" if m else "?"

    stage2_output = ""
    stage3_output = ""

    if "stage2_weather: answered" in log_slice:
        stage2_output = response_text
    elif "stage2_music_play: matched existing playlist" in log_slice:
        stage2_output = response_text
    elif (
        "stage2_music_play: query=" in log_slice
        and "matched existing playlist" not in log_slice
        and "no match" not in log_slice
    ):
        stage2_output = response_text
    elif "stage2_music_play:" in log_slice and "no match" in log_slice:
        # music stage 2 ran but couldn't find the song — it still returned
        # a Stage 2 response text ("Unable to find the song in our list.")
        stage2_output = response_text
    else:
        # classification was others, or weather/music stage 2 escalated.
        stage3_output = response_text

    return classification, stage2_output, stage3_output


def main() -> None:
    print(f"Running {len(PROMPTS)} prompts through {ENDPOINT}\n")
    results = []
    started = time.perf_counter()

    for i, prompt in enumerate(PROMPTS, 1):
        log_start = _log_size()
        t0 = time.perf_counter()
        try:
            r = httpx.post(
                ENDPOINT,
                json={"message": prompt, "session_id": "bench-stages", "platform": "voice"},
                timeout=300.0,
            )
            elapsed = time.perf_counter() - t0
            r.raise_for_status()
            response_text = (r.json().get("response") or "").strip()
        except Exception as e:
            elapsed = time.perf_counter() - t0
            response_text = f"[error: {type(e).__name__}: {e}]"

        time.sleep(0.1)  # let service flush log
        log_slice = _new_log_text(log_start)
        classification, s2, s3 = _parse(log_slice, response_text)

        results.append(
            {
                "i": i,
                "prompt": prompt,
                "classification": classification,
                "stage2": s2,
                "stage3": s3,
                "time_s": round(elapsed, 2),
            }
        )
        mark = "S2" if s2 else ("S3" if s3 else "??")
        short = (s2 or s3)[:70]
        print(f"[{i:2d}] {elapsed:6.2f}s  {classification:16s}  {mark}  {short}")

    total_elapsed = time.perf_counter() - started
    print(f"\nDone in {total_elapsed:.1f}s")

    RESULTS_PATH.write_text(
        json.dumps(
            {
                "endpoint": ENDPOINT,
                "total_elapsed_s": round(total_elapsed, 2),
                "results": results,
            },
            indent=2,
        )
    )
    print(f"saved: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
