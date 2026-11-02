"""Generated beatmaps and audio (map_gen.py, audio_gen.py)."""
import json
import math
import os

import pytest

import config
import map_gen
from audio_gen import wav_is_valid
from beatmap import load_beatmap


def circles(level):
    return map_gen.make_beatmap(level)["objects"]


@pytest.mark.parametrize("level", ["Easy", "Normal"])
def test_maps_are_deterministic(level):
    assert map_gen.make_beatmap(level) == map_gen.make_beatmap(level)


def test_circle_counts():
    assert len(circles("Easy")) == 60
    assert len(circles("Normal")) == 128


@pytest.mark.parametrize("level", ["Easy", "Normal"])
def test_circles_stay_on_the_playfield(level):
    r = 54.4 - 4.48 * map_gen.LEVELS[level]["difficulty"]["cs"]
    for o in circles(level):
        assert r <= o["x"] <= config.PLAYFIELD_W - r
        assert r <= o["y"] <= config.PLAYFIELD_H - r


@pytest.mark.parametrize("level, min_gap_ms", [("Easy", 1000), ("Normal", 250)])
def test_fastest_rhythm(level, min_gap_ms):
    times = [o["time"] for o in circles(level)]
    assert min(b - a for a, b in zip(times, times[1:])) >= min_gap_ms


@pytest.mark.parametrize("level", ["Easy", "Normal"])
def test_jumps_respect_the_level_limit(level):
    limit = map_gen.LEVELS[level]["max_jump"]
    objs = circles(level)
    for a, b in zip(objs, objs[1:]):
        # positions are rounded to 0.1 px when saved
        assert math.hypot(b["x"] - a["x"], b["y"] - a["y"]) <= limit + 0.2


def test_easy_is_easier_than_normal():
    easy, normal = (map_gen.LEVELS[lv]["difficulty"] for lv in ("Easy", "Normal"))
    assert easy["ar"] < normal["ar"]        # more time to read
    assert easy["cs"] < normal["cs"]        # bigger circles
    assert easy["od"] < normal["od"]        # looser timing


# ---------------------------------------------------------------- generated files
def test_all_assets_are_generated_and_valid(assets):
    for path in (os.path.join(map_gen.FIRST_MAP_DIR, "audio.wav"), map_gen.CALIBRATION_AUDIO,
                 map_gen.MENU_MUSIC):
        assert wav_is_valid(path), path
    for path in map_gen.LEVEL_PATHS.values():
        assert load_beatmap(path).objects


def test_truncated_audio_is_regenerated(assets):
    wav = os.path.join(map_gen.FIRST_MAP_DIR, "audio.wav")
    size = os.path.getsize(wav)
    with open(wav, "r+b") as f:
        f.truncate(size // 3)                      # like a crash halfway through writing
    assert not wav_is_valid(wav)
    map_gen.ensure_assets()
    assert wav_is_valid(wav) and os.path.getsize(wav) == size


def test_broken_beatmap_is_regenerated(assets):
    path = map_gen.LEVEL_PATHS["Easy"]
    with open(path, "w") as f:
        f.write('{"title": "broken"')
    map_gen.ensure_assets()
    assert json.load(open(path)) == map_gen.make_beatmap("Easy")


def test_no_temporary_files_are_left(assets):
    map_gen.ensure_assets()
    leftovers = [f for _, _, fs in os.walk(config.DATA_DIR) for f in fs if f.endswith(".tmp")]
    assert leftovers == []


def test_wav_validation_rejects_garbage(tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not a wav file")
    assert not wav_is_valid(str(bad))
    assert not wav_is_valid(str(tmp_path / "missing.wav"))


def test_unwritable_data_folder_gives_a_clear_error(monkeypatch, tmp_path):
    blocker = tmp_path / "a_file"
    blocker.write_text("a file where a folder should be")
    monkeypatch.setattr(map_gen, "FIRST_MAP_DIR", str(blocker / "maps" / "first_steps"))
    with pytest.raises(map_gen.StartupError, match="couldn't create its game files"):
        map_gen.ensure_assets()
