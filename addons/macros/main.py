"""Macros module for OHK."""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from evdev import ecodes
from ohk import config
from ohk.addon import OHKAddon
from ohk.macros import MacroRecorder, MacroPlayer


def _key_display(code):
    """Human-readable name for an evdev key code."""
    name = ecodes.KEY.get(code, code)
    if isinstance(name, list):
        name = name[0]
    if isinstance(name, str) and name.startswith("KEY_"):
        name = name[4:]
    return str(name)


class MacroEditor:
    """Window for editing a macro's events."""

    def __init__(self, parent, macro_name, on_save=None):
        self.macro_name = macro_name
        self.on_save = on_save
        self.data = config.load_macro(macro_name)
        self.events = list(self.data.get("events", []))

        self.win = tk.Toplevel(parent)
        self.win.title(f"Edit Macro — {macro_name}")
        self.win.resizable(True, True)
        self.win.transient(parent)
        self.win.grab_set()
        self.win.geometry("600x450")

        self._build_ui()
        self._populate_tree()

    def _build_ui(self):
        main = tk.Frame(self.win, padx=8, pady=8)
        main.pack(fill="both", expand=True)

        # Treeview
        tree_frame = tk.Frame(main)
        tree_frame.pack(fill="both", expand=True)

        cols = ("#", "Type", "Detail", "Action", "Delay (s)")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=12,
                                 selectmode="extended")
        for col in cols:
            width = 50 if col == "#" else 80 if col in ("Type", "Action", "Delay (s)") else 200
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, minwidth=40)
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(tree_frame, command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.config(yscrollcommand=scrollbar.set)

        # Buttons row 1
        btn1 = tk.Frame(main)
        btn1.pack(fill="x", pady=(8, 0))

        tk.Button(btn1, text="Add Key", font=("monospace", 9),
                  command=self._add_key).pack(side="left", padx=(0, 4))
        tk.Button(btn1, text="Add Mouse Click", font=("monospace", 9),
                  command=self._add_mouse).pack(side="left", padx=(0, 4))
        tk.Button(btn1, text="Add Delay", font=("monospace", 9),
                  command=self._add_delay).pack(side="left", padx=(0, 4))
        tk.Button(btn1, text="Edit", font=("monospace", 9),
                  command=self._edit_selected).pack(side="left", padx=(0, 4))
        tk.Button(btn1, text="Delete", font=("monospace", 9),
                  command=self._delete_selected).pack(side="left", padx=(0, 4))

        # Buttons row 2
        btn2 = tk.Frame(main)
        btn2.pack(fill="x", pady=(4, 0))

        tk.Button(btn2, text="Move Up", font=("monospace", 9),
                  command=self._move_up).pack(side="left", padx=(0, 4))
        tk.Button(btn2, text="Move Down", font=("monospace", 9),
                  command=self._move_down).pack(side="left", padx=(0, 4))

        tk.Button(btn2, text="Save", font=("monospace", 9, "bold"),
                  command=self._save).pack(side="right", padx=(4, 0))
        tk.Button(btn2, text="Cancel", font=("monospace", 9),
                  command=self.win.destroy).pack(side="right")

    def _populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        prev_time = 0
        for i, evt in enumerate(self.events):
            t = evt.get("time", 0)
            delay = round(t - prev_time, 4)
            prev_time = t

            if evt["type"] == "key":
                etype = "Key"
                detail = _key_display(evt["code"])
            elif evt["type"] == "mouse_click":
                etype = "Mouse"
                detail = f"{evt['button']} @ {evt['x']},{evt['y']}"
            else:
                etype = evt["type"]
                detail = ""

            action = evt.get("action", "").capitalize()
            self.tree.insert("", "end", iid=str(i),
                             values=(i + 1, etype, detail, action, f"{delay:.4f}"))

    def _get_selected_idx(self):
        """Return first selected index, or None."""
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _get_selected_indices(self):
        """Return all selected indices as a sorted list."""
        sel = self.tree.selection()
        return sorted(int(s) for s in sel) if sel else []

    def _insert_after_selected(self, evt):
        idx = self._get_selected_idx()
        if idx is not None:
            pos = idx + 1
        else:
            pos = len(self.events)

        # Set time based on position
        if pos == 0:
            evt["time"] = 0
        elif pos <= len(self.events):
            evt["time"] = self.events[pos - 1].get("time", 0) + 0.05
        else:
            evt["time"] = self.events[-1].get("time", 0) + 0.05 if self.events else 0

        self.events.insert(pos, evt)
        self._populate_tree()

    # ── Add dialogs ──────────────────────────────────────────────────────

    def _add_key(self):
        dlg = tk.Toplevel(self.win)
        dlg.title("Add Key Event")
        dlg.resizable(False, False)
        dlg.transient(self.win)
        dlg.grab_set()

        frame = tk.Frame(dlg, padx=12, pady=12)
        frame.pack()

        tk.Label(frame, text="Action:", font=("monospace", 10)).grid(row=0, column=0, sticky="w")
        action_var = tk.StringVar(value="press")
        tk.OptionMenu(frame, action_var, "press", "release").grid(row=0, column=1, sticky="w", padx=(8, 0))

        tk.Label(frame, text="Delay (s):", font=("monospace", 10)).grid(row=1, column=0, sticky="w", pady=(4, 0))
        delay_var = tk.StringVar(value="0.05")
        tk.Entry(frame, textvariable=delay_var, width=8, font=("monospace", 10)).grid(
            row=1, column=1, sticky="w", padx=(8, 0), pady=(4, 0))

        tk.Label(frame, text="Press a key to capture:", font=("monospace", 10)).grid(
            row=2, column=0, columnspan=2, pady=(8, 0))

        key_label = tk.Label(frame, text="(waiting...)", font=("monospace", 12, "bold"), fg="#bf360c")
        key_label.grid(row=3, column=0, columnspan=2, pady=(4, 0))

        captured = {"code": None}

        def on_key(event):
            # Map tkinter keysym to evdev code
            code = _tkinter_to_evdev(event.keycode, event.keysym)
            if code is not None:
                captured["code"] = code
                key_label.config(text=_key_display(code), fg="#2e7d32")

        dlg.bind("<KeyPress>", on_key)

        def confirm():
            if captured["code"] is None:
                messagebox.showwarning("No Key", "Press a key first.", parent=dlg)
                return
            try:
                delay = float(delay_var.get())
            except ValueError:
                delay = 0.05

            idx = self._get_selected_idx()
            if idx is not None:
                base_time = self.events[idx].get("time", 0) + delay
            elif self.events:
                base_time = self.events[-1].get("time", 0) + delay
            else:
                base_time = 0

            evt = {"type": "key", "code": captured["code"],
                   "action": action_var.get(), "time": round(base_time, 4)}
            dlg.destroy()
            self._insert_event_at_pos(evt)

        tk.Button(frame, text="Add", font=("monospace", 10),
                  command=confirm).grid(row=4, column=0, columnspan=2, pady=(8, 0))

    def _add_mouse(self):
        dlg = tk.Toplevel(self.win)
        dlg.title("Add Mouse Click")
        dlg.resizable(False, False)
        dlg.transient(self.win)
        dlg.grab_set()

        frame = tk.Frame(dlg, padx=12, pady=12)
        frame.pack()

        fields = {}
        for i, (label, default) in enumerate([("X:", "500"), ("Y:", "300")]):
            tk.Label(frame, text=label, font=("monospace", 10)).grid(row=i, column=0, sticky="w", pady=(2, 0))
            var = tk.StringVar(value=default)
            tk.Entry(frame, textvariable=var, width=8, font=("monospace", 10)).grid(
                row=i, column=1, sticky="w", padx=(8, 0), pady=(2, 0))
            fields[label] = var

        tk.Label(frame, text="Button:", font=("monospace", 10)).grid(row=2, column=0, sticky="w", pady=(2, 0))
        btn_var = tk.StringVar(value="left")
        tk.OptionMenu(frame, btn_var, "left", "right", "middle").grid(row=2, column=1, sticky="w", padx=(8, 0))

        tk.Label(frame, text="Action:", font=("monospace", 10)).grid(row=3, column=0, sticky="w", pady=(2, 0))
        action_var = tk.StringVar(value="press")
        tk.OptionMenu(frame, action_var, "press", "release").grid(row=3, column=1, sticky="w", padx=(8, 0))

        tk.Label(frame, text="Delay (s):", font=("monospace", 10)).grid(row=4, column=0, sticky="w", pady=(2, 0))
        delay_var = tk.StringVar(value="0.05")
        tk.Entry(frame, textvariable=delay_var, width=8, font=("monospace", 10)).grid(
            row=4, column=1, sticky="w", padx=(8, 0), pady=(2, 0))

        def confirm():
            try:
                x = int(fields["X:"].get())
                y = int(fields["Y:"].get())
                delay = float(delay_var.get())
            except ValueError:
                messagebox.showwarning("Invalid", "Enter valid numbers.", parent=dlg)
                return

            idx = self._get_selected_idx()
            if idx is not None:
                base_time = self.events[idx].get("time", 0) + delay
            elif self.events:
                base_time = self.events[-1].get("time", 0) + delay
            else:
                base_time = 0

            evt = {"type": "mouse_click", "x": x, "y": y,
                   "button": btn_var.get(), "action": action_var.get(),
                   "time": round(base_time, 4)}
            dlg.destroy()
            self._insert_event_at_pos(evt)

        tk.Button(frame, text="Add", font=("monospace", 10),
                  command=confirm).grid(row=5, column=0, columnspan=2, pady=(8, 0))

    def _add_delay(self):
        val = simpledialog.askfloat("Add Delay", "Delay in seconds:", initialvalue=0.5,
                                     minvalue=0.001, parent=self.win)
        if val is None:
            return
        idx = self._get_selected_idx()
        if idx is not None:
            # Shift all events after idx by the delay amount
            for i in range(idx + 1, len(self.events)):
                self.events[i]["time"] = round(self.events[i]["time"] + val, 4)
        self._populate_tree()

    def _insert_event_at_pos(self, evt):
        idx = self._get_selected_idx()
        pos = (idx + 1) if idx is not None else len(self.events)
        self.events.insert(pos, evt)
        self._populate_tree()

    # ── Edit ─────────────────────────────────────────────────────────────

    def _edit_selected(self):
        indices = self._get_selected_indices()
        if not indices:
            return

        if len(indices) == 1:
            self._edit_single(indices[0])
        else:
            self._edit_multiple(indices)

    def _edit_single(self, idx):
        evt = self.events[idx]

        dlg = tk.Toplevel(self.win)
        dlg.title(f"Edit Event #{idx + 1}")
        dlg.resizable(False, False)
        dlg.transient(self.win)
        dlg.grab_set()

        frame = tk.Frame(dlg, padx=12, pady=12)
        frame.pack()

        # Action
        tk.Label(frame, text="Action:", font=("monospace", 10)).grid(row=0, column=0, sticky="w")
        action_var = tk.StringVar(value=evt.get("action", "press"))
        tk.OptionMenu(frame, action_var, "press", "release").grid(row=0, column=1, sticky="w", padx=(8, 0))

        # Delay
        prev_time = self.events[idx - 1].get("time", 0) if idx > 0 else 0
        current_delay = round(evt.get("time", 0) - prev_time, 4)

        tk.Label(frame, text="Delay (s):", font=("monospace", 10)).grid(row=1, column=0, sticky="w", pady=(4, 0))
        delay_var = tk.StringVar(value=str(current_delay))
        tk.Entry(frame, textvariable=delay_var, width=10, font=("monospace", 10)).grid(
            row=1, column=1, sticky="w", padx=(8, 0), pady=(4, 0))

        # Type-specific fields
        row = 2
        extra_vars = {}

        if evt["type"] == "key":
            tk.Label(frame, text=f"Key: {_key_display(evt['code'])}", font=("monospace", 10)).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(4, 0))
        elif evt["type"] == "mouse_click":
            for label, key in [("X:", "x"), ("Y:", "y")]:
                tk.Label(frame, text=label, font=("monospace", 10)).grid(row=row, column=0, sticky="w", pady=(2, 0))
                var = tk.StringVar(value=str(evt.get(key, 0)))
                tk.Entry(frame, textvariable=var, width=8, font=("monospace", 10)).grid(
                    row=row, column=1, sticky="w", padx=(8, 0), pady=(2, 0))
                extra_vars[key] = var
                row += 1

            tk.Label(frame, text="Button:", font=("monospace", 10)).grid(row=row, column=0, sticky="w", pady=(2, 0))
            btn_var = tk.StringVar(value=evt.get("button", "left"))
            tk.OptionMenu(frame, btn_var, "left", "right", "middle").grid(
                row=row, column=1, sticky="w", padx=(8, 0))
            extra_vars["button"] = btn_var
            row += 1

        def confirm():
            try:
                new_delay = float(delay_var.get())
            except ValueError:
                new_delay = current_delay

            new_time = round(prev_time + new_delay, 4)
            evt["time"] = new_time
            evt["action"] = action_var.get()

            if evt["type"] == "mouse_click":
                try:
                    evt["x"] = int(extra_vars["x"].get())
                    evt["y"] = int(extra_vars["y"].get())
                except ValueError:
                    pass
                if "button" in extra_vars:
                    evt["button"] = extra_vars["button"].get()

            dlg.destroy()
            self._populate_tree()

        tk.Button(frame, text="OK", font=("monospace", 10),
                  command=confirm).grid(row=row + 1, column=0, columnspan=2, pady=(8, 0))

    def _edit_multiple(self, indices):
        """Edit multiple selected events at once."""
        dlg = tk.Toplevel(self.win)
        dlg.title(f"Edit {len(indices)} Events")
        dlg.resizable(False, False)
        dlg.transient(self.win)
        dlg.grab_set()

        frame = tk.Frame(dlg, padx=12, pady=12)
        frame.pack()

        tk.Label(frame, text=f"Editing {len(indices)} events", font=("monospace", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        # Action (optional — leave blank to keep each event's current action)
        tk.Label(frame, text="Action:", font=("monospace", 10)).grid(row=1, column=0, sticky="w")
        action_var = tk.StringVar(value="(keep)")
        tk.OptionMenu(frame, action_var, "(keep)", "press", "release").grid(
            row=1, column=1, sticky="w", padx=(8, 0))

        # Delay — set all to this value
        tk.Label(frame, text="Set delay (s):", font=("monospace", 10)).grid(row=2, column=0, sticky="w", pady=(4, 0))
        delay_var = tk.StringVar(value="")
        tk.Entry(frame, textvariable=delay_var, width=10, font=("monospace", 10)).grid(
            row=2, column=1, sticky="w", padx=(8, 0), pady=(4, 0))

        tk.Label(frame, text="Leave delay blank to keep current", font=("monospace", 8),
                 fg="#999999").grid(row=3, column=0, columnspan=2, sticky="w")

        def confirm():
            new_action = action_var.get()
            delay_str = delay_var.get().strip()
            new_delay = None
            if delay_str:
                try:
                    new_delay = float(delay_str)
                except ValueError:
                    pass

            # Process in order so updated times cascade correctly
            for idx in sorted(indices):
                evt = self.events[idx]

                if new_action != "(keep)":
                    evt["action"] = new_action

                if new_delay is not None:
                    # Use the already-updated previous event's time
                    prev_time = self.events[idx - 1]["time"] if idx > 0 else 0
                    evt["time"] = round(prev_time + new_delay, 4)

            dlg.destroy()
            self._populate_tree()

        tk.Button(frame, text="Apply", font=("monospace", 10),
                  command=confirm).grid(row=4, column=0, columnspan=2, pady=(8, 0))

    # ── Delete / Move ────────────────────────────────────────────────────

    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        indices = sorted([int(s) for s in sel], reverse=True)
        for i in indices:
            if i < len(self.events):
                del self.events[i]
        self._populate_tree()

    def _move_up(self):
        idx = self._get_selected_idx()
        if idx is None or idx == 0:
            return
        self.events[idx], self.events[idx - 1] = self.events[idx - 1], self.events[idx]
        # Swap times too
        self.events[idx]["time"], self.events[idx - 1]["time"] = \
            self.events[idx - 1]["time"], self.events[idx]["time"]
        self._populate_tree()
        self.tree.selection_set(str(idx - 1))

    def _move_down(self):
        idx = self._get_selected_idx()
        if idx is None or idx >= len(self.events) - 1:
            return
        self.events[idx], self.events[idx + 1] = self.events[idx + 1], self.events[idx]
        self.events[idx]["time"], self.events[idx + 1]["time"] = \
            self.events[idx + 1]["time"], self.events[idx]["time"]
        self._populate_tree()
        self.tree.selection_set(str(idx + 1))

    # ── Save ─────────────────────────────────────────────────────────────

    def _save(self):
        # Rebuild absolute times from delays to ensure consistency
        if self.events:
            # Keep existing times as-is (they were edited in place)
            pass
        self.data["events"] = self.events
        config.save_macro(self.macro_name, self.data)
        if self.on_save:
            self.on_save()
        self.win.destroy()


# ── Tkinter keysym to evdev mapping ──────────────────────────────────────

_KEYSYM_TO_EVDEV = {
    "space": ecodes.KEY_SPACE, "Return": ecodes.KEY_ENTER,
    "BackSpace": ecodes.KEY_BACKSPACE, "Tab": ecodes.KEY_TAB,
    "Escape": ecodes.KEY_ESC, "Delete": ecodes.KEY_DELETE,
    "Insert": ecodes.KEY_INSERT, "Home": ecodes.KEY_HOME,
    "End": ecodes.KEY_END, "Prior": ecodes.KEY_PAGEUP,
    "Next": ecodes.KEY_PAGEDOWN, "Up": ecodes.KEY_UP,
    "Down": ecodes.KEY_DOWN, "Left": ecodes.KEY_LEFT,
    "Right": ecodes.KEY_RIGHT, "Caps_Lock": ecodes.KEY_CAPSLOCK,
    "Shift_L": ecodes.KEY_LEFTSHIFT, "Shift_R": ecodes.KEY_RIGHTSHIFT,
    "Control_L": ecodes.KEY_LEFTCTRL, "Control_R": ecodes.KEY_RIGHTCTRL,
    "Alt_L": ecodes.KEY_LEFTALT, "Alt_R": ecodes.KEY_RIGHTALT,
    "Super_L": ecodes.KEY_LEFTMETA, "Super_R": ecodes.KEY_RIGHTMETA,
}

# Add F1-F12
for _i in range(1, 13):
    _KEYSYM_TO_EVDEV[f"F{_i}"] = getattr(ecodes, f"KEY_F{_i}")

# Build letter/number map
for _code, _name in ecodes.KEY.items():
    if isinstance(_name, list):
        _name = _name[0]
    if isinstance(_name, str) and _name.startswith("KEY_") and len(_name) == 5:
        ch = _name[4:].lower()
        _KEYSYM_TO_EVDEV[ch] = _code


def _tkinter_to_evdev(keycode, keysym):
    """Best-effort conversion from tkinter key event to evdev code."""
    if keysym in _KEYSYM_TO_EVDEV:
        return _KEYSYM_TO_EVDEV[keysym]
    keysym_lower = keysym.lower()
    if keysym_lower in _KEYSYM_TO_EVDEV:
        return _KEYSYM_TO_EVDEV[keysym_lower]
    # Try single char
    if len(keysym) == 1:
        ch = keysym.lower()
        if ch in _KEYSYM_TO_EVDEV:
            return _KEYSYM_TO_EVDEV[ch]
    return None


# ── Main addon class ─────────────────────────────────────────────────────

class MacrosAddon(OHKAddon):
    name = "Macros"
    description = "Record and replay keyboard/mouse sequences"
    version = "2.0"
    help_text = (
        "Macros\n"
        "\n"
        "Record keyboard and mouse sequences, then\n"
        "replay them with a hotkey.\n"
        "\n"
        "Recording:\n"
        "  1. Press F9 (or your Record key) to start\n"
        "  2. Perform your actions (key presses, etc.)\n"
        "  3. Press F9 again to stop recording\n"
        "  4. Enter a name for the macro\n"
        "\n"
        "Playback:\n"
        "  - Select a macro and click Play, or\n"
        "  - Assign a hotkey with 'Set Hotkey' and\n"
        "    press that key anytime to replay\n"
        "\n"
        "Editing:\n"
        "  - Select a macro and click Edit to open\n"
        "    the macro editor window\n"
        "  - Add, remove, reorder events\n"
        "  - Change delays and key assignments\n"
        "\n"
        "Macros are saved to ~/.config/ohk/macros/"
    )

    def __init__(self, app):
        super().__init__(app)
        self.keybinds = app.keybinds
        self.recorder = MacroRecorder()
        self.player = MacroPlayer()
        self._rec_status = None
        self._rec_btn = None
        self._macro_listbox = None
        self._bind_buttons = {}

    def build_tab(self, parent):
        frame = tk.Frame(parent, padx=12, pady=12)

        # Recording status
        self._rec_status = tk.StringVar(value="Not recording")
        tk.Label(frame, textvariable=self._rec_status, font=("monospace", 11, "bold"),
                 fg="#333333").grid(row=0, column=0, columnspan=3, sticky="w")

        # Record button
        self._rec_btn = tk.Button(frame, text="Record", font=("monospace", 10),
                                   command=self._toggle_recording, width=10)
        self._rec_btn.grid(row=1, column=0, pady=(8, 0), sticky="w")

        # Stop playback button
        tk.Button(frame, text="Stop Playback", font=("monospace", 10),
                  command=self._stop_macro, width=12).grid(row=1, column=1, pady=(8, 0),
                                                            padx=(8, 0), sticky="w")

        # Separator
        tk.Frame(frame, height=1, bg="#cccccc").grid(row=2, column=0, columnspan=3,
                                                      sticky="we", pady=(10, 6))

        # Macro list
        tk.Label(frame, text="Saved Macros", font=("monospace", 11, "bold")).grid(
            row=3, column=0, columnspan=3, sticky="w")

        list_frame = tk.Frame(frame)
        list_frame.grid(row=4, column=0, columnspan=3, sticky="we", pady=(4, 0))

        self._macro_listbox = tk.Listbox(list_frame, font=("monospace", 10), height=6, width=30)
        self._macro_listbox.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(list_frame, command=self._macro_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self._macro_listbox.config(yscrollcommand=scrollbar.set)

        # Macro action buttons
        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=3, sticky="we", pady=(6, 0))

        tk.Button(btn_frame, text="Play", font=("monospace", 9),
                  command=self._play_selected).pack(side="left", padx=(0, 4))
        tk.Button(btn_frame, text="Edit", font=("monospace", 9),
                  command=self._edit_selected).pack(side="left", padx=(0, 4))
        tk.Button(btn_frame, text="Set Hotkey", font=("monospace", 9),
                  command=self._set_macro_hotkey).pack(side="left", padx=(0, 4))
        tk.Button(btn_frame, text="Disable Hotkey", font=("monospace", 9),
                  command=self._disable_macro_hotkey).pack(side="left", padx=(0, 4))
        tk.Button(btn_frame, text="Delete", font=("monospace", 9),
                  command=self._delete_selected).pack(side="left", padx=(0, 4))

        # Record keybind
        tk.Frame(frame, height=1, bg="#cccccc").grid(row=6, column=0, columnspan=3,
                                                      sticky="we", pady=(10, 6))
        tk.Label(frame, text="Record Key:", font=("monospace", 10)).grid(row=7, column=0, sticky="w")
        btn = tk.Button(frame, text=config.key_name(self.keybinds["record"]),
                        font=("monospace", 10), width=12,
                        command=lambda: self.app.start_rebind("record"))
        btn.grid(row=7, column=1, sticky="w", padx=(8, 0))
        self._bind_buttons["record"] = btn
        self.app.bind_buttons["record"] = btn

        self._refresh_macro_list()
        return frame

    def on_key_event(self, code, value):
        if self.recorder.recording:
            if code != self.keybinds.get("record"):
                self.recorder.on_key_event(code, value)

        if code == self.keybinds.get("record") and value == 1:
            self._toggle_recording()
            return

        if value == 1:
            for macro_name in config.list_macros():
                data = config.load_macro(macro_name)
                hotkey = data.get("hotkey")
                if hotkey is not None and code == hotkey:
                    self._play_macro(macro_name)
                    return

    def _toggle_recording(self):
        if self.recorder.recording:
            events = self.recorder.stop_recording()
            if events:
                self.app.root.after(0, lambda: self._save_recording(events))
        else:
            self.recorder.start_recording()
        self._schedule_refresh()

    def _save_recording(self, events):
        name = simpledialog.askstring("Save Macro", "Macro name:", parent=self.app.root)
        if not name:
            return
        name = name.strip().replace(" ", "_")
        if not name:
            return
        data = {"name": name, "hotkey": None, "events": events}
        config.save_macro(name, data)
        self._refresh_macro_list()

    def _play_macro(self, name):
        if self.player.playing:
            self.player.stop()
            return
        try:
            data = config.load_macro(name)
        except (FileNotFoundError, KeyError):
            return
        events = data.get("events", [])
        if not events:
            return
        self.player.play(events, speed=1.0, loops=1,
                         on_done=lambda: self._schedule_refresh())
        self._schedule_refresh()

    def _stop_macro(self):
        self.player.stop()
        self._schedule_refresh()

    def _play_selected(self):
        sel = self._macro_listbox.curselection()
        if not sel:
            return
        name = self._macro_listbox.get(sel[0]).split("  [")[0]
        self._play_macro(name)

    def _edit_selected(self):
        sel = self._macro_listbox.curselection()
        if not sel:
            return
        name = self._macro_listbox.get(sel[0]).split("  [")[0]
        MacroEditor(self.app.root, name, on_save=self._refresh_macro_list)

    def _set_macro_hotkey(self):
        sel = self._macro_listbox.curselection()
        if not sel:
            return
        name = self._macro_listbox.get(sel[0]).split("  [")[0]
        messagebox.showinfo("Set Hotkey", f"Press any key to set the hotkey for '{name}'.\n"
                            "The next key you press globally will be assigned.")
        self.app._macro_rebinding = name
        self.app.rebinding = "__macro__"

    def _disable_macro_hotkey(self):
        sel = self._macro_listbox.curselection()
        if not sel:
            return
        name = self._macro_listbox.get(sel[0]).split("  [")[0]
        try:
            data = config.load_macro(name)
            data["hotkey"] = None
            config.save_macro(name, data)
        except Exception:
            pass
        self._refresh_macro_list()

    def _delete_selected(self):
        sel = self._macro_listbox.curselection()
        if not sel:
            return
        name = self._macro_listbox.get(sel[0]).split("  [")[0]
        if messagebox.askyesno("Delete Macro", f"Delete macro '{name}'?"):
            config.delete_macro(name)
            self._refresh_macro_list()

    def _refresh_macro_list(self):
        if self._macro_listbox is None:
            return
        self._macro_listbox.delete(0, tk.END)
        for name in config.list_macros():
            data = config.load_macro(name)
            hotkey = data.get("hotkey")
            suffix = f"  [{config.key_name(hotkey)}]" if hotkey else ""
            self._macro_listbox.insert(tk.END, name + suffix)

    def _refresh(self):
        if self._rec_btn is None:
            return
        if self.recorder.recording:
            self._rec_status.set("Recording...")
            self._rec_btn.config(text="Stop")
        else:
            self._rec_status.set("Not recording")
            self._rec_btn.config(text="Record")

        self._refresh_macro_list()

        for action, btn in self._bind_buttons.items():
            if self.app.rebinding == action:
                btn.config(text="Press a key...", fg="#bf360c")
            else:
                btn.config(text=config.key_name(self.keybinds[action]), fg="#333333")

    def _schedule_refresh(self):
        try:
            self.app.root.after(0, self._refresh)
        except Exception:
            pass
