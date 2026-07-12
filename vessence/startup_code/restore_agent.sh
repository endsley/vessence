#!/bin/bash
# restore_agent.sh - Advanced System Provisioner for the AI Agent
# Run this after restoring from USB backup to fully rebuild the system.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/startup_env.sh"
startup_bootstrap_env

MINICONDA_HOME="${HOME_DIR}/miniconda3"
KOKORO_ENV_YML="$VESSENCE_HOME/configs/kokoro_env.yml"
SYSTEM_DEPS_FILE="$VESSENCE_HOME/configs/system_deps.txt"
ADK_HOME="${HOME_DIR}/google-adk-env/adk-venv"
OMNI_VENV="$VESSENCE_HOME/omniparser_venv"
REQ_ADK="$VESSENCE_HOME/configs/requirements_adk.txt"
REQ_OMNI="$VESSENCE_HOME/configs/requirements_omniparser.txt"
GEMINI_BRIDGE_HOME="${HOME_DIR}/gemini_cli_bridge"
GEMINI_BRIDGE_ENV="$GEMINI_BRIDGE_HOME/.env"

echo "-------------------------------------------------------"
echo "STARTING FULL AGENT PROVISIONING..."
echo "-------------------------------------------------------"

# 0. Claude Code CLI
echo "[0/7] Installing Claude Code CLI..."
if ! command -v claude &>/dev/null; then
    npm install -g @anthropic-ai/claude-code
    echo "Claude Code installed."
else
    echo "Claude Code already present: $(claude --version 2>/dev/null || echo 'version unknown')"
fi

# 0b. Ollama (local LLM runtime)
echo "[0b/7] Checking Ollama..."
if ! command -v ollama &>/dev/null; then
    echo "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
else
    echo "Ollama present: $(ollama --version 2>/dev/null || echo 'ok')"
fi

echo "Pulling required Ollama models (this may take a while)..."
ollama pull qwen2.5-coder:14b || echo "WARNING: qwen2.5-coder:14b pull failed — retry manually with: ollama pull qwen2.5-coder:14b"

# 1. System Dependency Check
echo "[1/7] Checking System dependencies..."
DEPS=$(cat "$SYSTEM_DEPS_FILE")
MISSING_DEPS=""

for dep in $DEPS; do
    if ! dpkg -s "$dep" >/dev/null 2>&1; then
        MISSING_DEPS="$MISSING_DEPS $dep"
    fi
done

if [ ! -z "$MISSING_DEPS" ]; then
    echo "Missing system tools: $MISSING_DEPS"
    echo "Attempting automated installation..."
    sudo apt-get update && sudo apt-get install -y $MISSING_DEPS
else
    echo "All system tools (ffmpeg, xdotool, etc.) are present."
fi

# 2. Miniconda and Kokoro Check
echo "[2/7] Verifying Miniconda and Kokoro Env..."
if [ ! -d "$MINICONDA_HOME" ]; then
    echo "Miniconda not found. Installing locally..."
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
    bash miniconda.sh -b -p "$MINICONDA_HOME"
    rm miniconda.sh
fi

source "$MINICONDA_HOME/bin/activate"
if ! conda info --envs | grep -q "kokoro"; then
    echo "Creating 'kokoro' environment from snapshot..."
    conda env create -f "$KOKORO_ENV_YML"
else
    echo "Kokoro environment is healthy."
fi
conda deactivate

# 3. Rebuild ADK Virtual Environment
echo "[3/7] Rebuilding ADK Python Environment..."
rm -rf "$HOME_DIR/google-adk-env/adk-venv"
mkdir -p "$HOME_DIR/google-adk-env"
python3 -m venv "$HOME_DIR/google-adk-env/adk-venv"
source "$ADK_HOME/bin/activate"
pip install --upgrade pip
pip install -r "$REQ_ADK"
deactivate

# 4. Rebuild OmniParser Virtual Environment
echo "[4/7] Rebuilding OmniParser Python Environment..."
rm -rf "$OMNI_VENV"
python3 -m venv "$OMNI_VENV"
source "$OMNI_VENV/bin/activate"
pip install --upgrade pip
pip install -r "$REQ_OMNI"
deactivate

# 5. Model Weights Verification
echo "[5/7] Verifying Model Weights..."
OMNI_WEIGHTS="$VESSENCE_HOME/omniparser/weights"
if [ -d "$OMNI_WEIGHTS" ]; then
    echo "OmniParser weights present."
else
    echo "WARNING: OmniParser weights not found at $OMNI_WEIGHTS"
    echo "  Download manually from HuggingFace: microsoft/OmniParser"
fi

KOKORO_WEIGHTS="$(find "$MINICONDA_HOME/envs/kokoro" -name '*.pt' 2>/dev/null | head -1)"
if [ -n "$KOKORO_WEIGHTS" ]; then
    echo "Kokoro model weights present."
else
    echo "WARNING: Kokoro model weights not found — run generate_identity_essay.py after setup."
fi

# 6. Restore .env files from backup (secrets not auto-copied — requires manual step)
echo "[6/7] Environment secrets check..."
if [ ! -f "$VESSENCE_HOME/.env" ]; then
    echo "WARNING: $VESSENCE_HOME/.env is missing!"
    echo "  Copy from backup or create fresh from .env.example:"
    echo "  cp $VESSENCE_HOME/.env.example $VESSENCE_HOME/.env"
    echo "  Then fill in: GOOGLE_API_KEY, OPENAI_API_KEY, DISCORD_TOKEN, DISCORD_CHANNEL_ID"
fi
if [ ! -f "$GEMINI_BRIDGE_ENV" ]; then
    echo "WARNING: $GEMINI_BRIDGE_ENV is missing!"
    echo "  Fill in: DISCORD_TOKEN (Jane's bot token), DISCORD_CHANNEL_ID"
fi

# 7. Final Health Check
echo "[7/7] Running System Diagnostics..."
source "$ADK_HOME/bin/activate"
cd "$VESSENCE_HOME"
python3 -c "import google.adk; import discord; import chromadb; print('Core Libraries: OK')"
deactivate

echo "-------------------------------------------------------"
echo "PROVISIONING COMPLETE!"
echo ""
echo "Next steps:"
echo "  1. Fill in .env files with API keys (see step 6 warnings above)"
echo "  2. Run: bash $VESSENCE_HOME/startup_code/start_all_bots.sh"
echo "  3. Restore complete. Ready to resume."
echo "-------------------------------------------------------"
