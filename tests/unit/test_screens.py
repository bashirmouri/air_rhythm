"""Screen logic, each screen on its own with a stand-in app: buttons (clicked or pinched,
the mouse working in hand mode) and calibration turning taps into an offset."""
import time

import pygame
import pytest

from air_rhythm.content.audio_gen import CALIB_COUNT_IN, CALIB_TAPS
from air_rhythm.core.playfield import Playfield
from air_rhythm.system import config, settings
from air_rhythm.ui import widgets as ui
from air_rhythm.ui.screens import base, calibration, menu
from air_rhythm.ui.screens import settings as settings_screen


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
        self.settings = dict(settings.DEFAULTS)
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


# ---------------------------------------------------------------- pause
class FakeTime:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class PlayApp(FakeApp):
    def __init__(self, kind="mouse"):
        super().__init__(kind)
        self.settings.update(no_fail=True)
        self.surface = pygame.display.get_surface()
        self.background = pygame.Surface(self.surface.get_size())
        self.hitsound = type("Silent", (), {"play": lambda self: None})()
        self.input.status_text = lambda: None

    def cursor_screen(self):
        return self.to_screen(self.input.cursor())


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=0, unicode="", scancode=0)


@pytest.fixture
def song(assets, monkeypatch):
    """A PlayScreen on the Easy map, with a fake clock so the test controls time."""
    from air_rhythm.ui.screens.play import PlayScreen
    fake = FakeTime()
    monkeypatch.setattr(time, "perf_counter", fake)
    monkeypatch.setattr(menu, "MenuScreen", lambda app: "menu")
    app = PlayApp()
    s = PlayScreen(app, assets.LEVEL_PATHS["Easy"])
    s.clock.audio = False                           # timing only; no music needed
    yield app, s, fake
    s.clock.stop()


def play_until(s, fake, ms):
    """Advance song time to `ms` (song time; negative = lead-in) and run one frame."""
    if ms >= 0 and s.clock._pending:                 # first the frame where the music starts
        fake.now = s.clock.start_t
        s.update()
    fake.now += (ms - s.clock.now_ms()) / 1000
    s.update()


def test_escape_pauses_and_freezes_the_song(song):
    app, s, fake = song
    play_until(s, fake, 3000)
    s.handle([key(pygame.K_ESCAPE)])
    assert s.state == "paused" and app.went_to is None           # paused, not quit
    fake.now += 60
    s.update()
    assert s.clock.now_ms() == pytest.approx(3000)
    s.draw(app.surface)                                          # the pause card draws


def test_losing_window_focus_pauses(song):
    app, s, fake = song
    play_until(s, fake, 1000)
    s.handle([pygame.event.Event(pygame.WINDOWFOCUSLOST)])
    assert s.state == "paused"


def test_resume_counts_down_then_carries_on_at_the_same_song_time(song):
    app, s, fake = song
    play_until(s, fake, 3000)
    s.handle([key(pygame.K_ESCAPE)])
    fake.now += 20
    s.handle([key(pygame.K_ESCAPE)])                             # Esc again = Resume
    assert s.state == "countdown"
    fake.now += config.RESUME_COUNTDOWN_MS / 1000 / 2
    s.update()
    s.draw(app.surface)
    assert s.state == "countdown" and s.clock.now_ms() == pytest.approx(3000)
    fake.now += config.RESUME_COUNTDOWN_MS / 1000 / 2
    s.update()
    assert s.state == "playing" and s.clock.now_ms() == pytest.approx(3000)
    fake.now += 0.25
    assert s.clock.now_ms() == pytest.approx(3250)


def test_presses_while_paused_or_counting_down_never_hit_circles(song):
    app, s, fake = song
    first = s.bm.objects[0]
    play_until(s, fake, first.time - 5)                       # pause just before the first circle
    s.handle([key(pygame.K_ESCAPE)])
    on_circle = (first.x, first.y)
    app.input.presses = [(fake.now, on_circle)]                  # pinch on the circle while paused
    s.update()
    s.resume()
    app.input.presses = [(fake.now, on_circle)]                  # ... and during the countdown
    s.update()
    fake.now += config.RESUME_COUNTDOWN_MS / 1000
    s.update()                                                   # the song resumes
    fake.now += 0.005
    app.input.presses = [(fake.now - 0.01, on_circle)]           # the camera reports a pinch late: it
    s.update()                                                   # happened before the song resumed
    assert s.game.results[0] is None
    play_until(s, fake, first.time)
    app.input.presses = [(fake.now, on_circle)]                  # once playing, a press counts
    s.update()
    assert s.game.results[0] == 300


def test_pause_menu_buttons(song):
    app, s, fake = song
    play_until(s, fake, 1000)
    s.pause()
    resume, retry, quit_ = s.pause_menu.buttons
    app.input.presses = [(fake.now, app.playfield.to_osu(*quit_.rect.center))]   # pinch on Quit
    s.update()
    assert app.went_to == "menu"
    s.pause()
    s.handle([key(pygame.K_r)])
    assert type(app.went_to).__name__ == "PlayScreen" and app.went_to is not s
    app.went_to.clock.stop()


