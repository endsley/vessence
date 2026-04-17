"""Thread-safe session context for the v2 pipeline.

The pipeline sets the session_id at request entry via set_current_session_id().
Stage 2 handlers (or anything else running in the same async task) can read it
via get_current_session_id() without needing the dispatcher to pass it explicitly.
"""

from contextvars import ContextVar

_current_session_id: ContextVar[str | None] = ContextVar("_current_session_id", default=None)


def set_current_session_id(sid: str | None) -> None:
    _current_session_id.set(sid)


def get_current_session_id() -> str | None:
    return _current_session_id.get()
