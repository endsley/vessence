# Environment Guide — Python Environments & Dependency Management

**Last Updated:** 2026-03-16

This document explains the multi-environment setup of Project Ambient, the known failure modes, the fixes applied, and the rules to follow when adding new scripts.

---

## The Problem

The system runs across **three isolated Python environments**. Each has a different set of installed packages. When a script is invoked with the wrong Python interpreter, it silently fails with `ModuleNotFoundError` — and since memory failures produce no visible crash in the Discord bridge (it just returns an empty context), these bugs can go unnoticed.

The most dangerous failure mode is:

```
$ python3 /home/chieh/vessence/agent_skills/search_memory.py "query"
ModuleNotFoundError: No module named 'chromadb'
```

This results in Jane or Amber responding **without any memory context** — no error shown to the user, no visible degradation, just silently wrong behavior.

---

## The Three Environments

| Environment | Python Binary | Key Packages | Used By |
|---|---|---|---|
| **ADK Venv** | `/home/chieh/google-adk-env/adk-venv/bin/python` | `chromadb`, `google-adk`, `discord.py`, `httpx`, `ollama`, `litellm`, `tiktoken` | Amber's brain, all agent skills, Discord bridges, memory scripts |
| **Kokoro Conda** | `/home/chieh/miniconda3/envs/kokoro/bin/python` | `kokoro`, `soundfile`, `torch` (GPU) | TTS only — `agent_skills/kokoro_tts.py` |
| **OmniParser Venv** | `/home/chieh/vessence/omniparser_venv/bin/python` | `ultralytics` (YOLOv8), `Florence-2` | Computer vision only — `agent_skills/omniparser_skill.py` |
| **System Python** | `/usr/bin/python3` | Standard library only | Nothing in this project should use this |

---

## Affected Scripts & Status

### Scripts that are called directly as subprocesses (shebang matters)

| Script | Shebang | Re-exec Guard | Status |
|---|---|---|---|
| `agent_skills/search_memory.py` | ✅ ADK venv | ✅ Yes | Fixed 2026-03-16 |
| `agent_skills/fallback_query.py` | ✅ ADK venv | ❌ No | Safe (shebang correct) |
| `agent_skills/janitor_memory.py` | ✅ ADK venv | ❌ No | Safe (shebang correct) |
| `agent_skills/research_assistant.py` | ✅ ADK venv | ❌ No | Safe (shebang correct) |
| `agent_skills/research_analyzer.py` | ✅ ADK venv | ❌ No | Safe (shebang correct) |
| `agent_skills/qwen_query.py` | ✅ ADK venv | ❌ No | Safe (shebang correct) |
| `agent_skills/kokoro_tts.py` | Check — needs Kokoro conda | ❌ No | Verify shebang points to kokoro env |

### Scripts that are imported as modules (shebang less critical)

| Script | Imported By | Risk |
|---|---|---|
| `agent_skills/local_vector_memory.py` | ADK server (`services.py`) | Low — ADK server runs in ADK venv |
| `agent_skills/conversation_manager.py` | `jane_session_wrapper.py` | Low — wrapper now has an explicit ADK shebang and re-exec guard |
| `agent_skills/services.py` | ADK server | Low |

---

## The Two-Layer Fix Applied to `search_memory.py`

`search_memory.py` is the most critical script — it runs before every response. It received both fixes:

### Layer 1: Correct Shebang
```python
#!/home/chieh/google-adk-env/adk-venv/bin/python
```
When the script is called as a direct executable (`./search_memory.py "query"`), the OS uses this line to select the interpreter. This is the first line of defense.

### Layer 2: Re-exec Guard
```python
_REQUIRED_PYTHON = "/home/chieh/google-adk-env/adk-venv/bin/python"
if os.path.exists(_REQUIRED_PYTHON) and sys.executable != _REQUIRED_PYTHON:
    os.execv(_REQUIRED_PYTHON, [_REQUIRED_PYTHON] + sys.argv)
```
When the script is called with the wrong Python (e.g., `python3 search_memory.py "query"`), this block detects the mismatch and immediately re-launches the process using the correct interpreter — passing all original arguments through unchanged. The original process is replaced (not forked), so there is no overhead. This is the second line of defense and makes the script safe regardless of how it is invoked.

---

## Root Cause Analysis

