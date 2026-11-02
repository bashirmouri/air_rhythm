"""Global constants for Air Rhythm. Tweak these to tune how the game feels."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def user_data_dir():
    """Per-user folder for settings, generated audio/maps, the hand model and logs.
    Installed games usually can't write next to their own files, so nothing goes there.
    Windows uses Local AppData (not Roaming): ~30 MB of regenerable audio shouldn't sync."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
        return os.path.join(base, "AirRhythm")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/AirRhythm")
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "air-rhythm")


# Portable mode keeps everything next to the game (USB stick, or running from source):
# start with --portable, or put a file named portable.txt in the game folder.
# AIR_RHYTHM_DATA_DIR overrides the location (used by tests).
PORTABLE = "--portable" in sys.argv or os.path.exists(os.path.join(ROOT, "portable.txt"))
DATA_DIR = os.environ.get("AIR_RHYTHM_DATA_DIR") or (ROOT if PORTABLE else user_data_dir())
MAPS_DIR = os.path.join(DATA_DIR, "maps")
ASSETS_DIR = os.path.join(DATA_DIR, "assets")
MODELS_DIR = os.path.join(DATA_DIR, "models")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
LOG_PATH = os.path.join(DATA_DIR, "air_rhythm.log")
# Where versions before the data folder kept their files (migrated on first start)
LEGACY_DIR = ROOT

# ---------------------------------------------------------------- window
TITLE = "Air Rhythm"
WINDOW_W, WINDOW_H = 1280, 720
TARGET_FPS = 120

# ---------------------------------------------------------------- audio
SAMPLE_RATE = 44100
AUDIO_BUFFER = 512          # smaller buffer = less audio delay
MENU_MUSIC_VOLUME = 0.5     # 0..1
MENU_MUSIC_FADE_IN_MS = 2500
MENU_MUSIC_FADE_OUT_MS = 900

# ---------------------------------------------------------------- playfield
# We use osu!'s playfield coordinates (512 x 384) so real osu! maps can be
# loaded later without converting positions.
PLAYFIELD_W, PLAYFIELD_H = 512, 384
CURSOR_MARGIN = 48          # how far (osu px) the cursor can go outside the playfield

# ---------------------------------------------------------------- hand tracking
CAMERA_INDEX = 0
CAMERA_W, CAMERA_H, CAMERA_FPS = 640, 480, 60   # 60 fps is requested; many webcams give 30
# Part of the camera image that maps to the whole playfield (left, top, right, bottom),
# normalized 0..1. Smaller zone = less arm movement, but more sensitive.
ACTIVE_ZONE = (0.20, 0.15, 0.80, 0.80)
# Pinch = thumb tip close to index tip, measured relative to hand size.
# Two thresholds (hysteresis) stop the pinch flickering on/off at the boundary.
PINCH_CLOSE = 0.28
PINCH_OPEN = 0.40
HAND_LOST_GRACE_S = 0.12    # hand can vanish this long before we count it as released
# One Euro filter: low min_cutoff = smoother when still; high beta = less lag when fast.
FILTER_MIN_CUTOFF = 1.5
FILTER_BETA = 8.0
FILTER_D_CUTOFF = 1.0
# The drawn cursor replays camera positions this many ms late, gliding between them, so it
# moves evenly even though webcams deliver frames unevenly. Higher = smoother but trails
# your hand more; 0 = raw (choppy). Hits always use the exact, undelayed position.
CURSOR_SMOOTHING_MS = 60

# ---------------------------------------------------------------- gameplay
LEAD_IN_MS = 2000
HIT_ANIM_MS = 240
MISS_ANIM_MS = 160
JUDGE_POPUP_MS = 600
