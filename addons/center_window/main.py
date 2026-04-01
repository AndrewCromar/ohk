"""Center Window module for OHK — centers a window on screen."""

import os
import subprocess
import tempfile
import threading
import time
import tkinter as tk

from evdev import ecodes
from ohk import config
from ohk.addon import OHKAddon
from ohk.combo import combo_active, combo_name


def _run_kwin_script(js_code):
    """Write JS to a temp file, load and run it via KWin scripting, then clean up."""
    tmp = tempfile.NamedTemporaryFile(suffix=".js", delete=False, mode="w")
    tmp.write(js_code)
    tmp.close()
    try:
        subprocess.run(
            ["qdbus6", "org.kde.KWin", "/Scripting", "loadScript", tmp.name],
            capture_output=True, timeout=2,
        )
        subprocess.run(
            ["qdbus6", "org.kde.KWin", "/Scripting", "start"],
            capture_output=True, timeout=2,
        )
        subprocess.run(
            ["qdbus6", "org.kde.KWin", "/Scripting", "unloadScript", tmp.name],
            capture_output=True, timeout=2,
        )
    except Exception:
        pass
    finally:
        os.unlink(tmp.name)


# KWin script: center the window under the mouse cursor
CENTER_UNDER_CURSOR_SCRIPT = """\
const pos = workspace.cursorPos;
const windows = workspace.windowList();
let target = null;
for (let i = 0; i < windows.length; i++) {
    const w = windows[i];
    if (w.minimized || !w.normalWindow) continue;
    const g = w.frameGeometry;
    if (pos.x >= g.x && pos.x < g.x + g.width &&
        pos.y >= g.y && pos.y < g.y + g.height) {
        // Pick the topmost window under cursor
        if (!target || w.stackingOrder > target.stackingOrder) {
            target = w;
        }
    }
}
if (target) {
    const screen = workspace.activeScreen.geometry;
    const x = screen.x + (screen.width - target.frameGeometry.width) / 2;
    const y = screen.y + (screen.height - target.frameGeometry.height) / 2;
    target.frameGeometry = {
        x: x, y: y,
        width: target.frameGeometry.width,
        height: target.frameGeometry.height
    };
}
"""

# KWin script: center the currently active/focused window
CENTER_ACTIVE_SCRIPT = """\
const win = workspace.activeWindow;
if (win && win.normalWindow) {
    const screen = workspace.activeScreen.geometry;
    const x = screen.x + (screen.width - win.frameGeometry.width) / 2;
    const y = screen.y + (screen.height - win.frameGeometry.height) / 2;
    win.frameGeometry = {
        x: x, y: y,
        width: win.frameGeometry.width,
        height: win.frameGeometry.height
    };
}
"""

DEFAULT_KEY = ecodes.KEY_F10


