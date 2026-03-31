"""OHK GUI application — tabbed interface with autoclicker, macros, and addons."""

import os
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from PIL import ImageTk

from . import config
from .addon_manager import AddonManager
from .clicker import Autoclicker, STATE_IDLE, STATE_LEFT, STATE_RIGHT, STATE_PAUSED
from .icon import make_icon
from .input import InputListener
from .macros import MacroRecorder, MacroPlayer


class OHKApp:
    def __init__(self, cps=20):
        # State
        self.keybinds = config.load_keybinds()
        self.rebinding = None  # action name waiting for key
        self.bind_buttons = {}

        # Modules
        self.clicker = Autoclicker()
        self.clicker.set_cps(cps)
        self.recorder = MacroRecorder()
        self.player = MacroPlayer()
        self.input_listener = InputListener()
        self.input_listener.add_callback(self._on_key_event)

        # Addons
        self.addon_manager = AddonManager(self)
        self.addon_manager.discover()
        self.addon_manager.load_enabled()

        # GUI
        self.root = None
        self._notebook = None
        self._build_gui()

    def run(self):
        self.clicker.start()
        self.input_listener.start()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        self.addon_manager.save_all_settings()
        self.root.destroy()

    # ── Input handling ───────────────────────────────────────────────────

    def _on_key_event(self, code, value):
        """Global key event handler from evdev."""
        # Rebinding mode — capture next keypress
        if self.rebinding is not None and value == 1:
            if self.rebinding == "__macro__" and hasattr(self, "_macro_rebinding"):
                # Assign hotkey to a macro
                name = self._macro_rebinding.split("  [")[0]
                del self._macro_rebinding
                self.rebinding = None
                try:
                    data = config.load_macro(name)
                    data["hotkey"] = code
                    config.save_macro(name, data)
                except Exception:
                    pass
                self.root.after(0, self._refresh_macro_list)
                self._schedule_refresh()
                return
            action = self.rebinding
            self.rebinding = None
            self.keybinds[action] = code
            config.save_keybinds(self.keybinds)
            self._schedule_refresh()
            return

        # Feed to macro recorder if recording
        if self.recorder.recording:
            # Don't record the record key itself
            if code != self.keybinds["record"]:
                self.recorder.on_key_event(code, value)

        kb = self.keybinds

        # Quit
        if code == kb["quit"] and value == 1:
            self.root.after(0, self.root.destroy)
            return

        # Record toggle
        if code == kb["record"] and value == 1:
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

        # Pause
        if code == kb["pause"] and value == 1:
            self.clicker.toggle_pause()
            self._schedule_refresh()
            return

        # Autoclicker keys (handle press, repeat, release)
        state = self.clicker.get_state()
        if state == STATE_PAUSED:
            return

        pressed = value in (1, 2)
        released = value == 0

        if code == kb["left_click"]:
            if pressed:
                self.clicker.set_state(STATE_LEFT)
            elif released and state == STATE_LEFT:
                self.clicker.set_state(STATE_IDLE)
            self._schedule_refresh()
        elif code == kb["right_click"]:
            if pressed:
                self.clicker.set_state(STATE_RIGHT)
            elif released and state == STATE_RIGHT:
                self.clicker.set_state(STATE_IDLE)
            self._schedule_refresh()

        # Forward to addons
        self.addon_manager.on_key_event(code, value)

    # ── Macro control ────────────────────────────────────────────────────

    def _toggle_recording(self):
        if self.recorder.recording:
            events = self.recorder.stop_recording()
            if events:
                self.root.after(0, lambda: self._save_recording(events))
        else:
            self.recorder.start_recording()
        self._schedule_refresh()

    def _save_recording(self, events):
        name = simpledialog.askstring("Save Macro", "Macro name:", parent=self.root)
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
        loops = 1
        self.player.play(events, speed=1.0, loops=loops,
                         on_done=lambda: self._schedule_refresh())
        self._schedule_refresh()

    def _stop_macro(self):
        self.player.stop()
        self._schedule_refresh()

    # ── GUI ──────────────────────────────────────────────────────────────

    def _schedule_refresh(self):
        try:
            self.root.after(0, self._refresh_all)
        except Exception:
            pass

    def _build_gui(self):
        self.root = tk.Tk()
        self.root.title("OHK — Onyx Hot Keys")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", False)

        try:
            icon_img = make_icon(64)
            icon_photo = ImageTk.PhotoImage(icon_img)
            self.root.iconphoto(True, icon_photo)
            self.root._icon_ref = icon_photo
        except Exception:
            pass

        notebook = ttk.Notebook(self.root)
        notebook.pack(padx=8, pady=8)
        self._notebook = notebook

        self._build_clicker_tab(notebook)
        self._build_macros_tab(notebook)
        self._build_settings_tab(notebook)
        self._build_addons_tab(notebook)

        # Build tabs for enabled addons
        self._addon_tabs = {}
        for folder_name, info in self.addon_manager.addons.items():
            if info.enabled and info.instance:
                try:
                    tab = info.instance.build_tab(notebook)
                    if tab is not None:
                        notebook.add(tab, text=info.name)
                        self._addon_tabs[folder_name] = tab
                except Exception as e:
                    print(f"Error building tab for addon '{info.name}': {e}")

    def _build_clicker_tab(self, notebook):
        frame = tk.Frame(notebook, padx=12, pady=12)
        notebook.add(frame, text="Autoclicker")

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
        spin.bind("<Return>", lambda e: self.root.focus_set())
        spin.bind("<Escape>", lambda e: self.root.focus_set())

        # Keybinds
        tk.Frame(frame, height=1, bg="#cccccc").grid(row=2, column=0, columnspan=2,
                                                      sticky="we", pady=(10, 6))
        row = 3
        for action, label_text in [("left_click", "Left Click:"), ("right_click", "Right Click:")]:
            tk.Label(frame, text=label_text, font=("monospace", 10)).grid(row=row, column=0,
                                                                           sticky="w", pady=(4, 0))
            btn = tk.Button(frame, text=config.key_name(self.keybinds[action]),
                            font=("monospace", 10), width=12,
                            command=lambda a=action: self._start_rebind(a))
            btn.grid(row=row, column=1, sticky="w", padx=(8, 0), pady=(4, 0))
            self.bind_buttons[action] = btn
            row += 1

        # Pause / Resume button
        tk.Frame(frame, height=1, bg="#cccccc").grid(row=row, column=0, columnspan=2,
                                                      sticky="we", pady=(10, 6))
        row += 1
        tk.Button(frame, text="Pause / Resume", command=self._toggle_pause,
                  font=("monospace", 10)).grid(row=row, column=0, columnspan=2, sticky="we")

        # Legend
        row += 1
        self._clicker_legend = tk.Label(frame, text="", font=("monospace", 9), fg="#666666")
        self._clicker_legend.grid(row=row, column=0, columnspan=2, pady=(8, 0))

        self.root.bind("<Button-1>", lambda e: self.root.focus_set()
                       if not isinstance(e.widget, tk.Spinbox) else None)

    def _build_macros_tab(self, notebook):
        frame = tk.Frame(notebook, padx=12, pady=12)
        notebook.add(frame, text="Macros")

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
                        command=lambda: self._start_rebind("record"))
        btn.grid(row=7, column=1, sticky="w", padx=(8, 0))
        self.bind_buttons["record"] = btn

        self._refresh_macro_list()

    def _build_settings_tab(self, notebook):
        frame = tk.Frame(notebook, padx=12, pady=12)
        notebook.add(frame, text="Settings")

        tk.Label(frame, text="Global Keybinds", font=("monospace", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w")

        row = 1
        for action, label_text in [("pause", "Pause:"), ("quit", "Quit:")]:
            tk.Label(frame, text=label_text, font=("monospace", 10)).grid(row=row, column=0,
                                                                           sticky="w", pady=(4, 0))
            btn = tk.Button(frame, text=config.key_name(self.keybinds[action]),
                            font=("monospace", 10), width=12,
                            command=lambda a=action: self._start_rebind(a))
            btn.grid(row=row, column=1, sticky="w", padx=(8, 0), pady=(4, 0))
            self.bind_buttons[action] = btn
            row += 1

        # Reset
        tk.Frame(frame, height=1, bg="#cccccc").grid(row=row, column=0, columnspan=2,
                                                      sticky="we", pady=(10, 6))
        row += 1
        tk.Button(frame, text="Reset All Defaults", command=self._reset_keybinds,
                  font=("monospace", 10)).grid(row=row, column=0, columnspan=2, sticky="we")

        row += 1
        tk.Label(frame, text="OHK — Onyx Hot Keys\nby ONYX Development",
                 font=("monospace", 9), fg="#888888", justify="center").grid(
            row=row, column=0, columnspan=2, pady=(16, 0))

    def _build_addons_tab(self, notebook):
        self._addons_frame = tk.Frame(notebook, padx=12, pady=12)
        notebook.add(self._addons_frame, text="Addons")

        # Rescan when tab gets focus
        notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        tk.Label(self._addons_frame, text="Installed Addons",
                 font=("monospace", 11, "bold")).pack(anchor="w")

        # Addon list
        list_frame = tk.Frame(self._addons_frame)
        list_frame.pack(fill="both", expand=True, pady=(8, 0))

        self._addon_listbox = tk.Listbox(list_frame, font=("monospace", 10), height=6, width=35)
        self._addon_listbox.pack(side="left", fill="both", expand=True)
        self._addon_listbox.bind("<<ListboxSelect>>", self._on_addon_select)

        scrollbar = tk.Scrollbar(list_frame, command=self._addon_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self._addon_listbox.config(yscrollcommand=scrollbar.set)

        # Addon info
        self._addon_info = tk.Label(self._addons_frame, text="Select an addon to see details",
                                     font=("monospace", 9), fg="#666666", justify="left", anchor="w")
        self._addon_info.pack(fill="x", pady=(6, 0))

        # Buttons
        btn_frame = tk.Frame(self._addons_frame)
        btn_frame.pack(fill="x", pady=(8, 0))

        self._addon_enable_btn = tk.Button(btn_frame, text="Enable", font=("monospace", 9),
                                            command=self._toggle_addon, width=10)
        self._addon_enable_btn.pack(side="left", padx=(0, 4))

        tk.Button(btn_frame, text="Open Addons Folder", font=("monospace", 9),
                  command=self._open_addons_folder).pack(side="left", padx=(0, 4))

        self._refresh_addon_list()
        # Track which addon tabs exist so we can add/remove them
        self._addon_tabs = {}  # folder_name -> tab widget

    def _on_tab_changed(self, _event):
        """Rescan addons when the Addons tab gets focus."""
        try:
            current = self._notebook.index(self._notebook.select())
            addons_idx = self._notebook.index(self._addons_frame)
            if current == addons_idx:
                self.addon_manager.rescan()
                self._refresh_addon_list()
        except Exception:
            pass

    def _refresh_addon_list(self):
        self._addon_listbox.delete(0, tk.END)
        for folder_name, info in self.addon_manager.addons.items():
            status = "[ON] " if info.enabled else "[OFF]"
            self._addon_listbox.insert(tk.END, f"{status} {info.name}")

    def _on_addon_select(self, _event):
        sel = self._addon_listbox.curselection()
        if not sel:
            return
        folder_name = list(self.addon_manager.addons.keys())[sel[0]]
        info = self.addon_manager.addons[folder_name]
        self._addon_info.config(
            text=f"{info.name} v{info.version}\n{info.description}")
        self._addon_enable_btn.config(text="Disable" if info.enabled else "Enable")

    def _toggle_addon(self):
        sel = self._addon_listbox.curselection()
        if not sel:
            return
        folder_name = list(self.addon_manager.addons.keys())[sel[0]]
        info = self.addon_manager.addons[folder_name]
        if info.enabled:
            # Disable — remove tab if it exists
            self.addon_manager.disable(folder_name)
            if folder_name in self._addon_tabs:
                self._notebook.forget(self._addon_tabs[folder_name])
                del self._addon_tabs[folder_name]
        else:
            # Enable — instantiate and add tab live
            self.addon_manager.enable(folder_name)
            if info.instance:
                try:
                    tab = info.instance.build_tab(self._notebook)
                    if tab is not None:
                        self._notebook.add(tab, text=info.name)
                        self._addon_tabs[folder_name] = tab
                except Exception as e:
                    print(f"Error building tab for addon '{info.name}': {e}")
        self._refresh_addon_list()
        self._addon_enable_btn.config(text="Disable" if info.enabled else "Enable")

    def _open_addons_folder(self):
        addons_dir = os.path.join(config.CONFIG_DIR, "addons")
        os.makedirs(addons_dir, exist_ok=True)
        try:
            subprocess.Popen(["xdg-open", addons_dir])
        except Exception:
            pass

    # ── GUI callbacks ────────────────────────────────────────────────────

    def _on_cps_change(self, *_args):
        try:
            v = int(self._cps_var.get())
            self.clicker.set_cps(v)
        except ValueError:
            pass

    def _toggle_pause(self):
        self.clicker.toggle_pause()
        self._refresh_all()

    def _start_rebind(self, action):
        self.rebinding = action
        self._refresh_all()

    def _reset_keybinds(self):
        self.rebinding = None
        self.keybinds.update(config.DEFAULT_KEYBINDS)
        config.save_keybinds(self.keybinds)
        self._refresh_all()

    def _play_selected(self):
        sel = self._macro_listbox.curselection()
        if not sel:
            return
        name = self._macro_listbox.get(sel[0])
        self._play_macro(name)

    def _set_macro_hotkey(self):
        sel = self._macro_listbox.curselection()
        if not sel:
            return
        name = self._macro_listbox.get(sel[0])
        messagebox.showinfo("Set Hotkey", f"Press any key to set the hotkey for '{name}'.\n"
                            "The next key you press globally will be assigned.")
        self._macro_rebinding = name
        self.rebinding = "__macro__"

    def _delete_selected(self):
        sel = self._macro_listbox.curselection()
        if not sel:
            return
        name = self._macro_listbox.get(sel[0])
        if messagebox.askyesno("Delete Macro", f"Delete macro '{name}'?"):
            config.delete_macro(name)
            self._refresh_macro_list()

    def _refresh_macro_list(self):
        self._macro_listbox.delete(0, tk.END)
        for name in config.list_macros():
            data = config.load_macro(name)
            hotkey = data.get("hotkey")
            suffix = f"  [{config.key_name(hotkey)}]" if hotkey else ""
            self._macro_listbox.insert(tk.END, name + suffix)

    # ── Refresh ──────────────────────────────────────────────────────────

    def _refresh_all(self):
        # Clicker status
        s = self.clicker.get_state()
        self._status_var.set(s)
        colors = {
            STATE_IDLE: "#333333",
            STATE_LEFT: "#2e7d32",
            STATE_RIGHT: "#1565c0",
            STATE_PAUSED: "#bf360c",
        }
        self._status_label.config(fg=colors.get(s, "#333333"))

        # Keybind buttons
        for action, btn in self.bind_buttons.items():
            if self.rebinding == action:
                btn.config(text="Press a key...", fg="#bf360c")
            else:
                btn.config(text=config.key_name(self.keybinds[action]), fg="#333333")

        # Handle macro hotkey rebinding
        if self.rebinding == "__macro__" and hasattr(self, "_macro_rebinding"):
            # This was handled in _on_key_event via the general rebind path
            pass

        # Legend
        lc = config.key_name(self.keybinds["left_click"])
        rc = config.key_name(self.keybinds["right_click"])
        p = config.key_name(self.keybinds["pause"])
        q = config.key_name(self.keybinds["quit"])
        self._clicker_legend.config(text=f"{lc}=left | {rc}=right | {p}=pause | {q}=quit")

        # Recording status
        if self.recorder.recording:
            self._rec_status.set("Recording...")
            self._rec_status.config(fg="#bf360c") if hasattr(self._rec_status, 'config') else None
            self._rec_btn.config(text="Stop")
        else:
            self._rec_status.set("Not recording")
            self._rec_btn.config(text="Record")

    def _on_key_event_rebind_macro(self, code):
        """Handle macro hotkey assignment."""
        if hasattr(self, "_macro_rebinding"):
            name = self._macro_rebinding
            del self._macro_rebinding
            try:
                data = config.load_macro(name)
                # name might have suffix from listbox, clean it
                clean = name.split("  [")[0]
                data = config.load_macro(clean)
                data["hotkey"] = code
                config.save_macro(clean, data)
            except Exception:
                pass
            self._schedule_refresh()
            self.root.after(0, self._refresh_macro_list)
