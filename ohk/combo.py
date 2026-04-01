"""Multi-key combo matching and display utilities."""

from . import config


def combo_active(held_keys, combo):
    """Check if all keys in a combo are currently held.

    Args:
        held_keys: set/frozenset of currently held evdev keycodes
        combo: list of evdev keycodes (the combo to match)

    Returns:
        True if all keys in the combo are held.
    """
    if not combo:
        return False
    return all(k in held_keys for k in combo)


def combo_name(combo):
    """Human-readable display name for a combo.

    Args:
        combo: list of evdev keycodes, or single int (backward compat)

    Returns:
        String like "SUPER+C+W" or "F10"
    """
    if isinstance(combo, int):
        return config.key_name(combo)
    if not combo:
        return "(none)"
    return "+".join(config.key_name(k) for k in combo)


def normalize_combo(value):
    """Ensure a keybind value is a list (backward compat from single int).

    Args:
        value: int or list

    Returns:
        list of ints
    """
    if isinstance(value, int):
        return [value]
    if isinstance(value, list):
        return value
    return [value]
