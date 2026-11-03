"""Screen logic, each screen on its own with a stand-in app: buttons (clicked or pinched,
the mouse working in hand mode) and calibration turning taps into an offset."""
import time

import pygame
import pytest

from air_rhythm.content.audio_gen import CALIB_COUNT_IN, CALIB_TAPS
from air_rhythm.core.playfield import Playfield
from air_rhythm.system import config
from air_rhythm.ui import widgets as ui
from air_rhythm.ui.screens import base, calibration, menu


@pytest.fixture(scope="module", autouse=True)
def display():
    pygame.init()
    pygame.display.set_mode((config.WINDOW_W, config.WINDOW_H))
    yield
    pygame.quit()


class FakeInput:
    def __init__(self, kind="hand", cursor=(256, 192)):
        self.kind, self._cursor, self.presses = kind, cursor, []

    def cursor(self):
        return self._cursor

    def take_presses(self):
        p, self.presses = self.presses, []
        return p


class FakeApp:
    """Just what screens use from the real App."""
    def __init__(self, kind="hand", cursor=(256, 192)):
        self.input = FakeInput(kind, cursor)
        self.playfield = Playfield(config.WINDOW_W, config.WINDOW_H)
        self.settings = {"input_offset_ms": 0.0}
        self.went_to = None

    def to_screen(self, pos):
        return None if pos is None else self.playfield.to_screen(*pos)

    def goto(self, screen):
        self.went_to = screen


class Buttons(base.ButtonScreen):
    def __init__(self, app):
        self.app, self.clicked = app, []
        self.buttons = [ui.Button("A", (300, 300), (200, 60), lambda: self.clicked.append("A")),
                        ui.Button("B", (900, 300), (200, 60), lambda: self.clicked.append("B"))]


def mouse(kind, pos=(300, 300), button=1):
    return pygame.event.Event(kind, pos=pos, button=button, rel=(0, 0), buttons=(0, 0, 0))


# ---------------------------------------------------------------- buttons
def test_mouse_click_works_in_hand_mode():
    s = Buttons(FakeApp("hand"))
    s.handle_mouse([mouse(pygame.MOUSEBUTTONDOWN, (300, 300))])
    s.handle_mouse([mouse(pygame.MOUSEBUTTONDOWN, (600, 600))])     # on no button
    s.handle_mouse([mouse(pygame.MOUSEBUTTONDOWN, (900, 300), button=3)])   # right click
    assert s.clicked == ["A"]


def test_in_mouse_mode_clicks_come_through_the_mouse_input_instead():
    s = Buttons(FakeApp("mouse"))
    s.handle_mouse([mouse(pygame.MOUSEBUTTONDOWN, (300, 300))])
    assert s.clicked == []          # MouseInput turns it into a press; no double click


def test_pinch_on_a_button_presses_it():
    app = FakeApp("hand")
    s = Buttons(app)
    app.input.presses = [(0.0, app.playfield.to_osu(900, 300))]
    s.update()
    assert s.clicked == ["B"]


def test_moving_the_mouse_takes_over_the_cursor_for_a_while():
    app = FakeApp("hand", cursor=(256, 192))
    s = Buttons(app)
    assert s.cursor_override() is None                               # mouse not touched: hand cursor
    s.handle_mouse([mouse(pygame.MOUSEMOTION)])
    assert s.cursor_override() is not None                           # mouse just moved
    s._mouse_moved_at = time.perf_counter() - base.MOUSE_ACTIVE_S - 0.1
    assert s.cursor_override() is None                               # back to the hand
    app.input._cursor = None
    assert s.cursor_override() is not None                           # no hand seen: keep the mouse


# ---------------------------------------------------------------- calibration
class FakeClock:
    """Song time in ms is simply the press time we give it."""
    def __init__(self):
        self.now = 0.0

    def update(self):
        pass

    def now_ms(self, t=None):
        return self.now if t is None else t

    def stop(self, fade_ms=0):
        pass


@pytest.fixture
def calib(assets, monkeypatch):
    monkeypatch.setattr(menu, "MenuScreen", lambda app: "menu")      # don't build the real menu
    app = FakeApp("hand")
    screen = calibration.CalibrationScreen(app)
    screen.clock.stop()
    screen.clock = FakeClock()
    return app, screen


def tap_beats(screen, offsets):
    """Tap on the counted beats, each `offset` ms late (negative = early)."""
    beats = screen.beats[CALIB_COUNT_IN:]
    screen.app.input.presses = [(b + d, None) for b, d in zip(beats, offsets, strict=False)]
    screen.update()


def finish(screen):
    screen.clock.now = screen.beats[-1] + 801
    screen.update()


def enter():
    return pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode="\r", scancode=0)


def test_offset_is_the_median_tap_delay(calib):
    app, s = calib
    offsets = [40] * (CALIB_TAPS - 2) + [200, -90]                   # two sloppy taps
    tap_beats(s, offsets)
    finish(s)
    assert s.done and s.result == 40                                  # the median ignores them
    s.handle([enter()])
    assert app.settings["input_offset_ms"] == 40.0 and app.went_to == "menu"


def test_taps_far_from_any_beat_are_ignored(calib):
    app, s = calib
    tap_beats(s, [40] * CALIB_TAPS)
    s.app.input.presses = [(s.beats[-1] + 300, None)]                 # 300 ms after the last beat
    s.update()
    assert len(s.taps) == CALIB_TAPS


def test_too_few_taps_give_no_result_and_save_nothing(calib):
    app, s = calib
    tap_beats(s, [40] * 7)                                            # 8 needed
    finish(s)
    assert s.done and s.result is None
    s.handle([enter()])
    assert app.settings["input_offset_ms"] == 0.0 and app.went_to is None


def test_escape_leaves_without_saving(calib):
    app, s = calib
    tap_beats(s, [40] * CALIB_TAPS)
    s.handle([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="", scancode=0)])
    assert app.went_to == "menu" and app.settings["input_offset_ms"] == 0.0
