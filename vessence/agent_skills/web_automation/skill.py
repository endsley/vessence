"""Web automation orchestrator — the Python surface Jane calls.

Phase 1 gives Jane two entry points:

  - :func:`run_task`: one-shot, takes an explicit ordered plan of actions,
    executes them under a single browser session, returns a summary.
    This is the fastest path — no LLM loop, no tool-calling protocol.
    Used by saved workflows (Phase 3) and by the handler when Opus has
    already decided the full plan.

  - :func:`dispatch_action`: low-level single-action entry used by the
    CLIENT_TOOL path. Opus emits ``web.<action>`` tool calls; the handler
    translates each into one ``dispatch_action`` call against the active
    session. The session itself is kept alive between calls by the
    caller (see ``jane_v2/classes/web_automation/handler.py``).

Safety is applied inside ``dispatch_action``: every action is classified
and a high/critical action with ``confirm=False`` is refused. The Jane
handler sets ``confirm=True`` after explicit user approval.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from . import actions as _actions
from . import safety as _safety
from .artifacts import RunDir, new_run_id
from .browser_session import BrowserSessionManager, SessionOptions

logger = logging.getLogger(__name__)


@dataclass
class TaskStep:
    """One entry in a pre-planned task."""
    action: str
    args: dict[str, Any] = field(default_factory=dict)
    confirm: bool = False  # Set True if the user has pre-approved this step.


@dataclass
class TaskResult:
    ok: bool
    run_id: str
    summary: str
    data: dict[str, Any] = field(default_factory=dict)


async def run_task(
    steps: list[TaskStep],
    *,
    label: str = "adhoc",
    options: SessionOptions | None = None,
) -> TaskResult:
    """Execute a pre-planned ordered list of actions in one browser session.

    Returns a :class:`TaskResult` with the final summary line and any
    extracted data. Creates a run directory for traces/artifacts and
    tears the browser context down when done.
    """
    run_id = new_run_id(label=label)
    run = RunDir(run_id)
    mgr = BrowserSessionManager.instance()

    final_data: dict[str, Any] = {}
    last_message = ""
    success = True

    try:
        async with mgr.session(run_id=run_id, options=options) as sess:
            for i, step in enumerate(steps, start=1):
                res = await dispatch_action(
                    sess.page,
                    action=step.action,
                    args=step.args,
                    run=run,
                    confirmed=step.confirm,
                )
                last_message = res.message
                if res.data:
                    final_data[f"step_{i}"] = res.data
                if not res.ok:
                    success = False
                    run.note_error(f"step {i} {step.action}: {res.message}")
                    break
        run.finish(status="completed" if success else "failed")
    except Exception as e:
        logger.exception("skill.run_task crashed: %s", e)
        run.note_error(f"run crashed: {e}")
        run.finish(status="failed")
        return TaskResult(ok=False, run_id=run_id, summary=f"Run crashed: {e}")

    return TaskResult(
        ok=success,
        run_id=run_id,
        summary=last_message or ("Run complete." if success else "Run failed."),
        data=final_data,
    )


async def dispatch_action(
    page: Any,
    *,
    action: str,
    args: dict[str, Any],
    run: RunDir,
    confirmed: bool = False,
) -> _actions.ActionResult:
    """Execute a single action against ``page`` and log it to ``run``.

    ``confirmed`` must be True when the action's risk is high or critical;
    otherwise this refuses and returns a prompting ``ActionResult`` that
    Jane surfaces to the user.
    """
    entry = _actions.REGISTRY.get(action)
    if entry is None:
        return _actions.ActionResult(
            ok=False,
            message=f"Unknown action: {action!r}",
        )

    # Validate required args — typed-registry pattern from browser-use.
    required = entry["required"]
    missing = [r for r in required if r not in args]
    if missing:
        return _actions.ActionResult(
            ok=False,
            message=f"Missing arg(s) for {action!r}: {', '.join(missing)}",
        )

    # URL-level block list.
    if action == "navigate" and _safety.is_blocked(args.get("url", "")):
        return _actions.ActionResult(
            ok=False,
            message=f"Refused: {args.get('url')!r} is in the block list.",
        )

    risk = _safety.classify_action(action, args, page=page)
    if _safety.requires_confirmation(risk) and not confirmed:
        return _actions.ActionResult(
            ok=False,
            message=(
                f"This {action} looks like a {risk}-risk action "
                f"(args={args}). Ask the user to confirm before proceeding."
            ),
            data={"needs_confirmation": True, "risk": risk},
        )

    fn = entry["fn"]
    t0 = time.perf_counter()
    try:
        result = await fn(page, **args)
    except TypeError as e:
        # Action got extra or wrong-typed kwargs; treat as bad input
        # rather than a crash.
        return _actions.ActionResult(
            ok=False, message=f"Bad args for {action!r}: {e}"
        )
    except Exception as e:
        logger.exception("skill.dispatch_action %s crashed: %s", action, e)
        result = _actions.ActionResult(ok=False, message=f"{action} crashed: {e}")
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    url = ""
    title = ""
    try:
        url = page.url
    except Exception:
        pass

    run.append_step(
        action=action,
        args=args,
        ok=result.ok,
        message=result.message,
        duration_ms=elapsed_ms,
        url=url,
        title=title,
    )
    return result


__all__ = [
    "TaskResult",
    "TaskStep",
    "dispatch_action",
    "run_task",
]
