"""Baseline benchmark — initial ack with NO tree index.

Measures the raw latency of the initial ack LLM without any memory
tree context, so we can compare against the tree-injected versions.

Usage:
    python benchmark_baseline.py [--model haiku|sonnet] [--rounds 3]
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agent_skills.claude_cli_llm import completion
from jane.config import CHEAP_MODEL, SMART_MODEL

BENCHMARK_DIR = os.path.dirname(os.path.abspath(__file__))

TEST_PROMPTS = [
    "What's my work schedule like?",
    "How does the memory system work and what changes have we discussed?",
    "What's Bob's phone number?",
    "Show me how to set up the Docker deployment",
    "Tell me about that thing we talked about yesterday",
]

BASELINE_PROMPT = """You are an initial acknowledgment assistant. Your job is to:
1. Read the user's message
2. Write a brief acknowledgment (1 sentence)

Respond in JSON only:
{{
  "ack": "Brief acknowledgment to user"
}}

User message: {user_prompt}
"""


def run_baseline(model: str, rounds: int = 3) -> dict:
    """Run baseline benchmark without tree index."""
    results = []

    for prompt in TEST_PROMPTS:
        prompt_results = []
        for r in range(rounds):
            full = BASELINE_PROMPT.format(user_prompt=prompt)
            start = time.perf_counter()
            try:
                response = completion(full, model=model, max_tokens=256, timeout=60)
                elapsed = time.perf_counter() - start
                error = None
            except Exception as e:
                elapsed = time.perf_counter() - start
                response = ""
                error = str(e)

            print(f"  [{prompt[:30]}...] round {r+1}: {int(elapsed*1000)}ms", flush=True)
            prompt_results.append({
                "elapsed_ms": int(elapsed * 1000),
                "prompt_tokens_est": len(full) // 4,
                "error": error,
            })

        valid = [r for r in prompt_results if not r["error"]]
        avg = int(sum(r["elapsed_ms"] for r in valid) / len(valid)) if valid else -1
        results.append({
            "prompt": prompt,
            "avg_latency_ms": avg,
            "rounds": prompt_results,
        })

    all_valid = [r for pr in results for r in pr["rounds"] if not r["error"]]
    overall_avg = (
        int(sum(r["elapsed_ms"] for r in all_valid) / len(all_valid))
        if all_valid
        else -1
    )

    return {
        "model": model,
        "overall_avg_latency_ms": overall_avg,
        "tests": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Baseline benchmark (no tree index)")
    parser.add_argument("--model", choices=["haiku", "sonnet"], default="haiku")
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()

    model_map = {"haiku": CHEAP_MODEL, "sonnet": SMART_MODEL}
    model = model_map[args.model]

    print(f"Baseline benchmark (no tree index)")
    print(f"Model: {args.model} ({model})")

    results = run_baseline(model, args.rounds)

    print(f"\nBaseline avg latency: {results['overall_avg_latency_ms']}ms")

    output = os.path.join(BENCHMARK_DIR, f"results_baseline_{args.model}.json")
    with open(output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved to {output}")


if __name__ == "__main__":
    main()
