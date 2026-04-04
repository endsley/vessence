#!/bin/bash
# Vessence Uninstaller for macOS

echo ""
echo "  ===================================="
echo "    Vessence Uninstaller for macOS"
echo "  ===================================="
echo ""
echo "  This will:"
echo "    - Stop all Vessence containers"
echo "    - Remove Docker images and volumes"
echo "    - Delete the Vessence install folder"
echo ""

INSTALL_DIR="$HOME/vessence"

read -p "  Are you sure you want to uninstall Vessence? (y/N): " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "  Cancelled."
    exit 0
fi

echo ""

if [ -f "$INSTALL_DIR/docker-compose.yml" ]; then
    echo "  Stopping Vessence containers..."
    cd "$INSTALL_DIR"
    docker compose down --rmi all --volumes 2>/dev/null
    echo "  [OK] Containers stopped, images and volumes removed."
else
    echo "  No docker-compose.yml found. Skipping container cleanup."
fi

echo ""

if [ -d "$INSTALL_DIR" ]; then
    echo "  Removing $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
    echo "  [OK] Install directory removed."
else
    echo "  Install directory not found. Nothing to remove."
fi

echo ""
echo "  ===================================="
echo "    Vessence has been uninstalled."
echo "  ===================================="
echo ""
