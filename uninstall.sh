#!/usr/bin/env bash
set -e

INSTALL_DIR="$HOME/.local/share/ohk"
ICON="$HOME/.local/share/icons/ohk.png"
DESKTOP="$HOME/.local/share/applications/ohk.desktop"
CONFIG_DIR="$HOME/.config/ohk"

echo "=== OHK (Onyx Hot Keys) Uninstaller ==="
echo ""

rm -rf "$INSTALL_DIR" && echo "Removed $INSTALL_DIR"
rm -f "$ICON" && echo "Removed $ICON"
rm -f "$DESKTOP" && echo "Removed $DESKTOP"

read -rp "Remove config (keybinds, macros) too? [y/N] " yn
case "$yn" in
    [Yy]*) rm -rf "$CONFIG_DIR" && echo "Removed $CONFIG_DIR" ;;
    *) echo "Kept $CONFIG_DIR" ;;
esac

update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo ""
echo "=== Uninstalled! ==="
