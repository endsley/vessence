#!/bin/bash
# restore_agent.sh - Advanced System Provisioner for Chieh's AI Agent
# Run this after restoring from USB backup to fully rebuild the system.
set -e

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
DEPS=$(cat /home/chieh/vessence/configs/system_deps.txt)
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
if [ ! -d "/home/chieh/miniconda3" ]; then
    echo "Miniconda not found. Installing locally..."
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
    bash miniconda.sh -b -p /home/chieh/miniconda3
    rm miniconda.sh
fi

source /home/chieh/miniconda3/bin/activate
if ! conda info --envs | grep -q "kokoro"; then
    echo "Creating 'kokoro' environment from snapshot..."
    conda env create -f /home/chieh/vessence/configs/kokoro_env.yml
else
    echo "Kokoro environment is healthy."
fi
conda deactivate

# 3. Rebuild ADK Virtual Environment
echo "[3/7] Rebuilding ADK Python Environment..."
rm -rf /home/chieh/google-adk-env/adk-venv
python3 -m venv /home/chieh/google-adk-env/adk-venv
source /home/chieh/google-adk-env/adk-venv/bin/activate
pip install --upgrade pip
pip install -r /home/chieh/vessence/configs/requirements_adk.txt
deactivate

# 4. Rebuild OmniParser Virtual Environment
echo "[4/7] Rebuilding OmniParser Python Environment..."
rm -rf /home/chieh/vessence/omniparser_venv
python3 -m venv /home/chieh/vessence/omniparser_venv
source /home/chieh/vessence/omniparser_venv/bin/activate
pip install --upgrade pip
pip install -r /home/chieh/vessence/configs/requirements_omniparser.txt
deactivate

# 5. Model Weights Verification
echo "[5/7] Verifying Model Weights..."
OMNI_WEIGHTS="/home/chieh/vessence/omniparser/weights"
if [ -d "$OMNI_WEIGHTS" ]; then
    echo "OmniParser weights present."
else
    echo "WARNING: OmniParser weights not found at $OMNI_WEIGHTS"
    echo "  Download manually from HuggingFace: microsoft/OmniParser"
fi

KOKORO_WEIGHTS="$(find /home/chieh/miniconda3/envs/kokoro -name '*.pt' 2>/dev/null | head -1)"
if [ -n "$KOKORO_WEIGHTS" ]; then
    echo "Kokoro model weights present."
else
    echo "WARNING: Kokoro model weights not found — run generate_identity_essay.py after setup."
fi

# 6. Restore .env files from backup (secrets not auto-copied — requires manual step)
echo "[6/7] Environment secrets check..."
if [ ! -f "/home/chieh/vessence/.env" ]; then
    echo "WARNING: /home/chieh/vessence/.env is missing!"
    echo "  Copy from backup or create fresh from .env.example:"
    echo "  cp /home/chieh/vessence/.env.example /home/chieh/vessence/.env"
    echo "  Then fill in: GOOGLE_API_KEY, OPENAI_API_KEY, DISCORD_TOKEN, DISCORD_CHANNEL_ID"
fi
if [ ! -f "/home/chieh/gemini_cli_bridge/.env" ]; then
    echo "WARNING: /home/chieh/gemini_cli_bridge/.env is missing!"
    echo "  Fill in: DISCORD_TOKEN (Jane's bot token), DISCORD_CHANNEL_ID"
fi

# 7. Final Health Check
echo "[7/7] Running System Diagnostics..."
source /home/chieh/google-adk-env/adk-venv/bin/activate
cd /home/chieh/vessence
python3 -c "import google.adk; import discord; import chromadb; print('Core Libraries: OK')"
deactivate

echo "-------------------------------------------------------"
echo "PROVISIONING COMPLETE!"
echo ""
echo "Next steps:"
echo "  1. Fill in .env files with API keys (see step 6 warnings above)"
echo "  2. Run: bash /home/chieh/vessence/startup_code/start_all_bots.sh"
echo "  3. Tell Chieh: 'Restore complete. Ready to resume.'"
echo "-------------------------------------------------------"
