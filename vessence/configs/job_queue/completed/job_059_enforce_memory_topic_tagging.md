# Job #59: Enforce Topic Tagging on All Memory Writes

Priority: 2
Status: completed
Created: 2026-03-30

## Description
Make the `--topic` flag required (not optional) on `add_fact.py` so every memory entry gets a topic tag. Memories without topics default to "General" which hurts retrieval — the embedding has no topic signal to match against.

### Changes
1. In `agent_skills/add_fact.py`: make `--topic` a required argument (error if missing)
2. Audit all callers of `add_fact.py` across the codebase (hooks, scripts, cron jobs, brain code) to ensure they pass `--topic`
3. Backfill existing topic-less memories in ChromaDB: query for entries where topic is None/"General" and infer a topic from the content (can use a local LLM for classification)

### Context
This was identified during a memory retrieval gap analysis. A memory about "switching from Claude to Gemini" had no topic set, making it harder to retrieve via semantic search. Enforcing topics improves recall across all memory tiers.

### Acceptance Criteria
- `add_fact.py` rejects calls without `--topic`
- All existing callers updated
- No topic-less entries remain in short_term_memory or user_memories collections

## Result
[ACK]Okay Chieh, a new task: enforcing memory topic tagging. Let me get the details and figure out a plan.[/ACK]This is a critical piece of the memory system. If turns are saved without a topic, they become invisible to the topic-based retrieval system. I'll investigate `conversation_manager.py` to
