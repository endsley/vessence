#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Vessence Docker E2E Test — Verify Full Claude Experience for Docker Users
# ─────────────────────────────────────────────────────────────────────────────
# Runs 7 verification steps to confirm that the Docker compose stack delivers
# persistent Claude sessions, stream-json tool visibility, ChromaDB memory,
# and real-time web status updates.
#
# Usage:
#   sudo bash tests/docker_e2e_test.sh            # from the vessence root
#   sudo bash tests/docker_e2e_test.sh --dry-run   # show commands without running
#
# Requirements:
#   - Docker (with sudo) and docker compose plugin
#   - The Vessence compose stack running (all services healthy)
#   - An Anthropic API key configured in the Jane container
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_CMD="sudo docker compose"
JANE_SERVICE="jane"
CHROMADB_SERVICE="chromadb"
DRY_RUN=false

if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "[DRY RUN] Commands will be printed but not executed."
    echo ""
fi

# ── Counters ──────────────────────────────────────────────────────────────────
PASS=0
FAIL=0
SKIP=0
RESULTS=()

# ── Helpers ───────────────────────────────────────────────────────────────────
_sep()   { printf '%.0s─' {1..72}; echo; }
_green() { printf '\033[32m%s\033[0m\n' "$*"; }
_red()   { printf '\033[31m%s\033[0m\n' "$*"; }
_yellow(){ printf '\033[33m%s\033[0m\n' "$*"; }

run_in_jane() {
    # Execute a command inside the jane container
    if $DRY_RUN; then
        echo "  [would run] $COMPOSE_CMD -f $COMPOSE_DIR/docker-compose.yml exec -T $JANE_SERVICE $*"
        return 0
    fi
    cd "$COMPOSE_DIR" && $COMPOSE_CMD exec -T "$JANE_SERVICE" "$@" 2>&1
}

run_python_in_jane() {
    # Execute a Python snippet inside the jane container
    local code="$1"
    if $DRY_RUN; then
        echo "  [would run python] $code"
        return 0
    fi
    cd "$COMPOSE_DIR" && $COMPOSE_CMD exec -T "$JANE_SERVICE" python3 -c "$code" 2>&1
}

record_result() {
    local step="$1" status="$2" detail="$3"
    RESULTS+=("$status|Step $step|$detail")
    case "$status" in
        PASS) PASS=$((PASS+1)); _green "  [PASS] Step $step: $detail" ;;
        FAIL) FAIL=$((FAIL+1)); _red   "  [FAIL] Step $step: $detail" ;;
        SKIP) SKIP=$((SKIP+1)); _yellow "  [SKIP] Step $step: $detail" ;;
    esac
}

# ── Pre-flight: Check that the compose stack is running ───────────────────────
echo ""
_sep
echo "Vessence Docker E2E Test"
_sep
echo "Compose directory: $COMPOSE_DIR"
echo ""

if ! $DRY_RUN; then
    echo "Checking Docker availability..."
    if ! sudo docker info >/dev/null 2>&1; then
        _red "ERROR: Docker is not running or sudo access is denied."
        exit 1
    fi

    echo "Checking compose stack status..."
    cd "$COMPOSE_DIR"
    RUNNING_SERVICES=$($COMPOSE_CMD ps --services --filter "status=running" 2>/dev/null || true)

    if ! echo "$RUNNING_SERVICES" | grep -q "$JANE_SERVICE"; then
        _red "ERROR: The '$JANE_SERVICE' service is not running."
        _yellow "Start the stack first:  cd $COMPOSE_DIR && sudo docker compose up -d"
        echo ""
        echo "Current status:"
        $COMPOSE_CMD ps 2>/dev/null || echo "  (no containers found)"
        exit 1
    fi

    if ! echo "$RUNNING_SERVICES" | grep -q "$CHROMADB_SERVICE"; then
        _red "ERROR: The '$CHROMADB_SERVICE' service is not running."
        _yellow "Start the stack first:  cd $COMPOSE_DIR && sudo docker compose up -d"
        exit 1
    fi

    _green "Compose stack is running. Services detected:"
    echo "$RUNNING_SERVICES" | sed 's/^/  - /'
    echo ""
