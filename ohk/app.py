"""OHK GUI application — thin shell that dispatches to modules and addons."""

import os
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

from PIL import ImageTk

from . import config
from .addon_manager import AddonManager
from .icon import make_icon
from .input import InputListener
from .modules.autoclicker import AutoclickerModule
from .modules.macros import MacrosModule


class OHKApp:
    def __init__(self, cps=20):
        # State
        self.keybinds = config.load_keybinds()
        self.rebinding = None
        self.bind_buttons = {}

        # Modules (built-in, always-on)
        self.modules = [
            AutoclickerModule(self),
            MacrosModule(self),
        ]
        self.modules[0].clicker.set_cps(cps)

        # Input
        self.input_listener = InputListener()
        self.input_listener.add_callback(self._on_key_event)

        # Addons (community, can be enabled/disabled)
        self.addon_manager = AddonManager(self)
        self.addon_manager.discover()
        self.addon_manager.load_enabled()

        # GUI
        self.root = None
        self._notebook = None
        self._build_gui()

    def run(self):
        for mod in self.modules:
            mod.start()
        self.input_listener.start()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        self.addon_manager.save_all_settings()
        self.root.destroy()

    # ── Public API for modules/addons ────────────────────────────────────

    def start_rebind(self, action):
        self.rebinding = action
        self._refresh_all()

    # ── Input handling ───────────────────────────────────────────────────

    def _on_key_event(self, code, value):
        """Global key event dispatcher."""
        # Rebinding mode
        if self.rebinding is not None and value == 1:
            if self.rebinding == "__macro__" and hasattr(self, "_macro_rebinding"):
                name = self._macro_rebinding.split("  [")[0]
                del self._macro_rebinding
                self.rebinding = None
                try:
                    data = config.load_macro(name)
                    data["hotkey"] = code
                    config.save_macro(name, data)
                except Exception:
                    pass
                self._refresh_all()
                return
            action = self.rebinding
            self.rebinding = None
            self.keybinds[action] = code
            config.save_keybinds(self.keybinds)
            self._refresh_all()
            return

        # Forward to modules
        for mod in self.modules:
            mod.on_key_event(code, value)

        # Forward to addons
        self.addon_manager.on_key_event(code, value)

    # ── GUI ──────────────────────────────────────────────────────────────

    def _refresh_all(self):
        """Refresh all module UIs."""
        for mod in self.modules:
            if hasattr(mod, '_refresh'):
                try:
                    mod._refresh()
                except Exception:
                    pass

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

        # Module tabs
        for mod in self.modules:
            tab = mod.build_tab(notebook)
            if tab is not None:
                notebook.add(tab, text=mod.name)

        # Addons management tab
        self._build_addons_tab(notebook)

        # Enabled addon tabs
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

        # Click anywhere to unfocus spinbox
        self.root.bind("<Button-1>", lambda e: self.root.focus_set()
                       if not isinstance(e.widget, tk.Spinbox) else None)

    # ── Addons tab ───────────────────────────────────────────────────────

    def _build_addons_tab(self, notebook):
        self._addons_frame = tk.Frame(notebook, padx=12, pady=12)
        notebook.add(self._addons_frame, text="Addons")

        notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        tk.Label(self._addons_frame, text="Installed Addons",
                 font=("monospace", 11, "bold")).pack(anchor="w")

        list_frame = tk.Frame(self._addons_frame)
        list_frame.pack(fill="both", expand=True, pady=(8, 0))

        self._addon_listbox = tk.Listbox(list_frame, font=("monospace", 10), height=6, width=35)
        self._addon_listbox.pack(side="left", fill="both", expand=True)
        self._addon_listbox.bind("<<ListboxSelect>>", self._on_addon_select)

        scrollbar = tk.Scrollbar(list_frame, command=self._addon_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self._addon_listbox.config(yscrollcommand=scrollbar.set)

        self._addon_info = tk.Label(self._addons_frame, text="Select an addon to see details",
                                     font=("monospace", 9), fg="#666666", justify="left", anchor="w")
        self._addon_info.pack(fill="x", pady=(6, 0))

        btn_frame = tk.Frame(self._addons_frame)
        btn_frame.pack(fill="x", pady=(8, 0))

        self._addon_enable_btn = tk.Button(btn_frame, text="Enable", font=("monospace", 9),
                                            command=self._toggle_addon, width=10)
        self._addon_enable_btn.pack(side="left", padx=(0, 4))

        tk.Button(btn_frame, text="Open Addons Folder", font=("monospace", 9),
                  command=self._open_addons_folder).pack(side="left", padx=(0, 4))

        # Credits
        tk.Label(self._addons_frame, text="OHK — Onyx Hot Keys\nby ONYX Development",
                 font=("monospace", 9), fg="#888888", justify="center").pack(pady=(12, 0))

        self._refresh_addon_list()

    def _on_tab_changed(self, _event):
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
            self.addon_manager.disable(folder_name)
            if folder_name in self._addon_tabs:
                self._notebook.forget(self._addon_tabs[folder_name])
                del self._addon_tabs[folder_name]
        else:
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
