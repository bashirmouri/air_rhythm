"""Beatmap format and difficulty formulas.

A beatmap is a JSON file next to its audio file:
{
  "title": ..., "artist": ..., "version": "Normal", "audio": "audio.wav",
  "bpm": 120, "lead_in_ms": 2000,
  "difficulty": {"ar": 5, "cs": 2.5, "od": 2, "hp": 3},
  "objects": [{"time": 2000, "x": 256, "y": 192, "new_combo": true}, ...]
}
Positions use osu!'s 512 x 384 playfield and the difficulty values mean the
same thing as in osu!, so an .osu importer can produce this format directly.
"""
import json
import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class HitCircle:
    time: float          # ms from the start of the audio
    x: float             # osu! playfield coordinates
    y: float
    new_combo: bool
    number: int          # number drawn on the circle (1, 2, 3... within a combo)
    color: int           # combo color index


@dataclass
class Beatmap:
    title: str
    artist: str
    version: str
    audio_path: str
    bpm: float
    lead_in_ms: float
    ar: float            # approach rate: how early circles appear
    cs: float            # circle size: higher = smaller circles
    od: float            # overall difficulty: higher = stricter timing
    hp: float            # health drain: higher = harsher
    objects: list = field(default_factory=list)

    @property
    def preempt(self):
        """ms between a circle appearing and the moment it must be hit (osu! formula)."""
        if self.ar < 5:
            return 1200 + 600 * (5 - self.ar) / 5
        return 1200 - 750 * (self.ar - 5) / 5

    @property
    def fade_in(self):
        return self.preempt * 2 / 3

    @property
    def radius(self):
        """Circle radius in osu! pixels (osu! formula)."""
        return 54.4 - 4.48 * self.cs

    @property
    def hit_windows(self):
        """(300, 100, 50) windows in ms: hit within +-window to get that score (osu! formula)."""
        return 80 - 6 * self.od, 140 - 8 * self.od, 200 - 10 * self.od


def load_beatmap(path):
    with open(path) as f:
        data = json.load(f)
    diff = data["difficulty"]

    objects, color, number = [], -1, 0
    for o in sorted(data["objects"], key=lambda o: o["time"]):
        if o.get("new_combo") or color < 0:
            color += 1
            number = 0
        number += 1
        objects.append(HitCircle(float(o["time"]), float(o["x"]), float(o["y"]),
                                 bool(o.get("new_combo")), number, color))

    return Beatmap(
        title=data.get("title", "Untitled"),
        artist=data.get("artist", "Unknown"),
        version=data.get("version", "Normal"),
        audio_path=os.path.join(os.path.dirname(os.path.abspath(path)), data["audio"]),
        bpm=float(data.get("bpm", 120)),
        lead_in_ms=float(data.get("lead_in_ms", 2000)),
        ar=float(diff.get("ar", 5)), cs=float(diff.get("cs", 4)),
        od=float(diff.get("od", 5)), hp=float(diff.get("hp", 5)),
        objects=objects,
    )
