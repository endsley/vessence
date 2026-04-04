import os
import re

try:
    import ollama
except ImportError:
    ollama = None

from agent_skills.web_search_utils import web_search
from jane.config import LOCAL_LLM_MODEL


RESEARCH_HINTS = (
    "research",
    "look up",
    "search",
    "find out",
    "what does the documentation say",
    "latest docs",
    "compare",
)

RESEARCH_VERBS = (
    "research",
    "look up",
    "search",
    "find out",
    "browse",
    "google",
    "check online",
    "check the web",
    "search the web",
    "search online",
)

RESEARCH_OBJECTS = (
    "documentation",
    "docs",
    "latest",
    "release notes",
    "pricing",
    "spec",
    "specs",
    "api",
    "official site",
    "official docs",
)


def should_offload_research(message: str) -> bool:
    lowered = (message or "").lower()
    if any(hint in lowered for hint in RESEARCH_HINTS):
        return True
    if any(verb in lowered for verb in RESEARCH_VERBS) and any(obj in lowered for obj in RESEARCH_OBJECTS):
        return True
    if re.search(r"\b(latest|current|recent)\b", lowered) and re.search(r"\b(docs|documentation|api|pricing|specs?)\b", lowered):
        return True
    return False


def run_research_offload(message: str) -> str:
    raw_results = web_search(message, max_results=6)
    if not raw_results.strip():
        return ""

    system_prompt = (
        "You are Jane's local research analyst running on gemma4:e4b. "
        "Given raw web search results, produce a compact, high-confidence research brief. "
        "Prioritize official documentation and recent sources. "
        "Output plain text with these sections: Findings, Recommended Direction, Sources."
    )
    user_prompt = f"Research query:\n{message}\n\nRaw search results:\n{raw_results[:15000]}"

    try:
        response = ollama.chat(
            model=os.environ.get("JANE_RESEARCH_MODEL", LOCAL_LLM_MODEL),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response["message"]["content"].strip()
    except Exception:
        return ""
