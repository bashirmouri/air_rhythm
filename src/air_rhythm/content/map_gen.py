"""Builds the first song's beatmaps (one per level) from the song structure in
audio_gen.py, and generates all audio assets on first launch."""
import json
import logging
import math
import os
import random
import shutil
from itertools import pairwise

from air_rhythm.content.audio_gen import (
    BAR,
    BEAT,
    BPM,
    DROP_MELODY,
    N_BARS,
    make_calibration,
    make_first_steps,
    make_menu_music,
    section_of,
    wav_is_valid,
    write_wav,
)
from air_rhythm.core.beatmap import load_beatmap
from air_rhythm.system import config

log = logging.getLogger(__name__)


class StartupError(Exception):
    """A problem the player can fix (disk full, folder not writable). The message is shown as is."""

FIRST_MAP_DIR = os.path.join(config.MAPS_DIR, "first_steps")
CALIBRATION_AUDIO = os.path.join(config.ASSETS_DIR, "calibration.wav")
MENU_MUSIC = os.path.join(config.ASSETS_DIR, "menu_music.wav")

DIFFICULTY = {"ar": 5, "cs": 2.5, "od": 2, "hp": 3}   # gentle: webcams add delay

# Every level plays the same song. Easy has half the circles (none faster than one
# per second), bigger circles, more time to read them, looser timing and shorter jumps.
LEVELS = {
    "Easy": {"file": "easy.json", "max_jump": 120,
             "difficulty": {"ar": 3, "cs": 1.5, "od": 0, "hp": 2}},
    "Normal": {"file": "beatmap.json", "max_jump": 190, "difficulty": DIFFICULTY},
}
LEVEL_PATHS = {name: os.path.join(FIRST_MAP_DIR, lv["file"]) for name, lv in LEVELS.items()}


def note_onsets(level="Normal"):
    """Where the circles go in time, following the music.
    Normal: intro/break = every 2 beats, verse = every beat, build = every beat
    plus a snare double, drop = on the melody notes.
    Easy: one circle per bar in the quiet parts, every 2 beats everywhere else."""
    out = []
    for bar in range(N_BARS):
        sec = section_of(bar)
        if level == "Easy":
            beats = [0] if sec in ("intro", "break", "outro") else [0, 2]
        elif sec in ("intro", "break"):
            beats = [0, 2]
        elif sec == "verse":
            beats = [0, 1, 2, 3]
        elif sec == "build":
            beats = [0, 1, 2, 3] + ([3.5] if bar % 2 == 1 else [])
        elif sec == "drop":
            beats = [b for b, _, _ in DROP_MELODY[bar % 4]]
        else:  # outro
            beats = [0, 2] if bar < 34 else [0]
        out += [(bar * BAR + b * BEAT, bar) for b in beats]
    return out


def place(times, radius, max_jump=190, seed=7):
    """Positions for each circle. Spacing grows with the time gap (fast notes =
    close together), the direction turns smoothly, and circles stay on the
    playfield without covering the last few."""
    rng = random.Random(seed)
    lo_x, hi_x = radius + 8, config.PLAYFIELD_W - radius - 8
    lo_y, hi_y = radius + 8, config.PLAYFIELD_H - radius - 8
    x, y = config.PLAYFIELD_W / 2, config.PLAYFIELD_H / 2
    angle = rng.uniform(0, 2 * math.pi)
    positions = [(x, y)]

    for prev_t, t in pairwise(times):
        gap_ms = (t - prev_t) * 1000
        dist = min(max(gap_ms * 0.24, 2 * radius * 1.1), max_jump)
        for attempt in range(60):
            if attempt < 30:
                turn = rng.choice((-1, 1)) * rng.uniform(math.radians(25), math.radians(100))
            else:
                turn = rng.uniform(-math.pi, math.pi)
            a = angle + turn
            nx, ny = x + dist * math.cos(a), y + dist * math.sin(a)
            if not (lo_x <= nx <= hi_x and lo_y <= ny <= hi_y):
                continue
            if any(math.hypot(nx - px, ny - py) < 2 * radius * 1.05
                   for px, py in positions[-4:-1]):
                continue
            break
        else:
            # stuck near an edge: head back toward the middle of the playfield
            a = math.atan2(config.PLAYFIELD_H / 2 - y, config.PLAYFIELD_W / 2 - x)
            a += rng.uniform(-0.4, 0.4)
            nx = min(max(x + dist * math.cos(a), lo_x), hi_x)
            ny = min(max(y + dist * math.sin(a), lo_y), hi_y)
        angle, x, y = a, nx, ny
        positions.append((x, y))
    return positions


