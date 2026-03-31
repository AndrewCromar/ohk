"""Base class for OHK addons."""

import tkinter as tk


class OHKAddon:
    """Base class that all OHK addons must extend.

    To create an addon:
    1. Create a folder in ~/.config/ohk/addons/your_addon/
    2. Add a main.py with a class that extends OHKAddon
    3. Override the methods you need

    Example:
        class MyAddon(OHKAddon):
            name = "My Addon"
            description = "Does cool stuff"
            version = "1.0"

            def build_tab(self, parent):
                frame = tk.Frame(parent, padx=12, pady=12)
                tk.Label(frame, text="Hello from my addon!").pack()
                return frame
    """

    name = "Unnamed Addon"
    description = ""
    version = "1.0"

    def __init__(self, app):
        """Called when the addon is loaded. `app` is the OHKApp instance."""
        self.app = app

    def build_tab(self, parent):
        """Build and return a tk.Frame to be added as a tab.

        Args:
            parent: The ttk.Notebook widget to add the tab to.

        Returns:
            A tk.Frame (or None to skip adding a tab).
        """
        return None

    def on_key_event(self, code, value):
        """Called on every global key event.

        Args:
            code: evdev key code (e.g. ecodes.KEY_A)
            value: 0=release, 1=press, 2=repeat
        """
        pass

    def on_enable(self):
        """Called when the addon is enabled."""
        pass

    def on_disable(self):
        """Called when the addon is disabled."""
        pass

    def get_settings(self):
        """Return a dict of addon-specific settings to persist.

        Returns:
            A JSON-serializable dict.
        """
        return {}

    def load_settings(self, data):
        """Load previously saved settings.

        Args:
            data: The dict that was returned by get_settings().
        """
        pass
