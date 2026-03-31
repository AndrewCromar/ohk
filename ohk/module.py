"""Base class for OHK modules (built-in, always-on features)."""

import tkinter as tk


class OHKModule:
    """Base class for built-in OHK modules.

    Modules are always active and ship with OHK. They cannot be disabled.
    Each module gets its own tab and receives global key events.
    """

    name = "Unnamed Module"

    def __init__(self, app):
        self.app = app

    def build_tab(self, parent):
        """Build and return a tk.Frame to be added as a tab."""
        return None

    def on_key_event(self, code, value):
        """Called on every global key event.

        Args:
            code: evdev key code
            value: 0=release, 1=press, 2=repeat
        """
        pass

    def start(self):
        """Called after GUI is built, before mainloop. Start background threads here."""
        pass
