"""Procedural audio, synthesized with NumPy:
  - "First Steps", the first song (120 BPM, A minor)
  - the calibration metronome
  - the hitsound

Generating the music ourselves means the tempo and every note time are known
exactly, so the beatmap lines up perfectly, and there are no copyright issues.
"""
import os
import wave

import numpy as np

from air_rhythm.system.config import SAMPLE_RATE as SR

# ======================================================================
# Song structure (map_gen.py reads this too, so circles land on the music)
# ======================================================================
BPM = 120
BEAT = 60.0 / BPM            # seconds per beat (0.5 s)
BAR = 4 * BEAT               # 4 beats per bar (2 s)
SECTIONS = [                 # (name, first bar, number of bars)
    ("intro", 0, 4),
    ("verse", 4, 8),
    ("build", 12, 8),
    ("break", 20, 4),
    ("drop", 24, 8),
    ("outro", 32, 4),
]
N_BARS = 36
SONG_TAIL = 3.0              # seconds of ring-out after the last bar

# Chord progression Am - F - C - G as (bass root, chord notes), MIDI note numbers
PROGRESSION = [(45, (57, 60, 64)), (41, (53, 57, 60)),
               (48, (55, 60, 64)), (43, (55, 59, 62))]
# 8th-note arpeggio for each chord
ARPS = [[69, 72, 76, 72, 69, 72, 76, 79],
        [65, 69, 72, 69, 65, 69, 72, 77],
        [67, 72, 76, 72, 67, 72, 76, 79],
        [67, 71, 74, 71, 67, 71, 74, 79]]
# Lead melody in the drop, per chord: (beat in bar, MIDI note, length in beats)
DROP_MELODY = [
    [(0, 76, 1), (1, 74, .5), (1.5, 72, .5), (2, 69, 1), (3, 72, 1)],
    [(0, 72, 1), (1, 74, .5), (1.5, 72, .5), (2, 69, 1.5), (3.5, 65, .5)],
    [(0, 67, 1), (1, 72, 1), (2, 76, 1), (3, 74, .5), (3.5, 72, .5)],
    [(0, 71, 1.5), (1.5, 74, .5), (2, 79, 1), (3, 76, 1)],
]

# Calibration metronome
CALIB_BEAT_MS = 600          # 100 BPM
CALIB_FIRST_MS = 1000        # first click 1 s after the track starts
CALIB_COUNT_IN = 4           # first 4 clicks: just listen
CALIB_TAPS = 16              # then pinch on these 16


def section_of(bar):
    for name, start, length in SECTIONS:
        if start <= bar < start + length:
            return name
    return "end"


# ======================================================================
# Basic building blocks
# ======================================================================
def _t(duration):
    """Time axis (seconds) for a sound of the given duration."""
    return np.arange(int(duration * SR)) / SR


def midi_to_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _saw(freq, t, harmonics=8):
    """Sawtooth built from a few harmonics (naturally soft, no filter needed)."""
    out = np.zeros_like(t)
    for k in range(1, harmonics + 1):
        if freq * k > SR / 2:
            break
        out += np.sin(2 * np.pi * freq * k * t) / k
    return out * (2 / np.pi)


def _square(freq, t, harmonics=9):
    out = np.zeros_like(t)
    for k in range(1, harmonics + 1, 2):
        if freq * k > SR / 2:
            break
        out += np.sin(2 * np.pi * freq * k * t) / k
    return out * (4 / np.pi)


def _fade_out(sig, seconds):
    n = min(len(sig), int(seconds * SR))
    if n > 0:
        sig[-n:] *= np.linspace(1, 0, n)
    return sig


class _Mix:
    """A stereo buffer we can drop sounds into at given times."""

    def __init__(self, duration):
        self.buf = np.zeros((int(duration * SR), 2))

    def add(self, start_s, sig, gain=1.0, pan=0.0):
        i = int(round(start_s * SR))
        if i >= len(self.buf):
            return
        n = min(len(sig), len(self.buf) - i)
        angle = (pan + 1) * np.pi / 4          # equal-power panning
        self.buf[i:i + n, 0] += sig[:n] * gain * np.cos(angle) * np.sqrt(2)
        self.buf[i:i + n, 1] += sig[:n] * gain * np.sin(angle) * np.sqrt(2)


# ======================================================================
# Instruments
# ======================================================================
def kick():
    t = _t(0.4)
    freq = 42 + 110 * np.exp(-t / 0.035)            # pitch drops fast: "thump"
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t / 0.16)
    click = np.random.default_rng(1).standard_normal(len(t)) * np.exp(-t / 0.002) * 0.3
    return np.tanh(1.5 * (body + click))


