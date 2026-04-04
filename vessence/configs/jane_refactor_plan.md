# Jane Core Files Refactor Plan
# Moving root-level source files to `jane/` subdirectory

Generated: 2026-03-17
Status: PENDING EXECUTION

---

## OBJECTIVE

Move 6 core Jane source files from `/home/chieh/vessence/` root into a new
`/home/chieh/vessence/jane/` subdirectory for cleaner project organization.

---

## FILES BEING MOVED

| From | To |
|------|----|
| `my_agent/config.py` | `my_agent/jane/config.py` |
| `my_agent/llm_config.py` | `my_agent/jane/llm_config.py` |
| `my_agent/services.py` | `my_agent/jane/services.py` |
| `my_agent/discord_bridge.py` | `my_agent/jane/discord_bridge.py` |
| `my_agent/jane_session_wrapper.py` | `my_agent/jane/jane_session_wrapper.py` |
| `my_agent/audit_wrapper.py` | `my_agent/jane/audit_wrapper.py` |

A new `my_agent/jane/__init__.py` (empty) must also be created to make `jane` a proper Python package.

---

## IMPORT RESOLUTION STRATEGY

All affected scripts already do:
```python
sys.path.insert(0, '/home/chieh/vessence')
```
This means Python looks in `/home/chieh/vessence/` first. After the move,
`config.py` no longer exists at root — it lives at `jane/config.py`.
Therefore ALL imports must change from:
- `from config import X` → `from jane.config import X`
- `from llm_config import X` → `from jane.llm_config import X`

The `jane/__init__.py` file makes `jane` a package, so `from jane.config import X` resolves to `my_agent/jane/config.py`. ✓

---

## COMPLETE CHANGE LIST

### STEP 1 — Create jane/ package
```bash
mkdir /home/chieh/vessence/jane
touch /home/chieh/vessence/jane/__init__.py
```

### STEP 2 — Move the 6 files
```bash
mv /home/chieh/vessence/config.py            /home/chieh/vessence/jane/
mv /home/chieh/vessence/llm_config.py        /home/chieh/vessence/jane/
mv /home/chieh/vessence/services.py          /home/chieh/vessence/jane/
mv /home/chieh/vessence/discord_bridge.py    /home/chieh/vessence/jane/
mv /home/chieh/vessence/jane_session_wrapper.py /home/chieh/vessence/jane/
mv /home/chieh/vessence/audit_wrapper.py     /home/chieh/vessence/jane/
```

### STEP 3 — Edit moved files (self-referential imports)

#### 3a. `jane/llm_config.py` — Line 3
```
BEFORE: from config import (
AFTER:  from jane.config import (
```

#### 3b. `jane/discord_bridge.py` — Lines 27-31
```
BEFORE: from config import (
AFTER:  from jane.config import (
```
Note: `sys.path.append(os.path.join(os.path.dirname(__file__), "amber"))` uses
`__file__` — after the move `__file__` will be `jane/discord_bridge.py`, so
this resolves to `jane/amber/` which does NOT exist. Must change to:
```python
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "amber"))
```

#### 3c. `jane/audit_wrapper.py` — Line 9
```
BEFORE: from config import LOGS_DIR
AFTER:  from jane.config import LOGS_DIR
```

#### 3d. `jane/jane_session_wrapper.py` — no config imports, NO CHANGE NEEDED

#### 3e. `jane/services.py` — no config imports, NO CHANGE NEEDED

#### 3f. `jane/config.py` — no imports of other moved files, NO CHANGE NEEDED

---

### STEP 4 — Edit amber/ files

#### 4a. `amber/logic/agent_logic.py` — Line 14
```
BEFORE: from llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
AFTER:  from jane.llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
```

#### 4b. `amber/agent.py` — Lines 16-17
```
BEFORE: from llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
AFTER:  from jane.llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM

BEFORE: from config import VAULT_DIR as _VAULT_DIR, JANITOR_REPORT as _JANITOR_REPORT, CONFIGS_DIR as _CONFIGS_DIR
AFTER:  from jane.config import VAULT_DIR as _VAULT_DIR, JANITOR_REPORT as _JANITOR_REPORT, CONFIGS_DIR as _CONFIGS_DIR
```

#### 4c. `amber/tools/vault_tools.py` — Line 17
```
BEFORE: from config import VAULT_DIR
AFTER:  from jane.config import VAULT_DIR
```

---

### STEP 5 — Edit agent_skills/ files

#### 5a. `agent_skills/research_assistant.py` — Line 9
```
BEFORE: from llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
AFTER:  from jane.llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
```

#### 5b. `agent_skills/local_vector_memory.py` — Line 35
```
BEFORE: from llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
AFTER:  from jane.llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
```

#### 5c. `agent_skills/add_fact.py` — Line 43
```
BEFORE: from config import VECTOR_DB_USER_MEMORIES, CHROMA_COLLECTION_USER_MEMORIES
AFTER:  from jane.config import VECTOR_DB_USER_MEMORIES, CHROMA_COLLECTION_USER_MEMORIES
```

#### 5d. `agent_skills/conversation_manager.py` — Line 14
```
BEFORE: from config import (
AFTER:  from jane.config import (
```
(11 imported symbols — only the `from` line changes, symbol list is unchanged)

#### 5e. `agent_skills/prompt_queue_runner.py` — Line 28
```
BEFORE: from config import (
AFTER:  from jane.config import (
```
(20 imported symbols — only the `from` line changes)

#### 5f. `agent_skills/qwen_orchestrator.py` — Line 11
```
BEFORE: from llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
AFTER:  from jane.llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
```

#### 5g. `agent_skills/git_backup.py` — Line 14
```
BEFORE: from llm_config import LOCAL_LLM_MODEL as MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
AFTER:  from jane.llm_config import LOCAL_LLM_MODEL as MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
```

