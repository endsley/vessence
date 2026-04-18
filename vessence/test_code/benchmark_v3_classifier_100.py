"""100-prompt benchmark for the v3 intent classifier.

Extends benchmark_v3_classifier.py with ~70 additional prompts that
stress:
  - Clean-signal variations per class (paraphrases, typos, STT-cut-offs)
  - Short-follow-up disambiguation with FIFO (pasta-like cases at scale)
  - Pivots inside an open flow
  - Adversarial phrasings that LOOK LIKE a class but aren't
  - Ambiguous utterances that should escalate to Stage 3 (safe escalation)
  - Edge cases from real-world STT garble and single-word replies

Case shape (reused from the 30-case bench):
  {"prompt": "...", "fifo": [{"role": "user|assistant", "text": "..."}, ...],
   "expected_stage": "stage2" | "stage3",
   "expected_class_contains": "substring",   # optional
   "note": "..."}

Usage:
  /home/chieh/google-adk-env/adk-venv/bin/python test_code/benchmark_v3_classifier_100.py
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


CASES: list[dict] = [
    # ══ CLEAN-SIGNAL, NO PRIOR FIFO (30 prompts, 3 per class × 10 classes) ══

    # weather (3)
    {"prompt": "what's the weather today", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "weather", "note": "weather clean"},
    {"prompt": "is it cold outside", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "weather", "note": "weather colloquial"},
    {"prompt": "how hot is it right now", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "weather", "note": "weather temperature query"},

    # timer (3)
    {"prompt": "set a 10 minute timer", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "timer", "note": "timer clean"},
    {"prompt": "start a timer for 25 minutes", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "timer", "note": "timer alt phrasing"},
    {"prompt": "alarm me in an hour", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "timer", "note": "alarm = timer"},

    # todo list (3)
    {"prompt": "what's on my todo list", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "todo", "note": "todo readback"},
    {"prompt": "add buy groceries to my todos", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "todo", "note": "todo add"},
    {"prompt": "what do I need to do today", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "todo", "note": "todo colloquial"},

    # greeting (3)
    {"prompt": "hi jane", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "greeting", "note": "greeting minimal"},
    {"prompt": "good morning jane how are you", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "greeting", "note": "greeting full"},
    {"prompt": "hey there", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "greeting", "note": "greeting casual"},

    # get time (3)
    {"prompt": "what time is it", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "time", "note": "time clean"},
    {"prompt": "tell me the time", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "time", "note": "time imperative"},
    {"prompt": "do you know what time it is", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "time", "note": "time indirect"},

    # send message (3)
    {"prompt": "text my wife I love her", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "send", "note": "sms basic"},
    {"prompt": "tell bob I'll be 15 minutes late", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "send", "note": "sms with body"},
    {"prompt": "message kathia that dinner is ready", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "send", "note": "sms 'message X that'"},

    # read messages (3)
    {"prompt": "read my messages", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "read", "note": "read clean"},
    {"prompt": "any new texts", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "read", "note": "unread check"},
    {"prompt": "what did alice text me", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "read", "note": "read from sender"},

    # shopping list (3)
    {"prompt": "add bread to shopping list", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "shopping", "note": "shopping add"},
    {"prompt": "what's on my shopping list", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "shopping", "note": "shopping readback"},
    {"prompt": "put eggs on my grocery list", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "shopping", "note": "grocery = shopping"},

    # music play (3)
    {"prompt": "play some music", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "music", "note": "music clean"},
    {"prompt": "put on my jazz playlist", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "music", "note": "music playlist"},
    {"prompt": "play coldplay", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "music", "note": "music artist"},

    # end conversation (3)
    {"prompt": "ok thanks", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "end", "note": "end sign-off"},
    {"prompt": "goodbye jane", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "end", "note": "end goodbye"},
    {"prompt": "that's all for now", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "end", "note": "end finishing"},

    # ══ FOLLOW-UPS WITH FIFO (20 prompts — short replies to open Jane Qs) ══

    {"prompt": "pasta", "fifo": [
        {"role": "user", "text": "set a 10 minute timer"},
        {"role": "assistant", "text": "Got it, 10 minutes. What should I call this timer?"},
     ], "expected_stage": "stage2", "expected_class_contains": "timer",
     "note": "timer label follow-up"},
    {"prompt": "laundry", "fifo": [
        {"role": "user", "text": "start a 30 minute timer"},
        {"role": "assistant", "text": "30 minutes. What's this timer for?"},
     ], "expected_stage": "stage2", "expected_class_contains": "timer",
     "note": "timer label follow-up"},
    {"prompt": "ten minutes", "fifo": [
        {"role": "user", "text": "start a timer"},
        {"role": "assistant", "text": "How long?"},
     ], "expected_stage": "stage2", "expected_class_contains": "timer",
     "note": "timer duration follow-up"},
    {"prompt": "half an hour", "fifo": [
        {"role": "user", "text": "set a timer"},
        {"role": "assistant", "text": "How long should the timer run?"},
     ], "expected_stage": "stage2", "expected_class_contains": "timer",
     "note": "timer duration — natural language"},
    {"prompt": "clinic", "fifo": [
        {"role": "user", "text": "what's on my todo list"},
        {"role": "assistant", "text": "Two categories: home and clinic. Which one?"},
     ], "expected_stage": "stage2", "expected_class_contains": "todo",
     "note": "todo category follow-up"},
    {"prompt": "home", "fifo": [
        {"role": "user", "text": "what do I need to do"},
        {"role": "assistant", "text": "Categories: home, clinic, urgent. Which?"},
     ], "expected_stage": "stage2", "expected_class_contains": "todo",
     "note": "todo category single word"},
    {"prompt": "urgent", "fifo": [
        {"role": "user", "text": "show me my todos"},
        {"role": "assistant", "text": "Categories: urgent, home, clinic. Which one?"},
     ], "expected_stage": "stage2", "expected_class_contains": "todo",
     "note": "todo category — 'urgent' single word"},
    {"prompt": "the clinic stuff", "fifo": [
        {"role": "user", "text": "what do I need to do today"},
        {"role": "assistant", "text": "Categories: urgent, clinic, home. Which one?"},
     ], "expected_stage": "stage2", "expected_class_contains": "todo",
     "note": "todo category with filler"},
    {"prompt": "yes send it", "fifo": [
        {"role": "user", "text": "text bob I'm on my way"},
        {"role": "assistant", "text": "Draft for Bob: 'I'm on my way'. Send?"},
     ], "expected_stage": "stage2", "expected_class_contains": "send",
     "note": "sms confirm"},
    {"prompt": "yeah send that", "fifo": [
        {"role": "user", "text": "text my wife I love her"},
        {"role": "assistant", "text": "Draft for Kathia: 'I love you'. Send?"},
     ], "expected_stage": "stage2", "expected_class_contains": "send",
     "note": "sms confirm variant"},
    {"prompt": "no don't send", "fifo": [
        {"role": "user", "text": "text alice meeting at 3"},
        {"role": "assistant", "text": "Draft for Alice: 'Meeting at 3'. Send?"},
     ], "expected_stage": "stage2", "expected_class_contains": "end",
     "note": "sms cancel — end conversation"},
    {"prompt": "change it to 4pm", "fifo": [
        {"role": "user", "text": "text alice meeting at 3"},
        {"role": "assistant", "text": "Draft for Alice: 'Meeting at 3'. Send?"},
     ], "expected_stage": "stage3",
     "note": "sms edit — needs reasoning brain"},
    {"prompt": "bye jane", "fifo": [
        {"role": "user", "text": "what's the weather"},
        {"role": "assistant", "text": "68 and sunny."},
     ], "expected_stage": "stage2", "expected_class_contains": "end",
     "note": "end after answer"},
    {"prompt": "night jane", "fifo": [
        {"role": "user", "text": "good night"},
        {"role": "assistant", "text": "Good night. Sleep well."},
     ], "expected_stage": "stage2", "expected_class_contains": "end",
     "note": "goodnight sign-off"},
    {"prompt": "thanks that's all", "fifo": [
        {"role": "user", "text": "what's on my todo"},
        {"role": "assistant", "text": "You have 3 items: …"},
     ], "expected_stage": "stage2", "expected_class_contains": "end",
     "note": "sign-off after readback"},
    {"prompt": "cool thanks", "fifo": [
        {"role": "user", "text": "what time is it"},
        {"role": "assistant", "text": "It's 2:15 PM."},
     ], "expected_stage": "stage2", "expected_class_contains": "end",
     "note": "sign-off cool-thanks"},
    {"prompt": "both please", "fifo": [
        {"role": "user", "text": "read my messages"},
        {"role": "assistant", "text": "I have 2 messages — one from Bob and one promo. Which?"},
     ], "expected_stage": "stage2", "expected_class_contains": "read",
     "note": "follow-up pick both"},
    {"prompt": "just the important ones", "fifo": [
        {"role": "user", "text": "read my email"},
        {"role": "assistant", "text": "You have 5 unread emails — 2 look important. Read all or just important?"},
     ], "expected_stage": "stage2", "expected_class_contains": "read",
     "note": "email subset select (read email path)"},
    {"prompt": "go ahead", "fifo": [
        {"role": "user", "text": "text alice I'm running late"},
        {"role": "assistant", "text": "Draft for Alice: 'I'm running late'. Send?"},
     ], "expected_stage": "stage2", "expected_class_contains": "send",
     "note": "sms confirm 'go ahead'"},
    {"prompt": "sure", "fifo": [
        {"role": "user", "text": "text bob hi"},
        {"role": "assistant", "text": "Draft for Bob: 'hi'. Send?"},
     ], "expected_stage": "stage2", "expected_class_contains": "send",
     "note": "sms confirm minimal"},

    # ══ PIVOTS MID-FLOW (10 prompts) ══

    {"prompt": "actually forget it, what time is it", "fifo": [
        {"role": "user", "text": "set a timer"},
        {"role": "assistant", "text": "How long?"},
     ], "expected_stage": "stage2", "expected_class_contains": "time",
     "note": "pivot timer → time"},
    {"prompt": "never mind, play some jazz", "fifo": [
        {"role": "user", "text": "text bob"},
        {"role": "assistant", "text": "What should I say?"},
     ], "expected_stage": "stage2", "expected_class_contains": "music",
     "note": "pivot sms → music"},
    {"prompt": "stop, add eggs to shopping", "fifo": [
        {"role": "user", "text": "read my messages"},
        {"role": "assistant", "text": "3 messages. Read them?"},
     ], "expected_stage": "stage2", "expected_class_contains": "shopping",
     "note": "pivot read → shopping"},
    {"prompt": "forget the timer tell my wife I love her", "fifo": [
        {"role": "user", "text": "set a timer"},
        {"role": "assistant", "text": "How long?"},
     ], "expected_stage": "stage2", "expected_class_contains": "send",
     "note": "pivot timer → sms"},
    {"prompt": "actually what's on my todo", "fifo": [
        {"role": "user", "text": "text alice"},
        {"role": "assistant", "text": "What should I say?"},
     ], "expected_stage": "stage2", "expected_class_contains": "todo",
     "note": "pivot sms → todo"},
    {"prompt": "nope, check my messages instead", "fifo": [
        {"role": "user", "text": "set a 20 minute timer"},
        {"role": "assistant", "text": "20 minutes. What's this timer for?"},
     ], "expected_stage": "stage2", "expected_class_contains": "read",
     "note": "pivot timer → read"},
    {"prompt": "wait hold on what time is it", "fifo": [
        {"role": "user", "text": "add milk"},
        {"role": "assistant", "text": "Milk added to shopping list."},
     ], "expected_stage": "stage2", "expected_class_contains": "time",
     "note": "pivot shopping → time"},
    {"prompt": "cancel, what's the weather", "fifo": [
        {"role": "user", "text": "text bob"},
        {"role": "assistant", "text": "What should I say?"},
     ], "expected_stage": "stage2", "expected_class_contains": "weather",
     "note": "pivot sms → weather"},
    {"prompt": "actually play some music", "fifo": [
        {"role": "user", "text": "what's on my todo"},
        {"role": "assistant", "text": "Categories: home, clinic, urgent. Which?"},
     ], "expected_stage": "stage2", "expected_class_contains": "music",
     "note": "pivot todo → music"},
    {"prompt": "scratch that, goodnight", "fifo": [
        {"role": "user", "text": "add bananas"},
        {"role": "assistant", "text": "Added to shopping list."},
     ], "expected_stage": "stage2", "expected_class_contains": "end",
     "note": "pivot → end conversation"},

    # ══ ADVERSARIAL — LOOKS LIKE CLASS X BUT IS NOT (20 prompts) ══

    {"prompt": "stop the music", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "music",
     "note": "adversarial: looks like 'stop' but is music control"},
    {"prompt": "cancel my timer", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "timer",
     "note": "adversarial: looks like cancel/end but is timer cancel"},
    {"prompt": "send me the weather forecast", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "weather",
     "note": "adversarial: 'send' but is weather"},
    {"prompt": "what did bob say in his last email last week", "fifo": [],
     "expected_stage": "stage3",
     "note": "adversarial: looks like read_email but needs memory → stage 3"},
    {"prompt": "delete all spam emails", "fifo": [], "expected_stage": "stage3",
     "note": "adversarial: email bulk action — no handler"},
    {"prompt": "what time is the meeting", "fifo": [], "expected_stage": "stage3",
     "note": "adversarial: 'time' but is calendar query → stage 3"},
    {"prompt": "my wife said she loves me", "fifo": [], "expected_stage": "stage3",
     "note": "adversarial: mentions 'wife' like sms but is narrative"},
    {"prompt": "tell me about python asyncio", "fifo": [], "expected_stage": "stage3",
     "note": "adversarial: 'tell me' but is a knowledge question"},
    {"prompt": "read me a poem", "fifo": [], "expected_stage": "stage3",
     "note": "adversarial: 'read' but is creative"},
    {"prompt": "list the groceries I bought yesterday", "fifo": [],
     "expected_stage": "stage3",
     "note": "adversarial: 'groceries' but needs memory"},
    {"prompt": "good morning how was your night", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "greeting",
     "note": "greeting with question suffix"},
    {"prompt": "how's it going", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "greeting",
     "note": "casual greeting"},
    {"prompt": "what day is today", "fifo": [], "expected_stage": "stage3",
     "note": "adversarial: looks like 'time' but is date"},
    {"prompt": "is tomorrow a holiday", "fifo": [], "expected_stage": "stage3",
     "note": "adversarial: calendar knowledge — no handler"},
    {"prompt": "add a meeting at 3pm", "fifo": [], "expected_stage": "stage3",
     "note": "adversarial: 'add' but is calendar add → no handler"},
    {"prompt": "never mind that", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "end",
     "note": "end conversation — dismissal"},
    {"prompt": "five more minutes", "fifo": [
        {"role": "user", "text": "set a 10 minute timer"},
        {"role": "assistant", "text": "10 minute timer started."},
     ], "expected_stage": "stage3",
     "note": "adversarial: 'five minutes' but ambiguous extend — stage 3"},
    {"prompt": "who sang this song", "fifo": [
        {"role": "user", "text": "play some jazz"},
        {"role": "assistant", "text": "Playing jazz."},
     ], "expected_stage": "stage3",
     "note": "adversarial: looks like music but is metadata question"},
    {"prompt": "turn it up", "fifo": [
        {"role": "user", "text": "play coldplay"},
        {"role": "assistant", "text": "Playing Coldplay."},
     ], "expected_stage": "stage2", "expected_class_contains": "music",
     "note": "music volume control"},
    {"prompt": "skip to the next one", "fifo": [
        {"role": "user", "text": "play jazz"},
        {"role": "assistant", "text": "Playing jazz."},
     ], "expected_stage": "stage2", "expected_class_contains": "music",
     "note": "music skip control"},

    # ══ AMBIGUOUS → STAGE 3 (10 prompts — safe escalations) ══

    {"prompt": "what should I do", "fifo": [], "expected_stage": "stage3",
     "note": "vague — needs Opus"},
    {"prompt": "help me out", "fifo": [], "expected_stage": "stage3",
     "note": "generic help"},
    {"prompt": "what did we talk about yesterday", "fifo": [],
     "expected_stage": "stage3", "note": "memory question"},
    {"prompt": "summarize my day", "fifo": [], "expected_stage": "stage3",
     "note": "summarization — Opus"},
    {"prompt": "what's going on at the clinic today", "fifo": [],
     "expected_stage": "stage3", "note": "ambiguous — todo or calendar"},
    {"prompt": "is it raining in tokyo", "fifo": [], "expected_stage": "stage3",
     "note": "weather outside home location"},
    {"prompt": "explain quantum entanglement", "fifo": [], "expected_stage": "stage3",
     "note": "deep knowledge"},
    {"prompt": "why is the sky blue", "fifo": [], "expected_stage": "stage3",
     "note": "trivia knowledge"},
    {"prompt": "remind me to call bob at 5", "fifo": [], "expected_stage": "stage3",
     "note": "reminder — no dedicated handler (stage3)"},
    {"prompt": "recommend a good book", "fifo": [], "expected_stage": "stage3",
     "note": "recommendation — Opus"},

    # ══ STT GARBLE / EDGE CASES (10 prompts) ══

    {"prompt": "uh set a timer five minutes", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "timer",
     "note": "STT filler 'uh'"},
    {"prompt": "jane play music please", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "music",
     "note": "wake-word included"},
    {"prompt": "hey jane what's the weather", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "weather",
     "note": "wake-word + weather"},
    {"prompt": "uh um what time", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "time",
     "note": "STT stutter + time"},
    {"prompt": "read read my messages", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "read",
     "note": "STT repeat"},
    {"prompt": "set a", "fifo": [], "expected_stage": "stage3",
     "note": "truncated utterance — STT cut off → stage 3"},
    {"prompt": "tell my", "fifo": [], "expected_stage": "stage3",
     "note": "truncated 'tell my …' — stage 3"},
    {"prompt": "ok", "fifo": [], "expected_stage": "stage3",
     "note": "bare 'ok' — no context, stage 3"},
    {"prompt": "maybe later", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "end", "note": "dismissal"},
    {"prompt": "never mind", "fifo": [], "expected_stage": "stage2",
     "expected_class_contains": "end", "note": "dismissal"},
]


# ── FIFO seeding helpers (copied from the 30-case bench) ─────────────────────


async def _patch_fifo_for_case(sid: str, prior_turns: list[dict]):
    if not prior_turns:
        return
    try:
        from vault_web.recent_turns import add as _recent_add, clear as _recent_clear
    except Exception as e:
        print(f"  (FIFO seed unavailable: {e})")
        return
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


async def _run_case(idx: int, case: dict) -> dict:
    prompt = case["prompt"]
    fifo = case.get("fifo", [])
    expected = case["expected_stage"]

    sid = f"bench-v3-100-{idx:03d}"
    await _patch_fifo_for_case(sid, fifo)

    t0 = time.perf_counter()
    cls, conf = await v3_classifier.classify(prompt, session_id=sid)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    if cls == "others" or conf not in ("Very High", "High"):
        actual_stage = "stage3"
    else:
        actual_stage = "stage2"

    class_ok = True
    if actual_stage == "stage2" and "expected_class_contains" in case:
        class_ok = case["expected_class_contains"] in cls

    stage_ok = actual_stage == expected
    ok = stage_ok and class_ok

    # Tag safe over-escalation: qwen returned "others" when expected was stage2.
    # Under Chieh's rule, this is acceptable (stage 3 picks up the right class).
    safe_over_escalation = (
        expected == "stage2"
        and actual_stage == "stage3"
    )

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
        "safe_over_escalation": safe_over_escalation,
        "note": case.get("note", ""),
    }


def _print_row(r: dict):
    if r["ok"]:
        flag = "✓"
    elif r["safe_over_escalation"]:
        flag = "~"  # safe — over-escalation to stage 3
    else:
        flag = "✗"
    stage_mark = " " if r["stage_ok"] else "!"
    class_mark = " " if r["class_ok"] else "!"
    print(
        f"  [{r['idx']:3d}] {flag} "
        f"{r['actual_stage']:<6}{stage_mark}  "
        f"{r['class']:<16}{class_mark}  "
        f"{r['confidence']:<10}  "
        f"{r['latency_ms']:>6}ms  "
        f"{r['prompt'][:60]}"
    )


async def main():
    print(f"Running {len(CASES)} classification cases through v3...\n")
    print(f"  {'idx':<4} {'ok':<2} {'stage':<8} {'class':<17} {'conf':<11} {'latency':<9}  prompt")
    print(f"  {'---':<4} {'--':<2} {'-----':<8} {'-----':<17} {'----':<11} {'-------':<9}  ------")

    results: list[dict] = []
    for idx, case in enumerate(CASES, 1):
        r = await _run_case(idx, case)
        results.append(r)
        _print_row(r)

    # Summary
    passed = sum(1 for r in results if r["ok"])
    safe_escalations = sum(1 for r in results if r["safe_over_escalation"])
    effective_pass = passed + safe_escalations
    total = len(results)
    latencies = [r["latency_ms"] for r in results]
    stage2_count = sum(1 for r in results if r["actual_stage"] == "stage2")
    stage3_count = total - stage2_count

    print("\nSummary")
    print(f"  strict pass:         {passed}/{total}")
    print(f"  safe over-escalation: {safe_escalations}  (qwen said 'others', expected stage2 — stage3 will handle it)")
    print(f"  effective pass:      {effective_pass}/{total}  "
          f"({effective_pass*100/total:.1f}%)")
    print(f"  stage2:              {stage2_count}")
    print(f"  stage3:              {stage3_count}")
    print(f"  latency:   median={statistics.median(latencies):.0f}ms  "
          f"mean={statistics.mean(latencies):.0f}ms  "
          f"p90={sorted(latencies)[int(0.9*total)-1]}ms  "
          f"p99={sorted(latencies)[int(0.99*total)-1]}ms  "
          f"max={max(latencies)}ms")

    # List failures (strict, not safe escalations)
    failures = [r for r in results if not r["ok"] and not r["safe_over_escalation"]]
    if failures:
        print(f"\nHARD failures ({len(failures)}):")
        for r in failures:
            reason = []
            if not r["stage_ok"]:
                reason.append(f"stage mismatch (expected {r['expected_stage']}, got {r['actual_stage']})")
            if not r["class_ok"]:
                reason.append(f"class '{r['class']}' did not contain expected")
            print(f"  [{r['idx']:3d}] {r['prompt'][:70]}")
            print(f"        {'; '.join(reason)}")
            print(f"        note: {r['note']}")

    safe = [r for r in results if r["safe_over_escalation"]]
    if safe:
        print(f"\nSAFE over-escalations ({len(safe)} — acceptable per Chieh's 'stage3 can handle it' rule):")
        for r in safe:
            print(f"  [{r['idx']:3d}] {r['prompt'][:70]}  (expected {r['expected_stage']}, got stage3)")

    out_path = Path(__file__).parent / "benchmark_v3_classifier_100_results.json"
    out_path.write_text(json.dumps({
        "total": total,
        "strict_passed": passed,
        "safe_over_escalation": safe_escalations,
        "effective_passed": effective_pass,
        "latency_median_ms": statistics.median(latencies),
        "latency_mean_ms": statistics.mean(latencies),
        "results": results,
    }, indent=2))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
