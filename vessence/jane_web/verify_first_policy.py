"""verify_first_policy.py — enforce tool-use evidence on code/debug questions.

When the user asks something that requires reading or running code
("why does X happen", "check the stage3 log", "is there a handler for
Y"), the Opus brain sometimes guesses from its training data instead of
actually grepping the repo. Codex flagged this as an enforcement
problem, not a prompting problem.

This module provides:

  1. `needs_verification(prompt)` — classifies a prompt as a code /
     debug / system question that demands real tool evidence.

  2. `STRONGER_VERIFY_INSTRUCTION` — a paragraph to append to the Opus
     system prompt when `needs_verification` is True, telling Opus it
     MUST call a tool before committing an answer.

  3. `ToolUseCounter` — tiny observer that wraps an `on_tool_use`
     callback and counts invocations for the current turn. The pipeline
     checks the count after the stream finishes; if zero, the turn is
     flagged as UNVERIFIED in the FIFO for later audit.

Out of scope (for now): the non-streaming retry loop. It would buffer
the full response, check evidence, and re-invoke Opus on failure, but
kills the streaming UX. Start with stronger prompting + post-turn
flagging; ratchet to a retry if observation shows the flag firing often.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ── Classifier ────────────────────────────────────────────────────────────────
#
# Keep deliberately narrow: only fire for questions that CLEARLY require
# looking at the codebase or logs. Conversational chat, creative writing,
# math, weather, general knowledge — all skip.

_CODE_TRIGGER_RE = re.compile(
    r"""(
        # Repo / code inspection
        \bread(?:\s+the)?\s+code\b | \blook\s+at\s+the\s+code\b | \bcheck\s+the\s+code\b
      | \btrace\b | \bwalk\s+through\b | \bgrep\b | \bsearch\s+the\s+repo\b
      | \bsearch\s+the\s+codebase\b | \bin\s+the\s+codebase\b
      | \bwhat\s+does\s+\w+\s+(?:do|return|emit)\b
        # "show me the X handler" / "the code" / "the function" etc.
      | \bshow\s+me\s+the\s+(?:\w+\s+)*(?:code|function|implementation|file|handler|class|method|module)\b
      | \bwhere\s+is\s+\w+(?:\s+defined|\s+handled|\s+called)?\b
        # "how does X work" allowing multi-word X
      | \bhow\s+does\s+(?:\w+\s+){1,6}work\b
      | \bwhich\s+file\b | \bwhat\s+file\b | \bwhat\s+function\b

        # Debugging — broader "why X verb" pattern so
        # "why does the timer fail" and "why is Jane crashing" both trigger
      | \bwhy\s+(?:is|isn'?t|does|doesn'?t|did|didn'?t|was|wasn'?t|were|weren'?t)\b
      | \b(?:fix|debug)\s+(?:this|the)\s+(?:bug|issue|error|crash|problem)\b
      | \broot\s+cause\b
      | \bwhat('?s|\s+is)\s+(?:happening|going\s+wrong|the\s+bug|the\s+issue)\b
      | \b(?:failing|broken|crashing|not\s+working)\s+(?:with|on|in|because)\b

        # System / log inspection
      | \bcheck\s+the\s+logs?\b | \bread\s+the\s+logs?\b | \btail\s+the\s+logs?\b
      | \blook\s+at\s+the\s+logs?\b
      | \bwhat\s+does\s+the\s+logs?\s+say\b
      | \bsystemd\b | \bcron(?:tab)?\b | \bjournalctl\b
      | \bcurl\s+(?:-s\s+)?(?:http|localhost)

        # File contents — allow path separators in filenames
      | \bwhat'?s\s+in\s+[\w/.\-]+\.\w+
      | \bread\s+[\w/.\-]+\.\w+
      | \b(?:configs?|settings?|\.env)\s+(?:file|contents?)\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)


_MEMORY_TRIGGER_RE = re.compile(
    r"""(
        # Prior decisions / remembered context
        \bwhat\s+(?:did|have)\s+we\s+(?:decide|decided|say|said|talked?\s+about)\b
      | \bwhat\s+were\s+we\s+(?:doing|working\s+on|talking\s+about)\b
      | \bwhat\s+was\s+the\s+(?:plan|decision|conclusion|reason)\b
      | \b(?:previously|earlier|last\s+time|before|in\s+the\s+past)\b
      | \b(?:remember|do\s+you\s+remember|recall)\b

        # Explicit memory / transcript / history requests
      | \b(?:memory|memories|chroma|long[-\s]?term|short[-\s]?term)\b
      | \b(?:transcript|conversation\s+history|android\s+transcript)\b
      | \b(?:stale\s+memor(?:y|ies)|memory\s+audit|flag\s+the\s+memor(?:y|ies))\b

        # Vessence/Jane operational history or design claims
      | \b(?:how\s+we\s+built|how\s+we\s+designed|why\s+we\s+changed)\b
      | \b(?:vessence|jane)\s+(?:operation|architecture|design|pipeline|stage\s*[123])\b
      | \b(?:classifier|stage\s*1|stage\s*2|stage\s*3)\s+(?:idea|plan|design|discussion)\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)


_EMPTY_MEMORY_SENTINELS = {
    "",
    "No relevant context found.",
    "No memories stored yet.",
}


@dataclass(frozen=True)
class EvidenceRequirements:
    code: bool = False
    memory: bool = False

    @property
    def any(self) -> bool:
        return self.code or self.memory

    def labels(self) -> list[str]:
        out: list[str] = []
        if self.code:
            out.append("code/log")
        if self.memory:
            out.append("Chroma memory")
        return out


def needs_verification(prompt: str) -> bool:
    """Return True if the prompt requires real tool evidence.

    Matches debug/code-inspection phrasings. Rejects casual chat,
    creative, or lookup-style asks that don't need repo access.
    """
    if not prompt:
        return False
    return bool(_CODE_TRIGGER_RE.search(prompt))


def needs_memory_evidence(prompt: str) -> bool:
    """Return True if the prompt needs historical/memory evidence."""
    if not prompt:
        return False
    return bool(_MEMORY_TRIGGER_RE.search(prompt))


def classify_evidence_requirements(prompt: str) -> EvidenceRequirements:
    """Classify which evidence sources are required for this turn."""
    return EvidenceRequirements(
        code=needs_verification(prompt),
        memory=needs_memory_evidence(prompt),
    )


def has_meaningful_memory(memory_text: str | None) -> bool:
    """True when a Chroma lookup produced usable context."""
    text = (memory_text or "").strip()
    if text in _EMPTY_MEMORY_SENTINELS:
        return False
    if text.startswith("Error:") or text.startswith("Librarian Error:"):
        return False
    return bool(text)


# ── Prompt-side enforcement ──────────────────────────────────────────────────

STRONGER_VERIFY_INSTRUCTION = (
    "<verify_first priority=\"critical\">\n"
    "This turn's user question is a code / log / system question. You MUST "
    "invoke at least one evidence-gathering tool (Read, Grep, Glob, Bash, "
    "WebFetch, WebSearch, or Agent) BEFORE committing an answer. Reading "
    "the code is cheap; guessing wrong is expensive.\n\n"
    "Concrete examples of what to do first — pick whichever fits the "
    "question, then answer from what you actually read:\n"
    "  - \"why does <feature> fail?\" → Grep for the feature name, then "
    "Read the handler file. e.g. `Grep(pattern=\"send_message\", "
    "type=\"py\")`\n"
    "  - \"what does <function> do?\" → Read the file that defines it. "
    "e.g. `Read(\"/home/chieh/ambient/vessence/jane_web/jane_v2/"
    "stage2_dispatcher.py\")`\n"
    "  - \"is <log/metric> healthy?\" → Tail the log. e.g. "
    "`Bash(\"tail -50 /home/chieh/ambient/vessence-data/logs/jane_web.log\")`\n\n"
    "Hard rules:\n"
    "- Do NOT guess from training memory of the repo. You have not seen "
    "today's version of these files.\n"
    "- Do NOT hedge with 'most likely', 'probably', 'I think', or 'my "
    "guess'. If you're about to write one of those phrases, that's your "
    "cue to call a tool instead.\n"
    "- If after reading the actual code you still aren't certain, say so "
    "plainly and list the specific files or signals you'd need next.\n"
    "- A one-token tool call just to clear this block is not acceptable. "
    "The tool call must plausibly surface the evidence needed.\n"
    "</verify_first>"
)


MEMORY_VERIFY_INSTRUCTION = (
    "<memory_verify priority=\"critical\">\n"
    "This turn's question depends on prior conversation, Chroma memory, or "
    "Vessence/Jane historical design context. You MUST ground the answer "
    "in Chroma evidence, not vague recollection.\n\n"
    "If a [REQUIRED CHROMA MEMORY EVIDENCE] block is present below, cite "
    "from it directly. If it is missing or insufficient, query Chroma "
    "yourself first — concrete examples:\n"
    "  - `Bash(\"python /home/chieh/ambient/vessence/startup_code/"
    "query_live_memory.py 'your query here'\")`\n"
    "  - `Bash(\"curl -s 'http://127.0.0.1:8083/query?q=your+query'\")` "
    "(memory daemon, ~0.5s)\n"
    "  - `Bash(\"python /home/chieh/ambient/vessence/agent_skills/"
    "search_memory.py 'your query'\")`\n\n"
    "Hard rules:\n"
    "- Do NOT answer from vague recollection.\n"
    "- If Chroma has no relevant hit, say that plainly, then fall back to "
    "code/log inspection where applicable.\n"
    "- Do NOT hedge with 'I think we decided...' — if you think it, look "
    "it up first.\n"
    "</memory_verify>"
)


def instruction_for_requirements(req: EvidenceRequirements) -> str:
    parts: list[str] = []
    if req.code:
        parts.append(STRONGER_VERIFY_INSTRUCTION)
    if req.memory:
        parts.append(MEMORY_VERIFY_INSTRUCTION)
    return "".join(parts)


# ── Tool-use observer ────────────────────────────────────────────────────────

class ToolUseCounter:
    """Wraps an existing on_tool_use callback and counts invocations.

    Usage:
        counter = ToolUseCounter(original_callback)
        manager.run_turn(..., on_tool_use=counter)
        ...
        if counter.count == 0 and needs_verification(prompt):
            logger.warning("...")

    The counter is stateless outside of .count, safe to reuse only if
    explicitly reset. In practice: instantiate per-turn.
    """

    def __init__(self, passthrough=None) -> None:
        self.count = 0
        self.names: list[str] = []
        self._passthrough = passthrough

    _NAME_CAP = 10  # keep the names list bounded for audit payload size

    def __call__(self, *args, **kwargs):
        self.count += 1
        # Callbacks in jane_proxy vary by provider: sometimes
        # (name, args) tuple, sometimes a single string. Record whatever
        # we can as a bare name for audit logs, capped to _NAME_CAP.
        if args and len(self.names) < self._NAME_CAP:
            first = args[0]
            if isinstance(first, str):
                self.names.append(first[:40])
            else:
                self.names.append(str(first)[:40])
        if self._passthrough is not None:
            try:
                return self._passthrough(*args, **kwargs)
            except Exception as e:
                logger.warning("verify_first: passthrough callback raised: %s", e)
        return None


def summarize_verification_status(
    prompt: str,
    counter: ToolUseCounter,
    memory_evidence: bool = False,
) -> dict:
    """Produce a small dict the pipeline can attach to the FIFO record.

    Keys:
      needed         — was verification required?
      tool_calls     — count of tool invocations during the turn
      tools_used     — names of tools invoked (truncated list)
      verified       — needed AND tool_calls > 0
      flagged        — needed AND tool_calls == 0 (possible hallucination)
    """
    req = classify_evidence_requirements(prompt)
    return {
        "needed": req.any,
        "requires_code": req.code,
        "requires_memory": req.memory,
        "tool_calls": counter.count,
        "tools_used": counter.names[:10],
        "memory_evidence": memory_evidence,
        "verified": ((not req.code) or counter.count > 0)
        and ((not req.memory) or memory_evidence),
        "flagged": (req.code and counter.count == 0)
        or (req.memory and not memory_evidence),
    }