def snare():
    t = _t(0.3)
    noise = np.diff(np.random.default_rng(2).standard_normal(len(t)), prepend=0) * 0.5
    tone = np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.04)
    return 0.6 * noise * np.exp(-t / 0.07) + 0.5 * tone


def hat(open_=False):
    t = _t(0.3 if open_ else 0.06)
    n = np.random.default_rng(3).standard_normal(len(t))
    bright = np.diff(np.diff(n, prepend=0), prepend=0) / 4   # crude high-pass
    return bright * np.exp(-t / (0.09 if open_ else 0.014))


def crash():
    t = _t(1.6)
    n = np.random.default_rng(4).standard_normal(len(t))
    return np.diff(n, prepend=0) * 0.35 * np.exp(-t / 0.55)


def bass(midi, dur):
    t = _t(dur)
    f = midi_to_hz(midi)
    sig = 0.6 * _saw(f, t, 6) + 0.6 * np.sin(2 * np.pi * f * t)
    env = np.minimum(1, t / 0.005) * np.exp(-t / 0.3)
    return _fade_out(sig * env, 0.01)


def pluck(midi, dur):
    t = _t(dur * 1.6)
    f = midi_to_hz(midi)
    sig = 0.5 * _square(f, t) + 0.3 * np.sin(2 * np.pi * 2 * f * t)
    env = np.minimum(1, t / 0.002) * np.exp(-t / 0.18)
    return _fade_out(sig * env, 0.02)


def pad(midis, dur):
    release = 0.6
    t = _t(dur + release)
    sig = np.zeros_like(t)
    for m in midis:
        f = midi_to_hz(m)
        sig += _saw(f * 1.003, t, 5) + _saw(f * 0.997, t, 5)   # two detuned voices = wide sound
    env = np.minimum(1, t / 0.35) * np.clip((dur + release - t) / release, 0, 1)
    return sig * env / (2 * len(midis))


def lead(midi, dur):
    release = 0.15
    t = _t(dur + release)
    f = midi_to_hz(midi)
    vibrato = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.minimum(1, t / 0.25)
    phase = 2 * np.pi * np.cumsum(f * vibrato) / SR
    sig = 0.5 * np.sin(phase) + 0.5 * sum(np.sin(k * phase) / k for k in range(1, 7))
    env = (np.minimum(1, t / 0.01) * (0.7 + 0.3 * np.exp(-t / 0.15))
           * np.clip((dur + release - t) / release, 0, 1))
    return sig * env


# ======================================================================
# Compositions
# ======================================================================
def make_first_steps():  # noqa: C901 -- the song's score, bar by bar: reads best in one place
    """Returns the song as a float stereo array in [-1, 1]."""
    mix = _Mix(N_BARS * BAR + SONG_TAIL)
    K, S, H, OH, CR = kick(), snare(), hat(), hat(open_=True), crash()

    for bar in range(N_BARS):
        sec = section_of(bar)
        t0 = bar * BAR
        ci = bar % 4
        root, chord = PROGRESSION[ci]

        def at(beat, t0=t0):                        # t0 bound now, not looked up later
            return t0 + beat * BEAT

        fade = 1 - (bar - 32) / 5 if sec == "outro" else 1.0

        # pad chords (every section)
        pad_gain = {"intro": .5, "verse": .35, "build": .3, "break": .5,
                    "drop": .28, "outro": .45}[sec]
        mix.add(t0, pad(chord, BAR), pad_gain * fade)

        # drums
        if sec in ("intro", "outro"):
            for beat in (0, 2):
                mix.add(at(beat), K, (.55 if sec == "intro" else .7) * fade)
        if sec in ("verse", "build", "drop"):
            for beat in range(4):
                mix.add(at(beat), K, .9)
        if sec in ("verse", "build"):
            for beat in range(4):
                mix.add(at(beat + .5), H, .35, pan=.25)
        if sec == "drop":
            for s in range(16):
                mix.add(at(s / 4), H, .3 if s % 2 else .15, pan=.25)
            for beat in range(4):
                mix.add(at(beat + .5), OH, .18, pan=-.2)
        if sec in ("build", "drop"):
            for beat in (1, 3):
                mix.add(at(beat), S, .55)
        if sec == "build" and bar % 2 == 1:
            mix.add(at(3.5), S, .3)                 # extra hit -> extra circle in the map
        if sec == "break" and bar == 23:            # snare roll + noise riser into the drop
            for s in range(16):
                mix.add(at(s / 4), S, .08 + .4 * s / 15)
            t = _t(BAR)
            riser = np.diff(np.random.default_rng(5).standard_normal(len(t)), prepend=0)
            mix.add(t0, riser * (t / BAR) ** 2, .25)
        if bar in (4, 24):
            mix.add(t0, CR, .4)

        # bass (8th notes, octave jumps in the drop)
        if sec in ("verse", "build", "drop"):
            for e in range(8):
                note = root + (12 if sec == "drop" and e % 2 else 0)
                mix.add(at(e / 2), bass(note, BEAT / 2 * .92), .5)

        # arpeggio
        if sec in ("build", "break", "drop", "outro"):
            g = {"build": .22, "break": .2, "drop": .12, "outro": .15}[sec] * fade
            for e, n in enumerate(ARPS[ci]):
                mix.add(at(e / 2), pluck(n, BEAT / 2), g, pan=.35 if e % 2 else -.35)

        # lead melody
        if sec == "drop":
            for beat, n, d in DROP_MELODY[ci]:
                mix.add(at(beat), lead(n, d * BEAT), .32)

    return _master(mix.buf, 0.9)


