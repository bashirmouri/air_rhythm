# Changelog

All notable changes to Air Rhythm. The version number lives in `src/air_rhythm/__init__.py`.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Setup guide** on the first start in hand mode (also in Settings > *Setup guide*):
  1. *Set up your camera*: a large camera view and a live checklist: camera on (and its
     frame rate), enough light, hand found, each with what to do if it isn't.
  2. *Try a pinch*: aim at three circles and pinch them; a pinch outside the circle says so.
  3. *Measure your delay*: straight into calibration, or later.
  Skippable at every step, or left for mouse play. Players updating from an earlier version
  have set up already and don't see it.
- **Tracking hints**: the game watches the camera's frame rate and brightness and how often
  the hand is lost, and says what would help: "Too dark for good tracking: turn on a light in
  front of you", "Camera is slow (14 fps): ...", "Hand keeps getting lost: ...". Shown at the
  top during a song (only while playing) and in the menu's status corner (there without the
  hand-lost hint, since lowering your hand in a menu is normal). Judged only after the camera
  has warmed up for 3 s, and brightness is averaged so a single flicker doesn't count.
- The main button of each step (e.g. *Next*) is highlighted.

### Fixed
- The packaged-game check used by release builds looked for the old camera log messages
  ("Camera 0 opened" / "Could not open the webcam"), renamed with the Settings screen; the
  next release build would have failed it.
- **Settings screen** (Settings in the menu, or S), with a large live camera view:
  - **Audio:** song, hitsound and menu music volume (menu music can be turned off).
  - **Timing:** a separate **sound delay** for Bluetooth headphones (they play sound
    ~150-250 ms late) next to the input delay, and *Measure input delay* (calibration, which
    now leaves the sound delay out of what it measures). Circles are drawn and judged on the
    song as you hear it, so with the sound delay set they line up with the music.
  - **Camera & hand:** which camera (1-4), hand area (Small / Medium / Large: how much arm
    movement covers the playfield), pinch sensitivity and cursor smoothing. Hand settings
    take effect immediately, without restarting the camera; switching camera restarts it,
    and a camera that doesn't exist shows a clear message instead of failing.
  - **Display:** fullscreen (also F11, now remembered), camera view in game, FPS counter.
  - Everything works by pinch or click; options are picked directly (no cycling), and
    volumes and delays have - / + buttons. Changes apply right away and are saved on exit.
  - Saved values are checked when loading: anything out of range or unknown (a hand-edited
    `settings.json`, or one from a newer version) falls back to the default with a log entry.
- The menu's *Calibrate offset* row is now **Settings**; calibration lives inside it
  (C still opens it from the menu).
- **Pause menu.** Esc during a song now pauses instead of quitting: **Resume**, **Retry** or
  **Quit to menu**, by pinch, click or key (Esc / Enter / Space resume, R retry, Q quit). The
  mouse works on it in hand mode too. The song also pauses by itself when the window loses
  focus (alt-tab, clicking another window) or is minimized.
- After resuming, a 3-2-1 countdown (1.8 s) before the song carries on, with a ring marking
  where your cursor was, so you can bring your hand back first. Pinches during the pause or
  the countdown never count as hits.
- Pausing doesn't shift timing: song time stops exactly while paused, and because the music
  can only pause and resume on its next audio buffer (~12 ms), the game measures the music's
  real position after each resume and corrects for it. Measured over 10 pauses: within
  ±2 ms of an unpaused song (without the correction it wandered up to 14 ms).

### Project
- Automated test suite (93 tests, `python -m pytest`): game rules, beatmaps, generated maps,
  hand tracking and cursor smoothing, model download, settings, packaged-build paths,
  startup failures and a full autoplay run through every screen.
- Tests run automatically on every push on Windows, Linux and macOS with Python 3.12-3.15.
- Releases are built by GitHub from a version tag: tests, build, a check that the built game
  starts, then a draft release with the zip and notes taken from this changelog.
- Code checks with ruff (`python -m ruff check .`) on every push. Fixed what it found: a
  helper in the song generator that captured a loop variable, and pairs of lists that
  must have the same length are now checked (`zip(..., strict=True)`). Generated songs
  and beatmaps are unchanged.
- The code is now one installable package, `air_rhythm`, in `src/`, organized in layers:
  `core` (game rules), `content` (generated songs and maps), `controls` (hand and mouse),
  `ui` (widgets, one file per screen), `system` (config, settings, logging) and `app`.
  A test enforces that lower layers never import higher ones. Run from source with
  `pip install -e .` and `python -m air_rhythm` (was `python main.py`).
- Tests are split into `tests/unit` (fast) and `tests/integration` (whole game); packaging
  moved to `packaging/`; developer docs moved from the README to `docs/` (architecture,
  development, releasing). Nothing changes for players.
- Maintenance pass: the hand tracker's per-frame logic moved out of the camera loop
  (`_on_frame()`), and `PlayScreen.draw()` was split into named steps (verified pixel-identical
  over 270 gameplay frames). New tests for menu buttons (mouse in hand mode, pinching),
  calibration's offset calculation, mouse/keyboard hits and the tracker's frame logic. Ruff
  now also limits function complexity. Line endings are normalized (`.gitattributes`).
  Removed unused code (`FIRST_MAP_PATH`, `HandTracker.fps`).

## [0.1.0] - 2026-11-02

First versioned release.

### Gameplay
- osu!-style hit circles played with your hand in front of a webcam: aim with the point
  between thumb and index finger, pinch to hit. Mouse mode (click / Z / X) and autoplay.
- Song "First Steps" (120 BPM), generated by the game's own synthesizer, in two levels:
  **Easy** (60 circles, at most one per second, bigger circles, looser timing) and
  **Normal** (128 circles following the melody).
- Calibration screen that measures and removes webcam/audio delay.
- Results screen with grade, accuracy, max combo, average timing and unstable rate.

### Main menu
- Modern two-column design: gradient Play card showing song and level, setting rows
  that show their value (segmented controls, toggle), animated hit-circle preview,
  camera status pill and keyboard hints.
- Calm looping menu music that fades in on the menu and out when you play (M mutes it).
- The mouse always works on menu screens, even in hand mode, so you can switch input
  when the camera doesn't work.

### Smoothness
- Hand cursor glides at an even speed even though webcams deliver frames unevenly
  (`CURSOR_SMOOTHING_MS`, default 60 ms); hits still use the exact capture-time position.
- Frame pacing follows vsync (no limiter fighting it), circle images are built before the
  song starts, and menu text/panels are cached: no dropped frames in testing at 60 Hz.

### Reliability
- Settings, generated audio/beatmaps, the hand model and the log live in a per-user
  data folder (`%LOCALAPPDATA%\AirRhythm` on Windows); `--portable` keeps them next to
  the game. Settings and the model from earlier builds are migrated.
- Hand model download is pinned, hash-checked, resumable after interruption and explains
  when there's no internet.
- Log file with startup diagnostics; an error window replaces silent crashes; damaged
  files are regenerated; the game runs silently when there is no sound device.

### Project
- MIT license, third-party notices, privacy note.
- Pinned dependency versions and supported Python 3.12–3.15.
- Standalone Windows build (no Python needed).
