import json
from datetime import datetime, timezone
from pathlib import Path

from jane.config import INTERRUPT_STACK_PATH, TASK_SPINE_PATH


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: str, default):
    file_path = Path(path)
    if not file_path.exists():
        return default
    try:
        return json.loads(file_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def _write_json(path: str, payload) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def load_task_spine() -> dict:
    default = {
        "primary_goal": "",
        "current_step": "",
        "next_steps": [],
        "side_quests": [],
        "return_to_step": "",
        "updated_at": "",
    }
    data = _read_json(TASK_SPINE_PATH, default)
    if not isinstance(data, dict):
        return default
    merged = {**default, **data}
    if not isinstance(merged.get("next_steps"), list):
        merged["next_steps"] = []
    if not isinstance(merged.get("side_quests"), list):
        merged["side_quests"] = []
    return merged


def save_task_spine(spine: dict) -> None:
    spine = {**spine}
    spine["updated_at"] = _utc_now()
    _write_json(TASK_SPINE_PATH, spine)


def load_interrupt_stack() -> list[dict]:
    data = _read_json(INTERRUPT_STACK_PATH, [])
    return data if isinstance(data, list) else []


def save_interrupt_stack(stack: list[dict]) -> None:
    _write_json(INTERRUPT_STACK_PATH, stack)


def set_primary_goal(primary_goal: str, current_step: str, next_steps: list[str]) -> dict:
    spine = load_task_spine()
    spine["primary_goal"] = primary_goal
    spine["current_step"] = current_step
    spine["next_steps"] = list(next_steps)
    spine["return_to_step"] = current_step
    save_task_spine(spine)
    return spine


def set_current_step(current_step: str, next_steps: list[str] | None = None) -> dict:
    spine = load_task_spine()
    spine["current_step"] = current_step
    spine["return_to_step"] = current_step
    if next_steps is not None:
        spine["next_steps"] = list(next_steps)
    save_task_spine(spine)
    return spine


def push_side_quest(task: str) -> dict:
    spine = load_task_spine()
    stack = load_interrupt_stack()
    stack.append(
        {
            "paused_primary_goal": spine.get("primary_goal", ""),
            "paused_step": spine.get("current_step", ""),
            "return_to_step": spine.get("return_to_step", "") or spine.get("current_step", ""),
            "side_quest": task,
            "paused_at": _utc_now(),
        }
    )
    save_interrupt_stack(stack)
    side_quests = list(spine.get("side_quests", []))
    if task not in side_quests:
        side_quests.append(task)
    spine["side_quests"] = side_quests
    save_task_spine(spine)
    return spine


def pop_side_quest(completed_task: str = "") -> dict:
    spine = load_task_spine()
    stack = load_interrupt_stack()
    if stack:
        frame = stack.pop()
        save_interrupt_stack(stack)
        spine["current_step"] = frame.get("return_to_step") or spine.get("current_step", "")
        spine["return_to_step"] = spine["current_step"]
    if completed_task:
        spine["side_quests"] = [item for item in spine.get("side_quests", []) if item != completed_task]
    save_task_spine(spine)
    return spine
