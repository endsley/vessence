#!/bin/bash

# --- 1. System Updates & Dependencies ---
echo "Updating system and installing base dependencies..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS - assumes Homebrew is installed
    brew update
    brew install node python@3.10
else
    # Linux (Debian/Ubuntu)
    sudo apt-get update
    sudo apt-get install -y nodejs npm python3-pip python3-venv
fi

# --- 2. Install Gemini CLI ---
# Official tool: @google/gemini-cli
echo "Installing Gemini CLI globally via npm..."
sudo npm install -g @google/gemini-cli

# --- 3. Install Google ADK ---
# The ADK (Agent Development Kit) is a Python-based framework.
echo "Setting up Google ADK in a virtual environment..."
mkdir -p ~/google-adk-env
python3 -m venv ~/google-adk-env/adk-venv
source ~/google-adk-env/adk-venv/bin/activate

# Install the core ADK package
pip install --upgrade pip
pip install google-adk

# --- 4. Configure Paths ---
# We need to make sure 'gemini' and 'adk' are accessible from any terminal.
echo "Configuring shell paths..."

SHELL_PROFILE="$HOME/.bashrc"
[[ "$SHELL" == *"zsh"* ]] && SHELL_PROFILE="$HOME/.zshrc"

# Ensure npm global bin is in PATH (usually /usr/local/bin, but just in case)
NPM_BIN=$(npm config get prefix)/bin
if [[ ":$PATH:" != *":$NPM_BIN:"* ]]; then
    echo "export PATH=\"\$PATH:$NPM_BIN\"" >> "$SHELL_PROFILE"
fi

# Add the ADK virtual env bin to PATH so you can call 'adk' directly
ADK_BIN="$HOME/google-adk-env/adk-venv/bin"
if [[ ":$PATH:" != *":$ADK_BIN:"* ]]; then
    echo "export PATH=\"\$PATH:$ADK_BIN\"" >> "$SHELL_PROFILE"
fi

echo "------------------------------------------------"
echo "✅ Installation Complete!"
echo "1. Run 'source $SHELL_PROFILE' to update your current session."
echo "2. Type 'gemini login' to authenticate the CLI."
echo "3. Type 'adk --help' to verify the Agent Development Kit."
echo "------------------------------------------------"
