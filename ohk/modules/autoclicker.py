"""Autoclicker module for OHK."""

import tkinter as tk

from .. import config
from ..clicker import Autoclicker, STATE_IDLE, STATE_LEFT, STATE_RIGHT, STATE_PAUSED
from ..module import OHKModule


class AutoclickerModule(OHKModule):
    name = "Autoclicker"

    def __init__(self, app):
        super().__init__(app)
        self.clicker = Autoclicker()
        self.keybinds = app.keybinds
        self._bind_buttons = {}
        self._status_var = None
        self._status_label = None
        self._cps_var = None
        self._clicker_legend = None

    def start(self):
        self.clicker.start()

    def build_tab(self, parent):
        frame = tk.Frame(parent, padx=12, pady=12)

        # Status
        self._status_var = tk.StringVar(value=STATE_IDLE)
        tk.Label(frame, text="Status:", font=("monospace", 11)).grid(row=0, column=0, sticky="w")
        self._status_label = tk.Label(frame, textvariable=self._status_var,
                                       font=("monospace", 14, "bold"), fg="#333333")
        self._status_label.grid(row=0, column=1, sticky="w", padx=(8, 0))

        # CPS
        tk.Label(frame, text="CPS:", font=("monospace", 11)).grid(row=1, column=0, sticky="w", pady=(8, 0))
        self._cps_var = tk.StringVar(value=str(self.clicker.cps))
        self._cps_var.trace_add("write", self._on_cps_change)
        spin = tk.Spinbox(frame, from_=1, to=200, textvariable=self._cps_var,
                          width=6, font=("monospace", 11))
        spin.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        spin.bind("<Return>", lambda e: self.app.root.focus_set())
        spin.bind("<Escape>", lambda e: self.app.root.focus_set())

        # Keybinds
        tk.Frame(frame, height=1, bg="#cccccc").grid(row=2, column=0, columnspan=2,
                                                      sticky="we", pady=(10, 6))
        row = 3
        for action, label_text in [("left_click", "Left Click:"), ("right_click", "Right Click:")]:
            tk.Label(frame, text=label_text, font=("monospace", 10)).grid(row=row, column=0,
                                                                           sticky="w", pady=(4, 0))
            btn = tk.Button(frame, text=config.key_name(self.keybinds[action]),
                            font=("monospace", 10), width=12,
                            command=lambda a=action: self.app.start_rebind(a))
            btn.grid(row=row, column=1, sticky="w", padx=(8, 0), pady=(4, 0))
            self._bind_buttons[action] = btn
            self.app.bind_buttons[action] = btn
            row += 1

        # Legend
        tk.Frame(frame, height=1, bg="#cccccc").grid(row=row, column=0, columnspan=2,
                                                      sticky="we", pady=(10, 6))
        row += 1
        self._clicker_legend = tk.Label(frame, text="", font=("monospace", 9), fg="#666666")
        self._clicker_legend.grid(row=row, column=0, columnspan=2, pady=(4, 0))

        self._refresh()
        return frame

    def on_key_event(self, code, value):
        kb = self.keybinds
        state = self.clicker.get_state()

        pressed = value in (1, 2)
        released = value == 0

        changed = False
        if code == kb["left_click"]:
            if pressed:
                self.clicker.set_state(STATE_LEFT)
                changed = True
            elif released and state == STATE_LEFT:
                self.clicker.set_state(STATE_IDLE)
                changed = True
        elif code == kb["right_click"]:
            if pressed:
                self.clicker.set_state(STATE_RIGHT)
                changed = True
            elif released and state == STATE_RIGHT:
                self.clicker.set_state(STATE_IDLE)
                changed = True

        if changed:
            try:
                self.app.root.after(0, self._refresh)
            except Exception:
                pass

    def _refresh(self):
        if self._status_var is None:
            return
        s = self.clicker.get_state()
        self._status_var.set(s)
        colors = {
            STATE_IDLE: "#333333",
            STATE_LEFT: "#2e7d32",
            STATE_RIGHT: "#1565c0",
            STATE_PAUSED: "#bf360c",
        }
        self._status_label.config(fg=colors.get(s, "#333333"))

        for action, btn in self._bind_buttons.items():
            if self.app.rebinding == action:
                btn.config(text="Press a key...", fg="#bf360c")
            else:
                btn.config(text=config.key_name(self.keybinds[action]), fg="#333333")

        lc = config.key_name(self.keybinds["left_click"])
        rc = config.key_name(self.keybinds["right_click"])
        self._clicker_legend.config(text=f"{lc}(hold)=left | {rc}(hold)=right")

    def _on_cps_change(self, *_args):
        try:
            v = int(self._cps_var.get())
            self.clicker.set_cps(v)
        except ValueError:
            pass
