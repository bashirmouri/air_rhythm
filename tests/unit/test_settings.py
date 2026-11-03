"""Saved settings and the one-time migration from older versions (settings.py)."""
import json
import logging
import os

import pytest

from air_rhythm.system import config, settings


@pytest.fixture
def settings_file(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(settings, "SETTINGS_PATH", str(path))
    return path


def test_defaults_when_there_is_no_file(settings_file):
    assert settings.load() == settings.DEFAULTS


def test_save_and_load_round_trip(settings_file):
    s = settings.load()
    s["input_offset_ms"] = 30.9
    s["level"] = "Normal"
    settings.save(s)
    assert settings.load() == s
    assert os.listdir(settings_file.parent) == ["settings.json"]      # no .tmp left


def test_corrupt_file_falls_back_to_defaults(settings_file, caplog):
    settings_file.write_text("{not json")
    with caplog.at_level(logging.WARNING):
        assert settings.load() == settings.DEFAULTS
    assert "using defaults" in caplog.text


def test_file_that_is_not_an_object_falls_back_to_defaults(settings_file):
    settings_file.write_text("[1, 2, 3]")
    assert settings.load() == settings.DEFAULTS


def test_unknown_keys_are_dropped_and_missing_ones_filled_in(settings_file):
    settings_file.write_text(json.dumps({"level": "Normal", "gesture": "clap"}))
    s = settings.load()
    assert s["level"] == "Normal" and "gesture" not in s
    assert s["menu_music"] is True


# ---------------------------------------------------------------- migration
@pytest.fixture
def folders(monkeypatch, tmp_path):
    old, new = tmp_path / "game_folder", tmp_path / "data_folder"
    (old / "models").mkdir(parents=True)
    monkeypatch.setattr(config, "LEGACY_DIR", str(old))
    monkeypatch.setattr(config, "DATA_DIR", str(new))
    return old, new


def test_old_settings_and_model_are_migrated(folders):
    old, new = folders
    (old / "settings.json").write_text('{"input_offset_ms": 30.9}')
    (old / "models" / "hand_landmarker.task").write_bytes(b"model")
    settings.migrate_legacy_files()
    assert json.loads((new / "settings.json").read_text()) == {"input_offset_ms": 30.9}
    assert (new / "models" / "hand_landmarker.task").read_bytes() == b"model"
    assert (old / "settings.json").exists()                  # the old files are left alone


def test_migration_never_overwrites_newer_settings(folders):
    old, new = folders
    (old / "settings.json").write_text('{"input_offset_ms": 1}')
    new.mkdir()
    (new / "settings.json").write_text('{"input_offset_ms": 2}')
    settings.migrate_legacy_files()
    assert json.loads((new / "settings.json").read_text()) == {"input_offset_ms": 2}


def test_no_migration_in_portable_mode_or_packaged_builds(folders, monkeypatch):
    old, new = folders
    (old / "settings.json").write_text("{}")
    monkeypatch.setattr(config, "DATA_DIR", str(old))        # portable: same folder
    settings.migrate_legacy_files()
    monkeypatch.setattr(config, "DATA_DIR", str(new))
    monkeypatch.setattr(config, "LEGACY_DIR", None)          # packaged build
    settings.migrate_legacy_files()
    assert not new.exists()
