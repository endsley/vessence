"""Dynamic loader for the tools/ + platforms/ directory structure.

A "tool" is a self-contained capability that Jane can invoke. Each tool lives
in its own folder at ~/ambient/tools/<name>/ with this layout:

    tools/<name>/
      mcp.json                 — declarative tool catalog (required)
      prompt.md                — system prompt section injected into Jane's
                                 context builder (required)
      server/                  — Python module with hooks (optional)
        __init__.py            — exports register() that returns a ToolHooks
        ...                    — tool-specific helpers, regex patterns, etc
      android/                 — Kotlin sources merged into the Android app
                                 at build time by the Gradle generator
        tools/*.kt             — handlers
        contacts/*.kt          — tool-internal helpers
        ...
        manifest-fragment.xml  — permissions/services merged into the main
                                 manifest (optional)

Jane's kernel code (jane/, jane_web/) discovers tools by scanning this
directory at startup. No hard-coded per-tool logic lives in the kernel.

The loader exposes:
  - load_all_tools()              — scan tools/, cache results
  - all_prompt_sections()         — list of markdown/plaintext prompt blocks
  - all_pre_dispatch_filters()    — list of callables (history) → bool
                                    (True = skip initial ack layer)
  - get_tool_mcp(name)            — raw MCP dict for a tool

Individual tool server hooks implement a tiny protocol: their __init__.py
exports a register() function returning a ToolHooks dataclass. The loader
calls register() once at startup and caches the result.
"""

from __future__ import annotations

import importlib
import importlib.util
import json as _json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class ToolHooks:
    """What a tool's server-side Python module can contribute to the kernel.

    All fields are optional. A tool that's purely client-side (all logic in
    Android handlers) can still have a prompt section and an MCP without
    providing any Python hooks.
    """

    # Returns True if the current turn should SKIP the Gemma initial-ack
    # layer and route straight to Jane's mind. Used by tools with multi-turn
    # state (e.g., SMS draft loop). Receives the in-memory conversation
    # history; returns a boolean. Called once per user turn.
    pre_dispatch_filters: list[Callable[[list[dict]], bool]] = field(default_factory=list)

    # Additional prompt text to append to Jane's system sections. Usually the
    # prompt.md content is enough, but a tool can contribute dynamic text too
    # (e.g., "today's weather cache is stale"). Called once per context build.
    dynamic_prompt_contributors: list[Callable[[dict], str]] = field(default_factory=list)


@dataclass
class LoadedTool:
    name: str                    # folder name (e.g., "phone")
    mcp: dict                    # parsed mcp.json
    prompt_text: str             # contents of prompt.md (empty string if missing)
    hooks: ToolHooks             # from server/__init__.py::register() (default empty)
    folder: Path                 # absolute path to the tool folder


_TOOLS_DIR_ENV = "JANE_TOOLS_DIR"
_DEFAULT_TOOLS_DIR = Path.home() / "ambient" / "tools"

_loaded_tools: list[LoadedTool] | None = None


def _tools_dir() -> Path:
    raw = os.environ.get(_TOOLS_DIR_ENV)
    if raw:
        return Path(raw)
    return _DEFAULT_TOOLS_DIR


def load_all_tools(force_reload: bool = False) -> list[LoadedTool]:
    """Scan the tools directory and load every tool found.

    Idempotent: result is cached in a module-level variable. Pass
    force_reload=True to re-scan (useful for tests or hot reloads). On
    force_reload, any previously-loaded tool modules are removed from
    sys.modules so stale code is not retained.
    """
    global _loaded_tools

    if force_reload and _loaded_tools is not None:
        # Purge any previously-loaded tool modules from sys.modules so a
        # re-scan sees fresh code. We use the same name prefix the loader
        # uses internally to spec modules below.
        import sys as _sys
        stale = [k for k in _sys.modules if k.startswith("_jane_tool_")]
        for k in stale:
            _sys.modules.pop(k, None)

    if _loaded_tools is not None and not force_reload:
        return _loaded_tools

    base = _tools_dir()
    tools: list[LoadedTool] = []
    if not base.exists():
        logger.warning("tool_loader: tools dir does not exist: %s", base)
        _loaded_tools = tools
        return tools

    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        if entry.is_symlink():
            # Symlink targets could point outside the expected tools tree;
            # refuse to follow them to keep the isolation boundary tight.
            logger.warning("tool_loader: refusing to follow symlink %s", entry)
            continue
        if entry.name.startswith("."):
            continue
        mcp_path = entry / "mcp.json"
        if not mcp_path.exists():
            continue  # not a tool folder
        try:
            tool = _load_single_tool(entry)
            tools.append(tool)
            logger.info("tool_loader: loaded '%s' (mcp=%s prompt=%d chars hooks=%s)",
                        tool.name, mcp_path.name, len(tool.prompt_text),
                        _hooks_summary(tool.hooks))
        except Exception as e:
            logger.error("tool_loader: failed to load '%s': %s", entry.name, e,
                         exc_info=True)

    _loaded_tools = tools
    return tools