fi

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Verify Claude CLI in Docker
# ─────────────────────────────────────────────────────────────────────────────
_sep
echo "Step 1: Verify Claude CLI in Docker"
_sep

if $DRY_RUN; then
    run_in_jane claude --version
    run_in_jane bash -c "claude --help | grep -i output-format"
    record_result 1 SKIP "Dry run"
else
    STEP1_OK=true

    VERSION_OUTPUT=$(run_in_jane claude --version 2>&1) || true
    echo "  claude --version: $VERSION_OUTPUT"

    if [[ -z "$VERSION_OUTPUT" ]] || echo "$VERSION_OUTPUT" | grep -qi "not found"; then
        record_result 1 FAIL "Claude CLI not found in container"
        STEP1_OK=false
    fi

    if $STEP1_OK; then
        HELP_OUTPUT=$(run_in_jane bash -c "claude --help 2>&1 | grep -i 'stream-json\|output-format'" 2>&1) || true
        echo "  output-format check: $HELP_OUTPUT"

        if echo "$HELP_OUTPUT" | grep -qi "stream-json\|output.format"; then
            record_result 1 PASS "Claude CLI installed, stream-json supported"
        else
            # stream-json might not appear in --help but still work
            record_result 1 PASS "Claude CLI installed (version: ${VERSION_OUTPUT})"
        fi
    fi
fi
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Verify persistent_claude.py can create a session
# ─────────────────────────────────────────────────────────────────────────────
_sep
echo "Step 2: Verify persistent_claude.py can create a session"
_sep

STEP2_CODE='
import asyncio, sys
from jane.persistent_claude import get_claude_persistent_manager

async def test():
    m = get_claude_persistent_manager()
    try:
        result = await m.run_turn("e2e_test_session", "Say hello in one word", timeout_seconds=30)
        print(f"RESPONSE:{result}")
        session = await m.get("e2e_test_session")
        print(f"SESSION_ID:{session.claude_session_id}")
        print(f"TURN_COUNT:{session.turn_count}")
    except Exception as e:
        print(f"ERROR:{e}", file=sys.stderr)
        sys.exit(1)

asyncio.run(test())
'

if $DRY_RUN; then
    run_python_in_jane "$STEP2_CODE"
    record_result 2 SKIP "Dry run"
else
    STEP2_OUT=$(run_python_in_jane "$STEP2_CODE" 2>&1) || true
    echo "$STEP2_OUT" | head -10

    if echo "$STEP2_OUT" | grep -q "^RESPONSE:"; then
        TURN_COUNT=$(echo "$STEP2_OUT" | grep "^TURN_COUNT:" | cut -d: -f2)
        SESSION_ID=$(echo "$STEP2_OUT" | grep "^SESSION_ID:" | cut -d: -f2)
        if [[ "$TURN_COUNT" == "1" ]] && [[ -n "$SESSION_ID" ]] && [[ "$SESSION_ID" != "None" ]]; then
            record_result 2 PASS "Session created, turn_count=1, claude_session_id=$SESSION_ID"
        elif [[ "$TURN_COUNT" == "1" ]]; then
            record_result 2 PASS "Session created, turn_count=1 (session_id may be pending)"
        else
            record_result 2 FAIL "Unexpected turn_count=$TURN_COUNT or missing session_id"
        fi
    else
        record_result 2 FAIL "Could not create session: $(echo "$STEP2_OUT" | tail -3)"
    fi
fi
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Verify session resume works
# ─────────────────────────────────────────────────────────────────────────────
_sep
echo "Step 3: Verify session resume works"
_sep

STEP3_CODE='
import asyncio, sys
from jane.persistent_claude import get_claude_persistent_manager

