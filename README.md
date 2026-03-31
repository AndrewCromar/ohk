# Autoclicker

A simple autoclicker for Linux with a GUI and rebindable global hotkeys. Works on both X11 and Wayland.

## Features

- **Hold-to-click** — hold a key to spam left or right clicks
- **Global hotkeys** — works even when another window is focused (via evdev)
- **Rebindable keys** — change hotkeys from the GUI, saved across sessions
- **Configurable CPS** — adjust clicks per second (1-200) from the GUI or CLI
- **Desktop integration** — shows up in your app launcher after install

## Default Hotkeys

| Key | Action |
|-----|--------|
| 1 (hold) | Spam left-click |
| 2 (hold) | Spam right-click |
| 3 | Pause / Resume |
| 4 | Quit |

All hotkeys can be rebound from the GUI.

## Requirements

- Linux (X11 or Wayland)
- Python 3.8+
- `tk` system package (for the GUI)
- User must be in the `input` group (for global hotkeys)

## Install

```bash
# Install tk if you don't have it
# Arch: sudo pacman -S tk
# Debian/Ubuntu: sudo apt install python3-tk
# Fedora: sudo dnf install python3-tkinter

# Add yourself to the input group (one-time, then log out and back in)
sudo usermod -aG input $USER

# Clone and install
git clone https://github.com/YOUR_USERNAME/autoclicker.git
cd autoclicker
chmod +x install.sh
./install.sh
```

After install, search for **"Autoclicker"** in your app launcher (KRunner, Rofi, etc).

## Run without installing

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python autoclicker.py
```

### CLI options

```
autoclicker.py [--cps N]    # set clicks per second (default: 20)
```

## Uninstall

```bash
chmod +x uninstall.sh
./uninstall.sh
```

## Config

Keybinds are saved to `~/.config/autoclicker/keybinds.json`.
