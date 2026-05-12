# Memory Verification Report — 2026-05-12 02:21

Checked: 20 | Stale: 10 | Fixed: 1 | Deleted: 0 | Errors: 17 | Skipped recent: 18

- **UPDATED** `9e243ef8-c9f` — Verified against the actual code: Codex's PARTIAL verdict is correct. list_available_essences() scans both _get_tools_dir() and _get_essences_dir(); runtime.load_essence() in _auto_load_essences is wrapped in a swallowing try/except; EssenceRuntime is initialized with TOOLS_DIR (legacy alias for SKILLS_DIR per jane/config.py:45); and the HTTP load/unload endpoints at lines 4158-4203 only call essence_loader functions and CapabilityRegistry, never EssenceRuntime.
- **ERROR** `901db7e5-f64` — parse_fail: You've hit your limit · resets 6am (America/New_York)
- **ERROR** `b7681cc2-e5c` — parse_fail: You've hit your limit · resets 6am (America/New_York)
- **ERROR** `37c3c677-9fe` — parse_fail: You've hit your limit · resets 6am (America/New_York)
- **ERROR** `707720f5-659` — parse_fail: You've hit your limit · resets 6am (America/New_York)
- **ERROR** `07699ebf-cd6` — parse_fail: You've hit your limit · resets 6am (America/New_York)
- **ERROR** `032cc1f6-19b` — parse_fail: You've hit your limit · resets 6am (America/New_York)
- **ERROR** `78a2c726-e5d` — parse_fail: You've hit your limit · resets 6am (America/New_York)
- **ERROR** `be4829ec-937` — parse_fail: You've hit your limit · resets 6am (America/New_York)
- **ERROR** `c1874433-4b9` — parse_fail: You've hit your limit · resets 6am (America/New_York)
