import re
import warnings

from agent_skills.private_handler_utils import _expires_at, pending_continuation


def test_pending_continuation_uses_warning_free_utc_expiry() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        pending = pending_continuation(
            handler_class="timer",
            awaiting="duration",
            question="How long?",
            data={"label": "tea"},
        )

    assert pending["data"] == {"label": "tea", "awaiting": "duration"}
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", pending["expires_at"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", _expires_at())
