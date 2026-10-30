# Air Rhythm

An osu!-style rhythm game played with your hand in front of a webcam. Aim with the
point between your thumb and index finger, and **pinch** to hit circles on the beat.

## Run it

```bash
pip install -r requirements.txt   # installs pygame-ce, a drop-in pygame fork with wheels for new Python versions
python main.py              # webcam (hand) mode
python main.py --mouse      # mouse + left click / Z / X, no camera needed
python main.py --autoplay   # watch a perfect play
```

On first launch the game generates its song and beatmap (a few seconds) and downloads
the MediaPipe hand model (~8 MB).

**First thing to do:** open *Calibrate offset* from the menu. Webcams add 50-150 ms of delay;
calibration measures it and the game subtracts it from every hit.

## Controls

| Key | Action |
|---|---|
| Pinch / click / Z / X | Hit, or press a menu button |
| Enter | Play |
| C | Calibrate |
| I | Switch hand / mouse input |
| N | No-fail on/off |
| V | Show/hide camera view |
| F11 | Fullscreen |
| Esc | Back / quit |

## How it works (file by file)

| File | What it does |
|---|---|
| `main.py` | Starts pygame, holds the current screen, runs the main loop, draws the cursor |
| `hand_tracker.py` | Background thread: webcam, MediaPipe, pinch detection, One Euro smoothing |
| `inputs.py` | Same interface for hand and mouse, so the game doesn't care which one you use |
| `clock.py` | Song clock: timing comes from a high-precision clock, never from frame counts |
| `gameplay.py` | Rules: hit windows, score, combo, accuracy, health. No drawing, easy to test |
| `play_screen.py` | Draws circles, approach circles, animations, HUD and the timing meter |
| `screens.py` | Menu, results and calibration screens |
| `beatmap.py` | Beatmap format + osu! difficulty formulas (AR, CS, OD) |
| `audio_gen.py` | Synthesizes the song, the metronome and the hitsound with NumPy |
| `map_gen.py` | Places circles on the song's beats and melody |
| `config.py` | All tuning values (pinch thresholds, smoothing, active zone...) |

## Tuning tips

- **Pinch fires too easily / not at all:** change `PINCH_CLOSE` and `PINCH_OPEN` in `config.py`.
- **Cursor shaky:** lower `FILTER_MIN_CUTOFF`. **Cursor lags on jumps:** raise `FILTER_BETA`.
- **Too much arm movement:** shrink `ACTIVE_ZONE` (the white box in the camera view).
- **Lighting:** a bright, even light on your hand makes tracking far more stable.

## Beatmap format

`maps/<song>/beatmap.json` next to its audio file. Positions use osu!'s 512x384 playfield
and AR/CS/OD/HP mean the same as in osu!, so an `.osu` importer can output this format directly.

## Next steps

- Song select + loading songs from other sources (`.osu` import)
- Sliders and spinners
- Pause menu, settings screen, skins