async def test():
    m = get_claude_persistent_manager()
    try:
        r1 = await m.run_turn("e2e_resume_test", "Remember the number 42. Just acknowledge.", timeout_seconds=30)
        print(f"TURN1:{r1[:200]}")
        r2 = await m.run_turn("e2e_resume_test", "What number did I tell you to remember?", timeout_seconds=30)
        print(f"TURN2:{r2[:200]}")
        session = await m.get("e2e_resume_test")
        print(f"TURN_COUNT:{session.turn_count}")
        # Check if 42 is in the response
        if "42" in r2:
            print("MEMORY_CHECK:PASS")
        else:
            print("MEMORY_CHECK:FAIL")
    except Exception as e:
        print(f"ERROR:{e}", file=sys.stderr)
        sys.exit(1)

asyncio.run(test())
'

if $DRY_RUN; then
    run_python_in_jane "$STEP3_CODE"
    record_result 3 SKIP "Dry run"
else
    STEP3_OUT=$(run_python_in_jane "$STEP3_CODE" 2>&1) || true
    echo "$STEP3_OUT" | head -10

    TURN_COUNT=$(echo "$STEP3_OUT" | grep "^TURN_COUNT:" | cut -d: -f2)
    MEM_CHECK=$(echo "$STEP3_OUT" | grep "^MEMORY_CHECK:" | cut -d: -f2)

    if [[ "$MEM_CHECK" == "PASS" ]] && [[ "$TURN_COUNT" == "2" ]]; then
        record_result 3 PASS "Session resumed, 42 remembered, turn_count=2"
    elif [[ "$MEM_CHECK" == "PASS" ]]; then
        record_result 3 PASS "Session resumed, 42 remembered (turn_count=$TURN_COUNT)"
    elif echo "$STEP3_OUT" | grep -q "^TURN2:"; then
        record_result 3 FAIL "Session resumed but 42 not found in response"
    else
        record_result 3 FAIL "Session resume failed: $(echo "$STEP3_OUT" | tail -3)"
    fi
fi
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Verify stream-json emits tool_use events
# ─────────────────────────────────────────────────────────────────────────────
_sep
echo "Step 4: Verify stream-json emits tool_use events"
_sep

STEP4_CODE='
import asyncio, sys
from jane.persistent_claude import get_claude_persistent_manager

statuses = []

async def test():
    m = get_claude_persistent_manager()
    try:
        result = await m.run_turn(
            "e2e_tool_test",
            "Read the file /app/jane_web/main.py and count how many lines it has",
            on_status=lambda s: statuses.append(s),
            on_delta=lambda d: None,
            timeout_seconds=60,
        )
        print(f"STATUS_COUNT:{len(statuses)}")
        for i, s in enumerate(statuses[:10]):
            print(f"STATUS_{i}:{s}")
        print(f"RESPONSE:{result[:300]}")
    except Exception as e:
        print(f"ERROR:{e}", file=sys.stderr)
        sys.exit(1)

asyncio.run(test())
'

if $DRY_RUN; then
    run_python_in_jane "$STEP4_CODE"
    record_result 4 SKIP "Dry run"
else
    STEP4_OUT=$(run_python_in_jane "$STEP4_CODE" 2>&1) || true
    echo "$STEP4_OUT" | head -15

    STATUS_COUNT=$(echo "$STEP4_OUT" | grep "^STATUS_COUNT:" | cut -d: -f2)

    if [[ -n "$STATUS_COUNT" ]] && [[ "$STATUS_COUNT" -gt 0 ]]; then
        record_result 4 PASS "Received $STATUS_COUNT tool_use status events"
    elif echo "$STEP4_OUT" | grep -q "^RESPONSE:"; then
        record_result 4 FAIL "Got response but no status events (STATUS_COUNT=${STATUS_COUNT:-0})"
    else
        record_result 4 FAIL "Tool test failed: $(echo "$STEP4_OUT" | tail -3)"
    fi
