"""Builds the first song's beatmap from the song structure in audio_gen.py,
and generates all audio assets on first launch."""
import json
import math
import os
import random

import config
from audio_gen import (BAR, BEAT, BPM, DROP_MELODY, N_BARS, make_calibration,
                       make_first_steps, section_of, write_wav)

FIRST_MAP_DIR = os.path.join(config.MAPS_DIR, "first_steps")
FIRST_MAP_PATH = os.path.join(FIRST_MAP_DIR, "beatmap.json")
CALIBRATION_AUDIO = os.path.join(config.ASSETS_DIR, "calibration.wav")

DIFFICULTY = {"ar": 5, "cs": 2.5, "od": 2, "hp": 3}   # gentle: webcams add delay


def note_onsets():
    """Where the circles go in time, following the music:
    intro/break = every 2 beats, verse = every beat, build = every beat plus a
    snare double, drop = on the melody notes."""
    out = []
    for bar in range(N_BARS):
        sec = section_of(bar)
        if sec in ("intro", "break"):
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


def place(times, radius, seed=7):
    """Positions for each circle. Spacing grows with the time gap (fast notes =
    close together), the direction turns smoothly, and circles stay on the
    playfield without covering the last few."""
    rng = random.Random(seed)
    lo_x, hi_x = radius + 8, config.PLAYFIELD_W - radius - 8
    lo_y, hi_y = radius + 8, config.PLAYFIELD_H - radius - 8
    x, y = config.PLAYFIELD_W / 2, config.PLAYFIELD_H / 2
    angle = rng.uniform(0, 2 * math.pi)
    positions = [(x, y)]

    for prev_t, t in zip(times, times[1:]):
        gap_ms = (t - prev_t) * 1000
        dist = min(max(gap_ms * 0.24, 2 * radius * 1.1), 190)
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


def make_beatmap():
    radius = 54.4 - 4.48 * DIFFICULTY["cs"]
    onsets = note_onsets()
    positions = place([t for t, _ in onsets], radius)

    objects, last_bar, last_sec = [], None, None
    for (t, bar), (x, y) in zip(onsets, positions):
        sec = section_of(bar)
        new_combo = not objects or (bar != last_bar and (bar % 2 == 0 or sec != last_sec))
        objects.append({"time": round(t * 1000), "x": round(x, 1), "y": round(y, 1),
                        "new_combo": new_combo})
        last_bar, last_sec = bar, sec

    return {
        "title": "First Steps", "artist": "Air Rhythm", "version": "Normal",
        "audio": "audio.wav", "bpm": BPM, "lead_in_ms": config.LEAD_IN_MS,
        "difficulty": DIFFICULTY, "objects": objects,
    }


def ensure_assets():
    """Generate the song, its beatmap and the calibration track if missing."""
    os.makedirs(FIRST_MAP_DIR, exist_ok=True)
    os.makedirs(config.ASSETS_DIR, exist_ok=True)
    audio = os.path.join(FIRST_MAP_DIR, "audio.wav")
    if not os.path.exists(audio):
        print("Generating the first song (one-time, a few seconds)...")
        write_wav(audio, make_first_steps())
    if not os.path.exists(FIRST_MAP_PATH):
        with open(FIRST_MAP_PATH, "w") as f:
            json.dump(make_beatmap(), f, indent=1)
    if not os.path.exists(CALIBRATION_AUDIO):
        write_wav(CALIBRATION_AUDIO, make_calibration())


if __name__ == "__main__":
    ensure_assets()
    print("Assets ready.")
