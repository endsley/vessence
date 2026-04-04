# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Increase recursion limit to prevent OllamaException on large LiteLLM responses
sys.setrecursionlimit(5000)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_skills.memory_retrieval import build_memory_sections
from jane.llm_config import LOCAL_LLM_MODEL, LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL_LITELLM
from jane.config import (
    CONFIGS_DIR as _CONFIGS_DIR,
    ENV_FILE_PATH as _ENV_FILE_PATH,
    JANITOR_REPORT as _JANITOR_REPORT,
    VAULT_DIR as _VAULT_DIR,
)
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.models.lite_llm import LiteLlm
from google.genai import types
from google.adk.plugins.save_files_as_artifacts_plugin import SaveFilesAsArtifactsPlugin
from amber.plugins.cleanup_plugin import ImageCleanupPlugin
from amber.logic.agent_logic import detect_facts_and_contradictions
from .tools.local_computer import LocalComputer
from .tools.research_tools import TechnicalResearchTool
from google.adk.tools.computer_use.computer_use_toolset import ComputerUseToolset
from google.adk.tools.google_search_tool import GoogleSearchTool
import logging

logger = logging.getLogger('amber.agent')

# ADK auto-loads repo-root .env, but runtime secrets live in VESSENCE_DATA_HOME/.env.
# Reload the canonical runtime env here so Amber sees the real API keys.
load_dotenv(_ENV_FILE_PATH, override=True)


def _extract_user_query(ctx) -> str:
    """Extract the latest user message from ADK context for prompt-tuned retrieval."""
    try:
        events = ctx.session.events
        for event in reversed(events):
            content = getattr(event, 'content', None)
            if content and getattr(content, 'role', None) == 'user':
                parts = getattr(content, 'parts', [])
                for part in parts:
                    text = getattr(part, 'text', None)
                    if text:
                        return text
    except Exception:
        pass
    return f"{os.environ.get('USER_NAME', 'the user')} personal life family hobbies social activities preferences work"


def _extract_session_id(ctx) -> str:
    try:
        session = getattr(ctx, "session", None)
        if session is None:
            return ""
        for attr in ("id", "session_id"):
            value = getattr(session, attr, "")
            if value:
                return str(value)
    except Exception:
        pass
    return ""


def _fetch_ambient_memory(query: str = "", session_id: str = "") -> str:
    if not query:
        query = f"{os.environ.get('USER_NAME', 'the user')} personal life family hobbies social activities preferences work"
    try:
        sections = build_memory_sections(query, assistant_name="Jane")
        if not sections:
            return ""
        return "\n\n".join(sections)
    except Exception as e:
        logger.warning(f"shared ambient memory fetch failed: {e}")
        return ""


