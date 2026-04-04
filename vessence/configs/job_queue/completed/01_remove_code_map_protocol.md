# Job: Remove CODE_MAP_PROTOCOL from every request's system prompt
Status: completed
Priority: 2
Created: 2026-03-27

## Objective
Remove the `CODE_MAP_PROTOCOL` text (~450 chars, ~110 tokens) from the default system prompt sections, since code map injection is disabled. This saves ~110 tokens on every single request.

## Context
In `jane/context_builder.py`, line 519 unconditionally includes `CODE_MAP_PROTOCOL` in the system prompt:
```python
system_sections = [BASE_SYSTEM_PROMPT, CODE_MAP_PROTOCOL]
```
But code map injection itself is commented out (lines 548-553). The protocol instructions tell the LLM how to use a code map it will never receive — pure token waste.

## Pre-conditions
None.

## Steps
1. In `jane/context_builder.py`, change line 519 from:
   ```python
   system_sections = [BASE_SYSTEM_PROMPT, CODE_MAP_PROTOCOL]
   ```
   to:
   ```python
   system_sections = [BASE_SYSTEM_PROMPT]
   ```
2. Do NOT delete the `CODE_MAP_PROTOCOL` constant — keep it defined so it can be re-enabled later if code map injection is turned back on.
3. If code map injection is ever re-enabled (the commented block at lines 548-553), `CODE_MAP_PROTOCOL` should be added back to `system_sections` at that time, gated on `profile.include_code_map`.

## Verification
1. Restart jane-web service
2. Send a test message on the web UI
3. Check the prompt dump log: `tail -1 $VESSENCE_DATA_HOME/logs/jane_prompt_dump.jsonl | python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(d['system_prompt_chars'])"` — should be ~450 chars smaller than before
4. Verify the response still works normally

## Files Involved
- `jane/context_builder.py` (line 519)

## Notes
- The constant `CODE_MAP_PROTOCOL` is defined at line 42-54 — leave it in place.
- This is a token optimization identified during an audit of the request pipeline. Average system prompt was 657 chars; this removes ~450 of those on non-project-work requests.
