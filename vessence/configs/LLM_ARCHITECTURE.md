# LLM Architecture — Model Assignments & Rationale

**Last Updated:** 2026-03-16 (qwen2.5-coder:14b migration)
**Status:** ⚠️ PARTIALLY OUTDATED (v0.1.71) — the Amber agent and its model
assignments (`amber/agent.py` with qwen_agent, deepseek hot-swap, etc.) were
retired when Jane became the sole agent. Current live models: Claude Opus 4.6
for Jane's main brain, gemma4:e4b for the prompt router (see gemma_router.py),
and optional qwen3 for local fallback research.
**Maintainer:** The user

This document describes every LLM used across the Project Ambient system, which model is assigned to which role, and the reasoning behind each assignment. The system uses a deliberate two-tier local LLM strategy alongside cloud models, each chosen for their specific strengths.

---

## Model Roster

| Model | Provider | Type | Primary Strength |
|---|---|---|---|
| `claude-sonnet-4-6` | Anthropic (Claude Code) | Cloud | Jane's primary brain — reasoning, code, systems, architecture |
| `gemini-3-flash-preview` | Google (ADK) | Cloud | Amber's primary brain — multimodal, fast |
| `qwen2.5-coder:14b` | Ollama (local) | Local | **All local tasks**: memory synthesis, research, archival, fallback, code sub-tasks |
| `gemini-2.5-flash` | Google GenAI API | Cloud | Nightly memory janitor (structured JSON output) |
| `deepseek-chat` | DeepSeek API | Cloud | Fallback Tier 2 (cloud, when local is down) |
| `gpt-4o` | OpenAI API | Cloud | Fallback Tier 3 (last resort) |

> **Note:** `qwen2.5-coder:14b` has been replaced by `qwen2.5-coder:14b` for all local tasks — smaller VRAM footprint and faster responses. Jane (Claude Code) handles all coding tasks natively.

---

## Assignment Table

| File | Model Assigned | Category |
|---|---|---|
| `agent_skills/search_memory.py` | `qwen2.5-coder:14b` | Memory — Librarian (CLI) |
| `agent_skills/local_vector_memory.py` | `qwen2.5-coder:14b` | Memory — Librarian (ADK/Amber) |
| `agent_skills/conversation_manager.py` | `ollama/qwen2.5-coder:14b` | Memory — Archivist & Compaction |
| `agent_skills/research_assistant.py` | `qwen2.5-coder:14b` | Research — Synthesis |
| `agent_skills/research_analyzer.py` | `qwen2.5-coder:14b` | Research — Search Analysis |
| `agent_skills/fallback_query.py` (Tier 1) | `qwen2.5-coder:14b` | Fallback — Local brain |
| `agent_skills/fallback_query.py` (Tier 2) | `deepseek-chat` (API) | Fallback — Cloud brain |
| `agent_skills/fallback_query.py` (Tier 3) | `gpt-4o` (API) | Fallback — Last resort |
| `agent_skills/qwen_query.py` | `qwen2.5-coder:14b` | Code — General queries (CLI utility) |
| `agent_skills/qwen_orchestrator.py` | `qwen2.5-coder:14b` | Code — 7-stage pipeline (Gemini/Amber compat only; NOT called when Claude is Jane) |
| `agent_skills/git_backup.py` | `qwen2.5-coder:14b` | Code — Commit message generation |
| `agent_skills/janitor_memory.py` | `gemini-2.5-flash` | Memory — Nightly deduplication |
| `amber/agent.py` (qwen_agent) | `qwen2.5-coder:14b` | Amber — Code sub-brain |
| `amber/agent.py` (amber root, default) | `gemini-3-flash-preview` | Amber — Primary brain |
| `amber/agent.py` (hot-swap: deepseek) | `deepseek-chat` (API) | Amber — Alternate brain |
| `amber/agent.py` (hot-swap: qwen-local) | `qwen2.5-coder:14b` | Amber — Offline brain |
| `gemini_cli_bridge/bridge.py` / Claude Code | `claude-sonnet-4-6` | Jane — Primary brain (replaced Gemini CLI) |

---

## Detailed Role Descriptions

### 1. Jane's Primary Brain — `claude-sonnet-4-6` (Claude Code)

**File:** `gemini_cli_bridge/bridge.py` → `claude -p` CLI (replaced `gemini --prompt`)
**When:** Every time the user sends a message to Jane via Discord, or interacts with Jane directly in the terminal.
**Why:** Claude Code (Sonnet 4.6) replaced Gemini CLI as Jane's primary intelligence. It is the strongest available model for code comprehension, multi-step reasoning, and systems work. It natively has access to file tools (Read, Write, Edit, Bash, Grep, Glob) without requiring a subprocess PTY wrapper. Its `/home/chieh/CLAUDE.md` system prompt is loaded at every session, giving Jane a consistent identity and initialization sequence.

**Memory injection:** The `~/.claude/settings.json` UserPromptSubmit hook fires `memory_hook.sh` before every response. This queries ChromaDB via `search_memory.py`, synthesizes with `qwen2.5-coder:14b` (local Ollama), and injects the result as `[Librarian Context]` — exactly replicating the behavior Jane had under Gemini CLI.

