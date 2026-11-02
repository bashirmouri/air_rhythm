"""Player settings saved between sessions (settings.json in the data folder)."""
import json
import logging
import os
import shutil

import config
from config import SETTINGS_PATH

log = logging.getLogger(__name__)

DEFAULTS = {
    "input_offset_ms": 0.0,   # measured by the calibration screen
    "input_mode": "hand",     # "hand" or "mouse"
    "level": "Easy",          # "Easy" or "Normal" (see map_gen.LEVELS)
    "no_fail": False,
    "show_camera": True,
    "menu_music": True,
}


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
        settings.update({k: v for k, v in data.items() if k in DEFAULTS})
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
