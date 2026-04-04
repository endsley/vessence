#!/usr/bin/env bash
# install.sh — Vessence first-run installer
#
# Usage:  bash install.sh
#
# What it does:
#   1. Asks which AI brain to use (Gemini / Claude / OpenAI)
#   2. Writes JANE_BRAIN to .env
#   3. Starts chromadb + jane, streams install logs to terminal
#   4. Waits for Jane to be healthy (Node.js + CLI install can take ~3 min)
#   5. Starts the onboarding wizard and prints the URL

set -euo pipefail

COMPOSE="docker compose"
JANE_CONTAINER="vessence-jane"
JANE_HEALTH_URL="http://localhost:8081/health"
ONBOARDING_URL="http://localhost:3000"
MAX_WAIT=600   # 10 minutes max before giving up
ENV_DIR="${VESSENCE_DATA_HOME:-./runtime}"
ENV_FILE="$ENV_DIR/.env"

# ── Helpers ───────────────────────────────────────────────────────────────────

hr() { printf '%.0s─' {1..62}; echo; }

# ── Banner ────────────────────────────────────────────────────────────────────

echo ""
hr
echo "  Vessence Installer"
hr
echo ""

# ── Step 1: Choose brain ──────────────────────────────────────────────────────

echo "Which AI brain do you want Jane to use?"
echo ""
echo "  1) Gemini  — Google (free tier available, recommended for first run)"
echo "  2) Claude  — Anthropic (requires Claude subscription or API key)"
echo "  3) OpenAI  — OpenAI (requires API key)"
echo ""
read -rp "Enter 1, 2, or 3 [default: 1]: " BRAIN_CHOICE

case "${BRAIN_CHOICE:-1}" in
    1|gemini)  JANE_BRAIN="gemini"  ;;
    2|claude)  JANE_BRAIN="claude"  ;;
    3|openai)  JANE_BRAIN="openai"  ;;
    *)
        echo "Unrecognised choice — defaulting to gemini."
        JANE_BRAIN="gemini"
        ;;
esac

echo ""
echo "→ Brain selected: $JANE_BRAIN"
echo ""

# ── Step 2: Write JANE_BRAIN to .env ─────────────────────────────────────────

mkdir -p "$ENV_DIR"

if [ -f "$ENV_FILE" ]; then
    if grep -q "^JANE_BRAIN=" "$ENV_FILE"; then
        sed -i "s/^JANE_BRAIN=.*/JANE_BRAIN=$JANE_BRAIN/" "$ENV_FILE"
    else
        echo "JANE_BRAIN=$JANE_BRAIN" >> "$ENV_FILE"
    fi
else
    echo "JANE_BRAIN=$JANE_BRAIN" > "$ENV_FILE"
fi

echo "→ JANE_BRAIN=$JANE_BRAIN written to $ENV_FILE"
echo ""

# ── Step 3: Start chromadb + jane (not onboarding yet) ───────────────────────

echo "Starting ChromaDB and Jane..."
$COMPOSE up -d chromadb jane
echo ""

# ── Step 4: Stream Jane logs so the user sees install progress ───────────────

echo "Installing Node.js and the $JANE_BRAIN CLI inside the Jane container."
echo "This takes a few minutes on first run. Log output below:"
echo ""
hr

# Tail logs in background; we'll stop it once Jane is healthy
docker logs -f "$JANE_CONTAINER" 2>&1 &
LOGS_PID=$!

# ── Step 5: Poll Jane's /health until it passes (or timeout) ─────────────────

elapsed=0
while [ $elapsed -lt $MAX_WAIT ]; do
    if curl -sf "$JANE_HEALTH_URL" >/dev/null 2>&1; then
        break
    fi
    sleep 5
    elapsed=$((elapsed + 5))
done

# Stop log tail
kill $LOGS_PID 2>/dev/null || true
wait $LOGS_PID 2>/dev/null || true

hr
echo ""

if [ $elapsed -ge $MAX_WAIT ]; then
    echo "✗  Jane did not become healthy within ${MAX_WAIT}s."
    echo "   Check logs:  docker logs $JANE_CONTAINER"
    exit 1
fi

echo "✓  Jane is ready! (${elapsed}s)"
echo ""

# ── Step 6: Start onboarding ─────────────────────────────────────────────────

echo "Starting the onboarding wizard..."
$COMPOSE up -d onboarding
echo ""

# Brief wait for onboarding to bind its port
sleep 2

hr
echo ""
echo "  Setup complete — open your browser:"
echo ""
echo "    $ONBOARDING_URL"
echo ""
hr
echo ""
