"""Turning the player's actions into hits: the mouse, and the hand tracker's per-frame
logic (controls/inputs.py, controls/hand_tracker.py). No camera needed."""
from types import SimpleNamespace as Point

import pygame
import pytest

from air_rhythm.controls import hand_tracker
from air_rhythm.controls.inputs import HandInput, MouseInput
from air_rhythm.core.playfield import Playfield
from air_rhythm.system import config


@pytest.fixture(scope="module", autouse=True)
def display():
    pygame.init()
    pygame.display.set_mode((config.WINDOW_W, config.WINDOW_H))
    yield
    pygame.quit()


def key(kind, k):
    return pygame.event.Event(kind, key=k, mod=0, unicode="", scancode=0)


def click(kind, button=1):
    return pygame.event.Event(kind, button=button, pos=(0, 0))


# ---------------------------------------------------------------- mouse
def test_left_click_and_z_x_are_hits_at_the_cursor():
    m = MouseInput(Playfield(config.WINDOW_W, config.WINDOW_H))
    m.handle_events([click(pygame.MOUSEBUTTONDOWN), key(pygame.KEYDOWN, pygame.K_z),
                     key(pygame.KEYDOWN, pygame.K_x)])
    presses = m.take_presses()
    assert len(presses) == 3
    assert all(pos == m.cursor() for _, pos in presses)
    assert m.take_presses() == []                       # taken once


def test_other_buttons_and_keys_do_nothing():
    m = MouseInput(Playfield(config.WINDOW_W, config.WINDOW_H))
    m.handle_events([click(pygame.MOUSEBUTTONDOWN, button=3), key(pygame.KEYDOWN, pygame.K_a)])
    assert m.take_presses() == [] and not m.is_down()


def test_held_until_every_source_is_released():
    m = MouseInput(Playfield(config.WINDOW_W, config.WINDOW_H))
    m.handle_events([key(pygame.KEYDOWN, pygame.K_z), click(pygame.MOUSEBUTTONDOWN)])
    m.handle_events([key(pygame.KEYUP, pygame.K_z)])
    assert m.is_down()                                  # the mouse button is still held
    m.handle_events([click(pygame.MOUSEBUTTONUP)])
    assert not m.is_down()


# ---------------------------------------------------------------- hand input
def hand_input():
    """A HandInput whose tracker isn't started (no camera)."""
    h = HandInput.__new__(HandInput)
    h.playfield, h.tracker, h._presses = None, hand_tracker.HandTracker(), []
    return h


def test_pinches_become_hits_with_capture_time_and_position():
    h = hand_input()
    h.tracker.events.put(("press", 12.5, (0.5, 0.5)))
    h.tracker.events.put(("release", 12.7, (0.5, 0.5)))
    h.handle_events([])
    assert h.take_presses() == [(12.5, (config.PLAYFIELD_W / 2, config.PLAYFIELD_H / 2))]


def test_hand_zone_reaches_a_little_past_the_playfield_edges():
    m = config.CURSOR_MARGIN
    assert HandInput._to_osu((0, 0)) == (-m, -m)
    assert HandInput._to_osu((1, 1)) == (config.PLAYFIELD_W + m, config.PLAYFIELD_H + m)
    assert HandInput._to_osu(None) is None


# ---------------------------------------------------------------- tracker: one frame at a time
def hand(gap):
    """Fake MediaPipe landmarks: hand size 0.2, thumb and index tips `gap` apart."""
    lm = [Point(x=0.5, y=0.5) for _ in range(21)]
    lm[hand_tracker.WRIST], lm[hand_tracker.MIDDLE_MCP] = Point(x=0.5, y=0.6), Point(x=0.5, y=0.4)
    lm[hand_tracker.THUMB_TIP] = Point(x=0.5 - gap / 2, y=0.5)
    lm[hand_tracker.INDEX_TIP] = Point(x=0.5 + gap / 2, y=0.5)
    return lm


OPEN, PINCHED = hand(0.12), hand(0.02)      # ratios 0.6 and 0.1 (thresholds 0.28 / 0.40)


def events(tr):
    out = []
    while not tr.events.empty():
        out.append(tr.events.get_nowait())
    return out


def test_pinch_and_release_events_carry_the_capture_time():
    tr = hand_tracker.HandTracker()
    tr._on_frame(OPEN, 640, 640, t=1.000)
    tr._on_frame(PINCHED, 640, 640, t=1.033)
    tr._on_frame(OPEN, 640, 640, t=1.066)
    got = events(tr)
    assert [(kind, t) for kind, t, _ in got] == [("press", 1.033), ("release", 1.066)]
    assert got[0][2] == pytest.approx(hand_tracker.map_to_zone(0.5, 0.5), abs=1e-6)
    assert tr.visible and not tr.pinched


def test_hand_lost_briefly_keeps_the_pinch():
    tr = hand_tracker.HandTracker()
    tr._on_frame(PINCHED, 640, 640, t=1.0)
    tr._on_frame(None, 640, 640, t=1.0 + config.HAND_LOST_GRACE_S / 2)
    assert tr.visible and tr.pinched
    assert [kind for kind, _, _ in events(tr)] == ["press"]


def test_hand_gone_releases_and_hides_the_cursor():
    tr = hand_tracker.HandTracker()
    tr._on_frame(PINCHED, 640, 640, t=1.0)
    tr._on_frame(None, 640, 640, t=1.0 + config.HAND_LOST_GRACE_S + 0.01)
    assert [kind for kind, _, _ in events(tr)] == ["press", "release"]
    assert not tr.visible and not tr.pinched
    assert tr.display_cursor(2.0) is None


def test_no_hand_at_all_shows_nothing():
    tr = hand_tracker.HandTracker()
    tr._on_frame(None, 640, 640, t=1.0)
    assert not tr.visible and events(tr) == []


def test_hand_settings_apply_to_the_running_tracker():
    h = hand_input()
    h.camera_index = 0
    same_camera = h.apply({"hand_area": "Small", "pinch_sensitivity": "High",
                           "cursor_smoothing": "Off", "camera_index": 0})
    tr = h.tracker
    assert same_camera
    assert tr.zone == config.HAND_AREAS["Small"]
    assert (tr._pinch.close, tr._pinch.open) == config.PINCH_SENSITIVITY["High"]
    assert tr.smoothing_ms == 0
    assert not h.apply({"camera_index": 2})              # another camera: needs a new tracker


def test_hand_area_changes_where_the_cursor_goes():
    right_of_center = [Point(x=p.x + 0.15, y=p.y) for p in OPEN]
    cursors = {}
    for area in ("Small", "Large"):
        tr = hand_tracker.HandTracker(zone=config.HAND_AREAS[area])
        tr._on_frame(right_of_center, 640, 480, t=1.0)
        cursors[area] = tr.cursor
    small, large = cursors["Small"], cursors["Large"]
    # the same hand position is further from the center in a smaller area
    assert abs(small[0] - 0.5) > abs(large[0] - 0.5)
