"""Shared test setup.

The game reads its data folder and SDL drivers when its modules are first imported, so
this file sets them up front: a throw-away data folder for the whole test session, and
headless video/audio so no window opens and no sound plays.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SESSION_DATA_DIR = tempfile.mkdtemp(prefix="air_rhythm_tests_")
os.environ["AIR_RHYTHM_DATA_DIR"] = SESSION_DATA_DIR
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

# A port nothing listens on: "the internet is down" without depending on the network.
UNREACHABLE_URL = "http://127.0.0.1:9/hand_landmarker.task"


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(SESSION_DATA_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def assets():
    """The generated songs and beatmaps, made once per test session (a few seconds)."""
    import map_gen
    map_gen.ensure_assets()
    return map_gen


@pytest.fixture
def write_beatmap(tmp_path):
    """Writes a beatmap JSON with the given circles and returns its path.
    Circles are (time_ms, x, y) or (time_ms, x, y, new_combo)."""
    def write(circles, ar=5, cs=4, od=5, hp=5, **fields):
        objects = [{"time": c[0], "x": c[1], "y": c[2], "new_combo": c[3] if len(c) > 3 else False}
                   for c in circles]
        data = {"title": "Test", "audio": "audio.wav", "difficulty":
                {"ar": ar, "cs": cs, "od": od, "hp": hp}, "objects": objects, **fields}
        path = tmp_path / "beatmap.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return str(path)
    return write


def run_game(code, data_dir, env=None, args=(), timeout=180):
    """Runs `code` in a fresh Python process, as if started with `python main.py *args`,
    with its own data folder. For tests that start the whole game (each needs a clean
    pygame and fresh config). Returns (exit code, output lines)."""
    full_env = dict(os.environ, AIR_RHYTHM_DATA_DIR=str(data_dir), PYTHONIOENCODING="utf-8")
    full_env.update(env or {})
    prelude = (f"import os, sys; sys.path.insert(0, {ROOT!r}); os.chdir({ROOT!r}); "
               f"sys.argv = ['main.py', *{list(args)!r}]\n")
    p = subprocess.run([sys.executable, "-c", prelude + textwrap.dedent(code)], env=full_env,
                       capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    return p.returncode, (p.stdout + p.stderr).splitlines()


def read_log(data_dir):
    path = os.path.join(str(data_dir), "air_rhythm.log")
    return open(path, encoding="utf-8").read() if os.path.exists(path) else ""
