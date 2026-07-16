#!/usr/bin/env python3
"""Codex MCP tools for Jane's shared code coordination board."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP


VESSENCE_HOME = Path(os.environ.get("VESSENCE_HOME", "/home/chieh/ambient/vessence"))
if str(VESSENCE_HOME) not in sys.path:
    sys.path.insert(0, str(VESSENCE_HOME))

from agent_skills.code_coordination import (  # noqa: E402
    ClaimConflict,
    CoordinationError,
    LegacyLockConflict,
    board_snapshot,
    claim_files,
    current_session_id,
    finish_task,
    format_board,
    heartbeat,
    post_message,
    post_task,
    release_files,
)


mcp = FastMCP("jane-coordination")


def _project(value: str) -> str | None:
    return str(value or "").strip() or None


def _error_text(exc: Exception) -> str:
    return f"Coordination blocked: {exc}"


@mcp.tool()
def code_coordination_board(project: str = "", include_history: bool = False) -> str:
    """Show active Codex tasks, file claims, messages, and exclusive locks.

    Call this before choosing an implementation slice in a shared codebase.
    Project may be an alias such as vessence, waterlily, or education, or an
    absolute project path.
    """
    try:
        snapshot = board_snapshot(
            project=_project(project),
            include_history=include_history,
            session_id=current_session_id(),
        )
        return format_board(snapshot, current_session=current_session_id())
    except CoordinationError as exc:
        return _error_text(exc)


@mcp.tool()
def post_code_task(task: str, project: str = "", files: list[str] | None = None) -> str:
    """Post this Codex task and optionally claim the files it will edit.

    Use before source edits. Claims are relative to the project root. Append
    `/**` to claim a directory tree. Do not claim the whole project unless the
    operation truly requires exclusivity.
    """
    try:
        item = post_task(
            task,
            project=_project(project),
            files=files or (),
            session_id=current_session_id(),
        )
        claims = ", ".join(claim["path"] for claim in item["claims"]) or "none"
        return f"Posted task #{item['id']} on {item['project']}; claims: {claims}"
    except (ClaimConflict, LegacyLockConflict, CoordinationError) as exc:
        return _error_text(exc)


@mcp.tool()
def claim_code_files(files: list[str], project: str = "", task: str = "") -> str:
    """Claim additional files or directory trees for the current posted task."""
    try:
        item = claim_files(
            files,
            project=_project(project),
            task=task or None,
            session_id=current_session_id(),
        )
        claims = ", ".join(claim["path"] for claim in item["claims"])
        return f"Task #{item['id']} now owns: {claims}"
    except (ClaimConflict, LegacyLockConflict, CoordinationError) as exc:
        return _error_text(exc)


@mcp.tool()
def release_code_files(files: list[str], project: str = "") -> str:
    """Release selected claims while keeping the current task active."""
    try:
        count = release_files(
            files,
            project=_project(project),
            session_id=current_session_id(),
        )
        return f"Released {count} claim(s)."
    except CoordinationError as exc:
        return _error_text(exc)


@mcp.tool()
def heartbeat_code_task(project: str = "") -> str:
    """Refresh the current task lease during a long-running implementation."""
    count = heartbeat(
        project=_project(project),
        session_id=current_session_id(),
    )
    return f"Refreshed {count} task lease(s)."


@mcp.tool()
def message_code_agents(message: str, project: str = "", to_session: str = "") -> str:
    """Post a broadcast or directed message to other Codex sessions."""
    try:
        message_id = post_message(
            message,
            project=_project(project),
            recipient_session_id=to_session or None,
            session_id=current_session_id(),
        )
        return f"Posted coordination message #{message_id}."
    except CoordinationError as exc:
        return _error_text(exc)


@mcp.tool()
def finish_code_task(
    project: str = "",
    result: str = "",
    canceled: bool = False,
    all_projects: bool = False,
) -> str:
    """Close current task claims, optionally across every active project."""
    changed = finish_task(
        project=_project(project),
        session_id=current_session_id(),
        result=result,
        canceled=canceled,
        all_projects=all_projects,
    )
    return "Task closed and claims released." if changed else "No active task found."


if __name__ == "__main__":
    mcp.run()
