#!/bin/bash
# install_brain.sh — First-boot CLI brain installer for Jane.
# Installs Node.js + the chosen CLI brain based on JANE_BRAIN env var.
# Skips if already installed (flag file check).

FLAG_FILE="/app/data/.brain_installed"
BRAIN="${JANE_BRAIN:-gemini}"

# Skip if already installed
if [ -f "$FLAG_FILE" ] && grep -q "$BRAIN" "$FLAG_FILE" 2>/dev/null; then
    echo "[install_brain] Brain '$BRAIN' already installed. Skipping."
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
        npm install -g openai-cli && npm cache clean --force
        ;;
    *)
        echo "[install_brain] Unknown brain: $BRAIN. Defaulting to gemini."
        npm install -g @google/gemini-cli@0.33.1 && npm cache clean --force
        BRAIN="gemini"
        ;;
esac

# Mark as installed
mkdir -p "$(dirname "$FLAG_FILE")"
echo "$BRAIN" > "$FLAG_FILE"
echo "[install_brain] Brain '$BRAIN' installed successfully."
