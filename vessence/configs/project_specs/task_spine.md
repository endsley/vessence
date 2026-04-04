# Task Spine

This file defines the anti-drift rule for long-running Jane/Codex sessions.

## Rule

There is always one primary spine for the session:

1. the main goal
2. the current step on that goal
3. the next steps after that

Side requests do not replace the spine unless the user explicitly says they are now the main priority.

## Enforcement

- Persistent state lives in:
  - `$VESSENCE_DATA_HOME/data/task_spine.json`
  - `$VESSENCE_DATA_HOME/data/interrupt_stack.json`
- The helper module is:
  - `jane/task_spine.py`
- When a side task begins, push the paused main step onto the interrupt stack.
- When the side task ends, pop the stack and resume the saved `return_to_step`.
- Status replies should be derived from the task spine, not from loose recollection.

## Current Primary Spine

1. Finish the new Jane web memory design with a Python-owned conversation summary plus separate Qwen summary updater.
2. Move `vessence`, `vessence-data`, and `vault` into `~/ambient`.
3. Cut systemd and crontab over to the `~/ambient/...` roots.
4. Re-verify Jane and Amber on Discord and the website after the move.
5. Verify `vessences.com` and `jane.vessences.com` publicly; if broken, fix them.
