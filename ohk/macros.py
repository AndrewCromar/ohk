"""Macro recording and playback for OHK."""

import threading
import time

from evdev import ecodes
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KBController

from . import config

# Map evdev key codes to pynput keys
_SPECIAL_KEYS = {
    ecodes.KEY_LEFTSHIFT: Key.shift,
    ecodes.KEY_RIGHTSHIFT: Key.shift_r,
    ecodes.KEY_LEFTCTRL: Key.ctrl,
    ecodes.KEY_RIGHTCTRL: Key.ctrl_r,
    ecodes.KEY_LEFTALT: Key.alt,
    ecodes.KEY_RIGHTALT: Key.alt_gr,
    ecodes.KEY_LEFTMETA: Key.cmd,
    ecodes.KEY_RIGHTMETA: Key.cmd_r,
    ecodes.KEY_TAB: Key.tab,
    ecodes.KEY_ENTER: Key.enter,
    ecodes.KEY_BACKSPACE: Key.backspace,
    ecodes.KEY_DELETE: Key.delete,
    ecodes.KEY_ESC: Key.esc,
    ecodes.KEY_SPACE: Key.space,
    ecodes.KEY_UP: Key.up,
    ecodes.KEY_DOWN: Key.down,
    ecodes.KEY_LEFT: Key.left,
    ecodes.KEY_RIGHT: Key.right,
    ecodes.KEY_HOME: Key.home,
    ecodes.KEY_END: Key.end,
    ecodes.KEY_PAGEUP: Key.page_up,
    ecodes.KEY_PAGEDOWN: Key.page_down,
    ecodes.KEY_INSERT: Key.insert,
    ecodes.KEY_CAPSLOCK: Key.caps_lock,
    ecodes.KEY_F1: Key.f1, ecodes.KEY_F2: Key.f2, ecodes.KEY_F3: Key.f3,
    ecodes.KEY_F4: Key.f4, ecodes.KEY_F5: Key.f5, ecodes.KEY_F6: Key.f6,
    ecodes.KEY_F7: Key.f7, ecodes.KEY_F8: Key.f8, ecodes.KEY_F9: Key.f9,
    ecodes.KEY_F10: Key.f10, ecodes.KEY_F11: Key.f11, ecodes.KEY_F12: Key.f12,
}

# Evdev code to character for simple keys
_CHAR_MAP = {}
for _code, _name in ecodes.KEY.items():
    if isinstance(_name, list):
        _name = _name[0]
    if isinstance(_name, str) and _name.startswith("KEY_") and len(_name) == 5:
        _CHAR_MAP[_code] = _name[4:].lower()


def _evdev_to_pynput(code):
    """Convert an evdev key code to a pynput key or KeyCode."""
    from pynput.keyboard import KeyCode as KC
    if code in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[code]
    if code in _CHAR_MAP:
        return KC.from_char(_CHAR_MAP[code])
    return None


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
    """Plays back a recorded macro."""

    def __init__(self):
        self.playing = False
        self._thread = None
        self._stop_flag = threading.Event()
        self.mouse = MouseController()
        self.keyboard = KBController()

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
                    # Sleep in small chunks so we can respond to stop quickly
                    end = time.monotonic() + delay
                    while time.monotonic() < end:
                        if self._stop_flag.is_set():
                            break
                        time.sleep(min(0.01, end - time.monotonic()))
                prev_time = evt["time"]

                if self._stop_flag.is_set():
                    break

                if evt["type"] == "key":
                    pkey = _evdev_to_pynput(evt["code"])
                    if pkey is None:
                        continue
                    if evt["action"] == "press":
                        self.keyboard.press(pkey)
                    else:
                        self.keyboard.release(pkey)
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