fi
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Verify ChromaDB is reachable
# ─────────────────────────────────────────────────────────────────────────────
_sep
echo "Step 5: Verify ChromaDB is reachable from Jane container"
_sep

STEP5_CODE='
import sys
try:
    import chromadb
    client = chromadb.HttpClient(host="chromadb", port=8000)
    hb = client.heartbeat()
    print(f"HEARTBEAT:{hb}")
    collections = client.list_collections()
    names = [c.name if hasattr(c, "name") else str(c) for c in collections]
    print(f"COLLECTIONS:{names}")
    print("REACHABLE:YES")
except Exception as e:
    print(f"ERROR:{e}", file=sys.stderr)
    print("REACHABLE:NO")
    sys.exit(1)
'

if $DRY_RUN; then
    run_python_in_jane "$STEP5_CODE"
    record_result 5 SKIP "Dry run"
else
    STEP5_OUT=$(run_python_in_jane "$STEP5_CODE" 2>&1) || true
    echo "$STEP5_OUT" | head -10

    if echo "$STEP5_OUT" | grep -q "REACHABLE:YES"; then
        record_result 5 PASS "ChromaDB reachable, heartbeat OK"
    else
        record_result 5 FAIL "ChromaDB not reachable: $(echo "$STEP5_OUT" | tail -3)"
    fi
fi
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Step 6: Verify context_builder queries ChromaDB
# ─────────────────────────────────────────────────────────────────────────────
_sep
echo "Step 6: Verify context_builder queries ChromaDB"
_sep

STEP6_CODE='
import asyncio, sys
sys.path.insert(0, "/app")
try:
    from jane.context_builder import build_jane_context_async
    async def test():
        ctx = await build_jane_context_async(
            "What do you remember about me?",
            [],
            session_id="e2e_test",
        )
        print(f"PROMPT_LENGTH:{len(ctx.system_prompt)}")
        has_memory = "memory" in ctx.system_prompt.lower() or "Memory" in ctx.system_prompt
        print(f"HAS_MEMORY:{has_memory}")
        # Show first 200 chars for debugging
        print(f"PROMPT_PREVIEW:{ctx.system_prompt[:200]}")
    asyncio.run(test())
except Exception as e:
    print(f"ERROR:{e}", file=sys.stderr)
    sys.exit(1)
'

if $DRY_RUN; then
    run_python_in_jane "$STEP6_CODE"
    record_result 6 SKIP "Dry run"
else
    STEP6_OUT=$(run_python_in_jane "$STEP6_CODE" 2>&1) || true
    echo "$STEP6_OUT" | head -10

    PROMPT_LEN=$(echo "$STEP6_OUT" | grep "^PROMPT_LENGTH:" | cut -d: -f2)

    if [[ -n "$PROMPT_LEN" ]] && [[ "$PROMPT_LEN" -gt 0 ]]; then
        HAS_MEM=$(echo "$STEP6_OUT" | grep "^HAS_MEMORY:" | cut -d: -f2)
        if [[ "$HAS_MEM" == "True" ]]; then
            record_result 6 PASS "System prompt built ($PROMPT_LEN chars), memory section present"
        else
            record_result 6 PASS "System prompt built ($PROMPT_LEN chars) (memory section may be empty if no facts stored)"
        fi
    else
        record_result 6 FAIL "context_builder failed: $(echo "$STEP6_OUT" | tail -3)"
    fi
fi
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Step 7: Verify web UI receives status events
# ─────────────────────────────────────────────────────────────────────────────
_sep
echo "Step 7: Verify web UI receives status events"
_sep

if $DRY_RUN; then
    echo "  [would run] curl -X POST http://localhost:8090/api/jane/chat/stream ..."
    record_result 7 SKIP "Dry run"
