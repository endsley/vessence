"""Risk classification + domain controls.

Phase 1 scope:
  - ``classify_action(action, args)`` → ``low | medium | high | critical``
  - ``domain_of(url)`` helper
  - Static block-list (``BLOCKED_DOMAINS``) for phishing/malware hosts
  - ``requires_confirmation(risk)`` gate

Saved workflows (Phase 3) will supply their own ``allowed_domains``
whitelist. For ad-hoc Phase 1 runs there is no whitelist — we rely on
Jane's user-facing confirmation prompts for high/critical actions.

Intentionally NOT here:
  - Secret redaction (that lives in ``artifacts.py`` since it's an
    artifact-writing concern).
  - Credential-domain binding (Phase 2, ``secrets.py``).
"""

from __future__ import annotations

import re
from typing import Any, Literal
from urllib.parse import urlparse

Risk = Literal["low", "medium", "high", "critical"]


# Minimal starter list — expand as we see real threats in the wild.
BLOCKED_DOMAINS: set[str] = {
    # Classic phishing / credential-stealer hosts — placeholder; real
    # list should come from a periodically-updated threat feed.
    "phishing.example",
    "malware.example",
}


# Phrase-based risk hints applied to navigation targets + extracted
# action intent. Purely heuristic — the real guard is the confirmation
# prompt Jane emits for high/critical.
_HIGH_RISK_KEYWORDS = (
    "pay", "payment", "checkout", "purchase", "buy-now",
    "transfer", "wire", "withdraw", "submit", "confirm",
    "delete", "unsubscribe", "cancel-subscription",
    "send-email", "send-message", "post-comment",
    "change-password", "change-email", "2fa-off",
)

_CRITICAL_KEYWORDS = (
    "pay-all", "wire-transfer", "delete-account",
    "transfer-all", "close-account",
)


def domain_of(url: str) -> str:
    """Return the host (no port) of ``url``, or empty on parse failure."""
    try:
        h = urlparse(url).hostname or ""
        return h.lower()
    except Exception:
        return ""


def is_blocked(url: str) -> bool:
    dom = domain_of(url)
    if not dom:
        return False
    return dom in BLOCKED_DOMAINS or any(
        dom.endswith("." + b) for b in BLOCKED_DOMAINS
    )


def classify_action(
    action: str,
    args: dict[str, Any],
    *,
    page: Any = None,
) -> Risk:
    """Return the risk level for one action invocation.

    Heuristic rules:
      - Navigation to a URL whose path contains a critical keyword → ``critical``
      - Navigation to a URL with a high-risk keyword → ``high``
      - ``click`` / ``fill`` / ``select`` on an element whose resolved
        name contains a high/critical keyword → that risk tier. ``page``
        is required to access the snapshot store for ref resolution.
      - ``extract``, ``snapshot``, ``status``, ``screenshot``, ``wait`` → ``low``
      - Everything else defaults to ``medium``.

    Perception-awareness (``page`` passed): ``click(ref="e04")`` with
    ``e04`` being a button named "Delete Account" correctly classifies
    as ``high``, even though the ref string itself is opaque.
    """
    action = (action or "").lower()
    if action in {"snapshot", "status", "wait", "screenshot"}:
        return "low"
    if action == "extract":
        return "low"
    if action == "navigate":
        url = args.get("url") or ""
        return _classify_url(url)

    # click / fill / press / select — resolve the ref via snapshot store,
    # then inspect role+name plus any literal text in args.
    resolved_name = ""
    resolved_role = ""
    ref = args.get("ref")
    if page is not None and isinstance(ref, str):
        # Lazy import to avoid a cycle (snapshot imports safety.domain_of).
        from .snapshot import lookup_ref
        el = lookup_ref(page, ref)
        if el is not None:
            resolved_name = (el.name or "").lower()
            resolved_role = (el.role or "").lower()

    blob = " ".join(
        [
            str(args.get("text", "")),
            str(args.get("value", "")),
            str(args.get("key", "")),
            resolved_name,
            resolved_role,
        ]
    ).lower()

    if _keyword_in(blob, _CRITICAL_KEYWORDS):
        return "critical"
    if _keyword_in(blob, _HIGH_RISK_KEYWORDS):
        return "high"
    return "medium"


def _classify_url(url: str) -> Risk:
    try:
        parsed = urlparse(url)
    except Exception:
        return "low"
    # Match against path + query only — avoids the "company" / "pay"
    # false positives Gemini flagged (hostnames + TLDs shouldn't trigger
    # risk unless clearly intended).
    path_blob = " ".join([
        (parsed.path or "").lower(),
        (parsed.query or "").lower(),
    ])
    if _keyword_in(path_blob, _CRITICAL_KEYWORDS):
        return "critical"
    if _keyword_in(path_blob, _HIGH_RISK_KEYWORDS):
        return "high"
    return "low"


def requires_confirmation(risk: Risk) -> bool:
    return risk in ("high", "critical")


_BOUNDARY = re.compile(r"[a-z0-9]+")


def _keyword_in(haystack: str, needles: tuple[str, ...]) -> bool:
    """Word-boundary-aware check. Splits haystack into alnum tokens and
    matches whole keywords (so "pay" won't fire on "company").

    Multi-word keywords (e.g. "pay-all", "delete-account") match by
    checking the hyphen-split tokens.
    """
    tokens = set(_BOUNDARY.findall(haystack))
    for n in needles:
        if "-" in n or " " in n:
            parts = re.split(r"[-\s]+", n)
            if all(p in tokens for p in parts if p):
                return True
        elif n in tokens:
            return True
    return False


__all__ = [
    "BLOCKED_DOMAINS",
    "Risk",
    "classify_action",
    "domain_of",
    "is_blocked",
    "requires_confirmation",
]
