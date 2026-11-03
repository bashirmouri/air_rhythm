# Architecture

The game is one Python package, `air_rhythm`, in `src/` (the standard "src layout"). Its
modules are grouped into **layers**. Each layer may only use the layers below it, so the
game rules never depend on how things are drawn, and can be tested without a window,
camera or sound.

```
          app            startup, main loop, crash handling
           │
   ┌───────┼────────┐
   ui   controls    │     ui: widgets and screens      controls: hand tracking, mouse
   │                │
 content            │     generated songs, music and beatmaps
   │                │
  core              │     game rules and timing
   │                │
   └──── system ────┘     config, settings, file locations, logging (used by all)
```

| Layer | May use | Folder |
|---|---|---|
| `system` | nothing else | `src/air_rhythm/system/` |
| `core` | system | `src/air_rhythm/core/` |
| `content` | core, system | `src/air_rhythm/content/` |
| `controls` | system | `src/air_rhythm/controls/` |
| `ui` | core, content, system | `src/air_rhythm/ui/` |
| `app` | everything | `src/air_rhythm/app.py` |

These rules are enforced by `tests/unit/test_architecture.py`: an import that breaks them
fails the tests (and so the GitHub checks). Every module may read the version from
`air_rhythm.__version__`. Imports are always absolute (`from air_rhythm.core.gameplay import
Gameplay`), never relative.

## Modules

| Module | What it does |
|---|---|
| `__init__.py` | `__version__`: the only place the version is written |
| `__main__.py` | `python -m air_rhythm` |
| `app.py` | Starts pygame, holds the current screen, runs the main loop, draws the cursor and camera preview; startup and crash handling |
| **core** | |
| `core/gameplay.py` | Rules: hit windows, score, combo, accuracy, health, grades |
| `core/beatmap.py` | Beatmap format + osu! difficulty formulas (AR, CS, OD) |
| `core/clock.py` | Song clock: timing comes from a high-precision clock, never from frame counts; pause/resume, and re-syncing to the music after a resume |
| `core/playfield.py` | osu!'s 512×384 playfield ↔ window pixels |
| **content** | |
| `content/audio_gen.py` | Synthesizes the song, the menu music, the metronome and the hitsound with NumPy |
| `content/map_gen.py` | Places circles on the song's beats and melody, one beatmap per level; makes sure all generated files exist and aren't damaged |
| **controls** | |
| `controls/hand_tracker.py` | Background thread: webcam, MediaPipe, pinch detection, One Euro filter, cursor smoothing, safe model download |
| `controls/inputs.py` | One interface for hand and mouse, so the game doesn't care which is used |
| **ui** | |
| `ui/widgets.py` | Fonts, text, panels and the menu widgets (Play card, option rows, choice and - / + rows, demo circle) |
| `ui/screens/base.py` | Shared logic for screens made of buttons (hover, click, pinch) |
| `ui/screens/menu.py` | Main menu |
| `ui/screens/play.py` | Gameplay: circles, approach circles, animations, HUD, timing meter; playing / paused / countdown states |
| `ui/screens/pause.py` | The pause card (Resume / Retry / Quit), drawn by the gameplay screen over the frozen song |
| `ui/screens/results.py` | Results after a song |
| `ui/screens/calibration.py` | Measures the player's input delay with a metronome |
| `ui/screens/settings.py` | Volumes, sound and input delay, camera and hand tracking, display; changes apply live (`App.apply_settings()`) |
| **system** | |
| `system/config.py` | Tuning values and where files live (data folder, portable mode, packaged build) |
| `system/settings.py` | Saved player settings, what values are allowed; one-time migration from old versions |
| `system/diagnostics.py` | Log file, startup facts for bug reports, the error window |

A **screen** is any object with `handle(events)`, `update()` and `draw(surface)`; `app.py`
switches screens with `app.goto(screen)`. New screens go in `ui/screens/`, one file each.
Screens that need each other in a loop (menu → play → results → menu) import the next one
inside the method that switches to it, to avoid circular imports.

## Keeping it maintainable

Checked automatically on every push (tests + `ruff check`):

- **Layers** only import downwards (`tests/unit/test_architecture.py`).
- **Complexity:** no function may have more than 12 decision points (ruff `C901`). If one
  grows past that, split it into named steps, like `PlayScreen.draw()` (beat pulse, circles,
  hit animations, judgments). The one exception is `make_first_steps()`, the song's score,
  which reads best bar by bar in one place.
- **Logic separate from devices:** anything that decides something (a pinch, a hit, an
  offset) lives in a function that can be called without a camera, window or sound, e.g.
  `HandTracker._on_frame()` gets one frame's hand landmarks; the camera loop only feeds it.
- **Line endings** are LF in every file on every OS (`.gitattributes`).

## Outside the package

| Folder | What's in it |
|---|---|
| `tests/unit/` | Fast tests of single modules (no window or camera) |
| `tests/integration/` | Tests that start the whole game in its own process |
| `tests/data/` | Recorded test data (real webcam frame timing) |
| `packaging/` | PyInstaller recipe (`air_rhythm.spec`) and the `.exe` entry point |
| `tools/` | Build, packaged-game check, release notes, icon |
| `docs/` | This file, development and release guides |
| `.github/workflows/` | Tests on every push; release builds from version tags |

## Where files live at runtime

| | Running from source | Packaged game |
|---|---|---|
| Code and `resources/` | `src/air_rhythm/` | inside `AirRhythm/_internal/` |
| Settings, generated audio/maps, model, log | per-user data folder (see README) | same |
| Pre-generated audio/maps, hand model | generated / downloaded on first start | shipped in `_internal/`, copied or used in place |
| Portable mode folder | the project folder | next to `AirRhythm.exe` |

All of this is decided in `system/config.py`.