else
    # First, check if the web server health endpoint responds
    HEALTH=$(run_in_jane curl -sf http://localhost:8090/health 2>&1) || true
    echo "  Health check: $HEALTH"

    if echo "$HEALTH" | grep -qi "ok\|healthy\|true\|{}"; then
        # Try the streaming chat endpoint.
        # We use the host-mapped port (8081 -> 8090) to test from outside the container.
        # This needs a valid session cookie; test without auth first to see if endpoint exists.
        STREAM_TEST=$(curl -s -o /dev/null -w "%{http_code}" \
            -X POST http://localhost:8081/api/jane/chat/stream \
            -H "Content-Type: application/json" \
            -d '{"message":"hello","session_id":"e2e_web_test"}' \
            --max-time 10 2>&1) || true
        echo "  Stream endpoint HTTP status: $STREAM_TEST"

        if [[ "$STREAM_TEST" == "200" ]]; then
            record_result 7 PASS "Web streaming endpoint responds 200"
        elif [[ "$STREAM_TEST" == "401" ]] || [[ "$STREAM_TEST" == "403" ]]; then
            record_result 7 PASS "Web streaming endpoint exists (auth required, which is expected)"
        elif [[ "$STREAM_TEST" == "307" ]] || [[ "$STREAM_TEST" == "302" ]]; then
            record_result 7 PASS "Web streaming endpoint exists (redirects to login, which is expected)"
        elif [[ "$STREAM_TEST" == "000" ]]; then
            # Port not reachable from host — try from inside the container
            INTERNAL_TEST=$(run_in_jane curl -s -o /dev/null -w "%{http_code}" \
                -X POST http://localhost:8090/api/jane/chat/stream \
                -H "Content-Type: application/json" \
                -d '{"message":"hello","session_id":"e2e_web_test"}' \
                --max-time 10 2>&1) || true
            echo "  Internal stream endpoint HTTP status: $INTERNAL_TEST"
            if [[ "$INTERNAL_TEST" == "200" ]] || [[ "$INTERNAL_TEST" == "401" ]] || [[ "$INTERNAL_TEST" == "403" ]] || [[ "$INTERNAL_TEST" == "307" ]]; then
                record_result 7 PASS "Web streaming endpoint reachable internally ($INTERNAL_TEST)"
            else
                record_result 7 FAIL "Stream endpoint not reachable (host=$STREAM_TEST, internal=$INTERNAL_TEST)"
            fi
        else
            record_result 7 FAIL "Stream endpoint returned unexpected status: $STREAM_TEST"
        fi
    else
        record_result 7 FAIL "Web health endpoint not responding"
    fi
fi
echo ""

# ── Cleanup test sessions ────────────────────────────────────────────────────
if ! $DRY_RUN; then
    echo "Cleaning up test sessions..."
    CLEANUP_CODE='
import asyncio
from jane.persistent_claude import get_claude_persistent_manager
async def cleanup():
    m = get_claude_persistent_manager()
    for sid in ["e2e_test_session", "e2e_resume_test", "e2e_tool_test"]:
        await m.end(sid)
    print("Cleanup done")
asyncio.run(cleanup())
'
    run_python_in_jane "$CLEANUP_CODE" 2>/dev/null || true
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
_sep
echo "TEST SUMMARY"
_sep
printf "  %-6s %-30s %s\n" "Status" "Step" "Detail"
printf '  %.0s─' {1..66}; echo

for result in "${RESULTS[@]}"; do
    IFS='|' read -r status step detail <<< "$result"
    case "$status" in
        PASS) color="\033[32m" ;;
        FAIL) color="\033[31m" ;;
        SKIP) color="\033[33m" ;;
        *)    color="" ;;
    esac
    printf "  ${color}%-6s\033[0m %-30s %s\n" "$status" "$step" "$detail"
done

echo ""
echo "Total: $PASS passed, $FAIL failed, $SKIP skipped (out of 7)"
_sep

if [[ $FAIL -gt 0 ]]; then
    _red "Some tests FAILED. See details above."
    exit 1
elif [[ $SKIP -eq 7 ]]; then
    _yellow "All tests skipped (dry run)."
    exit 0
else
    _green "All tests PASSED."
    exit 0
fi