async def unified_instruction_provider(ctx):
    vault_dir = _VAULT_DIR
    janitor_report_path = _JANITOR_REPORT
    manifest_path = os.path.join(_CONFIGS_DIR, "amber_capabilities.json")
    
    # 1. Load Manifest
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

    # 2. Get file stats for vault summary
    files_info = "Vault Status: [Empty]"
    if os.path.exists(vault_dir):
        total_files = sum([len(files) for r, d, files in os.walk(vault_dir)])
        files_info = f"Vault Status: {total_files} files stored locally."

    # 3. Get Janitor status
    janitor_status = ""
    if os.path.exists(janitor_report_path):
        with open(janitor_report_path, 'r') as f:
            rep = f.read()
            janitor_status = f"\nLast Maintenance Report: {rep}"

    # 4. Build Dynamically
    default_role = f"{os.environ.get('USER_NAME', 'the user')}'s personal assistant"
    persona = (
        f"You are {manifest.get('identity', 'Amber')}, {manifest.get('role', default_role)}.\n"
        f"Context: {manifest.get('family_context', '')}\n\n"
        "OPERATING PROTOCOLS:\n"
    )
    
    for i, cap in enumerate(manifest.get('capabilities', []), 1):
        persona += f"{i}. {cap['name'].upper()}: {cap['description']} (Tools: {', '.join(cap['tools'])})\n"
        if 'instruction' in cap:
            persona += f"   - {cap['instruction']}\n"

    # Add system-specific instructions that aren't in the manifest
    persona += (
        "\nADDITIONAL PROTOCOLS:\n"
        "- INTERACTION: Be warm, friendly, and efficient. Always address the user by their preferred name.\n"
        "- MAINTENANCE: You have a scheduled maintenance task that runs every night at 3:00 AM.\n"
        "- RESPONSE FORMAT: ALWAYS respond with a TEXT message first. Text is your primary output. Only use tools when genuinely needed for the specific request. After completing all tool calls, send a final text response — do NOT loop or chain unnecessary tool calls.\n"
        "- VOICE: NEVER call generate_speech unless the user explicitly asks for audio or voice output.\n"
        "- MEMORY RETRIEVAL: Before answering ANY question about the user's personal life, preferences, habits, people they know, family, hobbies, work, health, or past events — ALWAYS call vault_search first with a relevant query. Do NOT answer 'I don't know' without first calling vault_search.\n"
        "- FILE READING: If the user asks about the contents of a markdown, text, code, config, JSON, CSV, or log file in the vault, use vault_read_file to read the actual file contents from disk before answering.\n"
    )

    # 5. Inject ambient memory context (full tiered retrieval + Qwen Librarian)
    user_query = _extract_user_query(ctx)
    session_id = _extract_session_id(ctx)
    memory_block = _fetch_ambient_memory(query=user_query, session_id=session_id)
    memory_section = ""
    if memory_block:
        memory_section = (
            f"\n\n## [Librarian Context] — Known facts about {os.environ.get('USER_NAME', 'the user')} (auto-loaded):\n"
            + memory_block
            + "\nUse these facts naturally when relevant. Do NOT re-fetch with vault_search unless you need deeper detail on a specific topic."
        )

    return f"{persona}\n\n{files_info}{janitor_status}{memory_section}"

