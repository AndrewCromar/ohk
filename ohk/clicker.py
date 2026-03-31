"""Autoclicker module for OHK."""

import threading
import time

from pynput.mouse import Button, Controller as MouseController

STATE_IDLE = "Idle"
STATE_LEFT = "Left Clicking"
STATE_RIGHT = "Right Clicking"
STATE_PAUSED = "Paused"


class Autoclicker:
    def __init__(self):
        self.mouse = MouseController()
        self.state = STATE_IDLE
        self.cps = 20
        self.lock = threading.Lock()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while True:
            with self.lock:
                s = self.state
                c = self.cps
            if s == STATE_LEFT:
                self.mouse.click(Button.left)
            elif s == STATE_RIGHT:
                self.mouse.click(Button.right)
            time.sleep(1.0 / max(c, 1))

    def set_state(self, new_state):
        with self.lock:
            self.state = new_state

    def get_state(self):
        with self.lock:
            return self.state

    def set_cps(self, cps):
        with self.lock:
            self.cps = max(1, cps)

    def toggle_pause(self):
        with self.lock:
            if self.state == STATE_PAUSED:
                self.state = STATE_IDLE
            else:
                self.state = STATE_PAUSED
            return self.state
