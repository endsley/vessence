#!/usr/bin/env python3
import argparse
import datetime
import json
import sys
import time
from statistics import mean

sys.path.insert(0, "/home/chieh/ambient/vessence")

import ollama

from agent_skills.memory.v1.memory_retrieval import build_memory_sections
from jane.config import LIBRARIAN_MODEL


def _build_prompts(query: str, sections: list[str], conversation_summary: str, assistant_name: str) -> tuple[str, str]:
    facts_block = "\n\n".join(sections)
    now_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    system_instr = (
        f"You are the Memory Librarian for the user's assistant {assistant_name}. "
        f"Current time: {now_str}.\n"
        "Each memory entry is labeled with its timestamp and a human-readable age.\n"
        "Analyze the memory tiers relative to the user's query and any conversation summary. "
        "Return only the shortest useful summary for the next response.\n"
        "Rules:\n"
        "1. Recency priority: Short-Term > Long-Term > Permanent. The newer timestamp wins on conflicts.\n"
        "2. Explicitly surface very recent items when they matter.\n"
        "3. Avoid repeating facts already obvious from the conversation summary unless memory adds an important correction.\n"
        "4. Ignore irrelevant noise.\n"
        "5. If nothing beyond the conversation summary is useful, respond exactly with 'No relevant context found.'\n"
        "6. Respond only with the synthesized summary."
    )
    user_prompt = (
        f"User Query: {query}\n\n"
        + (f"Conversation Summary:\n{conversation_summary}\n\n" if conversation_summary else "")
        + f"Memory Tiers:\n{facts_block}"
    )
    return system_instr, user_prompt


def _ns_to_sec(value: int | None) -> float:
    if not value:
        return 0.0
    return round(value / 1_000_000_000, 4)


def _rough_tokens(text: str) -> int:
    return round(len(text) / 4)


def run_once(query: str, conversation_summary: str, assistant_name: str) -> dict:
    t0 = time.perf_counter()
    sections = build_memory_sections(query)
    build_sec = time.perf_counter() - t0

    system_prompt, user_prompt = _build_prompts(query, sections, conversation_summary, assistant_name)
    prompt_chars = len(system_prompt) + len(user_prompt)

    t1 = time.perf_counter()
    response = ollama.chat(
        model=LIBRARIAN_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    wall_chat_sec = time.perf_counter() - t1
    data = response.model_dump()
    summary = (data.get("message") or {}).get("content", "").strip()

    prompt_eval_count = data.get("prompt_eval_count") or 0
    eval_count = data.get("eval_count") or 0
    prompt_eval_sec = _ns_to_sec(data.get("prompt_eval_duration"))
    eval_sec = _ns_to_sec(data.get("eval_duration"))

    return {
        "query": query,
        "sections": len(sections),
        "section_chars": sum(len(s) for s in sections),
        "build_sections_sec": round(build_sec, 4),
        "prompt_chars": prompt_chars,
        "prompt_rough_tokens": _rough_tokens(system_prompt) + _rough_tokens(user_prompt),
        "ollama_wall_sec": round(wall_chat_sec, 4),
        "ollama_total_sec": _ns_to_sec(data.get("total_duration")),
        "ollama_load_sec": _ns_to_sec(data.get("load_duration")),
        "ollama_prompt_eval_sec": prompt_eval_sec,
        "ollama_eval_sec": eval_sec,
        "prompt_eval_count": prompt_eval_count,
        "eval_count": eval_count,
        "prompt_eval_tok_per_sec": round(prompt_eval_count / prompt_eval_sec, 2) if prompt_eval_sec else None,
        "eval_tok_per_sec": round(eval_count / eval_sec, 2) if eval_sec else None,
        "summary_chars": len(summary),
        "summary_words": len(summary.split()),
        "summary_rough_tokens": _rough_tokens(summary),
        "summary_preview": summary[:240],
        "end_to_end_sec": round(build_sec + wall_chat_sec, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Gemma memory-librarian stages.")
    parser.add_argument("--assistant-name", default="Jane")
    parser.add_argument("--conversation-summary", default="")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("queries", nargs="+")
    args = parser.parse_args()

    all_runs = []
    for query in args.queries:
        runs = [run_once(query, args.conversation_summary, args.assistant_name) for _ in range(args.repeat)]
        all_runs.append({
            "query": query,
            "runs": runs,
            "avg": {
                "build_sections_sec": round(mean(r["build_sections_sec"] for r in runs), 4),
                "ollama_wall_sec": round(mean(r["ollama_wall_sec"] for r in runs), 4),
                "ollama_total_sec": round(mean(r["ollama_total_sec"] for r in runs), 4),
                "ollama_load_sec": round(mean(r["ollama_load_sec"] for r in runs), 4),
                "ollama_prompt_eval_sec": round(mean(r["ollama_prompt_eval_sec"] for r in runs), 4),
                "ollama_eval_sec": round(mean(r["ollama_eval_sec"] for r in runs), 4),
                "prompt_rough_tokens": round(mean(r["prompt_rough_tokens"] for r in runs), 1),
                "summary_rough_tokens": round(mean(r["summary_rough_tokens"] for r in runs), 1),
                "end_to_end_sec": round(mean(r["end_to_end_sec"] for r in runs), 4),
            },
        })

    print(json.dumps({
        "model": LIBRARIAN_MODEL,
        "repeat": args.repeat,
        "results": all_runs,
    }, indent=2))


if __name__ == "__main__":
    main()