**Coding:** Claude Code handles all coding tasks (scripting, debugging, architecture) directly — no Qwen delegation needed for Jane. `qwen_orchestrator.py` is preserved for when Amber/Gemini needs a 7-stage pipeline, but is not invoked by Claude.

---

### 2. Amber's Primary Brain — `gemini-3-flash-preview` (Google ADK)

**File:** `amber/agent.py`
**When:** Every conversation Amber has via Discord. Amber processes all messages through the ADK web server running on `localhost:8000`.
**Why:** Gemini Flash is multimodal (handles images natively), fast, and deeply integrated with Google ADK's tool framework. Amber's use cases — screenshot vision, computer control, vault management, TTS — align well with Gemini's strengths. The model is hot-swappable at startup via the `AMBER_BRAIN_MODEL` environment variable without any code changes.

---

### 3. Memory Librarian — `gemma3:4b` (local Ollama)

**Files:** `agent_skills/search_memory.py`, `agent_skills/local_vector_memory.py`
**When:**
- `search_memory.py`: Invoked as a subagent before every response Jane gives. It queries the ChromaDB `user_memories` collection for the top 20 semantically similar memories and passes them to qwen2.5-coder:14b for synthesis.
- `local_vector_memory.py`: Used by Amber's ADK server as a `BaseMemoryService`. Fetches the top 100 memories and synthesizes them before injecting into Amber's context.
- `amber/agent.py`: Amber's per-turn memory auto-injection path now also uses the librarian model rather than the general local reasoning model.
**Why:** This is a pure synthesis task. The raw vector search returns many potentially conflicting, redundant, or tangentially related memories. `gemma3:4b` is fast, local, and sufficient for:
  1. Deduplicate redundant facts
  2. Resolve contradictions by preferring the most recent memory
  3. Discard noise irrelevant to the current query
  4. Produce a single, high-fidelity narrative summary

The result is injected as a `[Librarian Context]` block into the agent's context, giving both Jane and Amber near-perfect recall without overwhelming the context window with raw vector data. Running this locally keeps memory operations private and cheap, while reserving `qwen2.5-coder:14b` for slower background research and synthesis work where latency is less important.

---

### 4. Session Archivist & Compaction — `qwen2.5-coder:14b` (local Ollama via LiteLLM)

**File:** `agent_skills/conversation_manager.py` (`ARCHIVIST_MODEL = "ollama/qwen2.5-coder:14b"`)
**When:** Two scenarios trigger the archivist:
  1. **Active compaction**: When the live conversation exceeds 75% of the max token budget (8192 tokens), the oldest chunk is extracted and summarized.
  2. **End-of-session archival (Intelligent Archivist)**: When the session ends, each message in the short-term ChromaDB is evaluated individually.
**Why:** Both tasks require nuanced judgment:
  - Compaction requires generating a faithful, neutral 3rd-person summary that preserves all key decisions and facts without loss — a reasoning task.
  - The Intelligent Archivist must decide "Keep" or "Discard" for each memory fragment, applying criteria like: is this an explicit directive? A factual update? A key decision? Or just a pleasantry or failed action? This binary classification under semantic context is exactly what a strong reasoning model excels at.

Using qwen2.5-coder:14b locally here is important: these operations run frequently and in the background. Cloud API calls would introduce latency and cost for what is essentially infrastructure work.

---

### 5. Research Synthesis — `qwen2.5-coder:14b` (local Ollama)

**Files:** `agent_skills/research_assistant.py`, `agent_skills/research_analyzer.py`
**When:** Invoked by Amber's `TechnicalResearchTool` when the user asks for technical research. Raw web search data (up to 15,000 characters) is passed in for analysis.
**Why:** Analyzing conflicting technical sources, extracting root causes, and identifying the highest-confidence fix from noisy web data is a reasoning-heavy task. qwen2.5-coder:14b's reasoning capability makes it well-suited for:
  - Weighing conflicting documentation sources
  - Identifying the most recent or authoritative answer
  - Producing a structured JSON output with `cause`, `fix`, and `source_url`

Running this locally avoids sending potentially sensitive technical context to a cloud API.

---

### 6. Fallback Brain Chain — `qwen2.5-coder:14b` → `deepseek-chat` → `gpt-4o`