def _load_single_tool(folder: Path) -> LoadedTool:
    name = folder.name
    # MCP (required)
    mcp_path = folder / "mcp.json"
    try:
        mcp = _json.loads(mcp_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"invalid mcp.json: {e}") from e
    if not isinstance(mcp, dict):
        raise RuntimeError("mcp.json must be a JSON object")

    # Prompt (required per spec, but loader is lenient — empty string if missing
    # so tools can migrate incrementally).
    prompt_path = folder / "prompt.md"
    prompt_text = ""
    if prompt_path.exists():
        try:
            prompt_text = prompt_path.read_text(encoding="utf-8").strip()
        except Exception as e:
            logger.warning("tool_loader: could not read %s: %s", prompt_path, e)

    # Server hooks (optional)
    hooks = _load_server_hooks(folder) or ToolHooks()

    return LoadedTool(name=name, mcp=mcp, prompt_text=prompt_text, hooks=hooks, folder=folder)


def _load_server_hooks(folder: Path) -> ToolHooks | None:
    server_init = folder / "server" / "__init__.py"
    if not server_init.exists():
        return None
    # Load as a standalone module so tool server code doesn't pollute the
    # top-level package namespace.
    module_name = f"_jane_tool_{folder.name}"
    spec = importlib.util.spec_from_file_location(module_name, server_init)
    if spec is None or spec.loader is None:
        logger.warning("tool_loader: could not build spec for %s", server_init)
        return None
    try:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:
        logger.error("tool_loader: exec_module failed for %s: %s", server_init, e,
                     exc_info=True)
        return None
    if not hasattr(mod, "register"):
        # No explicit register() — a tool can have server/ helpers without
        # contributing any kernel hooks. Return empty ToolHooks.
        return ToolHooks()
    try:
        result = mod.register()
    except Exception as e:
        logger.error("tool_loader: register() failed for %s: %s", server_init, e,
                     exc_info=True)
        return ToolHooks()
    if not isinstance(result, ToolHooks):
        logger.warning("tool_loader: register() for %s did not return ToolHooks (got %s)",
                       folder.name, type(result).__name__)
        return ToolHooks()
    return result


def _hooks_summary(h: ToolHooks) -> str:
    return f"pre_dispatch={len(h.pre_dispatch_filters)} dynamic_prompt={len(h.dynamic_prompt_contributors)}"


# ── Convenience accessors used by the kernel ──────────────────────────────


def all_prompt_sections() -> list[str]:
    """Return every tool's static prompt.md content, in alphabetical tool order."""
    return [t.prompt_text for t in load_all_tools() if t.prompt_text]


def all_pre_dispatch_filters() -> list[Callable[[list[dict]], bool]]:
    """Return every pre-dispatch filter contributed by all loaded tools."""
    out: list[Callable[[list[dict]], bool]] = []
    for t in load_all_tools():
        out.extend(t.hooks.pre_dispatch_filters)
    return out


def get_tool_mcp(name: str) -> dict | None:
    for t in load_all_tools():
        if t.name == name:
            return t.mcp
    return None


def should_skip_initial_ack(history: list[dict]) -> bool:
    """Run every tool's pre-dispatch filters. If ANY returns True, skip the
    Gemma initial-ack layer and route the current turn straight to Jane's mind.
    """
    for f in all_pre_dispatch_filters():
        try:
            if f(history):
                return True
        except Exception as e:
            logger.warning("tool_loader: pre_dispatch filter raised: %s", e)
    return False
