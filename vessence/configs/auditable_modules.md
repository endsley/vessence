# Auditable Modules

Modules the nightly code auditor is allowed to inspect, test, and patch.

The auditor rotates through this list one entry per night. Each module has:
- **path**: file to audit
- **spec**: where the intended behavior is documented
- **safety_level**: `safe` (small, isolated) | `careful` (touches integrations) | `skip` (don't audit yet)

## Whitelisted modules

| Path | Spec | Safety |
|---|---|---|
| `jane_web/jane_v2/classes/greeting/handler.py` | `configs/v2_3stage_pipeline.md` | safe |
| `jane_web/jane_v2/classes/send_message/handler.py` | `CLAUDE.md` SMS Protocols | careful |
| `jane_web/jane_v2/classes/read_messages/handler.py` | docstring | safe |
| `jane_web/jane_v2/classes/shopping_list/handler.py` | docstring | safe |
| `jane_web/jane_v2/classes/weather/handler.py` | docstring | safe |
| `jane_web/jane_v2/classes/music_play/handler.py` | docstring | careful |
| `jane_web/jane_v2/stage1_classifier.py` | `configs/v2_3stage_pipeline.md` | safe |
| `jane_web/jane_v2/stage2_dispatcher.py` | docstring | safe |
| `jane_web/jane_v2/recent_context.py` | docstring | safe |
| `intent_classifier/v2/classifier.py` | `configs/v2_3stage_pipeline.md` | careful |
| `agent_skills/sms_helpers.py` | docstring | careful |
| `agent_skills/shopping_list.py` | docstring | safe |
| `vault_web/recent_turns.py` | docstring | safe |

## Hard skip — never audit autonomously

- `CLAUDE.md` (config, human-curated)
- `jane_web/jane_proxy.py` (1500+ lines, load-bearing)
- `jane_web/main.py` (FastAPI app entry, breaks everything if wrong)
- `vault_web/database.py` (schema migrations need human review)
- Anything in `android/` (requires APK rebuild)
- Anything in `startup_code/` (system integration)
