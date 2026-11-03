# Development

## Setup

Python 3.12–3.15. From the project folder:

```bash
python -m venv .venv
.venv\Scripts\activate                 # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt    # exact versions (requirements.txt + test/build tools)
pip install -e .                       # the game as an editable package: code changes apply right away
```

`requirements.txt` pins what the game needs, `requirements-dev.txt` adds pytest, ruff and the
build tools, and `requirements-lock.txt` is the full, exact set releases are built with.
MediaPipe changes its API between releases: upgrade on purpose, then run the tests.

## Run

```bash
python -m air_rhythm              # hand mode (webcam)
python -m air_rhythm --mouse      # mouse + left click / Z / X, no camera needed
python -m air_rhythm --autoplay   # watch a perfect play
python -m air_rhythm --portable   # keep settings and generated files in the project folder
```

(`air-rhythm` does the same once the package is installed.) On first launch the game
generates its songs, beatmaps and menu music (a few seconds) and downloads the hand model
(~8 MB). `AIR_RHYTHM_DATA_DIR=<folder>` uses a different data folder, handy for testing
without touching your real settings. `AIR_RHYTHM_QUIT_AFTER_S=10` closes the game after
10 seconds (used by automated checks).

## Tests and checks

```bash
python -m pytest                  # everything, ~2 min
python -m pytest tests/unit       # just the fast ones, ~25 s
python -m ruff check .            # code checks (add --fix for import order)
```

No camera, window, sound or internet needed: SDL runs headless, every test session gets a
throw-away data folder, and the model download is tested against a local web server.
Both run on every push on GitHub (Windows, Linux, macOS × Python 3.12–3.15).

| File | What it checks |
|---|---|
| `tests/unit/test_gameplay.py` | Hit windows, score, combo, accuracy, health, fail/no-fail, grades |
| `tests/unit/test_beatmap.py` | osu! formulas (AR, CS, OD), combo numbers and colors, loading |
| `tests/unit/test_map_gen.py` | Easy/Normal maps (deterministic, on the playfield, rhythm and jump limits), damaged files rebuilt |
| `tests/unit/test_hand_tracker.py` | Pinch detection, filtering, cursor smoothing (with real webcam timing), safe model download |
| `tests/unit/test_settings.py` | Defaults, corrupt files, migration from older versions |
| `tests/unit/test_inputs.py` | Mouse clicks and Z/X as hits; pinches reaching the game; the tracker's per-frame logic (pinch, release, hand briefly lost) |
| `tests/unit/test_screens.py` | Buttons clicked or pinched (mouse works in hand mode); calibration turning taps into an offset |
| `tests/unit/test_architecture.py` | The layer rules in [architecture.md](architecture.md) |
| `tests/integration/test_packaged_build.py` | File locations in the packaged build vs. from source |
| `tests/integration/test_startup.py` | Whole game: first start, no sound device, broken map, crash window, offline |
| `tests/integration/test_smoke.py` | Every screen, and autoplay getting a perfect score on both levels |

## Tuning (`src/air_rhythm/system/config.py`)

- **Pinch fires too easily / not at all:** `PINCH_CLOSE` and `PINCH_OPEN`.
- **Cursor shaky:** lower `FILTER_MIN_CUTOFF`. **Cursor lags on jumps:** raise `FILTER_BETA`.
- **Cursor choppy:** raise `CURSOR_SMOOTHING_MS` (smoother, but trails your hand more).
  **Cursor feels late:** lower it (`0` = raw camera positions).
- **Too much arm movement:** shrink `ACTIVE_ZONE` (the white box in the camera view).

## Levels and the beatmap format

Levels are defined in `LEVELS` in `src/air_rhythm/content/map_gen.py`; the circle rhythm for
each is in `note_onsets`. To add a level, add both; missing beatmaps are generated on the next
launch. A beatmap is a JSON file next to its audio file in the data folder
(`maps/first_steps/easy.json` and `beatmap.json` for Normal). Positions use osu!'s
512×384 playfield and AR/CS/OD/HP mean the same as in osu!, so an `.osu` importer can output
this format directly.

## Build the Windows game locally

```bash
python tools/build.py              # dist\AirRhythm\AirRhythm.exe and dist\AirRhythm-<version>-windows-x64.zip
python tools/smoke_test_build.py   # starts the built game and checks it works
python tools/release_notes.py dist\AirRhythm-<version>-windows-x64.zip   # preview the release notes
```

The build checks the pinned versions, pre-generates the audio and beatmaps, bundles the
checksum-verified hand model, runs PyInstaller with `packaging/air_rhythm.spec`, and adds every
bundled package's license files. Releases themselves are built by GitHub: see
[releasing.md](releasing.md).
