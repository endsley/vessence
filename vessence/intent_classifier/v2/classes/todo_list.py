"""TODO_LIST — read-back of Chieh's personal task/errand list.

Sourced from a Google Doc, mirrored to $VESSENCE_DATA_HOME/todo_list_cache.json
every 30 min. The Stage 2 handler asks "which category?" and routes the
follow-up reply back to itself via STAGE2_FOLLOWUP.

EXAMPLES discipline (after adversarial pass):
  - Every positive exemplar mentions 'todo' / 'to-do' / 'to do' /
    'task(s)' / 'errand(s)' — NEVER bare 'my list'. Generic 'my X list'
    is a proven false-positive magnet (wish list, reading list, etc.).
  - Always framed as a READ action. Edit/add phrasings route to
    DELEGATE_OPUS (see contrast exemplars there).
  - No Ambient-project mentions here — those belong on Stage 3.
  - Category-filtered reads (home/students/urgent) still require an
    explicit task/to-do/errand word, not just the category name.
  - Do NOT train on personal/domain-specific nouns. They are broad anchors
    and can pull vague questions into TODO_LIST through Chroma similarity.
"""

CLASS_NAME = "TODO_LIST"
NEEDS_LLM = False

EXAMPLES = [
    # Core read phrasings — every one anchors on todo/to-do/task/errand.
    "what's on my to do list",
    "what's on my todo list",
    "what's on my to-do list",
    "what's on my todo",
    "what's on my to-do",
    "read me my to do list",
    "read me my todo list",
    "read me my to-do list",
    "read my to do list",
    "read my todo list",
    "read my task list",
    "read my tasks",
    "show me my to-do list",
    "show me my todo list",
    "show me my tasks",
    "show my todo list",
    "go through my todo list",
    "go through my to do list",
    "run through my todo list",
    "run through my to-do",
    "let's go through my to-do",
    "catch me up on my todo",
    "catch me up on my tasks",
    "tell me what's on my todo",
    "tell me what's on my to-do list",
    "what's left on my to do",
    "what's left on my todo",
    "what's left on my todo list",
    "what's pending on my todo",
    "what's still on my todo",

    # Pending-task / errand phrasings — all must be questions about the
    # list as a whole, not "I already did X" style completion statements.
    "what tasks are on my todo",
    "what tasks are pending on my todo",
    "any pending tasks on my todo list",
    "what pending tasks are on my todo",
    "what errands do I have on my todo",
    "what errands are left on my todo",
    "what errands are still on my todo list",
    "what do I need to do on my todo today",
    "what's urgent on my todo list",
    "what's immediate on my to-do",
    "what's urgent on my to-do",

    # Category-filtered reads — all include an explicit task/to-do/errand anchor.
    # Generic todo-list density replaces older personal/domain-specific
    # positives; category routing is handled by Stage 2 context or follow-up.
    "what's on my todo list today",
    "what's on my todo list for today",
    "what is on my todo list today",
    "what do I have on my todo list today",
    "what tasks are on my todo list today",
    "what pending tasks are on my todo list today",
    "what errands are on my todo list today",
    "what's still on my todo list today",
    "what's left on my todo list today",
    "what should I do from my todo list today",
    "what's on my todo for home",
    "what's on my todo for the house",
    "what tasks do I have for the house",
    "what tasks do I have for home",
    "what household tasks are on my todo",
    "what home tasks are on my todo",
    "what tasks do I have for my students",
    "what tasks do I have for the students",
    "what's on my todo for my students",
    "what's on my todo for the students",
    "any student tasks left on my todo",
    "what student tasks are on my todo",
    "urgent tasks on my todo",
    "anything urgent on my todo list",
    "what urgent tasks are on my todo",

    # "run through" / "catch me up" / "go through" framings.
    "catch me up on my todo",
    "catch me up on my todo list",
    "catch me up on my tasks",
    "catch me up on my task list",
    "catch me up on my errands",
    "run through my to-do",
    "run through my to do list",
    "run through my todo",
    "run through my tasks",
    "run through my task list",
    "go through my todo",
    "go through my todo list",
    "go through my tasks",
    "go through my task list",
    "walk me through my todo",
    "walk me through my tasks",
]

CONTEXT = """\
The user wants to READ their personal TODO list — errands, clinic work,
home chores, student tasks, or general pending items. This is a
read-only query against a mirrored Google Doc; Jane does not edit the
list here.

Output exactly:
CLASSIFICATION: TODO_LIST
CATEGORY: <optional category name if the user mentioned one — "clinic",
"home", "students", "urgent" — else empty>"""
