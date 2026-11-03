"""Beatmap loading and the osu! difficulty formulas (beatmap.py)."""
import json
import os

import pytest

from air_rhythm.core.beatmap import load_beatmap


@pytest.mark.parametrize("ar, preempt", [(0, 1800), (5, 1200), (10, 450), (3, 1440)])
def test_approach_rate_to_preempt(write_beatmap, ar, preempt):
    bm = load_beatmap(write_beatmap([(1000, 0, 0)], ar=ar))
    assert bm.preempt == pytest.approx(preempt)
    assert bm.fade_in == pytest.approx(preempt * 2 / 3)


@pytest.mark.parametrize("cs, radius", [(0, 54.4), (4, 36.48), (2.5, 43.2), (1.5, 47.68)])
def test_circle_size_to_radius(write_beatmap, cs, radius):
    assert load_beatmap(write_beatmap([(1000, 0, 0)], cs=cs)).radius == pytest.approx(radius)


@pytest.mark.parametrize("od, windows", [(0, (80, 140, 200)), (5, (50, 100, 150)), (10, (20, 60, 100))])
def test_overall_difficulty_to_hit_windows(write_beatmap, od, windows):
    assert load_beatmap(write_beatmap([(1000, 0, 0)], od=od)).hit_windows == pytest.approx(windows)


def test_combo_numbers_and_colors(write_beatmap):
    bm = load_beatmap(write_beatmap([(1000, 0, 0), (2000, 0, 0), (3000, 0, 0, True), (4000, 0, 0)]))
    assert [o.number for o in bm.objects] == [1, 2, 1, 2]
    assert [o.color for o in bm.objects] == [0, 0, 1, 1]   # the first circle always starts a combo


def test_objects_are_sorted_by_time(write_beatmap):
    bm = load_beatmap(write_beatmap([(3000, 0, 0), (1000, 0, 0), (2000, 0, 0)]))
    assert [o.time for o in bm.objects] == [1000, 2000, 3000]


def test_missing_fields_get_defaults(tmp_path):
    path = tmp_path / "map.json"
    path.write_text(json.dumps({"audio": "a.wav", "difficulty": {},
                                "objects": [{"time": 5, "x": 1, "y": 2}]}))
    bm = load_beatmap(str(path))
    assert (bm.title, bm.artist, bm.version) == ("Untitled", "Unknown", "Normal")
    assert (bm.ar, bm.cs, bm.od, bm.hp, bm.bpm, bm.lead_in_ms) == (5, 4, 5, 5, 120, 2000)


def test_audio_path_is_next_to_the_beatmap(write_beatmap, tmp_path):
    bm = load_beatmap(write_beatmap([(1000, 0, 0)]))
    assert bm.audio_path == os.path.join(str(tmp_path), "audio.wav")


def test_broken_json_raises(tmp_path):
    path = tmp_path / "map.json"
    path.write_text('{"objects": [')
    with pytest.raises(ValueError):
        load_beatmap(str(path))
