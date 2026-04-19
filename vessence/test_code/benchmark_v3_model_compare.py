"""A/B benchmark: qwen2.5:7b vs qwen3.5:2b on the v3 100-case suite.

Runs the exact same 100 cases from benchmark_v3_classifier_100.py
through each model back-to-back (fresh warm run per model), capturing:
  - classification correctness (strict pass + effective pass)
  - per-case latency
  - head-to-head agreement

This requires LOCAL_LLM in jane_web/jane_v2/models.py to be
swappable at call time. We monkey-patch v3_classifier._call_qwen
to inject the model override per run.

Usage:
  /home/chieh/google-adk-env/adk-venv/bin/python test_code/benchmark_v3_model_compare.py
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, "/home/chieh/ambient/vessence")

# Pull the 100 cases + harness from the existing benchmark
from test_code.benchmark_v3_classifier_100 import (  # noqa: E402
    CASES, _patch_fifo_for_case,
)
from intent_classifier.v3 import classifier as v3  # noqa: E402


MODELS = ["qwen2.5:7b", "qwen3.5:2b", "gemma4:e2b", "gemma4:e4b"]


def _make_qwen_caller(model_override: str):
    """Build a _call_qwen replacement that forces a specific Ollama model."""
    async def _call(prompt_text: str) -> str:
        import httpx
        from jane_web.jane_v2.models import (
            LOCAL_LLM_NUM_CTX,
            OLLAMA_KEEP_ALIVE,
            OLLAMA_URL,
        )
        body = {
            "model": model_override,
            "prompt": prompt_text,
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 60,
                "num_ctx": LOCAL_LLM_NUM_CTX,
            },
            "keep_alive": OLLAMA_KEEP_ALIVE,
        }
        async with httpx.AsyncClient(timeout=v3._LLM_TIMEOUT) as client:
            r = await client.post(OLLAMA_URL, json=body)
            r.raise_for_status()
            return (r.json().get("response") or "").strip()
    return _call


async def _unload_all_models():
    """Ask Ollama to evict every currently-loaded runner, so the next model
    we warm up has the VRAM it needs. Required when comparing models whose
    combined footprint exceeds GPU memory."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get("http://localhost:11434/api/ps")
            loaded = (r.json() or {}).get("models", [])
        for m in loaded:
            name = m.get("name") or m.get("model")
            if not name:
                continue
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    await client.post(
                        "http://localhost:11434/api/generate",
                        json={
                            "model": name,
                            "prompt": "",
                            "keep_alive": 0,  # immediate unload
                            "stream": False,
                        },
                    )
            except Exception as e:
                print(f"    unload {name} failed: {e}")
    except Exception as e:
        print(f"    api/ps failed: {e}")


async def _warmup(model: str):
    """Send a throwaway request so Ollama loads the runner + fills KV cache.
    Uses a 180 s timeout to absorb cold-start model load (gemma4:e4b is 8 B
    and takes ~30-60 s from cold disk)."""
    import httpx
    from jane_web.jane_v2.models import (
        LOCAL_LLM_NUM_CTX,
        OLLAMA_KEEP_ALIVE,
        OLLAMA_URL,
    )
    body = {
        "model": model,
        "prompt": 'Reply with just "ok".',
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 20,
            "num_ctx": LOCAL_LLM_NUM_CTX,
        },
        "keep_alive": OLLAMA_KEEP_ALIVE,
    }
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(OLLAMA_URL, json=body)
            r.raise_for_status()
    except Exception as e:
        print(f"  warmup {model} failed: {e}")


