#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="$HOME/.local/share/ohk"
ICON_DIR="$HOME/.local/share/icons"
DESKTOP_DIR="$HOME/.local/share/applications"

echo "=== OHK (Onyx Hot Keys) Installer ==="
echo ""

# Check for python3 and tk
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is not installed."
    echo "Install it with your package manager (e.g. sudo pacman -S python)"
    exit 1
fi

python3 -c "import tkinter" 2>/dev/null || {
    echo "ERROR: tkinter is not available."
    echo "Install it with your package manager:"
    echo "  Arch:   sudo pacman -S tk"
    echo "  Debian: sudo apt install python3-tk"
    echo "  Fedora: sudo dnf install python3-tkinter"
    exit 1
}

# Check input group for global hotkeys
if ! groups | grep -qw input; then
    echo "WARNING: Your user is not in the 'input' group."
    echo "Global hotkeys won't work without it. Run:"
    echo "  sudo usermod -aG input \$USER"
    echo "Then log out and back in."
    echo ""
    read -rp "Continue anyway? [y/N] " yn
    case "$yn" in
        [Yy]*) ;;
        *) exit 1 ;;
    esac
fi

# Copy files to install dir
echo "Installing to $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
cp -r "$SCRIPT_DIR/ohk" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/"

# Create venv and install deps
echo "Setting up Python virtual environment ..."
python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# Generate icon
echo "Generating icon ..."
mkdir -p "$ICON_DIR"
"$INSTALL_DIR/.venv/bin/python" -c "
from PIL import Image, ImageDraw
img = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
s = 128 / 64.0
cursor = [
    (8*s, 4*s), (8*s, 52*s), (20*s, 40*s),
    (32*s, 56*s), (38*s, 52*s), (26*s, 36*s),
    (40*s, 34*s), (8*s, 4*s),
]
d.polygon(cursor, fill=(30, 30, 30, 255), outline=(255, 255, 255, 255), width=max(1, int(2*s)))
img.save('$ICON_DIR/ohk.png')
"

# Create .desktop entry
echo "Creating desktop entry ..."
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/ohk.desktop" <<EOF
[Desktop Entry]
Name=OHK
Comment=Onyx Hot Keys — Macro & Automation for Linux
Exec=$INSTALL_DIR/.venv/bin/python -m ohk
Icon=$ICON_DIR/ohk.png
Type=Application
Categories=Utility;
Terminal=false
StartupWMClass=ohk
EOF

# Update desktop database
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo ""
echo "=== Installed! ==="
echo "You can now search for 'OHK' in your app launcher."
echo "Or run directly: $INSTALL_DIR/.venv/bin/python -m ohk"