#### 5h. `agent_skills/search_memory.py` — Line 34
```
BEFORE: from config import (
AFTER:  from jane.config import (
```
(10 imported symbols — only the `from` line changes)

#### 5i. `agent_skills/qwen_query.py` — Line 7
```
BEFORE: from llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
AFTER:  from jane.llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
```

#### 5j. `agent_skills/add_forgettable_memory.py` — Line 51
```
BEFORE: from config import SHORT_TERM_TTL_DAYS as DEFAULT_TTL_DAYS, VECTOR_DB_SHORT_TERM as SHORT_TERM_DB_PATH, CHROMA_COLLECTION_SHORT_TERM
AFTER:  from jane.config import SHORT_TERM_TTL_DAYS as DEFAULT_TTL_DAYS, VECTOR_DB_SHORT_TERM as SHORT_TERM_DB_PATH, CHROMA_COLLECTION_SHORT_TERM
```

#### 5k. `agent_skills/research_analyzer.py` — Line 7
```
BEFORE: from llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
AFTER:  from jane.llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
```

#### 5l. `agent_skills/fallback_query.py` — Line 14
```
BEFORE: from llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
AFTER:  from jane.llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
```

#### 5m. `agent_skills/janitor_memory.py` — Line 13
```
BEFORE: from config import (
AFTER:  from jane.config import (
```
(9 imported symbols — only the `from` line changes)

#### 5n. `agent_skills/nightly_audit.py` — Line 23
```
BEFORE: from config import (
AFTER:  from jane.config import (
```
(4 imported symbols — only the `from` line changes)

---

### STEP 6 — Edit shell scripts

#### 6a. `start_agent.sh` — Line 13 (pkill) and Line 34 (nohup)
```
BEFORE (pkill):  pkill -9 -f "python discord_bridge.py" || true
AFTER  (pkill):  pkill -9 -f "discord_bridge.py" || true
(pattern still matches jane/discord_bridge.py in process list)

BEFORE (nohup):  nohup python discord_bridge.py > ...
AFTER  (nohup):  nohup python jane/discord_bridge.py > ...
```

#### 6b. `startup_code/reliable_start.sh` — Line 6 (pkill) and Line 55 (nohup)
```
BEFORE (pkill):  pkill -9 -f "adk web|discord_bridge.py|bridge.py" || true
AFTER  (pkill):  no change needed (pattern "discord_bridge.py" still matches)

BEFORE (nohup):  nohup $VENV_BIN/python discord_bridge.py > ...
AFTER  (nohup):  nohup $VENV_BIN/python jane/discord_bridge.py > ...
```

#### 6c. `startup_code/start_all_bots.sh` — Line 10 (pkill) and Line 39 (nohup)
```
BEFORE (pkill):  pkill -9 -f "discord_bridge.py" || true
AFTER  (pkill):  no change needed (pattern still matches)

BEFORE (nohup):  nohup $VENV_BIN/python discord_bridge.py > ...
AFTER  (nohup):  nohup $VENV_BIN/python jane/discord_bridge.py > ...
```

---

## SPECIAL CASE: discord_bridge.py amber sys.path

`discord_bridge.py` currently has:
```python
sys.path.append(os.path.join(os.path.dirname(__file__), "amber"))
```
After moving to `jane/discord_bridge.py`, `__file__` = `.../jane/discord_bridge.py`
so `os.path.dirname(__file__)` = `.../jane/` and the path would resolve to `.../jane/amber/` — which does NOT exist.

**Fix:** Change to use absolute path OR navigate up one level:
```python
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "amber"))
```

---

## FILES WITH NO CHANGES NEEDED

- `jane/config.py` — no internal imports of moved files
- `jane/services.py` — imports from `agent_skills` only
- `jane/jane_session_wrapper.py` — imports from `agent_skills` only
- `startup_code/restore_agent.sh` — no direct invocations of moved files
- `startup_code/bot_watchdog.sh` — no direct invocations of moved files
- `startup_code/INITIALIZE_NEW_SYSTEM.md` — doc only, no code

---

## TOTAL CHANGE COUNT

| Category | Files | Import lines changed |
|----------|-------|---------------------|
| Moved files (self-ref) | 3 | 3 |
| amber/ | 3 | 4 |
| agent_skills/ | 14 | 14 |
| Shell scripts | 3 | 3 (nohup lines only) |
| Special (amber sys.path in discord_bridge) | 1 | 1 |
| **TOTAL** | **24** | **25** |

---

## POST-EXECUTION VERIFICATION

Run these tests to confirm everything works:

```bash
cd /home/chieh/vessence

# 1. Test jane package imports
/home/chieh/google-adk-env/adk-venv/bin/python -c "
from jane.config import AGENT_ROOT, VAULT_DIR
from jane.llm_config import LOCAL_LLM_MODEL
print('jane imports OK')
print('AGENT_ROOT:', AGENT_ROOT)
print('LOCAL_LLM_MODEL:', LOCAL_LLM_MODEL)
"

# 2. Test agent_skills that import jane.config
/home/chieh/google-adk-env/adk-venv/bin/python /home/chieh/vessence/agent_skills/add_fact.py --help 2>&1 | head -3

# 3. Test search_memory
/home/chieh/google-adk-env/adk-venv/bin/python /home/chieh/vessence/agent_skills/search_memory.py "test" 2>&1 | tail -5

# 4. Test amber imports
/home/chieh/google-adk-env/adk-venv/bin/python -c "
import sys; sys.path.insert(0, '/home/chieh/vessence')
sys.path.append('/home/chieh/vessence/amber')
from amber.agent import root_agent
print('amber agent OK')
"
```
