"""Handler invocation helpers for the v2 Stage 2 dispatcher."""

from __future__ import annotations

import inspect
from typing import Any


def accepted_handler_params(handler: Any) -> set[str]:
    """Return optional dispatcher kwargs accepted by `handler`."""
    try:
        parameters = inspect.signature(handler).parameters
    except (TypeError, ValueError):
        return set()
    return {name for name in ("context", "pending", "params") if name in parameters}


def build_handler_kwargs(
    handler: Any,
    *,
    context: str,
    pending: dict | None,
    params: dict | None,
) -> dict[str, Any]:
    """Build backward-compatible kwargs for a Stage 2 handler."""
    accepted = accepted_handler_params(handler)
    kwargs: dict[str, Any] = {}
    if "context" in accepted:
        kwargs["context"] = context
    if "pending" in accepted:
        handler_pending = pending
        if isinstance(handler_pending, dict) and "question" in handler_pending:
            handler_pending = dict(handler_pending)
            handler_pending.pop("question", None)
        kwargs["pending"] = handler_pending
    if "params" in accepted:
        kwargs["params"] = params
    return kwargs