def make_beatmap(level="Normal"):
    lv = LEVELS[level]
    radius = 54.4 - 4.48 * lv["difficulty"]["cs"]
    onsets = note_onsets(level)
    positions = place([t for t, _ in onsets], radius, lv["max_jump"])

    objects, last_bar, last_sec = [], None, None
    for (t, bar), (x, y) in zip(onsets, positions, strict=True):
        sec = section_of(bar)
        new_combo = not objects or (bar != last_bar and (bar % 2 == 0 or sec != last_sec))
        objects.append({"time": round(t * 1000), "x": round(x, 1), "y": round(y, 1),
                        "new_combo": new_combo})
        last_bar, last_sec = bar, sec

    return {
        "title": "First Steps", "artist": "Air Rhythm", "version": level,
        "audio": "audio.wav", "bpm": BPM, "lead_in_ms": config.LEAD_IN_MS,
        "difficulty": lv["difficulty"], "objects": objects,
    }


def _beatmap_is_valid(path):
    try:
        return len(load_beatmap(path).objects) > 0
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def _copy_pregenerated(path, is_valid):
    """Packaged builds ship ready-made copies of the generated files. Copy one into the
    data folder (atomically) if it exists and is valid. Returns True if it did."""
    if not config.PREGENERATED_DIR:
        return False
    src = os.path.join(config.PREGENERATED_DIR, os.path.relpath(path, config.DATA_DIR))
    if not (os.path.exists(src) and is_valid(src)):
        return False
    shutil.copyfile(src, path + ".tmp")
    os.replace(path + ".tmp", path)
    return True


def ensure_assets():
    """Make sure the song, its beatmaps, the calibration track and the menu music exist and
    aren't damaged (truncated audio, broken JSON). Missing ones are copied from the
    packaged build if it has them, otherwise generated. Raises StartupError if the files
    can't be written."""
    audio = os.path.join(FIRST_MAP_DIR, "audio.wav")
    wavs = [(audio, make_first_steps, "the first song"),
            (CALIBRATION_AUDIO, make_calibration, "the calibration track"),
            (MENU_MUSIC, make_menu_music, "the menu music")]
    try:
        os.makedirs(FIRST_MAP_DIR, exist_ok=True)
        os.makedirs(config.ASSETS_DIR, exist_ok=True)
        for path, make, what in wavs:
            if not wav_is_valid(path):
                if os.path.exists(path):
                    log.warning("%s is damaged, replacing it", path)
                if not _copy_pregenerated(path, wav_is_valid):
                    log.info("Generating %s (one-time, a few seconds)...", what)
                    write_wav(path, make())
        for level, path in LEVEL_PATHS.items():
            if not _beatmap_is_valid(path):
                if os.path.exists(path):
                    log.warning("%s is damaged, replacing it", path)
                if not _copy_pregenerated(path, _beatmap_is_valid):
                    _write_json(path, make_beatmap(level))
    except OSError as e:
        raise StartupError(
            f"Air Rhythm couldn't create its game files in\n{config.DATA_DIR}\n\n{e}\n\n"
            "Free up some disk space, or check that this folder can be written to.") from e


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ensure_assets()
    log.info("Assets ready in %s", config.DATA_DIR)