**File:** `agent_skills/fallback_query.py`
**When:** The Discord bridge invokes the fallback chain when the primary brain (Claude Code or Amber's ADK server) is unresponsive, rate-limited, or returns an empty response.
**Why — Three-tier design:**
  - **Tier 1 (`deepseek-chat`, API)**: First resort because it provides fast, capable responses at low cost without requiring local GPU resources.
  - **Tier 2 (local DeepSeek-R1)**: If the DeepSeek API is unavailable (e.g., no internet, API key issue), the local model keeps the system operational even during complete internet outages.
  - **Tier 3 (`gpt-4o`, API)**: Last resort. The most capable and most expensive cloud option, used only when both local and DeepSeek are down.

**Notification:** All three tiers prepend a clear `⚠️ Claude is unavailable` warning to their responses so the user always knows he is not talking to the primary brain.

---

### 7. Code Subagent — `qwen2.5-coder:14b` (local Ollama)

**Files:** `agent_skills/qwen_query.py`, `amber/agent.py` (qwen_agent)
**When:**
  - `qwen_query.py`: Called directly by Jane (or scripts) for general-purpose code queries, log triage, script generation.
  - `amber/agent.py` (qwen_agent): Amber's root agent delegates technical subtasks to this specialized sub-agent to avoid spending Gemini tokens on routine coding work.
**Why:** Qwen3-Coder is a state-of-the-art code model. Its strengths align precisely with the tasks delegated to it:
  - Boilerplate and scaffolding generation
  - Unit test generation
  - Log analysis and debug triage
  - Code refactoring
  - Regex generation
  - Bash/terminal scripting
  - SQL optimization
  - Documentation and type hinting
  - Reading and understanding small code snippets

These tasks do not require deep reasoning chains — they require accurate code synthesis. Qwen3-Coder at 30B handles them faster and with better code quality than a general reasoner of the same size. Running locally keeps this completely free, enabling Jane and Amber to offload routine coding work without API cost.

---

### 8. 7-Stage Coding Orchestrator — `qwen2.5-coder:14b` (local Ollama)

**File:** `agent_skills/qwen_orchestrator.py`
**When:** Invoked for complex, multi-stage code implementation tasks. The pipeline runs: Spec Drafting → Research → Dependency Check → Context Harvest → Implementation → Audit → Validation.
**Why:** Each stage produces artifacts (spec.md, implementation code, test suite) that are primarily code or code-adjacent. Qwen3-Coder's code generation quality makes it the right choice for the implementation-heavy stages (5, 7). The auditor persona (Stage 6) also benefits from a model that understands code deeply enough to spot logical flaws and security issues.

---

### 9. Git Commit Message Generation — `qwen2.5-coder:14b` (local Ollama)

**File:** `agent_skills/git_backup.py`
**When:** Every time the automated nightly git backup runs and detects staged changes. The git diff (capped at 4,000 characters) is sent to the model for a concise commit message under 80 characters.
**Why:** This is a small, routine scripting task — exactly what a coder-specialized model handles efficiently. No reasoning chains needed; just good code comprehension to summarize what changed.

---

### 10. Nightly Memory Janitor — `gemini-2.5-flash` (Google GenAI API)

**File:** `agent_skills/janitor_memory.py`
**When:** Runs nightly at 3:00 AM via cron. Fetches all memories from the `user_memories` ChromaDB collection, groups them by topic, and identifies redundant/duplicate facts for consolidation.
**Why:** This task requires structured JSON output (the model must return a valid merge plan with `original_ids`, `new_fact`, and `new_subtopic`). Gemini 2.5 Flash with `response_mime_type: application/json` guarantees schema-compliant output, which is critical for the janitor to safely delete old IDs and insert consolidated facts without corrupting the memory database. It also runs only once per night, so the cloud API cost is negligible. Permanent memories (vault file references, `memory_type: permanent`) are protected from consolidation regardless.

---

## Design Philosophy

### Why `qwen2.5-coder:14b`?

The system previously used `qwen2.5-coder:14b`. Migrated to **`qwen2.5-coder:14b`** for the following reasons:

1. **Size**: At 14B vs 30B, it uses significantly less VRAM and runs faster on the local GPU.

2. **Code specialization**: qwen2.5-coder is purpose-built for code tasks — the primary use case for the local model (sub-agent code work, commit messages, research synthesis).

3. **Sufficient quality**: For all delegated local tasks (memory synthesis, research summarization, code sub-tasks, fallback), the 14B coder variant performs well within acceptable quality bounds.

**Result:** Smaller footprint, faster responses, always warm in VRAM.

### Why Keep Operations Local?

Several critical operations are intentionally routed to local models rather than cloud APIs:

1. **Memory operations** contain personal facts about the user and their family. These should not leave the machine.
2. **Research synthesis** may involve proprietary technical context.
3. **Cost**: Memory is queried before *every* response. At cloud API rates, this would be prohibitively expensive at scale.
4. **Latency**: Local inference (especially with GPU) is fast enough for background tasks and acceptable for interactive fallback.
5. **Offline resilience**: The system remains functional during internet outages for Tier 1 fallback and all memory operations.

### The Fallback Hierarchy Principle

The fallback chain is designed so that at no point does the system silently degrade. Every fallback tier announces itself with a `⚠️ Claude is unavailable` prefix. This is intentional: the user should always know whether he is talking to his primary brain (Claude Code) or an emergency substitute, so he can calibrate his expectations accordingly.

---

## Changing Models

To swap any model, update the relevant constant in the file listed above and restart the relevant service. No other code changes are needed. For Amber's primary brain, set the `AMBER_BRAIN_MODEL` environment variable in `/home/chieh/vessence/.env` to `gemini` (default), `deepseek`, or `qwen` and restart the ADK server.
