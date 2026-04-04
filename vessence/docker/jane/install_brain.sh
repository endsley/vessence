#!/bin/bash
# install_brain.sh — First-boot CLI brain installer for Jane.
# Installs Node.js + the chosen CLI brain based on JANE_BRAIN env var.
# Skips only when the expected CLI binary is actually present.

FLAG_FILE="/app/data/.brain_installed"
BRAIN="${JANE_BRAIN:-gemini}"

expected_cli_bin() {
    case "$1" in
        gemini) echo "gemini" ;;
        claude) echo "claude" ;;
        openai) echo "codex" ;;
        *) echo "gemini" ;;
    esac
}

is_brain_installed() {
    local brain="$1"
    local cli_bin
    cli_bin="$(expected_cli_bin "$brain")"
    command -v "$cli_bin" >/dev/null 2>&1
}

EXPECTED_BIN="$(expected_cli_bin "$BRAIN")"

# Skip if already installed
if [ -f "$FLAG_FILE" ] && grep -q "$BRAIN" "$FLAG_FILE" 2>/dev/null && is_brain_installed "$BRAIN"; then
    echo "[install_brain] Brain '$BRAIN' already installed and '$EXPECTED_BIN' is present. Skipping."
    exit 0
fi

echo "[install_brain] Installing brain: $BRAIN"

# Install Node.js if not present
if ! command -v node &>/dev/null; then
    echo "[install_brain] Installing Node.js 22..."
    apt-get update -qq && apt-get install -y -qq --no-install-recommends gnupg \
        && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
        && apt-get install -y -qq --no-install-recommends nodejs \
        && rm -rf /var/lib/apt/lists/*
fi

# Install the chosen CLI
case "$BRAIN" in
    gemini)
        echo "[install_brain] Installing Gemini CLI..."
        npm install -g @google/gemini-cli@0.33.1 && npm cache clean --force
        ;;
    claude)
        echo "[install_brain] Installing Claude Code CLI..."
        npm install -g @anthropic-ai/claude-code && npm cache clean --force
        ;;
    openai)
        echo "[install_brain] Installing OpenAI/Codex CLI..."
        npm install -g @openai/codex && npm cache clean --force
        ;;
    *)
        echo "[install_brain] Unknown brain: $BRAIN. Defaulting to gemini."
        npm install -g @google/gemini-cli@0.33.1 && npm cache clean --force
        BRAIN="gemini"
        EXPECTED_BIN="$(expected_cli_bin "$BRAIN")"
        ;;
esac

if ! is_brain_installed "$BRAIN"; then
    echo "[install_brain] ERROR: '$BRAIN' install finished but expected CLI '$EXPECTED_BIN' is not in PATH."
    exit 1
fi

# Post-install configuration
if [ "$BRAIN" = "gemini" ]; then
    # Gemini CLI requires settings.json for headless API-key auth
    # and trustedFolders.json to skip the interactive trust prompt.
    GEMINI_DIR="$HOME/.gemini"
    mkdir -p "$GEMINI_DIR"
    if [ ! -f "$GEMINI_DIR/settings.json" ]; then
        echo '{"security":{"auth":{"selectedType":"gemini-api-key"}}}' > "$GEMINI_DIR/settings.json"
        echo "[install_brain] Created Gemini settings.json with API key auth."
    fi
    if [ ! -f "$GEMINI_DIR/trustedFolders.json" ]; then
        echo '{"/tmp":"TRUST_FOLDER","/app":"TRUST_FOLDER","/":"TRUST_FOLDER"}' > "$GEMINI_DIR/trustedFolders.json"
        echo "[install_brain] Created Gemini trustedFolders.json."
    fi
fi

# Mark as installed
mkdir -p "$(dirname "$FLAG_FILE")"
echo "$BRAIN" > "$FLAG_FILE"
echo "[install_brain] Brain '$BRAIN' installed successfully with CLI '$EXPECTED_BIN'."