# ======================================================================
# Menu music: a calm loop in the same key and chords as First Steps
# ======================================================================
MENU_BPM = 80
MENU_BEAT = 60.0 / MENU_BPM      # 0.75 s
MENU_BAR = 4 * MENU_BEAT         # 3 s
MENU_BARS = 16                   # 48 s loop
# Am9 - Fmaj7 - Cmaj7 - G6 as (bass root, chord notes)
MENU_CHORDS = [(45, (57, 60, 64, 67, 71)), (41, (53, 57, 60, 64)),
               (48, (55, 59, 60, 64)), (43, (55, 59, 62, 64))]
MENU_BELLS = [[69, 72, 76, 79, 76, 72, 71, 72],      # bell arpeggio, one note per 8th
              [65, 69, 72, 76, 72, 69, 67, 69],
              [67, 71, 72, 76, 72, 71, 67, 64],
              [67, 71, 74, 76, 74, 71, 67, 62]]
MENU_MELODY = [[(0, 76, 1.5), (1.5, 74, .5), (2, 72, 2)],    # (beat, note, length in beats)
               [(0, 72, 1.5), (1.5, 69, .5), (2, 67, 2)],
               [(0, 67, 1), (1, 72, 1), (2, 76, 2)],
               [(0, 74, 3), (3, 71, 1)]]


def soft_pad(midis, dur):
    """Warm pad: detuned sines with a slow swell and long release (no buzz)."""
    release = 1.6
    t = _t(dur + release)
    sig = np.zeros_like(t)
    for m in midis:
        f = midi_to_hz(m)
        sig += (np.sin(2 * np.pi * f * 1.002 * t) + np.sin(2 * np.pi * f * 0.998 * t)
                + 0.15 * np.sin(2 * np.pi * 2 * f * t))
    tremolo = 1 + 0.08 * np.sin(2 * np.pi * 0.35 * t)
    env = np.minimum(1, t / 1.0) * np.clip((dur + release - t) / release, 0, 1)
    return sig * env * tremolo / (2 * len(midis))


def sub_bass(midi, dur):
    release = 0.8
    t = _t(dur + release)
    env = np.minimum(1, t / 0.08) * np.clip((dur + release - t) / release, 0, 1)
    return np.sin(2 * np.pi * midi_to_hz(midi) * t) * env


def bell(midi, dur=1.6):
    """Soft mallet/kalimba tone: sine plus a quiet bright partial that dies fast."""
    t = _t(dur)
    f = midi_to_hz(midi)
    sig = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 3 * f * t) * np.exp(-t / 0.08)
    return sig * np.minimum(1, t / 0.004) * np.exp(-t / 0.45)


def soft_lead(midi, dur):
    release = 0.5
    t = _t(dur + release)
    vibrato = 1 + 0.003 * np.sin(2 * np.pi * 5 * t) * np.minimum(1, t / 0.4)
    phase = 2 * np.pi * np.cumsum(midi_to_hz(midi) * vibrato) / SR
    sig = np.sin(phase) + 0.2 * np.sin(2 * phase) + 0.08 * np.sin(3 * phase)
    env = np.minimum(1, t / 0.09) * np.clip((dur + release - t) / release, 0, 1)
    return sig * env


