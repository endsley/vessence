"""Pure Markdown document helpers for the autonomous job queue runner."""
from __future__ import annotations

import re
from pathlib import Path


PRIORITY_MAP = {"high": 1, "1": 1, "medium": 2, "2": 2, "low": 3, "3": 3}
PROMPT_SECTIONS = ["Objective", "Context", "Steps", "Verification", "Files Involved", "Notes"]
SELF_CONTINUATION_INSTRUCTION = (
    "\n\n## Self-Continuation\n"
    "At the end of EVERY response, run:\n"
    "```bash\n"
    "/home/chieh/google-adk-env/adk-venv/bin/python "
    "$VESSENCE_HOME/agent_skills/check_continuation.py\n"
    "```\n"
    "If `should_continue` is true: display "
    "`**[Auto-continuing → Job #N]:** [text]` and execute `run job queue:`. "
    "Repeat until false. If false, stop silently."
)


def parse_job_content(content: str, file_path: str) -> dict:
    title_match = re.search(r"^# Job:\s*(.+)", content, re.MULTILINE)
    status_match = re.search(r"^Status:\s*(.+)", content, re.MULTILINE)
    priority_match = re.search(r"^Priority:\s*(.+)", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else Path(file_path).stem
    status = status_match.group(1).strip().split()[0].lower() if status_match else "unknown"
    priority_raw = priority_match.group(1).strip().lower() if priority_match else "3"
    priority = PRIORITY_MAP.get(priority_raw, 3)
    return {
        "file": file_path,
        "title": title,
        "status": status,
        "priority": priority,
        "content": content,
    }


def job_num_from_filename(file_path: str, default: int = 999) -> int:
    match = re.match(r"^(\d+)", Path(file_path).name)
    return int(match.group(1)) if match else default


def pending_job_summary(
    content: str,
    file_path: str,
    *,
    missing_title: str | None = None,
) -> dict | None:
    job = parse_job_content(content, file_path)
    if job["status"] != "pending":
        return None
    if missing_title is not None and not re.search(r"^# Job:\s*(.+)", content, re.MULTILINE):
        job["title"] = missing_title
    return {
        "num": job_num_from_filename(file_path),
        "title": job["title"],
        "priority": job["priority"],
        "file": file_path,
    }


def sort_pending_job_summaries(jobs: list[dict]) -> list[dict]:
    return sorted(jobs, key=lambda job: (job["priority"], job["num"]))


def pending_job_summaries_from_dir(jobs_dir: str | Path) -> list[dict]:
    root = Path(jobs_dir)
    if not root.is_dir():
        return []

    jobs = []
    for path in sorted(root.iterdir(), key=lambda p: p.name):
        if path.suffix != ".md" or path.name == "README.md" or not path.is_file():
            continue
        try:
            content = path.read_text()
            job = pending_job_summary(content, str(path), missing_title=path.name)
            if job:
                jobs.append(job)
        except Exception:
            continue
    return sort_pending_job_summaries(jobs)


def set_status_content(content: str, new_status: str, result_summary: str = "") -> str:
    content = re.sub(
        r"^Status:\s*.+",
        f"Status: {new_status}",
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if not result_summary:
        return content
    if "## Result" in content:
        return re.sub(
            r"## Result\s*\n.*",
            f"## Result\n{result_summary}",
            content,
            count=1,
            flags=re.DOTALL,
        )
    return content.rstrip() + f"\n\n## Result\n{result_summary}\n"


def build_prompt(job: dict) -> str:
    content = job["content"]
    prompt_parts = [f"# Task: {job['title']}", ""]
    for section in PROMPT_SECTIONS:
        match = re.search(
            rf"^## {section}\s*\n(.*?)(?=^## |\Z)",
            content,
            re.MULTILINE | re.DOTALL,
        )
        if not match:
            continue
        body = match.group(1).strip()
        if not body:
            continue
        prompt_parts.append(f"## {section}")
        prompt_parts.append(body)
        prompt_parts.append("")
    prompt_text = "\n".join(prompt_parts).strip()
    return prompt_text + SELF_CONTINUATION_INSTRUCTION
