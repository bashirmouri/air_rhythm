"""Song clock: the single source of truth for 'where are we in the song'.

Rhythm games must never count frames for timing (frame times jitter). Instead
we note the exact moment the music started and measure from there with
time.perf_counter(), a high-precision clock.
"""
import time

import pygame


class SongClock:
    def __init__(self):
        self.start_t = None
        self._pending = False

    def start(self, audio_path, lead_in_ms):
        # Without a sound device the clock still runs (silent play); only the music is skipped.
        self.audio = pygame.mixer.get_init() is not None
        if self.audio:
            pygame.mixer.music.load(audio_path)
        # Song time is negative during the lead-in, then 0 when the music starts.
        self.start_t = time.perf_counter() + lead_in_ms / 1000
        self._pending = True

    def update(self):
        if self._pending and time.perf_counter() >= self.start_t:
            if self.audio:
                pygame.mixer.music.play()
            self.start_t = time.perf_counter()   # re-align to the real start
            self._pending = False

    def now_ms(self, t=None):
        """Song time in ms for perf_counter time t (default: now)."""
        if t is None:
            t = time.perf_counter()
        return (t - self.start_t) * 1000

    def stop(self, fade_ms=0):
        if not getattr(self, "audio", False):
            return
        if fade_ms:
            pygame.mixer.music.fadeout(fade_ms)
        else:
            pygame.mixer.music.stop()
