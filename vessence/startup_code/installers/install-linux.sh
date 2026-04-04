#!/bin/bash
# Vessence Installer for Linux
# Run: bash install-linux.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "  ===================================="
echo "    Vessence Installer for Linux"
echo "  ===================================="
echo ""

# ── Check for Docker ──────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "  [!] Docker is not installed."
    echo ""
    echo "      Option 1 — Install Docker Engine (recommended for Linux):"
    echo "        curl -fsSL https://get.docker.com | sudo sh"
    echo "        sudo usermod -aG docker \$USER"
    echo "        newgrp docker"
    echo ""
    echo "      Option 2 — Install Docker Desktop:"
    echo "        https://www.docker.com/products/docker-desktop/"
    echo ""
    echo "      After installing, run this installer again."
    exit 1
fi

# ── Check Docker is running ───────────────────────────────────────────
if ! docker info &>/dev/null; then
    echo "  [!] Docker is installed but not running."
    echo ""
    echo "      Start Docker with:"
    echo "        sudo systemctl start docker"
    echo ""
    echo "      If you get a permission error, add yourself to the docker group:"
    echo "        sudo usermod -aG docker \$USER"
    echo "        newgrp docker"
    echo ""
    exit 1
fi

# ── Check docker compose ──────────────────────────────────────────────
if ! docker compose version &>/dev/null; then
    echo "  [!] Docker Compose plugin not found."
    echo ""
    echo "      Install it with:"
    echo "        sudo apt install docker-compose-plugin"
    echo "      or:"
    echo "        sudo dnf install docker-compose-plugin"
    echo ""
    exit 1
fi

echo "  [OK] Docker is installed and running."
echo ""

# ── Choose AI provider for Jane ──────────────────────────────────────
echo "  ------------------------------------"
echo "    Choose Jane's AI provider"
echo "  ------------------------------------"
echo ""
echo "    1. Gemini  (free — uses your Google API key)"
echo "    2. Claude  (best for coding — requires Anthropic API key)"
echo "    3. OpenAI  (GPT models — requires OpenAI API key)"
echo ""

JANE_BRAIN="gemini"
JANE_WEB_PERMISSIONS="0"

read -r -p "  Enter 1, 2, or 3 [default: 1]: " PROVIDER_CHOICE

case "$PROVIDER_CHOICE" in
    2)
        JANE_BRAIN="claude"
        JANE_WEB_PERMISSIONS="1"
        echo ""
        echo "  [OK] Jane will use Claude Code. Web permission gating enabled."
        ;;
    3)
        JANE_BRAIN="openai"
        echo ""
        echo "  [OK] Jane will use OpenAI."
        ;;
    *)
        echo ""
        echo "  [OK] Jane will use Gemini (default)."
        ;;
esac
echo ""

# ── Set up directory ──────────────────────────────────────────────────
INSTALL_DIR="$HOME/vessence"

echo "  Install directory: $INSTALL_DIR"
echo ""

mkdir -p "$INSTALL_DIR"

# ── Copy all files (source, Dockerfiles, configs) ───────────────────
echo "  Copying files..."
cp -rf "$SCRIPT_DIR"/* "$INSTALL_DIR/" 2>/dev/null
cp -rf "$SCRIPT_DIR"/.env.example "$INSTALL_DIR/" 2>/dev/null

echo "  [OK] Files copied to $INSTALL_DIR"
echo ""

# ── Create .env with provider selection ──────────────────────────────
mkdir -p "$INSTALL_DIR/runtime"
mkdir -p "$INSTALL_DIR/vault"
if [ ! -f "$INSTALL_DIR/runtime/.env" ]; then
    echo "  Creating .env with your provider selection..."
    cat > "$INSTALL_DIR/runtime/.env" <<ENVEOF
# Vessence runtime - created by installer
JANE_BRAIN=$JANE_BRAIN
JANE_WEB_PERMISSIONS=$JANE_WEB_PERMISSIONS
ENVEOF
    echo "  [OK] .env created with JANE_BRAIN=$JANE_BRAIN"
else
    echo "  [OK] Existing .env found, keeping it."
    echo "      Provider selection will be available in the onboarding wizard."
fi
echo ""

# ── Build and start ──────────────────────────────────────────────────
echo "  Building and starting Vessence (this may take a few minutes on first run)..."
echo ""
cd "$INSTALL_DIR"
docker compose build --no-cache
docker compose up -d

echo ""
echo "  ===================================="
echo "    Vessence is running!"
echo "  ===================================="
echo ""
echo "    Jane's brain: $JANE_BRAIN"
echo ""
echo "    Onboarding:  http://localhost:3000"
echo "    Jane:        http://jane.localhost"
echo "    (Vault is accessible through Jane's interface)"
echo ""
echo "    To stop:   docker compose down"
echo "    To start:  docker compose up -d"
echo ""

# ── Open browser ──────────────────────────────────────────────────────
if command -v xdg-open &>/dev/null; then
    xdg-open "http://localhost:3000" 2>/dev/null &
fi
