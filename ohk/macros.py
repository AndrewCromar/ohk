"""Macro recording and playback for OHK."""

import threading
import time

import evdev
from evdev import ecodes, UInput
from pynput.mouse import Button, Controller as MouseController

from . import config


class MacroRecorder:
    """Records keyboard and mouse events into a macro."""

    def __init__(self):
        self.recording = False
        self.events = []
        self._start_time = 0
        self._lock = threading.Lock()

    def start_recording(self):
        with self._lock:
            self.events = []
            self._start_time = time.monotonic()
            self.recording = True

    def stop_recording(self):
        with self._lock:
            self.recording = False
            return list(self.events)

    def on_key_event(self, code, value):
        """Called from input listener during recording. value: 0=release, 1=press."""
        with self._lock:
            if not self.recording:
                return
            if value not in (0, 1):  # skip repeats
                return
            elapsed = time.monotonic() - self._start_time
            self.events.append({
                "type": "key",
                "code": code,
                "action": "press" if value == 1 else "release",
                "time": round(elapsed, 4),
            })

    def on_mouse_click(self, x, y, button, pressed):
        """Can be called to record mouse clicks."""
        with self._lock:
            if not self.recording:
                return
            elapsed = time.monotonic() - self._start_time
            self.events.append({
                "type": "mouse_click",
                "x": x,
                "y": y,
                "button": button,  # "left", "right", "middle"
                "action": "press" if pressed else "release",
                "time": round(elapsed, 4),
            })


class MacroPlayer:
    """Plays back a recorded macro using evdev uinput for keys (Wayland compatible)."""

    def __init__(self):
        self.playing = False
        self._thread = None
        self._stop_flag = threading.Event()
        self.mouse = MouseController()
        self._uinput = None

    def _get_uinput(self):
        if self._uinput is None:
            # Create a virtual keyboard with all standard keys
            self._uinput = UInput(
                {ecodes.EV_KEY: list(range(1, 256))},
                name="OHK Macro Keyboard",
            )
        return self._uinput

    def play(self, events, speed=1.0, loops=1, on_done=None):
        """Play macro in a background thread. loops=0 means infinite."""
        self._stop_flag.clear()
        self.playing = True
        self._thread = threading.Thread(
            target=self._play_loop,
            args=(events, speed, loops, on_done),
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._stop_flag.set()
        self.playing = False

    def _play_loop(self, events, speed, loops, on_done):
        ui = self._get_uinput()
        iteration = 0
        while loops == 0 or iteration < loops:
            if self._stop_flag.is_set():
                break
            prev_time = 0
            for evt in events:
                if self._stop_flag.is_set():
                    break
                delay = (evt["time"] - prev_time) / speed
                if delay > 0:
                    end = time.monotonic() + delay
                    while time.monotonic() < end:
                        if self._stop_flag.is_set():
                            break
                        time.sleep(min(0.01, end - time.monotonic()))
                prev_time = evt["time"]

                if self._stop_flag.is_set():
                    break

                if evt["type"] == "key":
                    code = evt["code"]
                    value = 1 if evt["action"] == "press" else 0
                    ui.write(ecodes.EV_KEY, code, value)
                    ui.syn()
                elif evt["type"] == "mouse_click":
                    self.mouse.position = (evt["x"], evt["y"])
                    btn = {
                        "left": Button.left,
                        "right": Button.right,
                        "middle": Button.middle,
                    }.get(evt["button"], Button.left)
                    if evt["action"] == "press":
                        self.mouse.press(btn)
                    else:
                        self.mouse.release(btn)

            iteration += 1

        self.playing = False
        if on_done:
            on_done()
