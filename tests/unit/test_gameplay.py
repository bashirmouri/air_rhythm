"""Game rules: judging, score, combo, accuracy, health and grades (gameplay.py)."""
import pytest

from air_rhythm.core.beatmap import load_beatmap
from air_rhythm.core.gameplay import Gameplay

# OD 5 -> hit windows 300/100/50 = +-50 / +-100 / +-150 ms. CS 4 -> radius 36.48.


def new_game(write_beatmap, circles, no_fail=False, **diff):
    return Gameplay(load_beatmap(write_beatmap(circles, **diff)), no_fail=no_fail)


@pytest.mark.parametrize("offset, judgment", [(0, 300), (-50, 300), (50, 300), (51, 100), (-100, 100),
                                              (101, 50), (-150, 50), (151, None), (-151, None)])
def test_judgment_by_timing(write_beatmap, offset, judgment):
    g = new_game(write_beatmap, [(1000, 100, 100)])
    assert g.press(1000 + offset, (100, 100)) == judgment


def test_press_must_be_on_the_circle(write_beatmap):
    g = new_game(write_beatmap, [(1000, 100, 100)])
    assert g.press(1000, (100 + 36, 100)) == 300          # inside the radius (36.48)
    g = new_game(write_beatmap, [(1000, 100, 100)])
    assert g.press(1000, (100 + 37, 100)) is None          # just outside


def test_score_and_combo(write_beatmap):
    g = new_game(write_beatmap, [(1000, 100, 100), (2000, 200, 100), (3000, 300, 100)])
    g.press(1000, (100, 100))
    g.press(2000, (200, 100))
    assert g.combo == 2
    assert g.score == 300 + int(300 * (1 + 1 / 25))       # combo multiplies score
    g.update(3200)                                         # third circle missed
    assert g.results == [300, 300, 0]
    assert g.combo == 0 and g.max_combo == 2


def test_a_circle_is_judged_only_once(write_beatmap):
    g = new_game(write_beatmap, [(1000, 100, 100)])
    assert g.press(1000, (100, 100)) == 300
    assert g.press(1010, (100, 100)) is None
    assert g.counts[300] == 1


def test_press_hits_the_earliest_circle_under_the_cursor(write_beatmap):
    # two stacked circles 100 ms apart: one press takes the earlier one
    g = new_game(write_beatmap, [(1000, 100, 100), (1100, 100, 100)])
    assert g.press(1050, (100, 100)) == 300
    assert g.results == [300, None]
    # a circle elsewhere doesn't block one under the cursor (no "notelock")
    g = new_game(write_beatmap, [(1000, 400, 300), (1100, 100, 100)])
    assert g.press(1100, (100, 100)) == 300
    assert g.results == [None, 300]


def test_unhit_circles_become_misses_after_their_window(write_beatmap):
    g = new_game(write_beatmap, [(1000, 100, 100)])
    g.update(1150)
    assert g.results == [None]                             # still inside the 50 window
    g.update(1151)
    assert g.results == [0] and g.counts[0] == 1


def test_accuracy_and_grades(write_beatmap):
    g = new_game(write_beatmap, [(1000 * i, 100, 100) for i in range(1, 5)])
    assert g.accuracy == 1.0 and g.grade() == "SS"         # nothing judged yet
    for t in (1000, 2000, 3000):
        g.press(t, (100, 100))
    g.press(4000 + 80, (100, 100))                         # one 100
    assert g.accuracy == pytest.approx((3 * 300 + 100) / 1200)
    assert g.grade() == "B"


def test_mean_error_and_unstable_rate(write_beatmap):
    g = new_game(write_beatmap, [(1000, 100, 100), (2000, 100, 100)])
    g.press(1000 + 20, (100, 100))
    g.press(2000 - 20, (100, 100))
    assert g.mean_error == 0
    assert g.unstable_rate == pytest.approx(200)           # 10 x stdev(+20, -20)


def test_missing_everything_fails(write_beatmap):
    g = new_game(write_beatmap, [(1000 + 200 * i, 100, 100) for i in range(40)], hp=5)
    g.update(0)
    g.update(1000 + 200 * 40 + 500)
    assert g.failed and g.grade() == "F"


def test_no_fail_never_fails(write_beatmap):
    g = new_game(write_beatmap, [(1000 + 200 * i, 100, 100) for i in range(40)], hp=5, no_fail=True)
    g.update(0)
    g.update(1000 + 200 * 40 + 500)
    assert not g.failed and g.health == 0


def test_health_drains_while_playing_but_not_in_breaks(write_beatmap):
    g = new_game(write_beatmap, [(1000, 100, 100), (2000, 100, 100), (20000, 100, 100)])
    g.press(1000, (100, 100))
    g.update(1000)
    playing = g.health
    g.update(1900)                                         # next circle close: drains
    assert g.health < playing
    g.press(2000, (100, 100))
    g.update(2000)
    before_break = g.health
    g.update(15000)                                        # next circle 5 s away: a break
    assert g.health == before_break


def test_finished_after_the_last_circle(write_beatmap):
    g = new_game(write_beatmap, [(1000, 100, 100)])
    g.press(1000, (100, 100))
    g.update(1000)
    assert not g.finished(2400)
    assert g.finished(2600)                                # 1.5 s after the last circle


def test_events_are_reported_once(write_beatmap):
    g = new_game(write_beatmap, [(1000, 100, 100), (2000, 100, 100)])
    g.press(1000, (100, 100))
    g.update(2200)
    assert [(i, j) for i, j, _, _ in g.drain_events()] == [(0, 300), (1, 0)]
    assert g.drain_events() == []
