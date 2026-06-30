"""Shared text sanitizers for untrusted model/context input."""

from __future__ import annotations

import re

_CLIENT_TOOL_MARKER_RE = re.compile(r"\[\[CLIENT_TOOL:", re.IGNORECASE)


def strip_client_tool_markers(text: str | None) -> str | None:
    """Neutralize client-tool marker openers in untrusted text.

    Replacing only the opener preserves surrounding content for diagnostics
    while preventing ``ToolMarkerExtractor`` from recognizing the string as an
    executable Android client-tool request.
    """
    if text is None:
        return None
    return _CLIENT_TOOL_MARKER_RE.sub("[[CLIENT-TOOL-STRIPPED:", text)
