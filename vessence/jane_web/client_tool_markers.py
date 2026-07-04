"""Client-tool marker extraction and TOOL_RESULT formatting helpers."""

from __future__ import annotations

import json
import re as _re
import uuid as _uuid

from jane_web.client_tool_json import find_json_object_end


def build_client_tool_marker(tool: str, args: dict, *, compact_json: bool = False) -> str:
    separators = (",", ":") if compact_json else None
    payload = json.dumps(args, separators=separators)
    return f"[[CLIENT_TOOL:{tool}:{payload}]]"


class ToolMarkerExtractor:
    """Streaming extractor for ``[[CLIENT_TOOL:name:json]]`` markers."""

    _OPEN = "[[CLIENT_TOOL:"
    _CLOSE = "]]"
    _MAX_HOLD = 4096
    _FENCE = "```"
    _TOOL_NAME_RE = _re.compile(r"^[a-z][a-z0-9_.]*$")

    def __init__(self) -> None:
        self._buffer: str = ""
        self._in_fence: bool = False

    def feed(self, chunk: str) -> tuple[str, list[dict]]:
        """Consume a delta chunk, return (safe_visible_text, tool_calls)."""
        if not chunk:
            return "", []
        self._buffer += chunk
        if len(self._buffer) > self._MAX_HOLD * 2:
            visible = self._buffer
            self._buffer = ""
            return visible, []
        return self._drain()

    def flush(self) -> tuple[str, list[dict]]:
        """Reveal any residual buffered text at stream end."""
        visible, calls = self._drain(final=True)
        tail = self._buffer
        self._buffer = ""
        out = visible + tail
        out = self._strip_orphan_close(out)
        return out, calls

    @classmethod
    def _strip_orphan_close(cls, text: str) -> str:
        """Remove trailing `]]` that is not paired with an earlier `[[`."""
        stripped = text.rstrip()
        while stripped.endswith(cls._CLOSE) and cls._OPEN not in stripped:
            stripped = stripped[: -len(cls._CLOSE)].rstrip()
        if stripped == text.rstrip():
            return text
        return stripped

    def _drain(self, final: bool = False) -> tuple[str, list[dict]]:
        """Extract complete markers from ``self._buffer``."""
        out_visible_parts: list[str] = []
        out_calls: list[dict] = []

        while True:
            if self._in_fence:
                close_idx = self._buffer.find(self._FENCE)
                if close_idx < 0:
                    hold = self._partial_fence_suffix_len(self._buffer)
                    if hold > 0:
                        out_visible_parts.append(self._buffer[:-hold])
                        self._buffer = self._buffer[-hold:]
                    else:
                        out_visible_parts.append(self._buffer)
                        self._buffer = ""
                    break
                end = close_idx + len(self._FENCE)
                out_visible_parts.append(self._buffer[:end])
                self._buffer = self._buffer[end:]
                self._in_fence = False
                continue

            opener_idx = self._buffer.find(self._OPEN)
            fence_idx = self._buffer.find(self._FENCE)
            next_opener = opener_idx if opener_idx >= 0 else len(self._buffer) + 1
            next_fence = fence_idx if fence_idx >= 0 else len(self._buffer) + 1

            if next_opener >= len(self._buffer) and next_fence >= len(self._buffer):
                hold = max(
                    self._partial_opener_suffix_len(self._buffer),
                    self._partial_fence_suffix_len(self._buffer),
                )
                if hold > 0:
                    out_visible_parts.append(self._buffer[:-hold])
                    self._buffer = self._buffer[-hold:]
                else:
                    out_visible_parts.append(self._buffer)
                    self._buffer = ""
                break

            if next_fence < next_opener:
                end = next_fence + len(self._FENCE)
                out_visible_parts.append(self._buffer[:end])
                self._buffer = self._buffer[end:]
                self._in_fence = True
                continue

            if next_opener > 0:
                out_visible_parts.append(self._buffer[:next_opener])
                self._buffer = self._buffer[next_opener:]

            close_end = self._find_marker_end(self._buffer)
            if close_end is None:
                if final or len(self._buffer) > self._MAX_HOLD:
                    out_visible_parts.append(self._buffer)
                    self._buffer = ""
                break

            marker_text = self._buffer[:close_end]
            parsed = self._parse_marker(marker_text)
            if parsed is not None:
                out_calls.append(parsed)
            else:
                out_visible_parts.append(marker_text)
            self._buffer = self._buffer[close_end:]

        return "".join(out_visible_parts), out_calls

    @staticmethod
    def _partial_opener_suffix_len(buf: str) -> int:
        """Length of the longest suffix of buf that is a proper prefix of _OPEN."""
        open_tok = ToolMarkerExtractor._OPEN
        max_check = min(len(buf), len(open_tok) - 1)
        for i in range(max_check, 0, -1):
            if buf.endswith(open_tok[:i]):
                return i
        return 0

    @staticmethod
    def _partial_fence_suffix_len(buf: str) -> int:
        """Length of longest suffix of buf that is a proper prefix of ```."""
        fence = ToolMarkerExtractor._FENCE
        max_check = min(len(buf), len(fence) - 1)
        for i in range(max_check, 0, -1):
            if buf.endswith(fence[:i]):
                return i
        return 0

    @classmethod
    def _find_marker_end(cls, buf: str) -> int | None:
        """Find the exclusive end index of a complete CLIENT_TOOL marker."""
        assert buf.startswith(cls._OPEN)
        if len(buf) > cls._MAX_HOLD:
            close = buf.find(cls._CLOSE, len(cls._OPEN))
            if 0 < close < cls._MAX_HOLD:
                return close + len(cls._CLOSE)
            return cls._MAX_HOLD
        i = len(cls._OPEN)
        name_start = i
        while i < len(buf) and buf[i] != ":":
            i += 1
        if i >= len(buf):
            return None
        if i == name_start:
            close = buf.find(cls._CLOSE, i)
            return close + len(cls._CLOSE) if close >= 0 else None
        i += 1
        if i >= len(buf):
            return None
        if buf[i] != "{":
            close = buf.find(cls._CLOSE, i)
            return close + len(cls._CLOSE) if close >= 0 else None
        json_end = find_json_object_end(buf, i)
        if json_end is None:
            return None
        if buf.startswith(cls._CLOSE, json_end):
            return json_end + len(cls._CLOSE)
        j = json_end
        while j < len(buf) and buf[j] in " \t\r\n":
            j += 1
        if j >= len(buf):
            return None
        if buf.startswith(cls._CLOSE, j):
            return j + len(cls._CLOSE)
        close = buf.find(cls._CLOSE, j)
        return close + len(cls._CLOSE) if close >= 0 else None

    @classmethod
    def _parse_marker(cls, marker_text: str) -> dict | None:
        """Parse ``[[CLIENT_TOOL:name:{json}]]`` into {tool, args, call_id}."""
        if not marker_text.startswith(cls._OPEN) or not marker_text.endswith(cls._CLOSE):
            return None
        inner = marker_text[len(cls._OPEN) : -len(cls._CLOSE)].rstrip()
        colon = inner.find(":")
        if colon < 0:
            return None
        name = inner[:colon].strip()
        if not cls._TOOL_NAME_RE.match(name):
            return None
        json_str = inner[colon + 1 :].strip()
        try:
            args = json.loads(json_str)
        except Exception:
            return None
        if not isinstance(args, dict):
            return None
        return {
            "tool": name,
            "args": args,
            "call_id": str(_uuid.uuid4()),
        }


