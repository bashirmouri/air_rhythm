"""Player settings saved between sessions (settings.json)."""
import json

from config import SETTINGS_PATH

DEFAULTS = {
    "input_offset_ms": 0.0,   # measured by the calibration screen
    "input_mode": "hand",     # "hand" or "mouse"
    "level": "Easy",          # "Easy" or "Normal" (see map_gen.LEVELS)
    "no_fail": False,
    "show_camera": True,
}


def load():
    settings = dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH) as f:
            settings.update(json.load(f))
    except (OSError, ValueError):
        pass
    return settings


def save(settings):
    try:
        with open(SETTINGS_PATH, "w") as f:
            json.dump(settings, f, indent=2)
    except OSError as e:
        print("Could not save settings:", e)
