"""30-prompt benchmark for the v3 Haiku-backed FIFO-aware classifier.

Exercises:
  - Clean-signal classifications (weather, timer, todo_list, greeting,
    send_message, read_messages, get_time, shopping_list, music_play)
  - Follow-up replies where FIFO has an open question (should SAME-route
    to the prior class)
  - Pivots mid-follow-up (should route to the new class)
  - Ambiguous prompts that should escalate to Stage 3

For each prompt, the benchmark:
  1. Optionally seeds a recent_turns FIFO for the session (to simulate
     prior Jane-asked-a-question context).
  2. Calls intent_classifier.v3.classifier.classify().
  3. Records returned (class, confidence) + latency.
  4. Compares against expected routing.

Must run with the HaikuStandingBrain subprocess either:
  - Spawned ahead of time (jane-web startup), or
  - Auto-spawned on first classify() call (takes ~1-2s for the first
    call, sub-second thereafter).

Usage:
  export JANE_USE_V3_PIPELINE=1   # optional, not required for the bench
  /home/chieh/google-adk-env/adk-venv/bin/python test_code/benchmark_v3_classifier.py
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/chieh/ambient/vessence")

from intent_classifier.v3 import classifier as v3_classifier  # noqa: E402


# ── Test cases ───────────────────────────────────────────────────────────────
# Each case: (prompt, prior_turns, expected_stage, notes)
#   prior_turns: list of dicts representing the FIFO before this turn.
#                {"role": "user"|"assistant", "text": "..."}  or  None / [].
#   expected_stage: "stage2" | "stage3"
#                   ("stage2" means classifier returns a specific class with
#                    High/Very High confidence; "stage3" means classifier
#                    returns ('others', 'Low').)


CASES: list[dict] = [
    # ── Clean-signal, no prior FIFO ───────────────────────────────────────
    {"prompt": "what's the weather today",
     "fifo": [],
     "expected_stage": "stage2",
     "expected_class_contains": "weather",
     "note": "simple weather query"},
    {"prompt": "set a 5 minute timer",
     "fifo": [],
     "expected_stage": "stage2",
     "expected_class_contains": "timer",
     "note": "simple timer set"},
    {"prompt": "what's on my todo list",
     "fifo": [],
     "expected_stage": "stage2",
     "expected_class_contains": "todo",
     "note": "todo readback"},
    {"prompt": "hi jane good morning",
     "fifo": [],
     "expected_stage": "stage2",
     "expected_class_contains": "greeting",
     "note": "greeting"},
    {"prompt": "what time is it right now",
     "fifo": [],
     "expected_stage": "stage2",
     "expected_class_contains": "time",
     "note": "time query"},
    {"prompt": "tell my wife I will be 20 minutes late",
     "fifo": [],
     "expected_stage": "stage2",
     "expected_class_contains": "send",
     "note": "sms intent"},
    {"prompt": "read my latest texts",
     "fifo": [],
     "expected_stage": "stage2",
     "expected_class_contains": "read",
     "note": "read messages"},
    {"prompt": "add milk to my shopping list",
     "fifo": [],
     "expected_stage": "stage2",
     "expected_class_contains": "shopping",
     "note": "shopping add"},
    {"prompt": "play my coldplay playlist",
     "fifo": [],
     "expected_stage": "stage2",
     "expected_class_contains": "music",
     "note": "music play"},

    # ── Complex reasoning / code questions → Stage 3 ──────────────────────
    {"prompt": "how does python's asyncio event loop actually work internally",
     "fifo": [],
     "expected_stage": "stage3",
     "note": "deep technical — needs Opus"},
    {"prompt": "why does the v3 classifier sometimes return Medium instead of High for clear prompts",
     "fifo": [],
     "expected_stage": "stage3",
     "note": "meta question about Jane's own code"},
    {"prompt": "can you explain the pythagorean theorem in simple terms",
     "fifo": [],
     "expected_stage": "stage3",
     "note": "general knowledge, no handler"},
    {"prompt": "tell me a story about a dragon who learns to code",
     "fifo": [],
     "expected_stage": "stage3",
     "note": "creative, no handler"},

    # ── Follow-ups: short answers to open Jane questions ─────────────────
    {"prompt": "clinic",
     "fifo": [
         {"role": "user", "text": "what's on my todo list"},
         {"role": "assistant", "text": "Two categories: home and clinic. Which one do you want to hear?"},
     ],
     "expected_stage": "stage2",
     "expected_class_contains": "todo",
     "note": "one-word follow-up to todo category question"},
    {"prompt": "the urgent stuff please",
     "fifo": [
         {"role": "user", "text": "what am I supposed to do today"},
         {"role": "assistant", "text": "4 categories: urgent, clinic, home, students. Which one?"},
     ],
     "expected_stage": "stage2",
     "expected_class_contains": "todo",
     "note": "multi-word follow-up to todo category question"},
    {"prompt": "pasta",
     "fifo": [
         {"role": "user", "text": "set a 10 minute timer"},
         {"role": "assistant", "text": "Got it, 10 minutes. What should I call this timer? Or say 'no label'."},
     ],
     "expected_stage": "stage2",
     "expected_class_contains": "timer",
     "note": "timer label follow-up"},
    {"prompt": "five minutes",
     "fifo": [
         {"role": "user", "text": "start a timer"},
         {"role": "assistant", "text": "Sure, how long should the timer run?"},
     ],
     "expected_stage": "stage2",
     "expected_class_contains": "timer",
     "note": "timer duration follow-up"},
    {"prompt": "yes send it",
     "fifo": [
         {"role": "user", "text": "text Kathia that I love her"},
         {"role": "assistant", "text": "Draft ready for Kathia: 'I love you'. Say 'yes' to send or 'cancel'."},
     ],
     "expected_stage": "stage2",
     "expected_class_contains": "send",
     "note": "sms confirmation follow-up"},

    # ── Pivots: user changes subject mid-follow-up ───────────────────────
    {"prompt": "actually what's the weather in tokyo right now",
     "fifo": [
         {"role": "user", "text": "what's on my todo list"},
         {"role": "assistant", "text": "4 categories: urgent, clinic, home, students. Which one?"},
     ],
     "expected_stage": "stage3",
     "note": "pivot from todo to weather — Tokyo is NOT the cached location (weather only handles Medford), so should escalate to Opus"},
    {"prompt": "never mind, tell my wife I'll be home late",
     "fifo": [
         {"role": "user", "text": "set a timer"},
         {"role": "assistant", "text": "How long should the timer run?"},
     ],
     "expected_stage": "stage2",
     "expected_class_contains": "send",
     "note": "pivot from timer to sms"},
    {"prompt": "forget the timer, play some music",
     "fifo": [
         {"role": "user", "text": "start a timer"},
         {"role": "assistant", "text": "How long should the timer run?"},
     ],
     "expected_stage": "stage2",
     "expected_class_contains": "music",
     "note": "pivot from timer to music"},
    {"prompt": "stop, what time is it",
     "fifo": [
         {"role": "user", "text": "what's on my todo list"},
         {"role": "assistant", "text": "4 categories available. Which one?"},
     ],
     "expected_stage": "stage2",
     "expected_class_contains": "time",
     "note": "pivot from todo to time"},

    # ── Genuine continuations that look like pivots superficially ────────
    {"prompt": "nine o'clock please",
     "fifo": [
         {"role": "user", "text": "set a timer"},
         {"role": "assistant", "text": "How long should the timer run?"},
     ],
     "expected_stage": "stage2",
     "expected_class_contains": "timer",
     "note": "duration answer that looks like time-query"},
    {"prompt": "the house one",
     "fifo": [
         {"role": "user", "text": "what do I need to do today"},
         {"role": "assistant", "text": "3 categories: clinic, home, urgent. Which one?"},
     ],
     "expected_stage": "stage2",
     "expected_class_contains": "todo",
     "note": "category answer containing 'house' (weak weather signal)"},

    # ── Short ambiguous prompts that should probably go to Stage 3 ──────
    {"prompt": "ok thanks",
     "fifo": [
         {"role": "user", "text": "what's the weather"},
         {"role": "assistant", "text": "It's 68 and sunny in Boston."},
     ],
     "expected_stage": "stage2",
     "expected_class_contains": "end",
     "note": "sign-off acknowledgment — now covered by end_conversation description"},
    {"prompt": "actually forget it",
     "fifo": [
         {"role": "user", "text": "set a timer"},
         {"role": "assistant", "text": "How long should the timer run?"},
     ],
     "expected_stage": "stage2",
     "expected_class_contains": "end",
     "note": "abandon / cancel current flow — end_conversation"},
    {"prompt": "what did we talk about yesterday",
     "fifo": [],
     "expected_stage": "stage3",
     "note": "memory question — needs full brain"},
    {"prompt": "remind me about the meeting",
     "fifo": [],
     "expected_stage": "stage3",
     "note": "vague, needs context / no matching handler"},

    # ── Mixed-intent prompts — human-obvious but embedding-tricky ───────
    {"prompt": "is it going to rain tomorrow during my 10am meeting",
     "fifo": [],
     "expected_stage": "stage2",
     "expected_class_contains": "weather",
     "note": "weather with temporal/context garnish"},
    {"prompt": "what's going on at the clinic today",
     "fifo": [],
     "expected_stage": "stage3",
     "note": "ambiguous — might be todo, might be calendar; expect Stage 3"},
]


# ── FIFO seeding helpers ─────────────────────────────────────────────────────


def _render_fifo(prior_turns: list[dict]) -> str:
    """Render a prior_turns list into the prose format recent_context produces."""
    lines: list[str] = []
    for t in prior_turns or []:
        role = t.get("role", "user")
        text = t.get("text", "").strip()
        label = "User" if role == "user" else "Jane"
        lines.append(f"{label}: {text}")
    return "\n".join(lines)


async def _patch_fifo_for_case(sid: str, prior_turns: list[dict]):
    """Inject the prior_turns into v2's recent_context for this session.

    We write the turns directly via recent_turns.add() so the classifier's
    call into recent_context.render_stage2_context() will see them.
    """
    if not prior_turns:
        return
    try:
        from vault_web.recent_turns import add as _recent_add, clear as _recent_clear
    except Exception as e:
        print(f"  (FIFO seed unavailable: {e})")
        return
    # Clear any existing turns for this bench session, then insert.
    try:
        _recent_clear(sid)
    except Exception:
        pass
    for t in prior_turns:
        role = t.get("role", "user")
        text = t.get("text", "").strip()
        prefix = "user: " if role == "user" else "jane: "
        try:
            _recent_add(sid, prefix + text)
        except Exception:
            pass


# ── Runner ───────────────────────────────────────────────────────────────────


async def _run_case(idx: int, case: dict) -> dict:
    prompt = case["prompt"]
    fifo = case.get("fifo", [])
    expected = case["expected_stage"]

    sid = f"bench-v3-{idx:02d}"
    await _patch_fifo_for_case(sid, fifo)

    t0 = time.perf_counter()
    cls, conf = await v3_classifier.classify(prompt, session_id=sid)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    # Decide the actual stage from the classifier's output contract.
    if cls == "others" or conf not in ("Very High", "High"):
        actual_stage = "stage3"
    else:
        actual_stage = "stage2"

    # Match expected_class_contains / expected_class_contains_any if present.
    class_ok = True
    if actual_stage == "stage2" and "expected_class_contains" in case:
        class_ok = case["expected_class_contains"] in cls
    elif actual_stage == "stage2" and "expected_class_contains_any" in case:
        class_ok = any(x in cls for x in case["expected_class_contains_any"])

    stage_ok = actual_stage == expected
    ok = stage_ok and class_ok

    return {
        "idx": idx,
        "prompt": prompt,
        "expected_stage": expected,
        "actual_stage": actual_stage,
        "class": cls,
        "confidence": conf,
        "latency_ms": latency_ms,
        "ok": ok,
        "stage_ok": stage_ok,
        "class_ok": class_ok,
        "note": case.get("note", ""),
    }


def _print_row(r: dict):
    flag = "✓" if r["ok"] else "✗"
    stage_mark = " " if r["stage_ok"] else "!"
    class_mark = " " if r["class_ok"] else "!"
    print(
        f"  [{r['idx']:2d}] {flag} "
        f"{r['actual_stage']:<6}{stage_mark}  "
        f"{r['class']:<14}{class_mark}  "
        f"{r['confidence']:<10}  "
        f"{r['latency_ms']:>5}ms  "
        f"{r['prompt'][:62]}"
    )


async def main():
    print(f"Running {len(CASES)} classification cases through v3...\n")
    print(f"  {'idx':<4} {'ok':<2} {'stage':<8} {'class':<15} {'conf':<11} {'latency':<8}  prompt")
    print(f"  {'---':<4} {'--':<2} {'-----':<8} {'-----':<15} {'----':<11} {'-------':<8}  ------")

    results: list[dict] = []
    for idx, case in enumerate(CASES, 1):
        r = await _run_case(idx, case)
        results.append(r)
        _print_row(r)

    # Summary
    passed = sum(1 for r in results if r["ok"])
    total = len(results)
    latencies = [r["latency_ms"] for r in results]
    stage2_count = sum(1 for r in results if r["actual_stage"] == "stage2")
    stage3_count = total - stage2_count

    print("\nSummary")
    print(f"  passed:    {passed}/{total}")
    print(f"  stage2:    {stage2_count}")
    print(f"  stage3:    {stage3_count}")
    print(f"  latency:   median={statistics.median(latencies):.0f}ms  "
          f"mean={statistics.mean(latencies):.0f}ms  "
          f"p90={sorted(latencies)[int(0.9*total)-1]}ms  "
          f"max={max(latencies)}ms")

    # List failures for triage
    failures = [r for r in results if not r["ok"]]
    if failures:
        print("\nFailures:")
        for r in failures:
            reason = []
            if not r["stage_ok"]:
                reason.append(f"stage mismatch (expected {r['expected_stage']})")
            if not r["class_ok"]:
                reason.append(f"class {r['class']!r} did not contain expected substring")
            print(f"  [{r['idx']:2d}] {r['prompt'][:80]}  —  {'; '.join(reason)}")
            print(f"       note: {r['note']}")

    # Write machine-readable results next to this script.
    out_path = Path(__file__).parent / "benchmark_v3_classifier_results.json"
    out_path.write_text(json.dumps({
        "total": total,
        "passed": passed,
        "latency_median_ms": statistics.median(latencies),
        "latency_mean_ms": statistics.mean(latencies),
        "results": results,
    }, indent=2))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
