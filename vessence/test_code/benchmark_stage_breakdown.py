"""Per-stage latency breakdown for the v2 3-stage pipeline.

Explicitly separates Stage 2's two LLM calls:
  - gate_ms  — universal WRONG_CLASS gate (qwen2.5:7b, ~50 tokens in)
  - handler_ms — the class handler (may or may not call an LLM itself)

Stage 1 is timed by calling `stage1_classifier.classify` directly; Stage 2
by calling `stage2_dispatcher._gate_check` and the handler separately;
Stage 3 by hitting the live /api/jane/chat endpoint with an "others"
prompt (Opus is cloud-dependent, no point re-implementing locally).

Prints mean / median / p90 per stage across `N` iterations per prompt.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/chieh/ambient/vessence")

from jane_web.jane_v2 import stage1_classifier, stage2_dispatcher  # noqa: E402

ENDPOINT = "http://localhost:8081/api/jane/chat"
RESULTS_PATH = Path(__file__).parent / "benchmark_stage_breakdown_results.json"

ITER = 3

PROMPTS_BY_CLASS = {
    # Prompts Stage 1 is expected to route to a specific class.
    "get time":   ["What time is it?", "give me the time", "current time?"],
    "weather":    ["What's the temperature?", "will it rain tomorrow?", "is it cold outside"],
    "greeting":   ["hi jane", "hello there", "good morning"],
    "todo list":  ["what's on my todo list", "what do I need to do today", "any urgent tasks"],
    "others":     [
        "how does python's asyncio event loop work",
        "what's 42 times 17",
        "explain the pythagorean theorem",
    ],
}

# Longer prompts (>5 words, with no meta signals) that force the _gate_check
# LLM call rather than the fast-bypass path. Use these specifically to
# benchmark the real LLM round-trip cost.
GATE_FULL_PROMPTS_BY_CLASS = {
    "get time":   [
        "can you please tell me what the current time is right now",
        "hey jane can you tell me the time right now please",
        "what's the current time here can you let me know",
    ],
    "weather":    [
        "hey jane can you tell me what the weather is going to be like tomorrow",
        "what is the temperature outside right now can you check",
        "is it going to rain later today or should I leave the umbrella",
    ],
    "greeting":   [
        "hi jane good morning how are you doing today",
        "hey jane it's great to see you how has your day been",
        "hello jane I hope you're having a wonderful morning today",
    ],
}


def _stats(xs: list[float]) -> dict:
    if not xs:
        return {"mean_ms": 0, "median_ms": 0, "p90_ms": 0, "n": 0}
    xs_sorted = sorted(xs)
    n = len(xs_sorted)
    p90_idx = max(0, int(0.9 * n) - 1)
    return {
        "n": n,
        "mean_ms": round(statistics.mean(xs) * 1000, 1),
        "median_ms": round(statistics.median(xs) * 1000, 1),
        "p90_ms": round(xs_sorted[p90_idx] * 1000, 1),
        "min_ms": round(min(xs) * 1000, 1),
        "max_ms": round(max(xs) * 1000, 1),
    }


async def time_stage1(prompts: list[str]) -> list[float]:
    # Warm the embedding model so the first call doesn't skew the numbers.
    await stage1_classifier.classify("warmup")
    out: list[float] = []
    for p in prompts:
        t0 = time.perf_counter()
        await stage1_classifier.classify(p)
        out.append(time.perf_counter() - t0)
    return out


async def time_gate(class_name: str, prompts: list[str]) -> list[float]:
    # Warm ollama so the model is already resident.
    await stage2_dispatcher._gate_check(class_name, "warmup", "")
    out: list[float] = []
    for p in prompts:
        t0 = time.perf_counter()
        await stage2_dispatcher._gate_check(class_name, p, "")
        out.append(time.perf_counter() - t0)
    return out


async def time_stage3_via_http(prompt: str) -> float:
    import httpx
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(
            ENDPOINT,
            json={"message": prompt, "session_id": "bench-stage-breakdown", "platform": "text"},
        )
        r.raise_for_status()
    return time.perf_counter() - t0


async def main() -> None:
    results: dict = {"iterations_per_prompt": ITER, "by_stage": {}, "by_class": {}}

    # ── Stage 1 ─────────────────────────────────────────────────────────
    all_stage1: list[float] = []
    per_class_stage1: dict[str, list[float]] = {}
    for cls, prompts in PROMPTS_BY_CLASS.items():
        xs = []
        for _ in range(ITER):
            xs.extend(await time_stage1(prompts))
        per_class_stage1[cls] = xs
        all_stage1.extend(xs)
    results["by_stage"]["stage1_embed"] = _stats(all_stage1)

    # ── Stage 2 gate — fast-bypass path (short prompts ≤5 words) ─────────
    all_gate_bypass: list[float] = []
    for cls, prompts in PROMPTS_BY_CLASS.items():
        if cls not in stage2_dispatcher._CLASS_DESCRIPTIONS:
            continue
        for _ in range(ITER):
            all_gate_bypass.extend(await time_gate(cls, prompts))
    results["by_stage"]["stage2_gate_bypass"] = _stats(all_gate_bypass)

    # ── Stage 2 gate — full LLM path (longer prompts force the LLM call) ─
    all_gate_llm: list[float] = []
    per_class_gate: dict[str, list[float]] = {}
    for cls, prompts in GATE_FULL_PROMPTS_BY_CLASS.items():
        if cls not in stage2_dispatcher._CLASS_DESCRIPTIONS:
            continue
        xs = []
        for _ in range(ITER):
            xs.extend(await time_gate(cls, prompts))
        per_class_gate[cls] = xs
        all_gate_llm.extend(xs)
    results["by_stage"]["stage2_gate_llm"] = _stats(all_gate_llm)

    # ── Stage 2 handler (via dispatch) for a class that is pure-python ──
    # todo_list is a good pick: no external LLM, reads a local cache.
    from jane_web.jane_v2 import stage2_dispatcher as s2d
    async def _handler_only(cls: str, prompt: str) -> float:
        """Invoke just the handler, matching the dispatcher's introspection logic."""
        import inspect
        meta = s2d.class_registry.get_registry().get(cls)
        if not meta or not meta.get("handler"):
            return 0.0
        handler = meta["handler"]
        try:
            sig = inspect.signature(handler)
            kwargs = {}
            if "context" in sig.parameters:
                kwargs["context"] = ""
            if "pending" in sig.parameters:
                kwargs["pending"] = None
        except (TypeError, ValueError):
            kwargs = {}
        t0 = time.perf_counter()
        if inspect.iscoroutinefunction(handler):
            await handler(prompt, **kwargs)
        else:
            await asyncio.to_thread(lambda: handler(prompt, **kwargs))
        return time.perf_counter() - t0

    handler_samples_todo: list[float] = []
    for _ in range(ITER):
        for p in PROMPTS_BY_CLASS["todo list"]:
            handler_samples_todo.append(await _handler_only("todo list", p))
    results["by_stage"]["stage2_handler_todo_list"] = _stats(handler_samples_todo)

    # Greeting handler (usually pure python / trivial)
    handler_samples_greet: list[float] = []
    for _ in range(ITER):
        for p in PROMPTS_BY_CLASS["greeting"]:
            handler_samples_greet.append(await _handler_only("greeting", p))
    results["by_stage"]["stage2_handler_greeting"] = _stats(handler_samples_greet)

    # ── Stage 3 (full round trip through the web server) ────────────────
    stage3_samples: list[float] = []
    for p in PROMPTS_BY_CLASS["others"]:
        try:
            stage3_samples.append(await time_stage3_via_http(p))
        except Exception as e:
            print(f"stage3 error on {p!r}: {e}")
    results["by_stage"]["stage3_end_to_end_http"] = _stats(stage3_samples)

    results["by_class"]["stage1"] = {k: _stats(v) for k, v in per_class_stage1.items()}
    results["by_class"]["stage2_gate"] = {k: _stats(v) for k, v in per_class_gate.items()}

    print(json.dumps(results, indent=2))
    RESULTS_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nSaved: {RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
