"""FORCE_STAGE3 — explicit user escalation to Stage 3 brain.

Triggered when the user deliberately asks Jane for careful/deep thinking.
Maps to "others" in the pipeline so Stage 2 is skipped entirely and
v1's full brain (Opus/Claude) handles the turn. A phrase-level
override in stage1_classifier guarantees these phrases win even
when another class's embedding matches loosely.

Exemplars are IMPERATIVES directed at Jane, not third-person statements
about thinking. Third-person / passing mentions of "think" / "careful"
should route to DELEGATE_OPUS, not here.
"""

CLASS_NAME = "FORCE_STAGE3"
NEEDS_LLM = False

EXAMPLES = [
    "Jane, think deeply about this",
    "Jane think deeply",
    "I want you to think carefully on this one",
    "please think carefully before answering",
    "Jane, think hard about this problem",
    "Jane really think about this",
    "take your time Jane and think it through",
    "use your deeper reasoning on this",
    "Jane use the big brain on this",
    "Jane let the smart one answer",
    "escalate this to Opus please",
    "escalate this to your main brain",
    "don't rush Jane, think this through",
    "Jane actually reason about this",
    "Jane give this some real thought",
    "think step by step Jane about this question",
    "Jane use your full brain on this",
    "Jane this needs careful thought from you",
    "please reason deeply about my question",
    "Jane ponder this carefully",
    "use stage 3 for this",
    "Jane use stage 3 on this",
    "route this to stage 3",
    "send this to stage 3",
    "stage 3 please",
]

CONTEXT = None
