#!/usr/bin/env python3
import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/chieh/ambient/vessence")

from agent_skills.memory.v1.memory_retrieval import build_memory_sections


def build_prompts(query: str, sections: list[str], conversation_summary: str, assistant_name: str) -> tuple[str, str]:
    facts_block = "\n\n".join(sections)
    now_str = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")
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


def rough_tokens(text: str) -> int:
    return round(len(text) / 4)


def section_stats(section: str) -> dict:
    header, _, body = section.partition("\n")
    lines = [line for line in body.splitlines() if line.strip()]
    return {
        "header": header,
        "chars": len(section),
        "rough_tokens": rough_tokens(section),
        "entries": len(lines),
        "preview": body[:700],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect the exact prompt sent to the memory librarian.")
    parser.add_argument("query")
    parser.add_argument("--assistant-name", default="Jane")
    parser.add_argument("--conversation-summary", default="")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    sections = build_memory_sections(args.query)
    system_prompt, user_prompt = build_prompts(
        args.query,
        sections,
        args.conversation_summary,
        args.assistant_name,
    )

    report = {
        "query": args.query,
        "assistant_name": args.assistant_name,
        "conversation_summary_chars": len(args.conversation_summary),
        "conversation_summary_rough_tokens": rough_tokens(args.conversation_summary),
        "system_prompt_chars": len(system_prompt),
        "system_prompt_rough_tokens": rough_tokens(system_prompt),
        "user_prompt_chars": len(user_prompt),
        "user_prompt_rough_tokens": rough_tokens(user_prompt),
        "total_prompt_chars": len(system_prompt) + len(user_prompt),
        "total_prompt_rough_tokens": rough_tokens(system_prompt) + rough_tokens(user_prompt),
        "section_count": len(sections),
        "sections": [section_stats(s) for s in sections],
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
    }

    pretty = []
    pretty.append("# Librarian Input Inspection")
    pretty.append("")
    pretty.append(f"Query: {args.query}")
    pretty.append(f"Assistant: {args.assistant_name}")
    pretty.append("")
    pretty.append("## Prompt Sizes")
    pretty.append(f"- Conversation summary: {report['conversation_summary_chars']} chars (~{report['conversation_summary_rough_tokens']} tokens)")
    pretty.append(f"- System prompt: {report['system_prompt_chars']} chars (~{report['system_prompt_rough_tokens']} tokens)")
    pretty.append(f"- User prompt: {report['user_prompt_chars']} chars (~{report['user_prompt_rough_tokens']} tokens)")
    pretty.append(f"- Total prompt: {report['total_prompt_chars']} chars (~{report['total_prompt_rough_tokens']} tokens)")
    pretty.append("")
    pretty.append("## Section Breakdown")
    for idx, sec in enumerate(report["sections"], start=1):
        pretty.append(f"{idx}. {sec['header']}")
        pretty.append(f"   chars: {sec['chars']} | rough tokens: {sec['rough_tokens']} | entries: {sec['entries']}")
        pretty.append("   preview:")
        pretty.append(sec["preview"])
        pretty.append("")
    pretty.append("## Full System Prompt")
    pretty.append(system_prompt)
    pretty.append("")
    pretty.append("## Full User Prompt")
    pretty.append(user_prompt)
    pretty_text = "\n".join(pretty).strip() + "\n"

    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(pretty_text, encoding="utf-8")
        print(str(path))
        return

    print(pretty_text)


if __name__ == "__main__":
    main()
