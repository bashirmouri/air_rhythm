"""Player settings saved between sessions (settings.json in the data folder)."""
import json
import logging
import os
import shutil

from air_rhythm.system import config
from air_rhythm.system.config import SETTINGS_PATH

log = logging.getLogger(__name__)

DEFAULTS = {
    "input_offset_ms": 0.0,   # camera + reaction delay, measured by the calibration screen
    "audio_offset_ms": 0.0,   # sound output delay (Bluetooth headphones: often 150-250 ms)
    "input_mode": "hand",     # "hand" or "mouse"
    "level": "Easy",          # "Easy" or "Normal" (see map_gen.LEVELS)
    "no_fail": False,
    "show_camera": True,
    "menu_music": True,
    "music_volume": 100,      # volumes in %
    "hitsound_volume": 50,
    "menu_music_volume": 50,
    "camera_index": 0,
    "hand_area": "Medium",            # keys of config.HAND_AREAS
    "pinch_sensitivity": "Medium",    # keys of config.PINCH_SENSITIVITY
    "cursor_smoothing": "Medium",     # keys of config.CURSOR_SMOOTHINGS
    "fullscreen": False,
    "show_fps": False,
}
# Allowed values; anything else in settings.json (edited by hand, or from a newer version) is
# replaced by the default, so a bad value can never break the game.
CHOICES = {
    "input_mode": ("hand", "mouse"),
    "hand_area": tuple(config.HAND_AREAS),
    "pinch_sensitivity": tuple(config.PINCH_SENSITIVITY),
    "cursor_smoothing": tuple(config.CURSOR_SMOOTHINGS),
}
RANGES = {
    "input_offset_ms": (-500, 500),
    "audio_offset_ms": (-200, 500),
    "music_volume": (0, 100),
    "hitsound_volume": (0, 100),
    "menu_music_volume": (0, 100),
    "camera_index": (0, config.CAMERA_COUNT - 1),
}


def is_valid(key, value):
    default = DEFAULTS[key]
    if isinstance(default, bool) or isinstance(value, bool):    # bool is an int in Python: check first
        return type(value) is type(default)
    if isinstance(default, (int, float)):
        low, high = RANGES[key]
        if not isinstance(value, (int, float)) or not low <= value <= high:
            return False
        return isinstance(value, int) or isinstance(default, float)   # no 50.5 % volume
    if key in CHOICES:
        return value in CHOICES[key]
    return isinstance(value, type(default))


def migrate_legacy_files():
    """Older versions saved next to the game. Copy what can't be recreated (settings with
    the calibration offset, and the downloaded hand model) into the data folder once.
    The old files are left where they are."""
    if config.LEGACY_DIR is None or os.path.normcase(config.LEGACY_DIR) == os.path.normcase(config.DATA_DIR):
        return
    for name in ("settings.json", os.path.join("models", "hand_landmarker.task")):
        old, new = os.path.join(config.LEGACY_DIR, name), os.path.join(config.DATA_DIR, name)
        if os.path.exists(old) and not os.path.exists(new):
            try:
                os.makedirs(os.path.dirname(new), exist_ok=True)
                shutil.copy2(old, new)
                log.info("Migrated %s to %s", old, new)
            except OSError as e:
                log.warning("Could not migrate %s: %s", old, e)


def load():
    settings = dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("settings.json does not contain an object")
        for key, value in data.items():
            if key not in DEFAULTS:
                continue
            if is_valid(key, value):
                settings[key] = value
            else:
                log.warning("Ignoring invalid setting %s=%r, using %r", key, value, DEFAULTS[key])
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as e:
        log.warning("Could not read %s, using defaults: %s", SETTINGS_PATH, e)
    return settings


def save(settings):
    """Write to a temporary file, then swap it in, so a crash mid-write can't corrupt it."""
    tmp = SETTINGS_PATH + ".tmp"
    try:
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        os.replace(tmp, SETTINGS_PATH)
    except OSError as e:
        log.warning("Could not save settings: %s", e)