def visible_text_and_client_tool_calls(text: str) -> tuple[str, list[dict]]:
    """Strip complete CLIENT_TOOL markers from a full text payload."""
    extractor = ToolMarkerExtractor()
    visible, tool_calls = extractor.feed(text)
    tail, tail_calls = extractor.flush()
    return (visible or "") + (tail or ""), tool_calls + tail_calls


_TOOL_RESULT_OPEN = "[TOOL_RESULT:"
_TOOL_RESULT_CLOSE = "]"


def _leading_tool_result_marker(user_message: str) -> tuple[dict, int] | None:
    stripped = user_message.lstrip()
    if not stripped.startswith(_TOOL_RESULT_OPEN):
        return None
    json_start = len(user_message) - len(stripped) + len(_TOOL_RESULT_OPEN)
    while json_start < len(user_message) and user_message[json_start] in " \t":
        json_start += 1
    if json_start >= len(user_message) or user_message[json_start] != "{":
        return None
    json_end = find_json_object_end(user_message, json_start)
    if json_end is None:
        return None
    marker_end = json_end
    while marker_end < len(user_message) and user_message[marker_end] in " \t":
        marker_end += 1
    if marker_end >= len(user_message) or user_message[marker_end] != _TOOL_RESULT_CLOSE:
        return None
    try:
        payload = json.loads(user_message[json_start:json_end])
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload, marker_end + len(_TOOL_RESULT_CLOSE)


def extract_tool_results(user_message: str) -> tuple[str, list[dict]]:
    """Strip leading [TOOL_RESULT:{json}] markers from a user message."""
    results: list[dict] = []
    cleaned = user_message
    while True:
        marker = _leading_tool_result_marker(cleaned)
        if marker is None:
            break
        payload, marker_end = marker
        results.append(payload)
        cleaned = cleaned[marker_end:].lstrip()
    return cleaned, results


_DELIM_OPEN = (
    "[PHONE TOOL RESULTS — results from tools that ran on the Android client since the last turn. "
    "Use these as background context, but ALWAYS prioritize the user's current message below. "
    "If the user has moved on to a new topic, respond to THEIR message first — "
    "do not fixate on stale tool results. Only mention tool results if they are "
    "directly relevant to what the user is asking NOW.]"
)
_DELIM_CLOSE = "[END PHONE TOOL RESULTS]"


def neutralize_delimiters(value: str) -> str:
    """Defuse substrings that could be mistaken for phone-tool result delimiters."""
    if not isinstance(value, str):
        return str(value)
    value = value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    value = value.replace("[PHONE TOOL RESULTS", "[phone_tool_results")
    value = value.replace("[END PHONE TOOL RESULTS", "[end_phone_tool_results")
    if len(value) > 2000:
        value = value[:2000] + "…(truncated)"
    return value


def format_tool_results_for_brain(results: list[dict]) -> str:
    """Format parsed tool results as a context block for Jane's mind."""
    if not results:
        return ""
    lines = [_DELIM_OPEN]
    for result in results:
        tool = neutralize_delimiters(result.get("tool", "?"))
        status = neutralize_delimiters(result.get("status", "?"))
        message = neutralize_delimiters(result.get("message", ""))
        lines.append(f"- tool={tool} status={status} message={message!r}")
        data = result.get("data")
        if isinstance(data, dict) and data:
            try:
                json_str = neutralize_delimiters(json.dumps(data, ensure_ascii=True))
                lines.append(f"  data={json_str}")
            except Exception:
                pass
        extra = result.get("extra")
        if isinstance(extra, dict) and extra:
            try:
                lines.append(f"  extra={neutralize_delimiters(json.dumps(extra, ensure_ascii=True))}")
            except Exception:
                pass
    lines.append(_DELIM_CLOSE)
    return "\n".join(lines)