class CenterWindowAddon(OHKAddon):
    name = "Center Window"
    description = "Center a window on screen with a hotkey or click"
    version = "1.1"
    help_text = (
        "Center Window\n"
        "\n"
        "Two ways to center a window:\n"
        "\n"
        "  Hotkey (default: F10):\n"
        "    Press the hotkey while using any window\n"
        "    and it will be centered instantly.\n"
        "\n"
        "  Button:\n"
        "    Click 'Center a Window' in the tab,\n"
        "    then click on the window you want to\n"
        "    center. It will snap to the center.\n"
        "\n"
        "Works on KDE Wayland via KWin scripting.\n"
        "The hotkey is rebindable from the tab."
    )

    def __init__(self, app):
        super().__init__(app)
        self._status_var = None
        self._bind_btn = None
        self._keys = [DEFAULT_KEY]  # combo (list of keycodes)
        self._waiting_for_click = False
        self._rebinding = False
        self._rebind_keys = []
        self._rebind_timer = None

    def build_tab(self, parent):
        frame = tk.Frame(parent, padx=12, pady=12)

        tk.Label(frame, text="Center Window", font=("monospace", 11, "bold")).pack(anchor="w")
        tk.Label(frame, text="Center a window on your screen",
                 font=("monospace", 9), fg="#666666").pack(anchor="w", pady=(0, 8))

        # Center by click button
        self._center_btn = tk.Button(frame, text="Center a Window (click to select)",
                                      font=("monospace", 10), command=self._start_pick)
        self._center_btn.pack(fill="x", pady=(0, 8))

        # Keybind
        kb_frame = tk.Frame(frame)
        kb_frame.pack(fill="x", pady=(0, 8))

        tk.Label(kb_frame, text="Hotkey:", font=("monospace", 10)).pack(side="left")
        self._bind_btn = tk.Button(kb_frame, text=combo_name(self._keys),
                                    font=("monospace", 10), width=12,
                                    command=self._start_rebind)
        self._bind_btn.pack(side="left", padx=(8, 0))

        # Status
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(frame, textvariable=self._status_var, font=("monospace", 10),
                 fg="#666666").pack(anchor="w", pady=(8, 0))

        return frame

    def on_key_event(self, code, value, held_keys=frozenset()):
        # Rebinding mode — collect combo
        if self._rebinding and value == 1:
            from evdev import ecodes as ec
            if code == ec.KEY_ESC:
                self._rebinding = False
                self._rebind_keys = []
                if self._rebind_timer:
                    self._rebind_timer.cancel()
                try:
                    self.app.root.after(0, self._refresh_bind_btn)
                except Exception:
                    pass
                return

            if code not in self._rebind_keys:
                self._rebind_keys.append(code)
            try:
                display = combo_name(self._rebind_keys) + "..."
                self.app.root.after(0, lambda: self._bind_btn.config(text=display, fg="#bf360c"))
            except Exception:
                pass

            if self._rebind_timer:
                self._rebind_timer.cancel()
            self._rebind_timer = threading.Timer(0.4, self._finish_rebind)
            self._rebind_timer.daemon = True
            self._rebind_timer.start()
            return

        # Waiting for click to pick a window
        if self._waiting_for_click:
            if code == 272 and value == 1:
                self._waiting_for_click = False
                threading.Thread(target=self._center_under_cursor, daemon=True).start()
            return

        # Hotkey: center the focused window instantly
        if value == 1 and combo_active(held_keys, self._keys):
            threading.Thread(target=self._center_active, daemon=True).start()

    def _finish_rebind(self):
        self._keys = list(self._rebind_keys)
        self._rebind_keys = []
        self._rebinding = False
        self._rebind_timer = None
        try:
            self.app.root.after(0, self._refresh_bind_btn)
        except Exception:
            pass

    def _start_pick(self):
        """Enter pick mode — next click will center that window."""
        self._waiting_for_click = True
        if self._status_var:
            self._status_var.set("Click on a window to center it...")
        if self._center_btn:
            self._center_btn.config(text="Click on a window...")

    def _center_under_cursor(self):
        """Center the window under the mouse cursor."""
        _run_kwin_script(CENTER_UNDER_CURSOR_SCRIPT)
        self._update_status("Centered window under cursor")
        try:
            self.app.root.after(0, lambda: self._center_btn.config(
                text="Center a Window (click to select)"))
        except Exception:
            pass

    def _center_active(self):
        """Center the currently active/focused window."""
        _run_kwin_script(CENTER_ACTIVE_SCRIPT)
        self._update_status("Centered active window")

    def _update_status(self, msg):
        if self._status_var:
            try:
                self.app.root.after(0, lambda: self._status_var.set(msg))
            except Exception:
                pass

    def _start_rebind(self):
        self._rebinding = True
        if self._bind_btn:
            self._bind_btn.config(text="Press a key...", fg="#bf360c")

    def _refresh_bind_btn(self):
        if self._bind_btn:
            self._bind_btn.config(text=combo_name(self._keys), fg="#333333")

    def get_settings(self):
        return {"keys": self._keys}

    def load_settings(self, data):
        keys = data.get("keys", data.get("key", DEFAULT_KEY))
        if isinstance(keys, int):
            keys = [keys]
        self._keys = keys
