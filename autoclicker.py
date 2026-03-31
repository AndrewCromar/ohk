#!/usr/bin/env python3
"""Autoclicker with rebindable hotkeys and a small tkinter GUI.

Uses evdev for global hotkey capture (works on Wayland).

Default hotkeys (global, work even when another window is focused):
    1 (hold) – spam left-click while held
    2 (hold) – spam right-click while held
    3        – toggle pause / resume
    4        – quit

Keybinds are saved to ~/.config/autoclicker/keybinds.json

Usage:
    .venv/bin/python autoclicker.py [--cps 20]
"""

import argparse
import json
import os
import selectors
import threading
import time
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

import evdev
from evdev import ecodes
from pynput.mouse import Button, Controller as MouseController

# ── Config ───────────────────────────────────────────────────────────────────

CONFIG_DIR = os.path.expanduser("~/.config/autoclicker")
CONFIG_FILE = os.path.join(CONFIG_DIR, "keybinds.json")

DEFAULT_KEYBINDS = {
    "left_click": ecodes.KEY_1,
    "right_click": ecodes.KEY_2,
    "pause": ecodes.KEY_3,
    "quit": ecodes.KEY_4,
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
        with open(CONFIG_FILE) as f:
            data = json.load(f)
        return {
            "left_click": data.get("left_click", DEFAULT_KEYBINDS["left_click"]),
            "right_click": data.get("right_click", DEFAULT_KEYBINDS["right_click"]),
            "pause": data.get("pause", DEFAULT_KEYBINDS["pause"]),
            "quit": data.get("quit", DEFAULT_KEYBINDS["quit"]),
        }
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return dict(DEFAULT_KEYBINDS)


def save_keybinds():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(keybinds, f)


# ── State ────────────────────────────────────────────────────────────────────

mouse = MouseController()

STATE_IDLE = "Idle"
STATE_LEFT = "Left Clicking"
STATE_RIGHT = "Right Clicking"
STATE_PAUSED = "Paused"

state = STATE_IDLE
state_lock = threading.Lock()
cps = 20
keybinds = load_keybinds()

# Rebinding state: which action is waiting for a keypress (None or action name)
rebinding = None
rebind_lock = threading.Lock()


# ── Keyboard discovery ──────────────────────────────────────────────────────

def find_keyboards():
    keyboards = []
    for path in evdev.list_devices():
        dev = evdev.InputDevice(path)
        caps = dev.capabilities().get(ecodes.EV_KEY, [])
        if ecodes.KEY_A in caps:
            keyboards.append(dev)
    return keyboards


# ── Evdev listener thread ───────────────────────────────────────────────────

def evdev_listener():
    global state, rebinding
    keyboards = find_keyboards()
    if not keyboards:
        print("WARNING: No keyboard devices found. Check /dev/input/ permissions.")
        print("Make sure your user is in the 'input' group: sudo usermod -aG input $USER")
        return

    print(f"Listening on: {', '.join(d.name for d in keyboards)}")

    sel = selectors.DefaultSelector()
    for dev in keyboards:
        sel.register(dev, selectors.EVENT_READ)

    while True:
        for key, _mask in sel.select():
            dev = key.fileobj
            for event in dev.read():
                if event.type != ecodes.EV_KEY:
                    continue
                if event.value != 1 and event.value != 0:
                    # Only care about press (1) and release (0), skip repeat (2)
                    # except for held click keys below
                    if event.value == 2:
                        # Treat repeat as held for click keys
                        with state_lock:
                            kb = keybinds
                        if event.code in (kb["left_click"], kb["right_click"]):
                            pass  # let it through as "pressed"
                        else:
                            continue

                code = event.code
                pressed = event.value in (1, 2)
                released = event.value == 0

                # Check if we're rebinding
                with rebind_lock:
                    if rebinding is not None and event.value == 1:
                        action = rebinding
                        rebinding = None
                        keybinds[action] = code
                        save_keybinds()
                        update_gui()
                        continue

                with state_lock:
                    kb = keybinds
                    if code == kb["quit"] and event.value == 1:
                        root.after(0, root.destroy)
                        return
                    elif code == kb["pause"] and event.value == 1:
                        state = STATE_IDLE if state == STATE_PAUSED else STATE_PAUSED
                    elif state == STATE_PAUSED:
                        continue
                    elif code == kb["left_click"]:
                        if pressed:
                            state = STATE_LEFT
                        elif released and state == STATE_LEFT:
                            state = STATE_IDLE
                    elif code == kb["right_click"]:
                        if pressed:
                            state = STATE_RIGHT
                        elif released and state == STATE_RIGHT:
                            state = STATE_IDLE
                    else:
                        continue

                update_gui()


# ── Clicker thread ──────────────────────────────────────────────────────────

def clicker_loop():
    while True:
        with state_lock:
            s = state
            c = cps
        if s == STATE_LEFT:
            mouse.click(Button.left)
        elif s == STATE_RIGHT:
            mouse.click(Button.right)
        time.sleep(1.0 / max(c, 1))


# ── GUI ─────────────────────────────────────────────────────────────────────

root = None
status_var = None
cps_var = None
status_label = None
legend_label = None
bind_buttons = {}

def make_icon(size=64):
    """Draw a crisp mouse cursor icon at the given size."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 64.0  # scale factor

    # Cursor arrow polygon (outline + fill)
    cursor = [
        (8*s, 4*s), (8*s, 52*s), (20*s, 40*s),
        (32*s, 56*s), (38*s, 52*s), (26*s, 36*s),
        (40*s, 34*s), (8*s, 4*s),
    ]
    d.polygon(cursor, fill=(30, 30, 30, 255), outline=(255, 255, 255, 255), width=max(1, int(2*s)))

    return img


def update_gui():
    if root is None:
        return
    try:
        root.after(0, _refresh)
    except Exception:
        pass


def _refresh():
    with state_lock:
        s = state
    status_var.set(s)
    colors = {
        STATE_IDLE: "#333333",
        STATE_LEFT: "#2e7d32",
        STATE_RIGHT: "#1565c0",
        STATE_PAUSED: "#bf360c",
    }
    status_label.config(fg=colors.get(s, "#333333"))

    # Update keybind buttons
    for action, btn in bind_buttons.items():
        with rebind_lock:
            if rebinding == action:
                btn.config(text="Press a key...", fg="#bf360c")
            else:
                btn.config(text=key_name(keybinds[action]), fg="#333333")

    # Update legend
    lc = key_name(keybinds["left_click"])
    rc = key_name(keybinds["right_click"])
    p = key_name(keybinds["pause"])
    q = key_name(keybinds["quit"])
    legend_label.config(text=f"{lc}=left | {rc}=right | {p}=pause | {q}=quit")


def on_cps_change(*_args):
    global cps
    try:
        v = int(cps_var.get())
        if v < 1:
            v = 1
        cps = v
    except ValueError:
        pass


def toggle_from_gui():
    global state
    with state_lock:
        if state == STATE_PAUSED:
            state = STATE_IDLE
        else:
            state = STATE_PAUSED
    update_gui()


def start_rebind(action):
    global rebinding
    with rebind_lock:
        rebinding = action
    update_gui()


def reset_keybinds():
    global rebinding
    with rebind_lock:
        rebinding = None
    keybinds.update(DEFAULT_KEYBINDS)
    save_keybinds()
    update_gui()


def build_gui():
    global root, status_var, cps_var, status_label, legend_label

    root = tk.Tk()
    root.title("Autoclicker")
    root.resizable(False, False)
    root.attributes("-topmost", False)

    try:
        icon_img = make_icon(64)
        icon_photo = ImageTk.PhotoImage(icon_img)
        root.iconphoto(True, icon_photo)
        root._icon_ref = icon_photo  # prevent garbage collection
    except Exception:
        pass

    frame = tk.Frame(root, padx=12, pady=12)
    frame.pack()

    row = 0

    # Status
    status_var = tk.StringVar(value=STATE_IDLE)
    tk.Label(frame, text="Status:", font=("monospace", 11)).grid(row=row, column=0, sticky="w")
    status_label = tk.Label(frame, textvariable=status_var, font=("monospace", 14, "bold"), fg="#333333")
    status_label.grid(row=row, column=1, columnspan=2, sticky="w", padx=(8, 0))
    row += 1

    # CPS
    tk.Label(frame, text="CPS:", font=("monospace", 11)).grid(row=row, column=0, sticky="w", pady=(8, 0))
    cps_var = tk.StringVar(value=str(cps))
    cps_var.trace_add("write", on_cps_change)
    spin = tk.Spinbox(frame, from_=1, to=200, textvariable=cps_var, width=6, font=("monospace", 11))
    spin.grid(row=row, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=(8, 0))
    spin.bind("<Return>", lambda e: root.focus_set())
    spin.bind("<Escape>", lambda e: root.focus_set())
    row += 1

    # Separator
    tk.Frame(frame, height=1, bg="#cccccc").grid(row=row, column=0, columnspan=3, sticky="we", pady=(10, 6))
    row += 1

    # Keybind section
    tk.Label(frame, text="Keybinds", font=("monospace", 11, "bold")).grid(row=row, column=0, columnspan=3, sticky="w")
    row += 1

    actions = [
        ("left_click", "Left Click:"),
        ("right_click", "Right Click:"),
        ("pause", "Pause:"),
        ("quit", "Quit:"),
    ]
    for action, label_text in actions:
        tk.Label(frame, text=label_text, font=("monospace", 10)).grid(row=row, column=0, sticky="w", pady=(4, 0))
        btn = tk.Button(
            frame,
            text=key_name(keybinds[action]),
            font=("monospace", 10),
            width=12,
            command=lambda a=action: start_rebind(a),
        )
        btn.grid(row=row, column=1, columnspan=2, sticky="w", padx=(8, 0), pady=(4, 0))
        bind_buttons[action] = btn
        row += 1

    # Reset defaults button
    tk.Button(frame, text="Reset Defaults", command=reset_keybinds, font=("monospace", 9)).grid(
        row=row, column=0, columnspan=3, pady=(6, 0), sticky="e"
    )
    row += 1

    # Separator
    tk.Frame(frame, height=1, bg="#cccccc").grid(row=row, column=0, columnspan=3, sticky="we", pady=(10, 6))
    row += 1

    # Pause / Resume button
    tk.Button(frame, text="Pause / Resume", command=toggle_from_gui, font=("monospace", 10)).grid(
        row=row, column=0, columnspan=3, pady=(0, 0), sticky="we"
    )
    row += 1

    # Legend
    lc = key_name(keybinds["left_click"])
    rc = key_name(keybinds["right_click"])
    p = key_name(keybinds["pause"])
    q = key_name(keybinds["quit"])
    legend_label = tk.Label(frame, text=f"{lc}=left | {rc}=right | {p}=pause | {q}=quit",
                            font=("monospace", 9), fg="#666666")
    legend_label.grid(row=row, column=0, columnspan=3, pady=(8, 0))

    # Click anywhere to unfocus spinbox
    root.bind("<Button-1>", lambda e: root.focus_set() if e.widget is not spin else None)

    return root


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    global cps
    parser = argparse.ArgumentParser(description="Autoclicker")
    parser.add_argument("--cps", type=int, default=20, help="Clicks per second (default: 20)")
    args = parser.parse_args()
    cps = max(1, args.cps)

    # Evdev keyboard listener (daemon)
    t_kb = threading.Thread(target=evdev_listener, daemon=True)
    t_kb.start()

    # Clicker thread (daemon)
    t_click = threading.Thread(target=clicker_loop, daemon=True)
    t_click.start()

    # GUI on main thread
    app = build_gui()
    app.mainloop()


if __name__ == "__main__":
    main()
