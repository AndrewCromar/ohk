"""Configuration management for OHK."""

import json
import os

from evdev import ecodes

CONFIG_DIR = os.path.expanduser("~/.config/ohk")
KEYBINDS_FILE = os.path.join(CONFIG_DIR, "keybinds.json")
MACROS_DIR = os.path.join(CONFIG_DIR, "macros")

DEFAULT_KEYBINDS = {
    "left_click": ecodes.KEY_1,
    "right_click": ecodes.KEY_2,
    "pause": ecodes.KEY_3,
    "quit": ecodes.KEY_4,
    "record": ecodes.KEY_F9,
}


def key_name(code):
    """Get a human-readable name for an evdev key code."""
    name = ecodes.KEY.get(code, code)
    if isinstance(name, list):
        name = name[0]
    if isinstance(name, str) and name.startswith("KEY_"):
        name = name[4:]
    return str(name)


def load_keybinds():
    try:
        with open(KEYBINDS_FILE) as f:
            data = json.load(f)
        return {k: data.get(k, v) for k, v in DEFAULT_KEYBINDS.items()}
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return dict(DEFAULT_KEYBINDS)


def save_keybinds(keybinds):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(KEYBINDS_FILE, "w") as f:
        json.dump(keybinds, f)


def load_macro(name):
    path = os.path.join(MACROS_DIR, f"{name}.json")
    with open(path) as f:
        return json.load(f)


def save_macro(name, data):
    os.makedirs(MACROS_DIR, exist_ok=True)
    path = os.path.join(MACROS_DIR, f"{name}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def delete_macro(name):
    path = os.path.join(MACROS_DIR, f"{name}.json")
    if os.path.exists(path):
        os.remove(path)


def list_macros():
    """Return list of saved macro names."""
    if not os.path.isdir(MACROS_DIR):
        return []
    return sorted(
        os.path.splitext(f)[0]
        for f in os.listdir(MACROS_DIR)
        if f.endswith(".json")
    )