def create_app() -> App:
    # --- Tools ---
    from .tools.vault_tools import VaultSaveTool, VaultSearchTool, VaultSendFileTool, VaultReorganizeTool, VaultDeleteTool, VaultReadFileTool, VaultAnalyzePdfTool, TerminalTool, MemoryUpdateTool, MemorySaveTool, VaultTunnelURLTool, VaultIndexTool, VaultFindAudioTool, VaultPlaylistTool
    from .tools.local_computer import LocalComputer
    from .tools.speech_tools import TextToSpeechTool
    
    vault_save = VaultSaveTool()
    vault_search = VaultSearchTool()
    vault_send = VaultSendFileTool()
    vault_read = VaultReadFileTool()
    vault_analyze_pdf = VaultAnalyzePdfTool()
    vault_delete = VaultDeleteTool()
    vault_reorganize = VaultReorganizeTool()
    vault_tunnel_url = VaultTunnelURLTool()
    vault_index = VaultIndexTool()
    vault_find_audio = VaultFindAudioTool()
    vault_playlist = VaultPlaylistTool()
    terminal = TerminalTool()
    mem_update = MemoryUpdateTool()
    mem_save = MemorySaveTool()
    generate_speech = TextToSpeechTool()
    research_tool = TechnicalResearchTool()
    google_search = GoogleSearchTool()

    # --- Model Selection (HOT SWAP) ---
    brain_mode = os.getenv("AMBER_BRAIN_MODEL", "gemini").lower()
    
    if brain_mode == "deepseek":
        logger.info("CORE BRAIN: DeepSeek Chat")
        main_model = LiteLlm(
            model="deepseek/deepseek-chat",
            api_base="https://api.deepseek.com/v1"
        )
    elif brain_mode in ["qwen", "qwen-local"]:
        logger.info(f"CORE BRAIN: Local {LOCAL_LLM_MODEL}")
        main_model = LiteLlm(
            model=LOCAL_LLM_MODEL_LITELLM,
            api_base=LOCAL_LLM_BASE_URL
        )
    elif brain_mode in ["gemma", "gemma3"]:
        _gemma_model = os.getenv("AMBER_GEMMA_MODEL", "gemma3:12b")
        logger.info(f"CORE BRAIN: Local {_gemma_model} (Ollama)")
        main_model = LiteLlm(
            model=f"ollama/{_gemma_model}",
            api_base=LOCAL_LLM_BASE_URL
        )
    else:
        logger.info("CORE BRAIN: Gemini 2.5 Flash")
        main_model = "gemini-2.5-flash"

    # --- Specialized Agents ---
    
    # Web Search Agent
    search_agent = LlmAgent(
        name="search_agent",
        model=main_model,
        instruction="You are a search specialist. Use the 'google_search' tool to find information. Provide concise summaries.",
        tools=[google_search],
        disallow_transfer_to_parent=False,
        disallow_transfer_to_peers=True,
        generate_content_config=types.GenerateContentConfig(
            response_modalities=["TEXT"]
        )
    )

    # Specialized Computer Control Agent
    computer_agent = LlmAgent(
        name="computer_agent",
        model=main_model,
        instruction=(
            "You are Amber's motor brain. You control the mouse and keyboard. "
            "You receive a screenshot and can perform clicks, scrolls, and typing. "
            "Always report what you are doing back to Amber."
        ),
        tools=[ComputerUseToolset(computer=LocalComputer())],
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
        generate_content_config=types.GenerateContentConfig(
            response_modalities=["TEXT"]
        )
    )

    # Specialized Qwen Agent for technical sub-tasks
    qwen_agent = LlmAgent(
        name="qwen_agent",
        model=LiteLlm(model=LOCAL_LLM_MODEL_LITELLM, api_base=LOCAL_LLM_BASE_URL),
        instruction=(
            "You are Amber's technical sub-brain, running locally via qwen2.5-coder:14b. "
            "Your job is to handle specific technical tasks to save Gemini tokens. These include: "
            "1) Boilerplate & Scaffolding, 2) Unit Test Generation, 3) Log Analysis & Debug Triage, "
            "4) Code Refactoring, 5) Regex Generation & Testing, 6) 'Fill-In-The-Middle' (FIM) Completion, "
            "7) Bash/Terminal Scripting, 8) SQL Query Optimization, 9) Documentation & Type Hinting, "
            "and 10) Reading/understanding small code snippets. "
            "CRITICAL: If a task involves actual file editing (writing files), complex multi-file debugging, "
            "or high-stakes architectural decisions, you MUST transfer back to your parent agent (Amber)."
        ),
        disallow_transfer_to_parent=False,
        disallow_transfer_to_peers=True
    )

    # Root Unified Agent
    # NOTE: after_agent_callback (fact extraction) and EventsCompaction are disabled
    # because they each make a full qwen2.5-coder:14b call, adding 2+ minutes per response.
    # Fact extraction is handled offline by janitor_memory.py instead.
    amber_agent = LlmAgent(
        name="amber",
        model=main_model,
        instruction=unified_instruction_provider,
        tools=[vault_save, vault_search, vault_send, vault_reorganize, vault_tunnel_url, vault_index, vault_find_audio, vault_playlist, terminal, mem_save, mem_update, vault_delete, vault_read, vault_analyze_pdf, generate_speech, research_tool],
        sub_agents=[search_agent, computer_agent, qwen_agent],
        generate_content_config=types.GenerateContentConfig(
            labels={"current_url": "about:blank"},
            response_modalities=["TEXT"]
        )
    )

    return App(
        name="amber",
        root_agent=amber_agent,
        plugins=[SaveFilesAsArtifactsPlugin(), ImageCleanupPlugin()]
    )

app = create_app() # ADK loader looks for root_agent or app