### Why did this happen?

1. **Organic growth**: The project started with Gemini CLI (which has its own Node.js runtime and invokes Python scripts via subprocess). Scripts were added incrementally without a consistent convention for shebangs.

2. **No enforcement**: Python's shebang is only used when a script is called as a direct executable. When called as `python3 script.py`, the shebang is ignored and whatever `python3` resolves to in PATH is used — which is the system Python on this machine.

3. **Silent failure**: `chromadb`, `ollama`, and `discord.py` are all absent from system Python. A `ModuleNotFoundError` on import causes the script to exit with code 1 and print nothing to stdout. The Discord bridge only checks for empty stdout, so it triggers the fallback chain silently.

---

## Rules for Adding New Scripts

### Rule 1: Always use the explicit shebang
Every new `.py` script that will be called as a subprocess must start with:
```python
#!/home/chieh/google-adk-env/adk-venv/bin/python
```
For TTS scripts: `#!/home/chieh/miniconda3/envs/kokoro/bin/python`
For OmniParser scripts: `#!/home/chieh/vessence/omniparser_venv/bin/python`

### Rule 2: Add the re-exec guard to any script that uses `chromadb` or `ollama`
Paste this block immediately after `import os` and `import sys`, before any other imports:
```python
_REQUIRED_PYTHON = "/home/chieh/google-adk-env/adk-venv/bin/python"
if os.path.exists(_REQUIRED_PYTHON) and sys.executable != _REQUIRED_PYTHON:
    os.execv(_REQUIRED_PYTHON, [_REQUIRED_PYTHON] + sys.argv)
```

### Rule 3: Make subprocess-called scripts executable
```bash
chmod +x /home/chieh/vessence/agent_skills/your_new_script.py
```

### Rule 4: Never import `chromadb` at module level without the guard
If you're writing a module that will be imported (not called directly), ensure the caller is already running in the ADK venv. Do not add the re-exec guard to modules — only to scripts with `if __name__ == "__main__":` blocks.

### Rule 5: Test in isolation before integrating
```bash
# Test with wrong Python (should auto-correct or fail gracefully):
python3 /home/chieh/vessence/agent_skills/your_script.py "test query"

# Test with correct Python directly:
/home/chieh/google-adk-env/adk-venv/bin/python /home/chieh/vessence/agent_skills/your_script.py "test query"

# Test as executable:
/home/chieh/vessence/agent_skills/your_script.py "test query"
```

---

## How to Diagnose Environment Issues

### Symptom: Memory context is empty / "No relevant context found" with no error
**Cause:** `search_memory.py` was called with wrong Python and failed silently.
**Check:** Run manually with system Python and look for `ModuleNotFoundError`:
```bash
python3 /home/chieh/vessence/agent_skills/search_memory.py "test"
```

### Symptom: `ModuleNotFoundError: No module named 'chromadb'`
**Cause:** Script running under system Python or wrong venv.
**Fix:** Call with explicit venv Python or ensure shebang + re-exec guard are present.

### Symptom: `ModuleNotFoundError: No module named 'ollama'`
**Cause:** Same as above — `ollama` is only in the ADK venv.

### Symptom: `ModuleNotFoundError: No module named 'google.adk'`
**Cause:** Script or import chain running outside ADK venv.

### Symptom: TTS produces no audio / `No module named 'kokoro'`
**Cause:** `kokoro_tts.py` invoked with wrong Python — needs the conda `kokoro` env.

### Quick environment check
```bash
# Verify chromadb is visible:
/home/chieh/google-adk-env/adk-venv/bin/python -c "import chromadb; print('OK')"

# Verify ollama is visible:
/home/chieh/google-adk-env/adk-venv/bin/python -c "import ollama; print('OK')"

# Verify ChromaDB has data:
/home/chieh/google-adk-env/adk-venv/bin/python -c "
import chromadb
c = chromadb.PersistentClient('/home/chieh/ambient/vector_db')
col = c.get_collection('user_memories')
print(f'user_memories: {col.count()} entries')
"
```

---

## Package Installation Reference

If a package is missing from the ADK venv:
```bash
/home/chieh/google-adk-env/adk-venv/bin/pip install <package>
```

Never install to system Python (`pip3 install`) — this pollutes the system and doesn't help any of the project's scripts.
