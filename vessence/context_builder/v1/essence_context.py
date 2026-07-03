"""Active essence context helpers for Jane prompt building."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def active_essence_names(data_home: str) -> list[str]:
    active_file = os.path.join(data_home, "data", "active_essence.json")
    if not os.path.isfile(active_file):
        return []
    try:
        with open(active_file, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        active_list = data.get("active", [])
        if not active_list:
            active_name = data.get("active_essence")
            if active_name:
                active_list = [active_name]
        return active_list
    except (json.JSONDecodeError, OSError):
        return []


def essence_search_dirs(ambient_base: str, tools_dir: str | None = None) -> tuple[str, str]:
    resolved_tools_dir = tools_dir or os.environ.get("ESSENCES_DIR", os.path.join(ambient_base, "skills"))
    return resolved_tools_dir, os.path.join(ambient_base, "essences")


def get_active_essence_personality() -> str:
    """Read active essence personality.md files and return prompt context."""
    data_home = os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data"))
    active_list = active_essence_names(data_home)
    if not active_list:
        return ""

    ambient_base = os.environ.get("AMBIENT_BASE", os.path.expanduser("~/ambient"))
    tools_dir, essences_dir = essence_search_dirs(ambient_base, os.environ.get("TOOLS_DIR"))
    parts = []
    for name in active_list:
        personality_path = os.path.join(tools_dir, name, "personality.md")
        if not os.path.isfile(personality_path):
            personality_path = os.path.join(essences_dir, name, "personality.md")
        if os.path.isfile(personality_path):
            try:
                content = Path(personality_path).read_text(encoding="utf-8", errors="replace").strip()
                if content:
                    parts.append(f"### Active Essence: {name}\n{content}")
            except Exception:
                pass
    return "\n\n".join(parts)


def get_active_essence_chromadb_path() -> str | None:
    """Return the ChromaDB path for the currently active essence, if any."""
    data_home = os.environ.get("VESSENCE_DATA_HOME", os.path.expanduser("~/ambient/vessence-data"))
    active_list = active_essence_names(data_home)
    if not active_list:
        return None

    ambient_base = os.environ.get("AMBIENT_BASE", os.path.expanduser("~/ambient"))
    tools_dir, essences_dir = essence_search_dirs(ambient_base, os.environ.get("TOOLS_DIR"))
    for name in active_list:
        for search_dir in [tools_dir, essences_dir]:
            chroma_path = os.path.join(search_dir, name, "knowledge", "chromadb")
            if os.path.isdir(chroma_path):
                return chroma_path
    return None


def extract_tool_signatures(tools_path: str) -> list[str]:
    """Extract public function signatures from a custom_tools.py file."""
    tools = []
    try:
        with open(tools_path) as handle:
            for line in handle:
                line = line.strip()
                if line.startswith("def ") and not line.startswith("def _"):
                    sig = line[4:]
                    paren_end = sig.find(") ->")
                    if paren_end == -1:
                        paren_end = sig.find("):")
                    if paren_end >= 0:
                        sig = sig[:paren_end + 1]
                    else:
                        sig = sig.rstrip(":").strip()
                    tools.append(sig.strip())
    except OSError:
        pass
    return tools


def get_essence_tools_description() -> str:
    """Scan loaded essences/tools and build a description for Jane's context."""
    ambient_base = os.environ.get("AMBIENT_BASE", os.path.expanduser("~/ambient"))
    tools_dir, essences_dir = essence_search_dirs(ambient_base, os.environ.get("TOOLS_DIR"))

    scan_entries: list[str] = []
    for scan_dir in [tools_dir, essences_dir]:
        if os.path.isdir(scan_dir):
            for entry in sorted(os.listdir(scan_dir)):
                scan_entries.append(os.path.join(scan_dir, entry))

    if not scan_entries:
        return ""

    tool_sections = []
    essence_sections = []
    for entry_path in scan_entries:
        entry = os.path.basename(entry_path)
        manifest_path = os.path.join(entry_path, "manifest.json")
        tools_path = os.path.join(entry_path, "functions", "custom_tools.py")
        if not os.path.isfile(manifest_path):
            continue

        try:
            with open(manifest_path) as handle:
                manifest = json.load(handle)
        except (json.JSONDecodeError, OSError):
            continue

        name = manifest.get("essence_name", entry)
        item_type = manifest.get("type", "tool")
        description = manifest.get("description", "")

        if item_type == "essence":
            section = f"### {name} (Essence — AI Agent)\n"
            section += f"Description: {description}\n"
            section += "Interaction: Delegate conversation to this essence. It has its own LLM brain and handles multi-step workflows autonomously.\n"
            if os.path.isfile(tools_path):
                tools = extract_tool_signatures(tools_path)
                if tools:
                    python_bin = os.environ.get("PYTHON_BIN", sys.executable)
                    section += f"Direct tool invoke (optional): `{python_bin} {tools_path} <function_name> '<json_args>'`\n"
                    section += "Available functions:\n"
                    for tool in tools:
                        section += f"- `{tool}`\n"
            essence_sections.append(section)
        else:
            if not os.path.isfile(tools_path):
                continue
            tools = extract_tool_signatures(tools_path)
            if not tools:
                continue

            python_bin = os.environ.get("PYTHON_BIN", sys.executable)
            section = f"### {name} (Tool)\n"
            section += f"Invoke: `{python_bin} {tools_path} <function_name> '<json_args>'`\n"
            section += "Available tools:\n"
            for tool in tools:
                section += f"- `{tool}`\n"
            tool_sections.append(section)

    parts = []
    if tool_sections:
        parts.append("## Tools\nYou invoke these directly on the user's behalf.\n\n" + "\n".join(tool_sections))
    if essence_sections:
        parts.append("## Essences (AI Agents)\nYou delegate to these — hand off the conversation when the user needs their expertise.\n\n" + "\n".join(essence_sections))

    return "\n\n".join(parts)
