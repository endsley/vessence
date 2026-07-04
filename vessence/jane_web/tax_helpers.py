"""Pure helpers for tax accountant web routes."""
from __future__ import annotations

import os
import json
import re
from collections.abc import Callable, Mapping
from typing import Any


_SAFE_TAX_FORM_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def is_safe_tax_form_name(form_name: str) -> bool:
    return bool(_SAFE_TAX_FORM_RE.match(form_name))


def tax_interview_answer_args(body: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "step_id": body.get("step_id", "filing_status"),
        "user_response": body.get("response", {}),
    }


def tax_tool_command(
    python_bin: str,
    tools_path: str,
    tool_name: str,
    args: Mapping[str, Any] | None = None,
) -> list[str]:
    command = [python_bin, tools_path, tool_name]
    if args:
        command.append(json.dumps(args))
    return command


def tax_tool_result_payload(returncode: int, stdout: str, stderr: str) -> dict[str, Any]:
    if returncode != 0:
        return {"status": "error", "message": stderr[:500]}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"status": "ok", "output": stdout.strip()}


def tax_output_dir(tax_essence_dir: str) -> str:
    return os.path.join(tax_essence_dir, "working_files", "output")


def latest_tax_form_file(
    output_dir: str,
    form_name: str,
    *,
    is_dir: Callable[[str], bool] = os.path.isdir,
    list_dir: Callable[[str], list[str]] = os.listdir,
) -> tuple[str, str] | None:
    if not is_dir(output_dir):
        return None
    matches = sorted([filename for filename in list_dir(output_dir) if filename.startswith(form_name)], reverse=True)
    if not matches:
        return None
    return (os.path.join(output_dir, matches[0]), matches[0])


def tax_result_path(tax_essence_dir: str) -> str:
    return os.path.join(tax_essence_dir, "working_files", "calculations", "tax_result.json")


def tax_uploads_dir(tax_essence_dir: str) -> str:
    return os.path.join(tax_essence_dir, "user_data", "uploads")


def tax_upload_path(uploads_dir: str, filename: str | None) -> str:
    safe_name = os.path.basename(filename or "upload")
    return os.path.join(uploads_dir, safe_name)


def tax_upload_document_args(file_path: str, doc_type: str) -> dict[str, str]:
    return {"file_path": file_path, "doc_type": doc_type}
