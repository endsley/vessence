#!/bin/bash
# Vessence Installer for macOS
# Double-click this file or run: bash install-mac.command

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="${VESSENCE_INSTALL_DIR:-$HOME/vessence}"
NONINTERACTIVE="${VESSENCE_NONINTERACTIVE:-0}"
SKIP_BROWSER="${VESSENCE_SKIP_BROWSER:-0}"
SKIP_COPY="${VESSENCE_SKIP_COPY:-0}"
PROVIDER_CHOICE="${VESSENCE_PROVIDER_CHOICE:-}"

pause_if_needed() {
    if [ "$NONINTERACTIVE" != "1" ]; then
        read -r -p "  Press Enter to exit..." _
    fi
}

fail() {
    echo "  [!] $1"
    echo ""
    pause_if_needed
    exit 1
}

copy_package_contents() {
    if [ "$SKIP_COPY" = "1" ]; then
        echo "  [OK] Copy step skipped by VESSENCE_SKIP_COPY=1."
        return
    fi

    if [ "$SCRIPT_DIR" = "$INSTALL_DIR" ]; then
        echo "  [OK] Installer is already running from $INSTALL_DIR, skipping file copy."
        return
    fi

    echo "  Copying files..."
    mkdir -p "$INSTALL_DIR"
    if ! (cd "$SCRIPT_DIR" && tar -cf - .) | (cd "$INSTALL_DIR" && tar -xf -); then
        fail "Failed to copy installer files into $INSTALL_DIR."
    fi

    for required_path in docker-compose.yml .env.example; do
        if [ ! -e "$INSTALL_DIR/$required_path" ]; then
            fail "Installer copy completed but $required_path is missing in $INSTALL_DIR."
        fi
    done
    echo "  [OK] Files copied to $INSTALL_DIR"
}

run_compose() {
    if ! docker compose "$@"; then
        fail "docker compose $* failed. Check the error output above."
    fi
}

wait_for_onboarding() {
    echo "  Waiting for onboarding to become ready at http://localhost:3000 ..."
    for _ in $(seq 1 120); do
        if curl -fsS http://localhost:3000/health >/dev/null 2>&1; then
            echo "  [OK] Onboarding is ready."
            return 0
        fi
        sleep 1
    done

    echo "  [!] Onboarding did not become ready within 120 seconds."
    echo "      Recent onboarding/jane logs:"
    docker compose ps onboarding jane || true
    docker compose logs --tail 60 onboarding jane || true
    fail "Onboarding never came up on http://localhost:3000."
}

echo ""
echo "  ===================================="
echo "    Vessence Installer for macOS"
echo "  ===================================="
echo ""

# ── Check for Docker Desktop ──────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "  [!] Docker is not installed."
    echo ""
    echo "      Vessence requires Docker Desktop to run."
    echo "      Download it from: https://www.docker.com/products/docker-desktop/"
    echo ""
    echo "      After installing Docker Desktop:"
    echo "        1. Launch Docker Desktop and wait for it to start"
    echo "        2. Run this installer again"
    echo ""
    pause_if_needed
    exit 1
fi

# ── Check Docker is running ───────────────────────────────────────────
if ! docker info &>/dev/null; then
    echo "  [!] Docker is installed but not running."
    echo ""
    echo "      Please start Docker Desktop and wait until it says"
    echo "      \"Docker Desktop is running\", then run this installer again."
    echo ""
    pause_if_needed
    exit 1
fi

# ── Check docker compose ──────────────────────────────────────────────
if ! docker compose version &>/dev/null; then
    echo "  [!] Docker Compose plugin not found."
    echo ""
    echo "      Update Docker Desktop to a recent version and make sure"
    echo "      the Compose plugin is enabled, then run this installer again."
    echo ""
    pause_if_needed
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

if [ -z "$PROVIDER_CHOICE" ] && [ "$NONINTERACTIVE" != "1" ]; then
    read -r -p "  Enter 1, 2, or 3 [default: 1]: " PROVIDER_CHOICE
fi

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

echo "  Install directory: $INSTALL_DIR"
echo ""

# ── Copy all files (source, Dockerfiles, configs) ───────────────────
copy_package_contents
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
run_compose build --no-cache
run_compose up -d

echo ""
echo "  ===================================="
echo "    Vessence is running!"
echo "  ===================================="
echo ""
echo "    Jane's brain: $JANE_BRAIN"
echo ""
echo "    Onboarding:  http://localhost:3000"
echo "    Jane:        http://localhost:8081"
echo "    Vault:       http://localhost:8081/vault"
echo "    (Vault is accessible through Jane's interface)"
echo ""
echo "    To stop:   docker compose down"
echo "    To start:  docker compose up -d"
echo ""

wait_for_onboarding

# ── Open browser ──────────────────────────────────────────────────────
if [ "$SKIP_BROWSER" != "1" ]; then
    open "http://localhost:3000" 2>/dev/null || true
fi

pause_if_needed
