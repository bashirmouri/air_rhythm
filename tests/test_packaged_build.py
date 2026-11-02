"""Where files live in a packaged (PyInstaller) build vs. running from source (config.py),
and the first-start copy of pre-generated files (map_gen.py). No build needed: the
packaged case is simulated by setting what PyInstaller sets (sys.frozen, sys._MEIPASS)."""
import json
import os

import config
import map_gen
from audio_gen import wav_is_valid, write_wav
from conftest import ROOT, run_game

import numpy as np

SHOW_CONFIG = """
import json, config
print("CONFIG", json.dumps({k: getattr(config, k) for k in (
    "FROZEN", "BUNDLE_DIR", "APP_DIR", "DATA_DIR", "PORTABLE", "PREGENERATED_DIR",
    "BUNDLED_MODEL", "LEGACY_DIR")} | {"MPLCONFIGDIR": os.environ["MPLCONFIGDIR"],
                                       "user_data_dir": config.user_data_dir()}))
"""


def packaged_config(tmp_path, portable=False):
    """config as a packaged build sees it: game unzipped to tmp/app, bundle in tmp/app/_internal."""
    app = tmp_path / "app"
    (app / "_internal").mkdir(parents=True)
    if portable:
        (app / "portable.txt").write_text("")
    fake_frozen = (f"import sys; sys.frozen = True; sys._MEIPASS = {str(app / '_internal')!r}; "
                   f"sys.executable = {str(app / 'AirRhythm.exe')!r}\n")
    code, out = run_game(fake_frozen + SHOW_CONFIG, tmp_path / "unused", env={
        "AIR_RHYTHM_DATA_DIR": "",                     # use the real default location logic
        "MPLCONFIGDIR": str(tmp_path / "pyinstaller_temp"),   # what PyInstaller's hook sets
        "LOCALAPPDATA": str(tmp_path / "localappdata"), "XDG_DATA_HOME": str(tmp_path / "xdg")})
    assert code == 0, out
    return app, json.loads(next(l for l in out if l.startswith("CONFIG "))[7:])


def test_packaged_build_paths(tmp_path):
    app, c = packaged_config(tmp_path)
    bundle = str(app / "_internal")
    assert c["FROZEN"] is True
    assert c["BUNDLE_DIR"] == bundle and c["APP_DIR"] == str(app)
    assert c["DATA_DIR"] == c["user_data_dir"] and str(tmp_path) in c["DATA_DIR"]
    assert c["PREGENERATED_DIR"] == os.path.join(bundle, "pregenerated")
    assert c["BUNDLED_MODEL"] == os.path.join(bundle, "models", "hand_landmarker.task")
    assert c["LEGACY_DIR"] is None                     # nothing to migrate in a packaged build
    # PyInstaller points matplotlib at a temp folder deleted on exit; we keep a real cache
    assert c["MPLCONFIGDIR"] == os.path.join(c["DATA_DIR"], "cache", "matplotlib")


def test_portable_txt_next_to_the_exe(tmp_path):
    app, c = packaged_config(tmp_path, portable=True)
    assert c["PORTABLE"] is True and c["DATA_DIR"] == str(app)


def test_running_from_source_uses_no_bundled_files(tmp_path):
    code, out = run_game(SHOW_CONFIG, tmp_path / "data")
    c = json.loads(next(l for l in out if l.startswith("CONFIG "))[7:])
    assert c["FROZEN"] is False and c["APP_DIR"] == ROOT
    assert c["PREGENERATED_DIR"] is None and c["BUNDLED_MODEL"] is None
    assert c["LEGACY_DIR"] == ROOT


def test_portable_flag_from_source(tmp_path):
    code, out = run_game(SHOW_CONFIG, tmp_path / "x", env={"AIR_RHYTHM_DATA_DIR": ""}, args=["--portable"])
    c = json.loads(next(l for l in out if l.startswith("CONFIG "))[7:])
    assert c["PORTABLE"] is True and c["DATA_DIR"] == ROOT


# ---------------------------------------------------------------- pre-generated files
def test_pregenerated_file_is_copied_on_first_start(monkeypatch, tmp_path):
    data, pre = tmp_path / "data", tmp_path / "pregenerated"
    target = data / "assets" / "menu_music.wav"
    (pre / "assets").mkdir(parents=True)
    target.parent.mkdir(parents=True)
    write_wav(str(pre / "assets" / "menu_music.wav"), np.zeros((4410, 2)))
    monkeypatch.setattr(config, "DATA_DIR", str(data))
    monkeypatch.setattr(config, "PREGENERATED_DIR", str(pre))
    assert map_gen._copy_pregenerated(str(target), wav_is_valid)
    assert wav_is_valid(str(target))
    assert os.listdir(target.parent) == ["menu_music.wav"]     # no .tmp left


def test_damaged_pregenerated_file_is_not_copied(monkeypatch, tmp_path):
    data, pre = tmp_path / "data", tmp_path / "pregenerated"
    (pre / "assets").mkdir(parents=True)
    (pre / "assets" / "menu_music.wav").write_bytes(b"broken")
    monkeypatch.setattr(config, "DATA_DIR", str(data))
    monkeypatch.setattr(config, "PREGENERATED_DIR", str(pre))
    assert not map_gen._copy_pregenerated(str(data / "assets" / "menu_music.wav"), wav_is_valid)


def test_nothing_is_copied_when_running_from_source():
    assert config.PREGENERATED_DIR is None
    assert not map_gen._copy_pregenerated(os.path.join(config.DATA_DIR, "x.wav"), wav_is_valid)
