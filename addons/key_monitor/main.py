"""Key Monitor — example OHK addon that logs key events."""

import time
import tkinter as tk

from evdev import ecodes
from ohk.addon import OHKAddon


class KeyMonitor(OHKAddon):
    name = "Key Monitor"
    description = "Displays a live log of all key events (press/release)"
    version = "1.0"

    def __init__(self, app):
        super().__init__(app)
        self.max_lines = 100
        self._text = None

    def build_tab(self, parent):
        frame = tk.Frame(parent, padx=12, pady=12)

        # Header
        tk.Label(frame, text="Key Monitor", font=("monospace", 11, "bold")).pack(anchor="w")
        tk.Label(frame, text="Live log of global key events",
                 font=("monospace", 9), fg="#666666").pack(anchor="w")

        # Text area with scrollbar
        text_frame = tk.Frame(frame)
        text_frame.pack(fill="both", expand=True, pady=(8, 0))

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")

        self._text = tk.Text(text_frame, font=("monospace", 10), height=12, width=40,
                             state="disabled", yscrollcommand=scrollbar.set,
                             bg="#1e1e1e", fg="#d4d4d4", insertbackground="#d4d4d4")
        self._text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._text.yview)

        # Buttons
        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill="x", pady=(8, 0))

        tk.Button(btn_frame, text="Clear", font=("monospace", 9),
                  command=self._clear).pack(side="left")

        # Max lines setting
        tk.Label(btn_frame, text="  Max lines:", font=("monospace", 9)).pack(side="left")
        self._max_var = tk.StringVar(value=str(self.max_lines))
        self._max_var.trace_add("write", self._on_max_change)
        spin = tk.Spinbox(btn_frame, from_=10, to=1000, textvariable=self._max_var,
                          width=5, font=("monospace", 9))
        spin.pack(side="left", padx=(4, 0))

        return frame

    def on_key_event(self, code, value):
        if self._text is None:
            return
        if value not in (0, 1):  # skip repeats
            return

        name = ecodes.KEY.get(code, code)
        if isinstance(name, list):
            name = name[0]
        if isinstance(name, str) and name.startswith("KEY_"):
            name = name[4:]

        action = "PRESS  " if value == 1 else "RELEASE"
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] {action} {name}\n"

        try:
            self._text.after(0, lambda l=line: self._append(l))
        except Exception:
            pass

    def _append(self, line):
        self._text.config(state="normal")
        self._text.insert("end", line)
        # Trim if over max lines
        line_count = int(self._text.index("end-1c").split(".")[0])
        if line_count > self.max_lines:
            self._text.delete("1.0", f"{line_count - self.max_lines}.0")
        self._text.see("end")
        self._text.config(state="disabled")

    def _clear(self):
        self._text.config(state="normal")
        self._text.delete("1.0", "end")
        self._text.config(state="disabled")

    def _on_max_change(self, *_args):
        try:
            self.max_lines = max(10, int(self._max_var.get()))
        except ValueError:
            pass

    def get_settings(self):
        return {"max_lines": self.max_lines}

    def load_settings(self, data):
        self.max_lines = data.get("max_lines", 100)