def test_mouse_works_on_the_pause_card_in_hand_mode(song):
    app, s, fake = song
    app.input.kind = "hand"
    s.pause()
    resume = s.pause_menu.buttons[0]
    s.handle([mouse(pygame.MOUSEBUTTONDOWN, resume.rect.center)])
    assert s.state == "countdown"


def test_calibration_leaves_the_sound_delay_out_of_the_input_delay(calib):
    app, s = calib
    app.settings["audio_offset_ms"] = 30.0          # e.g. Bluetooth headphones, set in Settings
    tap_beats(s, [40] * CALIB_TAPS)                 # taps measured 40 ms late in total
    finish(s)
    assert s.result == 10                           # 30 of those 40 ms are the sound


def test_calibration_can_return_to_another_screen(calib):
    app, s = calib
    s._back = lambda: "settings"
    s.handle([key(pygame.K_ESCAPE)])
    assert app.went_to == "settings"


# ---------------------------------------------------------------- sound delay in gameplay
def test_sound_delay_moves_the_beat_to_when_it_is_heard(song):
    app, s, fake = song
    app.settings["audio_offset_ms"] = 100.0         # sound comes out 100 ms late
    first = s.bm.objects[0]
    play_until(s, fake, first.time + 100)           # clock: 100 ms past the circle ...
    assert s.song_ms() == pytest.approx(first.time, abs=1e-6)   # ... which is when it is heard
    app.input.presses = [(fake.now, (first.x, first.y))]
    s.update()
    assert s.game.results[0] == 300                 # pinching on the heard beat is perfect


# ---------------------------------------------------------------- settings screen
class SettingsApp(PlayApp):
    def __init__(self, kind="mouse"):
        super().__init__(kind)
        self.audio_ok, self.applied = True, 0
        self.input.preview_surface = lambda: None
        self.input.status_text = lambda: None

    def apply_settings(self):
        self.applied += 1


@pytest.fixture
def screen(monkeypatch):
    monkeypatch.setattr(menu, "MenuScreen", lambda app: "menu")
    app = SettingsApp()
    s = settings_screen.SettingsScreen(app)
    s.draw(app.surface)                             # everything draws
    return app, s


def row(s, text):
    return next(b for b in s.buttons if b.text == text)


def pinch_at(app, s, screen_pos):
    app.input.presses = [(0.0, app.playfield.to_osu(*screen_pos))]
    s.update()


def test_plus_and_minus_by_pinch(screen):
    app, s = screen
    song = row(s, "Song")
    minus, plus = song.boxes()
    pinch_at(app, s, minus.center)
    assert app.settings["music_volume"] == 90 and app.applied == 1
    pinch_at(app, s, plus.center)
    pinch_at(app, s, plus.center)                   # can't go past 100 %
    assert app.settings["music_volume"] == 100


def test_offsets_step_by_5_ms(screen):
    app, s = screen
    _, plus = row(s, "Sound delay").boxes()
    pinch_at(app, s, plus.center)
    assert app.settings["audio_offset_ms"] == 5.0


def test_pressing_a_choice_picks_it_directly(screen):
    app, s = screen
    area = row(s, "Hand area")
    _, segments = ui._segments(area.options, (area.rect.right - 16, area.rect.centery))
    pinch_at(app, s, segments[0].center)            # "Small" (from Medium: not simply the next one)
    assert app.settings["hand_area"] == "Small"
    pinch_at(app, s, (area.rect.x + 40, area.rect.centery))     # on the label: next one
    assert app.settings["hand_area"] == "Medium"


def test_mouse_click_works_on_settings_in_hand_mode(screen):
    app, s = screen
    app.input.kind = "hand"
    _, segments = ui._segments([str(i + 1) for i in range(config.CAMERA_COUNT)],
                               (row(s, "Camera").rect.right - 16, row(s, "Camera").rect.centery))
    s.handle([mouse(pygame.MOUSEBUTTONDOWN, segments[3].center)])     # camera 4
    assert app.settings["camera_index"] == 3


def test_menu_music_turns_off_below_the_lowest_step_and_back_on(screen):
    app, s = screen
    music = row(s, "Menu music")
    minus, plus = music.boxes()
    app.settings["menu_music_volume"] = 10
    pinch_at(app, s, minus.center)
    assert app.settings["menu_music"] is False and music.text_value() == "Off"
    pinch_at(app, s, plus.center)
    assert app.settings["menu_music"] is True and music.text_value() == "10%"


def test_toggles_and_leaving(screen):
    app, s = screen
    pinch_at(app, s, row(s, "Show FPS").rect.center)
    assert app.settings["show_fps"] is True
    s.handle([key(pygame.K_ESCAPE)])
    assert app.went_to == "menu"


def test_measuring_input_delay_comes_back_to_settings(screen, assets):
    app, s = screen
    pinch_at(app, s, row(s, "Measure input delay").rect.center)
    calib_screen = app.went_to
    assert isinstance(calib_screen, calibration.CalibrationScreen)
    calib_screen.handle([key(pygame.K_ESCAPE)])
    assert isinstance(app.went_to, settings_screen.SettingsScreen)
