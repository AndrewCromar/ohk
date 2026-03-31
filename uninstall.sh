#!/usr/bin/env bash
set -e

INSTALL_DIR="$HOME/.local/share/autoclicker"
ICON="$HOME/.local/share/icons/autoclicker.png"
DESKTOP="$HOME/.local/share/applications/autoclicker.desktop"
CONFIG_DIR="$HOME/.config/autoclicker"

echo "=== Autoclicker Uninstaller ==="
echo ""

rm -rf "$INSTALL_DIR" && echo "Removed $INSTALL_DIR"
rm -f "$ICON" && echo "Removed $ICON"
rm -f "$DESKTOP" && echo "Removed $DESKTOP"

read -rp "Remove config (keybinds) too? [y/N] " yn
case "$yn" in
    [Yy]*) rm -rf "$CONFIG_DIR" && echo "Removed $CONFIG_DIR" ;;
    *) echo "Kept $CONFIG_DIR" ;;
esac

update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo ""
echo "=== Uninstalled! ==="
