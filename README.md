# OHK — Onyx Hot Keys

A macro and automation tool for Linux by **ONYX Development**. Think AutoHotKey, but for Linux — works on both X11 and Wayland.

## Features

- **Autoclicker** — hold a key to spam left or right clicks, configurable CPS (1-200)
- **Macro Recording** — record keyboard and mouse sequences, replay them with a hotkey
- **Global Hotkeys** — works even when another window is focused (via evdev)
- **Rebindable Keys** — change any hotkey from the GUI, saved across sessions
- **Desktop Integration** — shows up in your app launcher after install

## Default Hotkeys

| Key | Action |
|-----|--------|
| 1 (hold) | Spam left-click |
| 2 (hold) | Spam right-click |
| 3 | Pause / Resume |
| 4 | Quit |
| F9 | Start / Stop recording |

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

### CLI options

```
python -m ohk [--cps N]    # set default clicks per second (default: 20)
```

## Macros

1. Press **F9** (or your record key) to start recording
2. Perform your actions (key presses, mouse clicks)
3. Press **F9** again to stop — you'll be prompted to name the macro
4. Assign a hotkey to the macro from the Macros tab
5. Press the hotkey anytime to replay the macro

Macros are saved to `~/.config/ohk/macros/`.

## Addons

OHK supports addons — self-contained Python scripts that add new tabs and features.

### Installing an addon

Drop an addon folder into `~/.config/ohk/addons/`:

```
~/.config/ohk/addons/
└── my_addon/
    └── main.py
```

Then enable it from the **Addons** tab in OHK and restart.

### Creating an addon

Create a `main.py` with a class that extends `OHKAddon`:

```python
import tkinter as tk
from ohk.addon import OHKAddon

class MyAddon(OHKAddon):
    name = "My Addon"
    description = "What it does"
    version = "1.0"

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

An example addon (`key_monitor`) is included with the install.

## Uninstall

```bash
chmod +x uninstall.sh
./uninstall.sh
```

## Config

All settings are stored in `~/.config/ohk/`:
- `keybinds.json` — hotkey assignments
- `macros/` — saved macro files
- `addons/` — installed addons
- `addon_settings.json` — addon enable/disable state and settings

---

Made by **ONYX Development**
