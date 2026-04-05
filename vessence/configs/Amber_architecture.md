# Amber Architecture & Design (LEGACY — retired)

> **Status (2026-04-04):** Amber has been retired. Jane is the sole agent. This document is preserved as historical reference only. The `vault_web/amber_proxy.py` bridge and its top-level shim were removed in v0.1.71, along with `vault-web.service`. The Discord bridge still runs but communicates directly with Jane.

This document describes the architecture, code structure, and design principles for Amber, the Discord-based assistant that preceded the current Jane-only runtime.

---

## 1. Core Logic & Location
- **Primary Directory:** `$VESSENCE_HOME/amber/` (retained for historical reference; not actively loaded)
- **Main Entry Point:** The core agent logic was defined in `amber/agent.py`.
- **Discord Bridge:** `jane/discord_bridge.py` now talks directly to Jane; the former `vault_web/amber_proxy.py` HTTP relay is gone.

## 2. Directory Structure & Purpose
- **amber/logic/** — Contains specialized logic modules (e.g., `agent_logic.py` with the fact extraction callback).
- **amber/plugins/** — Holds plugins that extend Amber's functionality (e.g., `cleanup_plugin.py`).
- **amber/tools/** — Tool definitions: `vault_tools.py`, `speech_tools.py`, `local_computer.py`, `research_tools.py`.

## 3. Design Philosophy
- Amber is designed to be a friendly, multi-modal personal assistant operating primarily through Discord.
- She shares the same core memory (ChromaDB vector DB) and human understanding (identity essays) as Jane.
- Her capabilities are extended through a modular system of tools, plugins, and sub-agents.

## 4. Model Selection (Hot-Swap)
Controlled by the `AMBER_BRAIN_MODEL` env var (default: `gemini`):
| Value | Model |
|---|---|
| `gemini` (default) | `gemini-2.5-flash` via Gemini API |
| `deepseek` | `deepseek/deepseek-chat` via LiteLlm |
| `qwen` / `qwen-local` | Local Qwen (from `LOCAL_LLM_MODEL_LITELLM`) via Ollama/LiteLlm |
| `gemma` / `gemma3` | Local Gemma (from `AMBER_GEMMA_MODEL`, default `gemma3:12b`) via Ollama/LiteLlm |

## 5. Sub-Agents
Amber delegates to three specialized sub-agents (all defined in `amber/agent.py`):

1. **search_agent** — Uses `GoogleSearchTool` for web searches. Can transfer back to parent.
2. **computer_agent** — Controls mouse/keyboard via `ComputerUseToolset` with `LocalComputer`. Cannot transfer back (fire-and-forget).
3. **qwen_agent** — Local Qwen model for token-saving technical sub-tasks (boilerplate, tests, log analysis, refactoring, regex, bash scripting, SQL, docs). Transfers back to parent for file edits or architectural decisions.

## 6. Core Capabilities & Tools

### 6.1 Vault File Management
Tools from `amber/tools/vault_tools.py`:
| Tool Class | Function Name | Purpose |
|---|---|---|
| `VaultSaveTool` | `vault_save` | Save uploaded files to the local vault |
| `VaultSearchTool` | `vault_search` | Search vault files and ChromaDB memory |
| `VaultSendFileTool` | `vault_send_file` | Send a vault file back to the user via Discord |
| `VaultDeleteTool` | `vault_delete` | Delete files from the vault |
| `VaultReadFileTool` | `vault_read_file` | Read text/code/config file contents from disk |
| `VaultAnalyzePdfTool` | `vault_analyze_pdf` | Extract and analyze PDF content |
| `VaultReorganizeTool` | `vault_reorganize` | Reorganize vault file structure |
| `VaultTunnelURLTool` | `vault_tunnel_url` | Get the current Cloudflare tunnel URL for vault web access |
| `VaultIndexTool` | `vault_index` | Reindex the vault file index in ChromaDB |
| `VaultFindAudioTool` | `vault_find_audio` | Search for audio files in the vault |
| `VaultPlaylistTool` | `vault_playlist` | Create/manage audio playlists |

### 6.2 Long-Term Memory
- **Tools:** `MemorySaveTool` (`memory_save`), `MemoryUpdateTool` (`memory_update`)
- **Implementation:** All memory writes call `add_fact.py` via subprocess. Memory reads call `search_memory.py` via subprocess. Amber bypasses ADK's built-in memory service entirely — the ADK server runs with no `--memory_service_uri` flag.
- **Auto-Injection:** On every turn, `unified_instruction_provider` calls `_fetch_ambient_memory(query)` which delegates to `agent_skills/memory_retrieval.py:get_memory_summary()`. The retrieval pipeline queries multiple ChromaDB collections (user_memories, long-term, short-term/forgettable) and synthesizes results via the **Librarian** (local model controlled by `LIBRARIAN_MODEL`, default `gemma3:4b`). The synthesized summary is injected as `[Librarian Context]` into the system prompt. Falls back to raw results if the librarian is unavailable.

### 6.3 Terminal Access
- **Tool:** `TerminalTool` (`terminal`) in `amber/tools/vault_tools.py`
- **Purpose:** Execute shell commands on the local machine.

### 6.4 Multi-Modal Speech
- **Tool:** `TextToSpeechTool` (`generate_speech`) in `amber/tools/speech_tools.py`
- **Description:** Uses a local Kokoro TTS engine to generate spoken audio, saved to the vault's audio directory.

### 6.5 Local Computer Control
- **Tool:** `LocalComputer` in `amber/tools/local_computer.py`
- **Description:** Controls the local computer's mouse and keyboard. Used by the `computer_agent` sub-agent via ADK's `ComputerUseToolset`.

### 6.6 Web Research
- **Tool:** `TechnicalResearchTool` (`technical_research_analysis`) in `amber/tools/research_tools.py`
- **Description:** Uses local Qwen to perform deep technical analysis on raw search data.
- **Tool:** `GoogleSearchTool` (`google_search`) — ADK built-in, used by the `search_agent` sub-agent.

## 7. Fact Extraction Callback
- **Location:** `amber/logic/agent_logic.py`
- **Function:** `detect_facts_and_contradictions(callback_context, llm_response)`
- **Purpose:** An `after_agent_callback` that analyzes each conversation turn to extract permanent facts about the user and save them to ChromaDB via `add_fact.py` subprocess.
- **Current Status:** DISABLED in production. The callback and ADK `EventsCompaction` are both commented out in `amber/agent.py` because each triggers a full local-LLM call adding 2+ minutes per response. Fact extraction is instead handled offline by `janitor_memory.py`.

## 8. Plugins
Registered in `create_app()` via `plugins=[SaveFilesAsArtifactsPlugin(), ImageCleanupPlugin()]`:

1. **SaveFilesAsArtifactsPlugin** — ADK built-in. Saves generated files as session artifacts.
2. **ImageCleanupPlugin** (`amber/plugins/cleanup_plugin.py`) — Runs `after_run_callback` to strip inline image data from session history after each turn, replacing images with `[Screenshot removed]` placeholders to save context space.

## 9. Instruction Provider
The `unified_instruction_provider(ctx)` async function in `amber/agent.py` dynamically builds Amber's system prompt each turn:
1. Loads capabilities manifest from `configs/amber_capabilities.json`
2. Computes vault file stats
3. Reads the janitor maintenance report
4. Appends operating protocols (interaction style, response format, memory retrieval rules, voice rules, file reading rules)
5. Injects `[Librarian Context]` memory block (see 6.2)