def _echo(buf, delay_s, feedback, repeats):
    """Repeating echo with alternating left/right repeats (cheap, spacious 'reverb')."""
    out = buf.copy()
    d = int(delay_s * SR)
    for k in range(1, repeats + 1):
        if k * d >= len(buf):
            break
        g = feedback ** k
        src = buf[:len(buf) - k * d]
        if k % 2:                                   # ping-pong: swap channels on odd repeats
            src = src[:, ::-1]
        out[k * d:] += src * g
    return out


def make_menu_music():
    """A smooth 48 s loop for the main menu. The tail is wrapped onto the start,
    so it loops without a gap or click. Returns float stereo in [-1, 1]."""
    loop = MENU_BARS * MENU_BAR
    tail = 6.0
    dry, wet = _Mix(loop + tail), _Mix(loop + tail)  # wet = sent through the echo
    K, BRUSH = kick(), hat(open_=True)

    for bar in range(MENU_BARS):
        t0 = bar * MENU_BAR
        ci = bar % 4
        root, chord = MENU_CHORDS[ci]
        second_half = bar >= 8

        dry.add(t0, soft_pad(chord, MENU_BAR), .55)
        dry.add(t0, sub_bass(root, MENU_BAR * .9), .32)
        dry.add(t0 + 2.5 * MENU_BEAT, sub_bass(root + 7, MENU_BEAT * 1.2), .14)   # passing fifth

        if bar >= 2:                                 # bells come in after the pad swells up
            g = .16 if bar < 4 else .2
            for e, n in enumerate(MENU_BELLS[ci]):
                if bar < 4 and e % 2:                # sparser at first
                    continue
                wet.add(t0 + e * MENU_BEAT / 2, bell(n), g, pan=.4 if e % 2 else -.4)

        if second_half:
            for beat, n, d in MENU_MELODY[ci]:
                wet.add(t0 + beat * MENU_BEAT, soft_lead(n, d * MENU_BEAT), .15, pan=.1)
            for beat in (0, 2.5):                    # soft, laid-back kick
                dry.add(t0 + beat * MENU_BEAT, K, .22)
            for beat in (1, 3):                      # brushed backbeat
                dry.add(t0 + beat * MENU_BEAT, BRUSH, .07, pan=-.3)

    buf = dry.buf + _echo(wet.buf, MENU_BEAT * .75, .38, 6)
    buf[:int(tail * SR)] += buf[int(loop * SR):int(loop * SR) + int(tail * SR)]   # wrap the tail
    return _master(buf[:int(loop * SR)], 0.6)


def make_calibration():
    n_beats = CALIB_COUNT_IN + CALIB_TAPS
    mix = _Mix(CALIB_FIRST_MS / 1000 + n_beats * CALIB_BEAT_MS / 1000 + 1.0)
    t = _t(0.1)
    for i in range(n_beats):
        f = 1500 if i < CALIB_COUNT_IN else 1000      # higher pitch during the count-in
        click = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.025)
        mix.add(CALIB_FIRST_MS / 1000 + i * CALIB_BEAT_MS / 1000, click)
    return _master(mix.buf, 0.8)


def make_hitsound():
    """Short soft 'tock', returned as int16 stereo (ready for pygame.sndarray)."""
    t = _t(0.12)
    noise = np.diff(np.random.default_rng(6).standard_normal(len(t)), prepend=0)
    sig = (np.sin(2 * np.pi * 900 * t) * np.exp(-t / 0.03)
           + 0.25 * noise * np.exp(-t / 0.004))
    sig = sig / np.max(np.abs(sig)) * 0.7
    stereo = np.stack([sig, sig], axis=1)
    return np.ascontiguousarray((stereo * 32767).astype(np.int16))


def _master(buf, peak):
    buf = np.tanh(buf * 1.1)                      # gentle soft clipping
    return buf / (np.max(np.abs(buf)) + 1e-9) * peak


def write_wav(path, stereo):
    """Write to a temporary file, then swap it in: a crash or full disk mid-write
    never leaves a half-written file behind."""
    data = (np.clip(stereo, -1, 1) * 32767).astype(np.int16)
    tmp = path + ".tmp"
    try:
        with wave.open(tmp, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(data.tobytes())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def wav_is_valid(path):
    """True if the file is a readable WAV whose audio data is all there (not truncated)."""
    try:
        with wave.open(path, "rb") as w:
            frames, frame_bytes = w.getnframes(), w.getnchannels() * w.getsampwidth()
        return frames > 0 and os.path.getsize(path) >= 44 + frames * frame_bytes
    except (OSError, EOFError, wave.Error):
        return False
