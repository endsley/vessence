"""Live benchmark of Jane v2's /api/jane/chat endpoint.

Hits the running service with 30 prompts spanning weather, music play,
and general/others topics. For each prompt we capture:
  - wall-clock latency
  - Stage 1 classification (from jane_web.log)
  - which handler processed it (Stage 2 weather, Stage 2 music, or
    Stage 3 escalation to v1 brain)
  - the first ~80 chars of Jane's response

Results are printed as a table and also saved to
test_code/benchmark_v2_live_results.json.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import httpx

ENDPOINT = "http://localhost:8081/api/jane/chat"
LOG_PATH = Path("/home/chieh/ambient/vessence-data/logs/jane_web.log")
RESULTS_PATH = (
    Path(__file__).parent / "benchmark_v2_live_results.json"
)
PROGRESS_PATH = Path("/tmp/bench_v2_progress.log")


PROMPTS: list[tuple[str, str]] = [
    # (category, prompt)
    # --- weather (expect Stage 2 weather) ---
    ("weather", "What's the temperature right now?"),
    ("weather", "How cold is it outside?"),
    ("weather", "Will it rain tomorrow?"),
    ("weather", "What's the high on Monday?"),
    ("weather", "Is the air quality okay today?"),
    ("weather", "How windy is it right now?"),
    ("weather", "What's the forecast for this week?"),
    ("weather", "Should I bring an umbrella tomorrow?"),
    ("weather", "What's the UV index today?"),
    ("weather", "How warm will it be on Tuesday?"),

    # --- music play (expect Stage 2 music) ---
    ("music_play", "Play my coldplay playlist"),
    ("music_play", "Put on some music"),
    ("music_play", "Play Bohemian Rhapsody"),
    ("music_play", "I want to hear some Brazilian music"),
    ("music_play", "Play something relaxing"),
    ("music_play", "Start the encanto playlist"),
    ("music_play", "Queue up some piano"),
    ("music_play", "Play a random song"),
    ("music_play", "Shuffle my coldplay playlist"),
    ("music_play", "Put on some Chinese music"),

    # --- others (expect Stage 3 escalation to Opus) ---
    ("others", "Hey, good morning!"),
    ("others", "How does Python's asyncio event loop work?"),
    ("others", "Nice weather we're having, huh."),
    ("others", "When was Bohemian Rhapsody released?"),
    ("others", "What's 42 times 17?"),
    ("others", "Explain the Pythagorean theorem simply"),
    ("others", "Write a haiku about coffee"),
    ("others", "How tall is the Eiffel Tower?"),
    ("others", "Translate 'good night' to Japanese"),
    ("others", "How does the weather cron job run in this codebase?"),
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


def _classify_and_handler(log_slice: str) -> tuple[str, str, str]:
    """Parse stage1 classification, stage selection, and the concrete
    method the winning stage used. Returns (classification, stage, method).
    """
    cls = conf = "?"
    m = _STAGE1_RE.search(log_slice)
    if m:
        cls, conf = m.group(1).strip(), m.group(2).strip()
    classification = f"{cls}:{conf}" if cls != "?" else "?"

    # Stage 2 weather — gemma4 read weather.json and produced an answer
    if "stage2_weather: answered" in log_slice:
        return classification, "Stage 2", "gemma4 + weather.json"
    if "stage2_weather: ESCALATE marker" in log_slice or "stage2_weather:" in log_slice and "escalating" in log_slice:
        # Weather tried but bailed → escalated
        if "stage3_escalate" in log_slice or "brain_execute" in log_slice or "send_message" in log_slice.lower():
            return classification, "Stage 3", "weather bailed → v1 brain"

    # Stage 2 music play — two tiers
    if "stage2_music_play: matched existing playlist" in log_slice:
        return classification, "Stage 2", "named playlist match"
    if "stage2_music_play: query=" in log_slice and "matched existing playlist" not in log_slice:
        if "no match" in log_slice:
            return classification, "Stage 3", "music no-match → v1 brain"
        return classification, "Stage 2", "library resolver (v1 fuzzy)"

    # Stage 3 — others / fallback
    if classification.startswith("others") or "escalate_others" in log_slice or "reason=others" in log_slice:
        return classification, "Stage 3", "v1 brain (Opus)"

    # Weather:Medium often escalates too
    if cls == "weather" and conf != "High":
        return classification, "Stage 3", "weather:Medium → v1 brain"

    return classification, "?", "?"


def _progress(msg: str) -> None:
    with PROGRESS_PATH.open("a") as f:
        f.write(msg + "\n")
    print(msg, flush=True)


def run() -> None:
    PROGRESS_PATH.write_text("")  # truncate
    _progress(f"v2 live benchmark starting against {ENDPOINT}")
    _progress(f"{len(PROMPTS)} prompts to run")
    _progress("")

    results = []
    started = time.perf_counter()

    for i, (category, prompt) in enumerate(PROMPTS, 1):
        log_start = _log_size()
        t0 = time.perf_counter()
        try:
            r = httpx.post(
                ENDPOINT,
                json={"message": prompt, "session_id": "bench-v2"},
                timeout=300.0,
            )
            elapsed = time.perf_counter() - t0
            r.raise_for_status()
            text = r.json().get("response", "") or ""
        except Exception as e:
            elapsed = time.perf_counter() - t0
            text = f"[error: {type(e).__name__}: {e}]"

        # Give the service a moment to flush the log, then read new lines.
        time.sleep(0.1)
        slice_text = _new_log_text(log_start)
        classification, stage, method = _classify_and_handler(slice_text)

        results.append(
            {
                "i": i,
                "category": category,
                "prompt": prompt,
                "classification": classification,
                "stage": stage,
                "method": method,
                "time_s": round(elapsed, 2),
                "output": text[:120],
                "output_full_len": len(text),
            }
        )

        _progress(
            f"[{i:2d}/{len(PROMPTS)}] {elapsed:6.2f}s  "
            f"{classification:16s}  {stage:8s}  {method:28s}  {prompt[:48]}"
        )

    total_elapsed = time.perf_counter() - started

    _progress("")
    _progress(f"=== done in {total_elapsed/60:.1f} minutes ===")

    # Save full results
    RESULTS_PATH.write_text(json.dumps({
        "endpoint": ENDPOINT,
        "prompts_count": len(PROMPTS),
        "total_elapsed_s": round(total_elapsed, 2),
        "results": results,
    }, indent=2))
    _progress(f"saved: {RESULTS_PATH}")

    # Print summary table
    _progress("")
    _progress("== RESULTS TABLE ==")
    header = (
        f"{'#':>3}  {'time':>7}  {'stage':<8}  "
        f"{'method':<28}  {'class':<16}  prompt"
    )
    _progress(header)
    _progress("-" * len(header))
    for r in results:
        _progress(
            f"{r['i']:>3}  {r['time_s']:>6.2f}s  {r['stage']:<8}  "
            f"{r['method']:<28}  {r['classification']:<16}  {r['prompt'][:50]}"
        )
        _progress(f"     -> {r['output'][:110]}")


if __name__ == "__main__":
    run()
