# Air Rhythm

An osu!-style rhythm game played with your hand in front of a webcam. Aim with the
point between your thumb and index finger, and **pinch** to hit circles on the beat.

## Play it (Windows, no Python needed)

1. Download `AirRhythm-<version>-windows-x64.zip` from the
   [Releases page](https://github.com/bashirmouri/air_rhythm/releases).
2. Unzip it anywhere and run `AirRhythm\AirRhythm.exe`.

The first start takes a few seconds longer; later starts take about a second.
Windows may show a SmartScreen warning because the game isn't code-signed: click
*More info* → *Run anyway*. Everything the game needs is in the zip, so it works offline.

## Run from source

Needs Python 3.12–3.15 (the range where every dependency ships pre-built wheels).

```bash
pip install -r requirements.txt   # exact, tested versions (see the comments in the file)
python main.py              # webcam (hand) mode
python main.py --mouse      # mouse + left click / Z / X, no camera needed
python main.py --autoplay   # watch a perfect play
python main.py --portable   # keep settings and game files next to the game
```

On first launch the game generates its song, beatmaps and menu music (a few seconds) and downloads
the MediaPipe hand model (~8 MB).

## Build the Windows release

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python tools\build.py
```

This makes `dist\AirRhythm\` (with `AirRhythm.exe`) and `dist\AirRhythm-<version>-windows-x64.zip`.
The build checks that the pinned versions are installed, pre-generates the audio and beatmaps,
bundles the checksum-verified hand model, and adds every bundled package's license files.
`requirements-lock.txt` lists the exact set of packages the release was built with.

To release a new version: bump `version.py`, add a section to `CHANGELOG.md`, build, and tag
the commit (`git tag v0.2.0`).

## Where files are saved

Settings, the generated songs and beatmaps, the hand model and the log live in a per-user folder,
not next to the game:

| OS | Folder |
|---|---|
| Windows | `%LOCALAPPDATA%\AirRhythm` |
| macOS | `~/Library/Application Support/AirRhythm` |
| Linux | `~/.local/share/air-rhythm` (or `$XDG_DATA_HOME/air-rhythm`) |

**Portable mode** keeps everything next to the game instead: start with `--portable`, or put an
empty file named `portable.txt` in the game folder. `AIR_RHYTHM_DATA_DIR` overrides the folder.
Settings and the hand model from older versions (saved next to the game) are copied over on first start.

Damaged files fix themselves: a half-written song or beatmap is regenerated on the next start,
and a broken hand model is downloaded again.

**Problems?** The log `air_rhythm.log` in that folder records what happened. If the game hits an
unexpected error it shows where the log is (press **L** in the error window to open the folder).
Please attach it when you report a bug.

**First thing to do:** open *Calibrate offset* from the menu. Webcams add 50-150 ms of delay;
calibration measures it and the game subtracts it from every hit.

## Controls

| Key | Action |
|---|---|
| Pinch / click / Z / X | Hit, or press a menu button |
| Enter | Play |
| L | Switch level: Easy / Normal |
| C | Calibrate |
| I | Switch hand / mouse input |
| N | No-fail on/off |
| M | Menu music on/off |
| V | Show/hide camera view |
| F11 | Fullscreen |
| Esc | Back / quit |

## How it works (file by file)

| File | What it does |
|---|---|
| `main.py` | Starts pygame, holds the current screen, runs the main loop, draws the cursor |
| `diagnostics.py` | Log file, startup info for bug reports, the error window shown instead of a crash |
| `hand_tracker.py` | Background thread: webcam, MediaPipe, pinch detection, One Euro smoothing |
| `inputs.py` | Same interface for hand and mouse, so the game doesn't care which one you use |
| `clock.py` | Song clock: timing comes from a high-precision clock, never from frame counts |
| `gameplay.py` | Rules: hit windows, score, combo, accuracy, health. No drawing, easy to test |
| `play_screen.py` | Draws circles, approach circles, animations, HUD and the timing meter |
| `screens.py` | Menu, results and calibration screens |
| `beatmap.py` | Beatmap format + osu! difficulty formulas (AR, CS, OD) |
| `audio_gen.py` | Synthesizes the song, the menu music, the metronome and the hitsound with NumPy |
| `map_gen.py` | Places circles on the song's beats and melody, one beatmap per level (`LEVELS`) |
| `config.py` | All tuning values (pinch thresholds, smoothing, active zone...) and the data folder location |
| `version.py` | The version number (the only place it's written) |
| `tools/build.py`, `air_rhythm.spec` | Builds the standalone Windows game and its zip |
| `tools/make_icon.py` | Draws the app icon (`resources/icon.png`, `icon.ico`) |

## Tuning tips

- **Pinch fires too easily / not at all:** change `PINCH_CLOSE` and `PINCH_OPEN` in `config.py`.
- **Cursor shaky:** lower `FILTER_MIN_CUTOFF`. **Cursor lags on jumps:** raise `FILTER_BETA`.
  **Cursor choppy:** raise `CURSOR_SMOOTHING_MS` (smoother, but trails your hand more).
  **Cursor feels late:** lower it (`0` = raw camera positions).
- **Too much arm movement:** shrink `ACTIVE_ZONE` (the white box in the camera view).
- **Lighting:** a bright, even light on your hand makes tracking far more stable.

## Levels

*First Steps* comes in two levels, chosen with the **Level** button (or **L**) in the menu:

- **Easy** (default): 60 circles, never faster than one per second, bigger circles that
  appear earlier, looser timing and shorter jumps.
- **Normal**: 128 circles that follow the melody in the drop.

To add a level, add an entry to `LEVELS` in `map_gen.py` (and a rule in `note_onsets`).
Missing beatmaps are generated on the next launch.

## Beatmap format

`maps/<song>/beatmap.json` next to its audio file. Positions use osu!'s 512x384 playfield
and AR/CS/OD/HP mean the same as in osu!, so an `.osu` importer can output this format directly.

## Next steps

- Song select + loading songs from other sources (`.osu` import)
- Sliders and spinners
- Pause menu, settings screen, skins

## License

Air Rhythm is released under the [MIT License](LICENSE). It uses pygame-ce (LGPL 2.1),
MediaPipe and its hand model (Apache 2.0), OpenCV (Apache 2.0) and NumPy (BSD); see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). All music and sounds are generated by
the game's own code.

**Privacy:** the camera image is processed on your computer only. It is never saved or sent
anywhere; the only network access is the one-time download of the hand model.
