# OHK — Onyx Hot Keys

A modular automation tool for Linux by **ONYX Development**. Think AutoHotKey, but for Linux — works on both X11 and Wayland.

## Features

All features are **modules** that can be enabled/disabled from the GUI.

### Built-in Modules

- **Autoclicker** — hold a key to spam left or right clicks, configurable CPS (1-200)
- **Macros** — record and replay keyboard/mouse sequences with a hotkey, full macro editor
- **Center Window** — center any window on screen with a hotkey or click-to-select (KDE Wayland)
- **Key Monitor** — live log of all key events for debugging

### Core

- **Global Hotkeys** — works even when another window is focused (via evdev)
- **Rebindable Keys** — change any hotkey from the GUI, saved across sessions
- **Module System** — enable/disable modules, add your own, settings persist across restarts
- **Desktop Integration** — shows up in your app launcher after install

## Default Hotkeys

| Key | Action |
|-----|--------|
| 1 (hold) | Spam left-click |
| 2 (hold) | Spam right-click |
| F9 | Start / Stop macro recording |
| F10 | Center active window |

All hotkeys can be rebound from the GUI.

## Requirements

- Linux (X11 or Wayland)
- Python 3.8+
- `tk` system package (for the GUI)
- User must be in the `input` group (for global hotkeys)
- KDE Plasma (for Center Window module — uses KWin scripting)

## Install

```bash
# Install tk if you don't have it
# Arch: sudo pacman -S tk
# Debian/Ubuntu: sudo apt install python3-tk
# Fedora: sudo dnf install python3-tkinter

# Add yourself to the input group (one-time, then log out and back in)
sudo usermod -aG input $USER

# Clone and install
git clone https://github.com/AndrewCromar/ohk.git
cd ohk
chmod +x install.sh
./install.sh
```

After install, search for **"OHK"** in your app launcher (KRunner, Rofi, etc).

## Run without installing

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m ohk
```

## Modules

### Autoclicker

Hold a key to spam mouse clicks at a configurable rate.

1. Enable from the Modules tab
2. Set your CPS (clicks per second)
3. Hold **1** for left-click spam, **2** for right-click spam
4. Release to stop

### Macros

Record and replay keyboard/mouse sequences.

1. Press **F9** to start recording
2. Perform your actions
3. Press **F9** again to stop — name your macro
4. Assign a hotkey from the Macros tab
5. Press the hotkey to replay

The macro editor lets you view, add, remove, reorder events, and edit delays. Select multiple events with shift-click to bulk edit.

### Center Window

Center any window on your screen (KDE Wayland).

- **Hotkey (F10)**: Instantly centers the focused window
- **Button**: Click "Center a Window", then click on the window to center

## Creating Modules

Create a folder in `~/.config/ohk/addons/` with a `main.py`:

```python
import tkinter as tk
from ohk.addon import OHKAddon

class MyModule(OHKAddon):
    name = "My Module"
    description = "What it does"
    version = "1.0"
    help_text = "Instructions shown in the help dialog"

    def build_tab(self, parent):
        frame = tk.Frame(parent, padx=12, pady=12)
        tk.Label(frame, text="Hello!").pack()
        return frame

    def on_key_event(self, code, value):
        # React to global key events (value: 0=release, 1=press)
        pass

    def get_settings(self):
        return {"my_setting": "value"}  # persisted across restarts

    def load_settings(self, data):
        self.my_setting = data.get("my_setting", "default")
```

Enable it from the Modules tab — no restart needed.

## Uninstall

```bash
chmod +x uninstall.sh
./uninstall.sh
```

## Config

All settings are stored in `~/.config/ohk/`:
- `keybinds.json` — hotkey assignments
- `macros/` — saved macro files
- `addons/` — installed modules
- `addon_settings.json` — module enable/disable state and settings

---

Made by **ONYX Development**
