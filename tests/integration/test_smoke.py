"""Smoke test: the whole game, headless, through every screen (changing a few settings on
the way). Autoplay plays a full map at 25x speed and must get a perfect score."""
from conftest import run_game

PLAY_THROUGH = """
import time, argparse, pygame
import air_rhythm.core.clock as clock
import air_rhythm.app as main
from air_rhythm.ui.screens.menu import MenuScreen
from air_rhythm.ui.screens.calibration import CalibrationScreen
from air_rhythm.ui.screens.results import ResultsScreen
from air_rhythm.ui.screens.play import PlayScreen

def fast_now(self, t=None):                     # the song runs 25x faster than real time
    return ((time.perf_counter() if t is None else t) - self.start_t) * 1000 * 25
clock.SongClock.now_ms = fast_now

app = main.App(argparse.Namespace(mouse=True, autoplay=True, map=None))
seen = []
def frames(n=10):
    for _ in range(n):
        screen = app.screen
        screen.handle([])
        if screen is app.screen:
            screen.update()
        app.screen.draw(app.surface)
        app.draw_camera_preview(app.surface)
        app.draw_cursor(app.surface)
        if type(app.screen).__name__ not in seen:
            seen.append(type(app.screen).__name__)

frames()
app.screen.calibrate(); frames()
app.screen.clock.stop(); app.goto(MenuScreen(app)); frames()
app.screen.open_settings(); frames()
app.screen._set("music_volume", 40); app.screen._set("hand_area", "Large"); frames()
app.screen.back(); frames()
for level in ("Easy", "Normal"):
    app.set_level(level)
    app.screen.play()
    print(f"MUSIC VOLUME {pygame.mixer.music.get_volume():.1f}")    # the dummy sound driver has a mixer
    end = time.perf_counter() + 20
    while not isinstance(app.screen, ResultsScreen) and time.perf_counter() < end:
        frames(1)
    g = app.screen.game
    print(f"RESULT {level}: {g.counts} grade {g.grade()} failed {g.failed}")
    app.screen.menu(); frames()
print("SCREENS:", " -> ".join(seen))
"""


def test_every_screen_and_perfect_autoplay(tmp_path):
    code, out = run_game(PLAY_THROUGH, tmp_path, timeout=240)
    assert code == 0, out[-15:]
    assert "RESULT Easy: {300: 60, 100: 0, 50: 0, 0: 0} grade SS failed False" in out, out[-15:]
    assert "RESULT Normal: {300: 128, 100: 0, 50: 0, 0: 0} grade SS failed False" in out, out[-15:]
    assert "SCREENS: MenuScreen -> CalibrationScreen -> SettingsScreen -> PlayScreen -> ResultsScreen" in out
    assert out.count("MUSIC VOLUME 0.4") == 2                          # the songs use the volume setting
