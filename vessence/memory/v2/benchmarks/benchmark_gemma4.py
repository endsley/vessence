"""Benchmark the initial ack classification using local Gemma 4 via Ollama.

# NOTE: This benchmark tested gemma4:e4b which has been removed. Kept for reference only.

Compares local Gemma 4 (gemma4:e4b) against the Claude CLI baseline.
Tests compact format only at 50/100/200/300 leaf scales, 3 rounds each.

Usage:
    python benchmark_gemma4.py [--rounds 3]
"""

import json
import os
import sys
import time
import argparse
from pathlib import Path

BENCHMARK_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Same test prompts and system prompt as the original benchmark
# ---------------------------------------------------------------------------

TEST_PROMPTS = [
    {
        "id": "simple_recall",
        "prompt": "What's my work schedule like?",
        "expected_branches": ["user_info/work", "user_info/personal/daily_routine"],
    },
    {
        "id": "cross_domain",
        "prompt": "How does the memory system work and what changes have we discussed?",
        "expected_branches": ["vessence/architecture/memory_system", "conversations/topics"],
    },
    {
        "id": "specific_lookup",
        "prompt": "What's Bob's phone number?",
        "expected_branches": ["user_info/relationships", "user_info/work/colleagues"],
    },
    {
        "id": "technical",
        "prompt": "Show me how to set up the Docker deployment",
        "expected_branches": ["vessence/deployment/docker", "knowledge/technical/devops"],
    },
    {
        "id": "vague",
        "prompt": "Tell me about that thing we talked about yesterday",
        "expected_branches": ["conversations/topics/recent_discussions"],
    },
]

SYSTEM_PROMPT_TEMPLATE = """You are an initial acknowledgment assistant. Your job is to:
1. Read the user's message
2. Look at the memory tree index below
3. Select 2-3 leaf paths most relevant to answering the user
4. Generate 1-3 grep keywords to search memory leaves
5. Write a brief acknowledgment (1 sentence)

Respond in JSON only:
{{
  "classified_leaves": ["path/to/leaf1.md", "path/to/leaf2.md"],
  "grep_keywords": ["keyword1", "keyword2"],
  "ack": "Brief acknowledgment to user"
}}

MEMORY TREE INDEX:
{tree_index}
"""