async def _run_case_with_model(idx: int, case: dict, model: str) -> dict:
    prompt = case["prompt"]
    fifo = case.get("fifo", [])
    pending = case.get("pending")
    expected = case["expected_stage"]

    sid = f"bench-v3-compare-{model.replace(':','_').replace('.','_')}-{idx:03d}"
    await _patch_fifo_for_case(sid, fifo, pending=pending)

    # Inject this model's _call_qwen for the duration of the classify call.
    orig = v3._call_qwen
    v3._call_qwen = _make_qwen_caller(model)
    try:
        t0 = time.perf_counter()
        cls, conf = await v3.classify(prompt, session_id=sid)
        latency_ms = int((time.perf_counter() - t0) * 1000)
    finally:
        v3._call_qwen = orig

    if cls == "others" or conf not in ("Very High", "High"):
        actual_stage = "stage3"
    else:
        actual_stage = "stage2"

    class_ok = True
    if actual_stage == "stage2" and "expected_class_contains" in case:
        class_ok = case["expected_class_contains"] in cls

    stage_ok = actual_stage == expected
    ok = stage_ok and class_ok
    safe_over = expected == "stage2" and actual_stage == "stage3"

    return {
        "idx": idx,
        "prompt": prompt,
        "model": model,
        "class": cls,
        "confidence": conf,
        "actual_stage": actual_stage,
        "latency_ms": latency_ms,
        "ok": ok,
        "stage_ok": stage_ok,
        "class_ok": class_ok,
        "safe_over_escalation": safe_over,
    }


async def main():
    print(f"Running {len(CASES)} cases × {len(MODELS)} models...\n")

    results_by_model: dict[str, list[dict]] = {m: [] for m in MODELS}

    for model in MODELS:
        print(f"─── {model} ───")
        print(f"  Unloading any currently-resident models to free VRAM...")
        await _unload_all_models()
        print(f"  Warming up {model} (may take ~30–60 s on cold start)...")
        await _warmup(model)
        # Second warmup to ensure the runner is fully hot
        await _warmup(model)

        for idx, case in enumerate(CASES, 1):
            r = await _run_case_with_model(idx, case, model)
            results_by_model[model].append(r)
            flag = "✓" if r["ok"] else ("~" if r["safe_over_escalation"] else "✗")
            print(f"  [{idx:3d}] {flag} {r['class']:<18s} {r['confidence']:<10s} {r['latency_ms']:>6}ms  {r['prompt'][:45]}")
        print()

    # Summary comparison
    print("═══ COMPARISON ═══")
    hdr = f"  {'model':<16} {'strict':>8} {'safe':>6} {'effective':>10} {'median':>8} {'p90':>8} {'p99':>8} {'max':>8}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))

    for model in MODELS:
        rs = results_by_model[model]
        passed = sum(1 for r in rs if r["ok"])
        safe = sum(1 for r in rs if r["safe_over_escalation"])
        effective = passed + safe
        lats = [r["latency_ms"] for r in rs]
        print(
            f"  {model:<16} "
            f"{passed:>6}/{len(rs):<2} "
            f"{safe:>6} "
            f"{effective:>8}/{len(rs):<2} "
            f"{statistics.median(lats):>6.0f}ms "
            f"{sorted(lats)[int(0.9*len(lats))-1]:>6}ms "
            f"{sorted(lats)[int(0.99*len(lats))-1]:>6}ms "
            f"{max(lats):>6}ms"
        )

    # Only-this-model-fails: where does exactly one model disagree with
    # the rest? Fast way to spot each model's weak spots.
    print()
    print("═══ ONLY-ONE-MODEL-GOT-IT-WRONG ═══")
    n_cases = len(CASES)
    for i in range(n_cases):
        per = [(m, results_by_model[m][i]) for m in MODELS]
        ok_models = [m for m, r in per if r["ok"]]
        fail_models = [m for m, r in per if not r["ok"]]
        if len(fail_models) == 1 and len(ok_models) >= 1:
            fm = fail_models[0]
            fr = results_by_model[fm][i]
            print(
                f"  [{fr['idx']:3d}] {fr['prompt'][:50]:<50s}\n"
                f"        {fm} FAIL: {fr['class']:<18s} {fr['confidence']:<10s} {fr['latency_ms']:>5}ms\n"
                f"        others OK"
            )

    # Save
    out = Path(__file__).parent / "benchmark_v3_model_compare_results.json"
    out.write_text(json.dumps({
        "models": MODELS,
        "total_cases": len(CASES),
        "results_by_model": results_by_model,
    }, indent=2))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    asyncio.run(main())
