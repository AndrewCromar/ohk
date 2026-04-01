"""Addon discovery, loading, and settings management."""

import importlib.util
import inspect
import json
import os
import sys

from .addon import OHKAddon
from . import config

ADDON_SETTINGS_FILE = os.path.join(config.CONFIG_DIR, "addon_settings.json")


class AddonInfo:
    """Metadata about a discovered addon."""

    def __init__(self, folder_name, addon_class):
        self.folder_name = folder_name
        self.addon_class = addon_class
        self.instance = None
        self.enabled = False

    @property
    def name(self):
        return self.addon_class.name

    @property
    def description(self):
        return self.addon_class.description

    @property
    def version(self):
        return self.addon_class.version


class AddonManager:
    """Manages addon discovery, loading, and settings persistence."""

    def __init__(self, app):
        self.app = app
        self.addons = {}  # folder_name -> AddonInfo
        self._settings = self._load_settings()

    def discover(self):
        """Scan the addons directory for available addons."""
        addons_dir = os.path.join(config.CONFIG_DIR, "addons")
        if not os.path.isdir(addons_dir):
            os.makedirs(addons_dir, exist_ok=True)
            return

        for folder_name in sorted(os.listdir(addons_dir)):
            folder_path = os.path.join(addons_dir, folder_name)
            main_path = os.path.join(folder_path, "main.py")

            if not os.path.isfile(main_path):
                continue

            addon_class = self._load_addon_class(folder_name, main_path)
            if addon_class is None:
                continue

            info = AddonInfo(folder_name, addon_class)
            info.enabled = folder_name in self._settings.get("enabled", [])
            self.addons[folder_name] = info

    def load_enabled(self):
        """Instantiate and initialize all enabled addons."""
        for folder_name, info in self.addons.items():
            if info.enabled:
                self._instantiate(info)

    def enable(self, folder_name):
        """Enable an addon and instantiate it live."""
        if folder_name not in self.addons:
            return
        info = self.addons[folder_name]
        info.enabled = True
        if info.instance is None:
            self._instantiate(info)
        self._save_enabled()

    def disable(self, folder_name):
        """Disable an addon and clean up its instance."""
        if folder_name not in self.addons:
            return
        info = self.addons[folder_name]
        if info.instance:
            try:
                settings = info.instance.get_settings()
                if settings:
                    if "settings" not in self._settings:
                        self._settings["settings"] = {}
                    self._settings["settings"][folder_name] = settings
            except Exception:
                pass
            info.instance.on_disable()
            info.instance = None
        info.enabled = False
        self._save_enabled()

    def rescan(self):
        """Re-scan addons directory for new/removed addons."""
        addons_dir = os.path.join(config.CONFIG_DIR, "addons")
        if not os.path.isdir(addons_dir):
            return

        current_folders = set()
        for folder_name in sorted(os.listdir(addons_dir)):
            folder_path = os.path.join(addons_dir, folder_name)
            main_path = os.path.join(folder_path, "main.py")
            if not os.path.isfile(main_path):
                continue
            current_folders.add(folder_name)
            if folder_name not in self.addons:
                addon_class = self._load_addon_class(folder_name, main_path)
                if addon_class:
                    info = AddonInfo(folder_name, addon_class)
                    info.enabled = folder_name in self._settings.get("enabled", [])
                    self.addons[folder_name] = info

        # Remove addons whose folders were deleted
        removed = [k for k in self.addons if k not in current_folders]
        for k in removed:
            info = self.addons[k]
            if info.instance:
                info.instance.on_disable()
            del self.addons[k]

    def get_enabled_addons(self):
        """Return list of AddonInfo for enabled addons with live instances."""
        return [info for info in self.addons.values()
                if info.enabled and info.instance is not None]

    def on_key_event(self, code, value, held_keys=frozenset()):
        """Forward key events to all enabled addons."""
        for info in self.get_enabled_addons():
            try:
                info.instance.on_key_event(code, value, held_keys)
            except TypeError:
                # Backward compat for addons that don't accept held_keys
                try:
                    info.instance.on_key_event(code, value)
                except Exception:
                    pass
            except Exception as e:
                print(f"Addon '{info.name}' error in on_key_event: {e}")

    def save_all_settings(self):
        """Save settings for all instantiated addons."""
        settings = self._settings
        if "settings" not in settings:
            settings["settings"] = {}

        for folder_name, info in self.addons.items():
            if info.instance:
                try:
                    addon_settings = info.instance.get_settings()
                    if addon_settings:
                        settings["settings"][folder_name] = addon_settings
                except Exception as e:
                    print(f"Addon '{info.name}' error in get_settings: {e}")

        self._settings = settings
        self._write_settings(settings)

    # ── Internal ─────────────────────────────────────────────────────────

    def _load_addon_class(self, folder_name, main_path):
        """Import main.py and find the OHKAddon subclass."""
        try:
            spec = importlib.util.spec_from_file_location(
                f"ohk_addon_{folder_name}", main_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            for _name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, OHKAddon) and obj is not OHKAddon:
                    return obj

        except Exception as e:
            print(f"Error loading addon '{folder_name}': {e}")
        return None

    def _instantiate(self, info):
        """Create an instance of the addon and load its settings."""
        try:
            info.instance = info.addon_class(self.app)
            saved = self._settings.get("settings", {}).get(info.folder_name, {})
            if saved:
                info.instance.load_settings(saved)
            info.instance.on_enable()
        except Exception as e:
            print(f"Error instantiating addon '{info.folder_name}': {e}")
            info.instance = None

    def _save_enabled(self):
        """Persist the list of enabled addon folder names."""
        self._settings["enabled"] = [
            name for name, info in self.addons.items() if info.enabled
        ]
        self._write_settings(self._settings)

    def _load_settings(self):
        try:
            with open(ADDON_SETTINGS_FILE) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"enabled": [], "settings": {}}

    def _write_settings(self, data):
        os.makedirs(config.CONFIG_DIR, exist_ok=True)
        with open(ADDON_SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=2)
