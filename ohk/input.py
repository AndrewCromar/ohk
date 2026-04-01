"""Global input handling via evdev (works on X11 and Wayland)."""

import selectors
import threading

import evdev
from evdev import ecodes


def find_keyboards():
    """Find input devices that have letter keys (i.e. actual keyboards)."""
    keyboards = []
    for path in evdev.list_devices():
        dev = evdev.InputDevice(path)
        caps = dev.capabilities().get(ecodes.EV_KEY, [])
        if ecodes.KEY_A in caps:
            keyboards.append(dev)
    return keyboards


class InputListener:
    """Reads raw key events from all keyboards via evdev.

    Tracks currently held keys and passes them to callbacks.
    Callbacks receive: fn(code, value, held_keys)
    """

    def __init__(self):
        self._callbacks = []
        self._thread = None
        self._held = set()
        self._held_lock = threading.Lock()

    def add_callback(self, fn):
        """Register a callback: fn(code, value, held_keys).

        - code: evdev keycode
        - value: 0=release, 1=press, 2=repeat
        - held_keys: frozenset of currently held keycodes
        """
        self._callbacks.append(fn)

    def get_held_keys(self):
        with self._held_lock:
            return frozenset(self._held)

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        keyboards = find_keyboards()
        if not keyboards:
            print("WARNING: No keyboard devices found. Check /dev/input/ permissions.")
            print("Make sure your user is in the 'input' group: sudo usermod -aG input $USER")
            return

        print(f"Listening on: {', '.join(d.name for d in keyboards)}")

        sel = selectors.DefaultSelector()
        for dev in keyboards:
            sel.register(dev, selectors.EVENT_READ)

        while True:
            for key, _mask in sel.select():
                dev = key.fileobj
                for event in dev.read():
                    if event.type != ecodes.EV_KEY:
                        continue

                    # Track held keys
                    with self._held_lock:
                        if event.value == 1:  # press
                            self._held.add(event.code)
                        elif event.value == 0:  # release
                            self._held.discard(event.code)
                        held = frozenset(self._held)

                    for fn in self._callbacks:
                        fn(event.code, event.value, held)
