"""Global constants for Air Rhythm. Tweak these to tune how the game feels."""
import os
import sys

# The air_rhythm package folder (src/air_rhythm, or inside the packaged build): its
# resources/ ship with the game.
PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCES_DIR = os.path.join(PACKAGE_DIR, "resources")
# Packaged build (PyInstaller): read-only bundled files live in sys._MEIPASS, and the
# folder the player sees (with AirRhythm.exe) is next to sys.executable.
FROZEN = getattr(sys, "frozen", False)
BUNDLE_DIR = getattr(sys, "_MEIPASS", PACKAGE_DIR)


def _source_root():
    """The project folder (with pyproject.toml) when running from a source checkout."""
    root = os.path.dirname(os.path.dirname(PACKAGE_DIR))
    return root if os.path.exists(os.path.join(root, "pyproject.toml")) else PACKAGE_DIR


# "The game folder": next to AirRhythm.exe, or the project folder when running from source.
APP_DIR = os.path.dirname(sys.executable) if FROZEN else _source_root()


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
PORTABLE = "--portable" in sys.argv or os.path.exists(os.path.join(APP_DIR, "portable.txt"))
DATA_DIR = os.environ.get("AIR_RHYTHM_DATA_DIR") or (APP_DIR if PORTABLE else user_data_dir())
# Files shipped with a packaged build only: pre-generated songs/beatmaps (copied to the
# data folder on first start instead of generating them) and the hand model (used in place).
# Running from source, these are None: everything is generated/downloaded into DATA_DIR.
PREGENERATED_DIR = os.path.join(BUNDLE_DIR, "pregenerated") if FROZEN else None
BUNDLED_MODEL = os.path.join(BUNDLE_DIR, "models", "hand_landmarker.task") if FROZEN else None
ICON_PATH = os.path.join(RESOURCES_DIR, "icon.png")
# MediaPipe imports matplotlib, which builds a font list on first use (~5 s). Keep its cache
# in our data folder so that happens once. In packaged builds PyInstaller points it at a
# temporary folder that is deleted on exit (rebuilt every start), so override that one.
_MPL_CACHE = os.path.join(DATA_DIR, "cache", "matplotlib")
if FROZEN:
    os.environ["MPLCONFIGDIR"] = _MPL_CACHE
else:
    os.environ.setdefault("MPLCONFIGDIR", _MPL_CACHE)
MAPS_DIR = os.path.join(DATA_DIR, "maps")
ASSETS_DIR = os.path.join(DATA_DIR, "assets")
MODELS_DIR = os.path.join(DATA_DIR, "models")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
LOG_PATH = os.path.join(DATA_DIR, "air_rhythm.log")
# Where versions before the data folder kept their files (migrated on first start).
# Packaged builds never stored anything there, so there is nothing to migrate.
LEGACY_DIR = None if FROZEN else APP_DIR

# ---------------------------------------------------------------- window
TITLE = "Air Rhythm"
WINDOW_W, WINDOW_H = 1280, 720
TARGET_FPS = 120

# ---------------------------------------------------------------- audio
SAMPLE_RATE = 44100
AUDIO_BUFFER = 512          # smaller buffer = less audio delay
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


# ---------------------------------------------------------------- player choices (Settings screen)
# The values above are the "Medium" defaults; the Settings screen picks one of these by name.
def _zone_scaled(f):
    """ACTIVE_ZONE made f times as big around the same center."""
    left, top, right, bottom = ACTIVE_ZONE
    cx, cy, hw, hh = (left + right) / 2, (top + bottom) / 2, (right - left) / 2 * f, (bottom - top) / 2 * f
    return (cx - hw, cy - hh, cx + hw, cy + hh)


# Hand area: smaller = less arm movement, but small hand shakes move the cursor more.
HAND_AREAS = {"Small": _zone_scaled(0.75), "Medium": ACTIVE_ZONE, "Large": _zone_scaled(1.25)}
# Pinch sensitivity (close, open thresholds): High = a looser pinch already counts.
PINCH_SENSITIVITY = {"Low": (0.22, 0.34), "Medium": (PINCH_CLOSE, PINCH_OPEN), "High": (0.34, 0.46)}
CURSOR_SMOOTHINGS = {"Off": 0, "Low": 30, "Medium": CURSOR_SMOOTHING_MS, "High": 100}
CAMERA_COUNT = 4            # cameras 1-4 to choose from (OpenCV indexes 0-3)
VOLUME_STEP = 10            # % per press on the Settings screen
OFFSET_STEP_MS = 5

# ---------------------------------------------------------------- gameplay
LEAD_IN_MS = 2000
HIT_ANIM_MS = 240
MISS_ANIM_MS = 160
JUDGE_POPUP_MS = 600
RESUME_COUNTDOWN_MS = 1800   # 3, 2, 1 after resuming from pause, before the song carries on
