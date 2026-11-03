"""The whole game starting up and failing gracefully. Each test runs the real game in its
own process with its own data folder (slower: a few seconds each)."""
import os
import textwrap

from conftest import ROOT, UNREACHABLE_URL, read_log, run_game

QUIT_RIGHT_AWAY = """
import pygame, main
real_run = main.App.run
def run(self):
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    return real_run(self)
main.App.run = run
main.main()
print("RETURNED")
"""

# Takes a screenshot of the error window, then closes it like a player pressing Esc.
CLOSE_ERROR_WINDOW = """
import pygame
real_flip = pygame.display.flip
def flip():
    real_flip()
    if pygame.display.get_caption()[0].startswith("Air Rhythm: "):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        print("ERROR WINDOW:", pygame.display.get_caption()[0])
pygame.display.flip = flip
"""


def project_files():
    return {f for f in os.listdir(ROOT) if f not in ("__pycache__", ".pytest_cache")}


def test_first_start(tmp_path):
    before = project_files()
    code, out = run_game(QUIT_RIGHT_AWAY, tmp_path, args=["--mouse"])
    assert code == 0 and "RETURNED" in out, out[-10:]
    files = {os.path.relpath(os.path.join(r, f), tmp_path) for r, _, fs in os.walk(tmp_path) for f in fs}
    assert {"settings.json", "air_rhythm.log", os.path.join("assets", "menu_music.wav"),
            os.path.join("maps", "first_steps", "easy.json")} <= files
    assert project_files() == before                       # nothing written next to the game
    log = read_log(tmp_path)
    for fact in ("starting", "mediapipe", "Data folder", "Display:", "vsync", "Air Rhythm closed"):
        assert fact in log, fact


def test_no_sound_device(tmp_path):
    code, out = run_game("""
        import time, argparse, main
        from play_screen import PlayScreen
        app = main.App(argparse.Namespace(mouse=True, autoplay=True, map=None))
        print("WARNING:", app.warning)
        app.screen.calibrate()
        print("STILL ON:", type(app.screen).__name__)
        app.screen.draw(app.surface)
        app.goto(PlayScreen(app, app.map_path, autoplay=True))
        t = time.perf_counter()
        while time.perf_counter() - t < 3:
            app.screen.update(); app.screen.draw(app.surface)
        print("PLAYED")
    """, tmp_path, env={"SDL_AUDIODRIVER": "no_such_driver"})
    assert code == 0, out[-10:]
    assert "WARNING: No sound device found: playing without sound" in out
    assert "STILL ON: MenuScreen" in out                    # calibration needs sound
    assert "PLAYED" in out


def test_broken_map_file_falls_back(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"objects": [}')
    code, out = run_game(f"""
        import argparse, os, main
        app = main.App(argparse.Namespace(mouse=True, autoplay=False, map={str(bad)!r}))
        print("MAP:", os.path.basename(app.map_path), "|", app.warning)
    """, tmp_path / "data")
    assert "MAP: easy.json | Couldn't load bad.json: playing First Steps instead" in out, out[-10:]


def test_unexpected_crash_shows_the_error_window(tmp_path):
    code, out = run_game(CLOSE_ERROR_WINDOW + textwrap.dedent("""
        import main, screens
        real_init = main.App.__init__
        def init(self, args):
            real_init(self, args)
            screens.MenuScreen.draw = lambda self, surf: 1 / 0   # crash on the first frame
        main.App.__init__ = init
        main.main()
        print("RETURNED")
    """), tmp_path, args=["--mouse"])
    assert code == 0 and "RETURNED" in out, out[-10:]
    assert "ERROR WINDOW: Air Rhythm: Something went wrong" in out
    log = read_log(tmp_path)
    assert "Unexpected error" in log and "ZeroDivisionError" in log and "Traceback" in log


def test_unwritable_data_folder_shows_why(tmp_path):
    blocker = tmp_path / "a_file"
    blocker.write_text("a file where the data folder should be")
    code, out = run_game(CLOSE_ERROR_WINDOW + "import main; main.main(); print('RETURNED')",
                         blocker / "data", args=["--mouse"])
    assert code == 0 and "RETURNED" in out, out[-10:]
    assert "ERROR WINDOW: Air Rhythm: Air Rhythm can't start" in out
    assert any("Startup failed: Air Rhythm couldn't create its game files" in line for line in out)


def test_offline_hand_mode_explains_in_the_menu(tmp_path):
    code, out = run_game(f"""
        import time, argparse, hand_tracker, main
        hand_tracker.MODEL_URL = {UNREACHABLE_URL!r}
        app = main.App(argparse.Namespace(mouse=False, autoplay=False, map=None))
        for _ in range(50):
            if app.input.tracker.error: break
            time.sleep(0.1)
        print("STATUS:", app.input.status_text())
        app.input.close()
    """, tmp_path)
    status = next((line for line in out if line.startswith("STATUS:")), out[-5:])
    assert "Couldn't download the hand-tracking model (no internet?)" in status
    assert "Camera problem" not in status
