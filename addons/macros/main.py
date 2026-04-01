"""Macros module for OHK."""

import tkinter as tk
from tkinter import messagebox, simpledialog

from ohk import config
from ohk.addon import OHKAddon
from ohk.macros import MacroRecorder, MacroPlayer


class MacrosAddon(OHKAddon):
    name = "Macros"
    description = "Record and replay keyboard/mouse sequences"
    version = "1.0"
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
        tk.Button(btn_frame, text="Set Hotkey", font=("monospace", 9),
                  command=self._set_macro_hotkey).pack(side="left", padx=(0, 4))
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
        # Feed to recorder if recording (skip record key itself)
        if self.recorder.recording:
            if code != self.keybinds.get("record"):
                self.recorder.on_key_event(code, value)

        # Record toggle
        if code == self.keybinds.get("record") and value == 1:
            self._toggle_recording()
            return

        # Check macro trigger hotkeys
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

    def _set_macro_hotkey(self):
        sel = self._macro_listbox.curselection()
        if not sel:
            return
        name = self._macro_listbox.get(sel[0]).split("  [")[0]
        messagebox.showinfo("Set Hotkey", f"Press any key to set the hotkey for '{name}'.\n"
                            "The next key you press globally will be assigned.")
        self.app._macro_rebinding = name
        self.app.rebinding = "__macro__"

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
