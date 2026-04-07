# Job: Jane-to-Essence Tool Bridge — Talk to Jane to Manage Essences

Status: complete
Priority: 2
Created: 2026-03-22

## Objective
Allow users to configure and interact with any loaded essence by talking to Jane. Jane should be able to invoke essence tools (add_topic, remove_topic, etc.) on the user's behalf through natural conversation.

## Context
Essences like Daily Briefing have their own tools defined in `functions/custom_tools.py`. These tools exist as standalone Python functions but are not callable by Jane. When the user says "add AI research to my daily briefing," Jane currently can't do anything about it.

Key files:
- `essences/daily_briefing/functions/custom_tools.py` — has `add_topic()`, `remove_topic()`, `list_topics()`, `fetch_topic_news()`
- `essences/daily_briefing/manifest.json` — declares capabilities, interaction patterns, conversation starters
- `essences/daily_briefing/user_data/topics.json` — user's tracked topics (currently empty)

## Design

### Tool Discovery
On startup (or when essences change), Jane reads each loaded essence's `manifest.json` to discover:
- Available tools (from `functions/custom_tools.py`)
- Conversation starters (hints for what users can ask)
- Capabilities (what the essence provides)

### Tool Invocation Bridge
Jane needs a way to call essence functions. Options:
1. **Subprocess**: `python <essence_dir>/functions/custom_tools.py <function_name> <args_json>` — requires a CLI entry point in each custom_tools.py
2. **Direct import**: `importlib.import_module` the essence's custom_tools and call functions directly
3. **HTTP**: Each essence runs a lightweight API — overkill for now

Recommend option 1 (subprocess) for isolation. Add a `if __name__ == "__main__"` block to custom_tools.py that dispatches based on argv.

### Context Injection
When Jane's system prompt is built (in `context_builder.py`), include a section listing available essence tools:
```
## Available Essence Tools
### Daily Briefing
- add_topic(name, keywords, priority) — Add a topic to track
- remove_topic(name) — Stop tracking a topic
- list_topics() — Show all tracked topics
- fetch_topic_news(topic_name) — Get latest news for a topic
To use: run `python /home/chieh/ambient/essences/daily_briefing/functions/custom_tools.py <function> '<json_args>'`
```

### Conversation Flow
User: "Add AI research to my daily briefing"
Jane: [reads essence tools from context] → runs `add_topic("AI Research", ["AI", "LLM", "machine learning"])` → "Done. I've added 'AI Research' to your daily briefing. It'll track news about AI, LLM, and machine learning."

## Files Involved
- `jane/context_builder.py` — inject essence tools into system prompt
- `agent_skills/essence_loader.py` — already loads essences, extend to expose tool metadata
- Each essence's `functions/custom_tools.py` — add CLI entry point
- `essences/daily_briefing/functions/custom_tools.py` — first essence to wire up

## Notes
- This is the first step of the "Jane as orchestrator" architecture
- Start with Daily Briefing as the proof-of-concept, then generalize
- The tool list should update dynamically when essences are loaded/unloaded
