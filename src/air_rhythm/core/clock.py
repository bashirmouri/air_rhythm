"""Song clock: the single source of truth for 'where are we in the song'.

Rhythm games must never count frames for timing (frame times jitter). Instead
we note the exact moment the music started and measure from there with
time.perf_counter(), a high-precision clock.

Pausing freezes song time; resuming moves the start forward by the time spent
paused, so the song carries on exactly where it stopped.

The music itself can't resume exactly on time: the mixer pauses and unpauses at its next
audio buffer (~12 ms), so each pause could shift the music against the clock by up to that,
and over many pauses this adds up. So the clock measures how far it is from the music the
mixer has actually played (get_pos(), which stops counting while paused) once when the song
starts, again after each resume, and corrects itself back to the starting offset.
(Seeking the music to the exact time doesn't work: WAV seeks round down to whole seconds.)
"""
import logging
import statistics
import time

import pygame

log = logging.getLogger(__name__)
SYNC_SAMPLES = 30        # frames measured (~0.5 s) for one clock-vs-music offset


class SongClock:
    def __init__(self):
        self.start_t = None
        self.paused_at = None        # perf_counter time of the pause, or None while running
        self._pending = False
        self.audio = False
        self._sync = None            # offset samples being collected, or None
        self._sync_base = None       # clock-vs-music offset measured when the song started (ms)

    def start(self, audio_path, lead_in_ms):
        # Without a sound device the clock still runs (silent play); only the music is skipped.
        self.audio = pygame.mixer.get_init() is not None
        if self.audio:
            pygame.mixer.music.load(audio_path)
        # Song time is negative during the lead-in, then 0 when the music starts.
        self.start_t = time.perf_counter() + lead_in_ms / 1000
        self._pending = True

    def update(self):
        if self.paused:
            return
        if self._pending and time.perf_counter() >= self.start_t:
            if self.audio:
                pygame.mixer.music.play()
            self.start_t = time.perf_counter()   # re-align to the real start
            self._pending = False
            self._sync = [] if self.audio else None
        elif self._sync is not None:
            self._measure_sync()

    def _measure_sync(self):
        pos = pygame.mixer.music.get_pos()          # ms of music played so far, or -1
        if pos < 0:
            return
        self._sync.append((time.perf_counter() - self.start_t) * 1000 - pos)
        if len(self._sync) < SYNC_SAMPLES:
            return
        offset = statistics.median(self._sync)      # get_pos moves in buffer steps: median evens it out
        self._sync = None
        if self._sync_base is None:
            self._sync_base = offset
        else:                                        # after a resume: undo what the pause shifted
            self.start_t += (offset - self._sync_base) / 1000
            log.debug("Resync after pause: %+.1f ms", offset - self._sync_base)

    @property
    def paused(self):
        return self.paused_at is not None

    def pause(self):
        if self.paused:
            return
        self.paused_at = time.perf_counter()
        if self.audio and not self._pending:     # during the lead-in the music hasn't started
            pygame.mixer.music.pause()

    def resume(self):
        if not self.paused:
            return
        self.start_t += time.perf_counter() - self.paused_at
        self.paused_at = None
        if self.audio and not self._pending:
            pygame.mixer.music.unpause()
            self._sync = []                      # measure afresh (drops one cut short by this pause)

    def now_ms(self, t=None):
        """Song time in ms for perf_counter time t (default: now; frozen while paused)."""
        if t is None:
            t = self.paused_at if self.paused else time.perf_counter()
        return (t - self.start_t) * 1000

    def stop(self, fade_ms=0):
        self.paused_at = None
        if not self.audio:
            return
        if fade_ms:
            pygame.mixer.music.fadeout(fade_ms)
        else:
            pygame.mixer.music.stop()
