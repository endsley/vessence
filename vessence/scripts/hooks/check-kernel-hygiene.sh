#!/usr/bin/env bash
# Vessence kernel hygiene lint — complement to the git pre-commit hook.
#
# The git pre-commit hook enforces tool/kernel isolation at commit time, BUT
# only for files git sees. Since tools/ is gitignored right now, git cannot
# see violations where a kernel file has been hardcoded to reference a specific
# tool. This script runs a static scan to catch those:
#
#   1. Kernel Python (vessence/jane/, vessence/jane_web/) must NOT contain
#      hardcoded strings naming specific tools (e.g., "contacts.sms_draft",
#      "messages.fetch_unread"). All such references should come from the
#      tool_loader.
#
#   2. Kernel Kotlin (vessence/android/app/src/main/java/com/vessences/android/)
#      — excluding files under tools/, contacts/, notifications/ which are
#      waiting for Phase 8 migration — must NOT import from per-tool packages.
#
#   3. Any import of ContactsCallHandler, ContactsSmsHandler, etc. from
#      non-dispatcher kernel code fails the scan.
#
# Exit codes:
#   0 — clean
#   1 — violations found
#
# Run manually: `vessence/scripts/hooks/check-kernel-hygiene.sh`
# Or wire into CI. This is NOT a commit-blocker; it's a drift detector.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

EXIT=0

# ── Rule 1: kernel Python must not hardcode tool names ─────────────────
# Allowlist: jane/tool_loader.py (legitimately knows tool concepts),
#            jane_web/jane_proxy.py fallback block (transitional — will be
#            removed once Phase 8 retires the legacy _has_open_sms_draft path).

BANNED_PY_PATTERNS=(
    "contacts\\.sms_draft"
    "contacts\\.sms_send"
    "contacts\\.sms_cancel"
    "contacts\\.call"
    "messages\\.fetch_unread"
    "messages\\.read_recent"
    "PHONE_TOOLS_PROTOCOL"
)

ALLOWLIST_PY=(
    "jane/tool_loader.py"
    "jane/context_builder.py"       # still holds PHONE_TOOLS_PROTOCOL fallback constant — Phase 7e removes it
)

is_allowlisted_py() {
    local f="$1"
    for allow in "${ALLOWLIST_PY[@]}"; do
        [ "$f" = "$allow" ] && return 0
    done
    return 1
}

echo "── Rule 1: kernel Python tool-name scan ──"
for pattern in "${BANNED_PY_PATTERNS[@]}"; do
    matches=$(grep -rln --include="*.py" -E "$pattern" jane/ jane_web/ 2>/dev/null || true)
    if [ -n "$matches" ]; then
        while IFS= read -r f; do
            [ -z "$f" ] && continue
            if ! is_allowlisted_py "$f"; then
                echo "  ⚠  $f contains banned pattern '$pattern'"
                EXIT=1
            fi
        done <<< "$matches"
    fi
done
[ "$EXIT" -eq 0 ] && echo "  ✓ clean (allowlist respected)"

# ── Rule 2: kernel Kotlin must not import per-tool handler packages ────
# Transitional allowlist: handler files themselves + ClientToolDispatcher (which
# currently registers handlers by name — Phase 8 auto-discovers via the Gradle
# generator and removes these references).

echo ""
echo "── Rule 2: kernel Kotlin per-tool import scan ──"
ANDROID_ROOT="android/app/src/main/java/com/vessences/android"
ALLOWLIST_KT=(
    "${ANDROID_ROOT}/tools/ClientToolDispatcher.kt"  # transitional — holds registration
    "${ANDROID_ROOT}/tools/ContactsCallHandler.kt"
    "${ANDROID_ROOT}/tools/ContactsSmsHandler.kt"
    "${ANDROID_ROOT}/tools/MessagesReadRecentHandler.kt"
    "${ANDROID_ROOT}/tools/MessagesFetchUnreadHandler.kt"
    "${ANDROID_ROOT}/contacts/ContactsResolver.kt"
    "${ANDROID_ROOT}/notifications/VessenceNotificationListener.kt"
    "${ANDROID_ROOT}/notifications/RecentMessagesBuffer.kt"
)

is_allowlisted_kt() {
    local f="$1"
    for allow in "${ALLOWLIST_KT[@]}"; do
        [ "$f" = "$allow" ] && return 0
    done
    return 1
}

# Simple forbidden-import patterns: kernel code should not import handler classes by name
FORBIDDEN_KT=(
    "import com\\.vessences\\.android\\.tools\\.ContactsCallHandler"
    "import com\\.vessences\\.android\\.tools\\.ContactsSmsHandler"
    "import com\\.vessences\\.android\\.tools\\.MessagesReadRecentHandler"
    "import com\\.vessences\\.android\\.tools\\.MessagesFetchUnreadHandler"
)

KT_BEFORE_EXIT="$EXIT"
for pattern in "${FORBIDDEN_KT[@]}"; do
    matches=$(grep -rln --include="*.kt" -E "$pattern" "$ANDROID_ROOT" 2>/dev/null || true)
    if [ -n "$matches" ]; then
        while IFS= read -r f; do
            [ -z "$f" ] && continue
            if ! is_allowlisted_kt "$f"; then
                echo "  ⚠  $f contains banned import '$pattern'"
                EXIT=1
            fi
        done <<< "$matches"
    fi
done
[ "$EXIT" -eq "$KT_BEFORE_EXIT" ] && echo "  ✓ clean (allowlist respected)"

echo ""
if [ "$EXIT" -eq 0 ]; then
    echo "✅ Kernel hygiene OK — no unauthorized tool references in kernel code."
else
    echo "❌ Kernel hygiene violations found. Fix the files above OR add them to the allowlist with a comment explaining the transitional exception."
fi
exit "$EXIT"
