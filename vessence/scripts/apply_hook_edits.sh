#!/bin/bash
# One-time script to apply the code map enforcement + Agent matcher edits.
# Run this from any terminal: bash ~/ambient/vessence/scripts/apply_hook_edits.sh

set -e

SETTINGS="$HOME/.claude/settings.json"
HOOK="$HOME/.claude/hooks/read_discipline_hook.py"

echo "=== 1/2: Adding Agent to PreToolUse matcher in settings.json ==="
if grep -q '"Read|Edit|Grep|Glob"' "$SETTINGS"; then
    sed -i 's/"Read|Edit|Grep|Glob"/"Read|Edit|Grep|Glob|Agent"/' "$SETTINGS"
    echo "  Done."
elif grep -q '"Read|Edit|Grep|Glob|Agent"' "$SETTINGS"; then
    echo "  Already patched."
else
    echo "  WARNING: Could not find expected matcher string. Manual edit needed."
fi

echo "=== 2/2: Adding Agent handler to read_discipline_hook.py ==="
if grep -q 'tool_name == "Agent"' "$HOOK"; then
    echo "  Already patched."
else
    # Insert the Agent block before the Grep/Glob block
    python3 - "$HOOK" << 'PYEOF'
import sys

hook_file = sys.argv[1]
with open(hook_file, 'r') as f:
    content = f.read()

AGENT_BLOCK = '''    # ── Agent calls: block if code map not read yet ─────────────────────────
    if tool_name == "Agent":
        prompt = tool_input.get("prompt", "")
        subagent_type = tool_input.get("subagent_type", "")
        is_code_search = subagent_type in ("Explore", "") and any(
            kw in prompt.lower()
            for kw in ("search", "find", "look", "check", "grep", "explore", "where", "how does", "how do")
        )
        if is_code_search:
            maps_read = state.get("code_maps_read", {})
            if not maps_read:
                _save_state(state)
                print(json.dumps({
                    "decision": "block",
                    "reason": (
                        "BLOCKED — read `configs/CODE_MAP_CORE.md` (or the relevant code map) before "
                        "launching an Agent to search the codebase. Use the map to locate files and "
                        "line ranges first, then either read directly or give the agent precise targets."
                    )
                }))
                return
        _save_state(state)
        print(json.dumps({"decision": "approve"}))
        return

'''

marker = '    # ── Track Grep/Glob calls + enforce Rule #3 (Code-map-first) ───────────\n'
if marker in content:
    content = content.replace(marker, AGENT_BLOCK + marker)
    with open(hook_file, 'w') as f:
        f.write(content)
    print("  Done.")
else:
    print("  WARNING: Could not find insertion marker. Manual edit needed.")
PYEOF
fi

echo ""
echo "All done. Changes take effect on the next Claude Code session."
