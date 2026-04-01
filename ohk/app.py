"""OHK GUI application — dispatches to modules (addons)."""

import os
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

from PIL import ImageTk

from . import config
from .addon_manager import AddonManager
from .icon import make_icon
from .input import InputListener


class OHKApp:
    def __init__(self, cps=20):
        self.keybinds = config.load_keybinds()
        self.rebinding = None
        self.bind_buttons = {}
        self._cps = cps

        # Input
        self.input_listener = InputListener()
        self.input_listener.add_callback(self._on_key_event)

        # All modules/addons go through addon manager
        self.addon_manager = AddonManager(self)
        self.addon_manager.discover()
        self.addon_manager.load_enabled()

        # GUI
        self.root = None
        self._notebook = None
        self._build_gui()

    def run(self):
        self.input_listener.start()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        self.addon_manager.save_all_settings()
        self.root.destroy()

    # ── Public API for modules ───────────────────────────────────────────

    def start_rebind(self, action):
        self.rebinding = action
        self._refresh_all()

    # ── Input handling ───────────────────────────────────────────────────

    def _on_key_event(self, code, value):
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

        # Forward to all enabled modules/addons
        self.addon_manager.on_key_event(code, value)

    # ── GUI ──────────────────────────────────────────────────────────────

    def _refresh_all(self):
        for info in self.addon_manager.get_enabled_addons():
            if hasattr(info.instance, '_refresh'):
                try:
                    info.instance._refresh()
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

        # Modules tab (home page) — first tab
        self._build_modules_tab(notebook)

        # Enabled module/addon tabs
        self._addon_tabs = {}
        for folder_name, info in self.addon_manager.addons.items():
            if info.enabled and info.instance:
                try:
                    tab = info.instance.build_tab(notebook)
                    if tab is not None:
                        notebook.add(tab, text=info.name)
                        self._addon_tabs[folder_name] = tab
                except Exception as e:
                    print(f"Error building tab for '{info.name}': {e}")

        self.root.bind("<Button-1>", lambda e: self.root.focus_set()
                       if not isinstance(e.widget, tk.Spinbox) else None)

    # ── Modules tab (home page) ──────────────────────────────────────────

    def _build_modules_tab(self, notebook):
        self._modules_frame = tk.Frame(notebook, padx=12, pady=12)
        notebook.add(self._modules_frame, text="Modules")

        notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Header with help button
        header_frame = tk.Frame(self._modules_frame)
        header_frame.pack(fill="x")

        tk.Label(header_frame, text="Modules",
                 font=("monospace", 11, "bold")).pack(side="left")

        tk.Button(header_frame, text="?", font=("monospace", 10, "bold"),
                  command=self._show_help, width=2).pack(side="right")

        # Module list
        list_frame = tk.Frame(self._modules_frame)
        list_frame.pack(fill="both", expand=True, pady=(8, 0))

        self._module_listbox = tk.Listbox(list_frame, font=("monospace", 10), height=8, width=35)
        self._module_listbox.pack(side="left", fill="both", expand=True)
        self._module_listbox.bind("<<ListboxSelect>>", self._on_module_select)

        scrollbar = tk.Scrollbar(list_frame, command=self._module_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self._module_listbox.config(yscrollcommand=scrollbar.set)

        # Module info
        self._module_info = tk.Label(self._modules_frame, text="Select a module to see details",
                                      font=("monospace", 9), fg="#666666", justify="left", anchor="w")
        self._module_info.pack(fill="x", pady=(6, 0))

        # Buttons
        btn_frame = tk.Frame(self._modules_frame)
        btn_frame.pack(fill="x", pady=(8, 0))

        self._module_enable_btn = tk.Button(btn_frame, text="Enable", font=("monospace", 9),
                                             command=self._toggle_module, width=10)
        self._module_enable_btn.pack(side="left", padx=(0, 4))

        self._module_help_btn = tk.Button(btn_frame, text="Help", font=("monospace", 9),
                                           command=self._show_module_help, width=6)
        self._module_help_btn.pack(side="left", padx=(0, 4))

        tk.Button(btn_frame, text="Open Modules Folder", font=("monospace", 9),
                  command=self._open_modules_folder).pack(side="left", padx=(0, 4))

        # Credits
        tk.Label(self._modules_frame, text="OHK — Onyx Hot Keys\nby ONYX Development",
                 font=("monospace", 9), fg="#888888", justify="center").pack(pady=(12, 0))

        self._refresh_module_list()

    def _on_tab_changed(self, _event):
        try:
            current = self._notebook.index(self._notebook.select())
            modules_idx = self._notebook.index(self._modules_frame)
            if current == modules_idx:
                self.addon_manager.rescan()
                self._refresh_module_list()
        except Exception:
            pass

    def _refresh_module_list(self):
        self._module_listbox.delete(0, tk.END)
        for folder_name, info in self.addon_manager.addons.items():
            status = "[ON] " if info.enabled else "[OFF]"
            self._module_listbox.insert(tk.END, f"{status} {info.name}")

    def _on_module_select(self, _event):
        sel = self._module_listbox.curselection()
        if not sel:
            return
        folder_name = list(self.addon_manager.addons.keys())[sel[0]]
        info = self.addon_manager.addons[folder_name]
        self._module_info.config(
            text=f"{info.name} v{info.version}\n{info.description}")
        self._module_enable_btn.config(text="Disable" if info.enabled else "Enable")

    def _toggle_module(self):
        sel = self._module_listbox.curselection()
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
                    print(f"Error building tab for '{info.name}': {e}")
        self._refresh_module_list()
        self._module_enable_btn.config(text="Disable" if info.enabled else "Enable")

    def _show_module_help(self):
        sel = self._module_listbox.curselection()
        if not sel:
            messagebox.showinfo("Help", "Select a module first.")
            return
        folder_name = list(self.addon_manager.addons.keys())[sel[0]]
        info = self.addon_manager.addons[folder_name]
        help_text = getattr(info.addon_class, 'help_text', '') or info.description

        help_win = tk.Toplevel(self.root)
        help_win.title(f"Help — {info.name}")
        help_win.resizable(False, False)
        help_win.transient(self.root)
        help_win.grab_set()

        frame = tk.Frame(help_win, padx=16, pady=16)
        frame.pack()

        tk.Label(frame, text=help_text, font=("monospace", 10), justify="left",
                 anchor="w").pack(fill="x", pady=(0, 10))
        tk.Button(frame, text="Close", font=("monospace", 10),
                  command=help_win.destroy, width=10).pack()

    def _open_modules_folder(self):
        modules_dir = os.path.join(config.CONFIG_DIR, "addons")
        os.makedirs(modules_dir, exist_ok=True)
        try:
            subprocess.Popen(["xdg-open", modules_dir])
        except Exception:
            pass

    def _show_help(self):
        help_win = tk.Toplevel(self.root)
        help_win.title("OHK — Help")
        help_win.resizable(False, False)
        help_win.transient(self.root)
        help_win.grab_set()

        frame = tk.Frame(help_win, padx=16, pady=16)
        frame.pack()

        tk.Label(frame, text="OHK — Onyx Hot Keys", font=("monospace", 13, "bold")).pack(anchor="w")
        tk.Label(frame, text="by ONYX Development", font=("monospace", 9), fg="#888888").pack(anchor="w", pady=(0, 10))

        help_text = (
            "OHK is a modular automation tool for Linux.\n"
            "All features are modules that can be enabled/disabled.\n"
            "\n"
            "Getting Started:\n"
            "  1. Go to the Modules tab\n"
            "  2. Select a module and click Enable\n"
            "  3. Its tab will appear — configure it there\n"
            "\n"
            "Adding New Modules:\n"
            "  1. Click 'Open Modules Folder'\n"
            "  2. Drop a module folder with a main.py inside\n"
            "  3. Switch to Modules tab to see it appear\n"
            "  4. Enable it and its tab will show up\n"
            "\n"
            "Keybinds:\n"
            "  Click any keybind button, then press a key\n"
            "  to assign it. Keybinds work globally even\n"
            "  when OHK is not focused.\n"
            "\n"
            "Config is stored in ~/.config/ohk/"
        )

        tk.Label(frame, text=help_text, font=("monospace", 10), justify="left",
                 anchor="w").pack(fill="x", pady=(0, 10))

        tk.Button(frame, text="Close", font=("monospace", 10),
                  command=help_win.destroy, width=10).pack()
