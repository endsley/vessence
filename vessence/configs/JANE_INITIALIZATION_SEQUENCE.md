# Jane Initialization Sequence

This is the canonical wake-up sequence for Jane.

Goal: every new session should reconstruct the same core identity, priorities, and live memory context before substantive work begins.

## Intent

Jane does not rely on hidden continuity. She rebuilds herself from:

1. Identity documents in the vault root
2. Architecture and project source-of-truth docs
3. Live ChromaDB memory under `$VESSENCE_DATA_HOME/vector_db`
4. Active prompt queue state

## Startup Order

### 1. Re-establish identity

Read these first:

1. `$VAULT_HOME/documents/chieh_identity_essay.txt`
2. `$VAULT_HOME/documents/jane_identity_essay.txt`
3. `$VESSENCE_DATA_HOME/user_profile.md` if present

### 2. Re-establish architecture

Read these next:

1. `$VESSENCE_HOME/configs/Jane_architecture.md`
2. `$VESSENCE_HOME/configs/memory_manage_architecture.md`
3. `$VESSENCE_HOME/configs/LLM_ARCHITECTURE.md`

### 3. Re-establish priorities

Read these next:

1. `$VESSENCE_HOME/configs/TODO_PROJECTS.md`
2. `$VESSENCE_HOME/configs/PROJECT_ACCOMPLISHMENTS.md`
3. `$VESSENCE_HOME/configs/project_specs/active_spec.md`
4. `$VESSENCE_HOME/configs/project_specs/current_task_state.json`
5. `$VAULT_HOME/documents/prompt_list.md`

### 4. Reconnect to live memory

The live memory root is:

- `$VESSENCE_DATA_HOME/vector_db`

Do not assume `$VESSENCE_HOME/vector_db` is the active store unless explicitly verified.

At startup, inspect:

1. `user_memories`
2. `short_term_memory`
3. `long_term_knowledge`

Recover both:

- high-level counts
- recent entries
- query-based recall for identity, current work, family/personal context, and technical priorities

### 5. Produce a startup summary

Before doing other work, mentally lock in:

- who Chieh is
- who Jane is
- current top project priorities
- what was recently being worked on
- any active unfinished prompts
- any memory-system or runtime caveats

## Bootstrap Command

Run:

```bash
PYTHONPATH="$VESSENCE_HOME" /home/chieh/google-adk-env/adk-venv/bin/python "$VESSENCE_HOME/startup_code/jane_bootstrap.py"
```

This script prints a compact startup digest from the live split-root data layout.

## Session Rule

If a new session begins and prior context is missing, restart from this sequence instead of guessing.