def load_tree_index(leaf_count: int, fmt: str) -> str:
    """Load a mock tree index file."""
    filename = f"tree_index_{fmt}_{leaf_count}.txt"
    filepath = os.path.join(BENCHMARK_DIR, filename)
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Missing {filepath} - run generate_mock_trees.py first")
    with open(filepath) as f:
        return f.read()


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token for English)."""
    return len(text) // 4


def call_gemma4(prompt: str) -> str:
    """Call Gemma 4 via Ollama. Tries the ollama library first, falls back to requests."""
    messages = [{"role": "user", "content": prompt}]
    options = {"num_predict": 512, "temperature": 0.3}

    try:
        import ollama
        response = ollama.chat(
            model="gemma4:e4b",
            messages=messages,
            options=options,
        )
        return response["message"]["content"]
    except ImportError:
        pass

    import requests
    resp = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "gemma4:e4b",
            "messages": messages,
            "stream": False,
            "options": options,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def run_single_benchmark(tree_index: str, user_prompt: str) -> dict:
    """Run a single benchmark call and measure performance."""
    full_prompt = SYSTEM_PROMPT_TEMPLATE.format(tree_index=tree_index)
    full_prompt += f"\n\nUser message: {user_prompt}"

    prompt_tokens = estimate_tokens(full_prompt)

    start = time.perf_counter()
    try:
        response = call_gemma4(full_prompt)
        elapsed = time.perf_counter() - start
        error = None
    except Exception as e:
        elapsed = time.perf_counter() - start
        response = ""
        error = str(e)

    # Try to parse JSON response
    parsed = None
    if response and not error:
        try:
            text = response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            parsed = json.loads(text)
        except (json.JSONDecodeError, IndexError):
            error = f"JSON parse failed: {response[:200]}"

    response_tokens = estimate_tokens(response)

    return {
        "elapsed_ms": int(elapsed * 1000),
        "prompt_tokens_est": prompt_tokens,
        "response_tokens_est": response_tokens,
        "total_tokens_est": prompt_tokens + response_tokens,
        "classified_leaves": parsed.get("classified_leaves", []) if parsed else [],
        "grep_keywords": parsed.get("grep_keywords", []) if parsed else [],
        "ack": parsed.get("ack", "") if parsed else "",
        "raw_response": response[:500],
        "error": error,
    }


def evaluate_classification(result: dict, expected_branches: list) -> dict:
    """Score how well the classification matched expected branches."""
    classified = result.get("classified_leaves", [])
    if not classified or not expected_branches:
        return {"score": 0.0, "hits": 0, "misses": len(expected_branches)}

    hits = 0
    for expected in expected_branches:
        for leaf in classified:
            if expected in leaf or any(
                part in leaf for part in expected.split("/")
            ):
                hits += 1
                break

    return {
        "score": hits / len(expected_branches) if expected_branches else 0.0,
        "hits": hits,
        "misses": len(expected_branches) - hits,
        "classified": classified,
        "expected": expected_branches,
    }


def run_full_benchmark(rounds: int = 3) -> dict:
    """Run the full benchmark suite -- compact format only."""
    leaf_counts = [50, 100, 200, 300]
    results = {}

    for leaf_count in leaf_counts:
        fmt = "compact"
        key = f"{fmt}_{leaf_count}"
        print(f"\n{'='*60}")
        print(f"Testing: {key} ({leaf_count} leaves, {fmt} format)")
        print(f"{'='*60}")

        try:
            tree_index = load_tree_index(leaf_count, fmt)
        except FileNotFoundError as e:
            print(f"  SKIP: {e}")
            continue

        index_chars = len(tree_index)
        index_tokens = estimate_tokens(tree_index)
        print(f"  Index size: {index_chars} chars (~{index_tokens} tokens)")

        config_results = []
        for test in TEST_PROMPTS:
            prompt_results = []
            for round_num in range(rounds):
                print(f"  [{test['id']}] round {round_num+1}/{rounds}...", end=" ", flush=True)

                result = run_single_benchmark(tree_index, test["prompt"])
                eval_result = evaluate_classification(result, test["expected_branches"])
                result["evaluation"] = eval_result

                status = "OK" if not result["error"] else f"ERR: {result['error'][:50]}"
                print(f"{result['elapsed_ms']}ms - {status}")

                prompt_results.append(result)

            valid = [r for r in prompt_results if not r["error"]]
            avg_latency = (
                sum(r["elapsed_ms"] for r in valid) / len(valid) if valid else -1
            )
            avg_score = (
                sum(r["evaluation"]["score"] for r in valid) / len(valid)
                if valid
                else 0.0
            )

            config_results.append({
                "test_id": test["id"],
                "prompt": test["prompt"],
                "avg_latency_ms": int(avg_latency),
                "avg_classification_score": round(avg_score, 2),
                "rounds": prompt_results,
                "error_count": len(prompt_results) - len(valid),
            })

        all_valid = [
            r
            for cr in config_results
            for r in cr["rounds"]
            if not r["error"]
        ]
        results[key] = {
            "leaf_count": leaf_count,
            "format": fmt,
            "index_chars": index_chars,
            "index_tokens_est": index_tokens,
            "model": "gemma4:e4b",
            "avg_latency_ms": (
                int(sum(r["elapsed_ms"] for r in all_valid) / len(all_valid))
                if all_valid
                else -1
            ),
            "avg_classification_score": (
                round(
                    sum(r["evaluation"]["score"] for r in all_valid)
                    / len(all_valid),
                    2,
                )
                if all_valid
                else 0.0
            ),
            "tests": config_results,
        }

    return results


def print_summary(results: dict):
    """Print a summary table of results."""
    print(f"\n{'='*80}")
    print("BENCHMARK SUMMARY  --  Gemma 4 (gemma4:e4b) via Ollama")
    print(f"{'='*80}")
    print(f"{'Config':<20} {'Leaves':>6} {'Index Chars':>12} {'~Tokens':>8} "
          f"{'Avg Latency':>12} {'Avg Score':>10}")
    print("-" * 80)

    for key in sorted(results):
        r = results[key]
        print(
            f"{key:<20} {r['leaf_count']:>6} {r['index_chars']:>12} "
            f"{r['index_tokens_est']:>8} {r['avg_latency_ms']:>10}ms "
            f"{r['avg_classification_score']:>10.2f}"
        )

    print("-" * 80)

    viable = {k: v for k, v in results.items() if v["avg_latency_ms"] > 0}
    if viable:
        fastest = min(viable, key=lambda k: viable[k]["avg_latency_ms"])
        best_score = max(viable, key=lambda k: viable[k]["avg_classification_score"])
        print(f"\nFastest:    {fastest} ({viable[fastest]['avg_latency_ms']}ms)")
        print(f"Best score: {best_score} ({viable[best_score]['avg_classification_score']:.2f})")


def main():
    parser = argparse.ArgumentParser(description="Benchmark initial ack with Gemma 4 via Ollama")
    parser.add_argument(
        "--rounds",
        type=int,
        default=3,
        help="Rounds per test prompt (default: 3)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file (default: results_gemma4.json)",
    )
    args = parser.parse_args()

    print("Benchmarking initial ack LLM")
    print("Model: gemma4:e4b (local Ollama)")
    print(f"Rounds per test: {args.rounds}")
    print(f"Test prompts: {len(TEST_PROMPTS)}")
    print(f"Formats: compact only")
    print(f"Leaf counts: 50, 100, 200, 300")

    results = run_full_benchmark(args.rounds)

    print_summary(results)

    output_file = args.output or os.path.join(BENCHMARK_DIR, "results_gemma4.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nFull results saved to {output_file}")


if __name__ == "__main__":
    main()
