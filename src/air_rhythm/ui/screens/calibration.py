"""Calibration: a metronome to pinch along with, measuring the player's input delay."""
import math
import statistics

import pygame

from air_rhythm.content.audio_gen import CALIB_BEAT_MS, CALIB_COUNT_IN, CALIB_FIRST_MS, CALIB_TAPS
from air_rhythm.content.map_gen import CALIBRATION_AUDIO
from air_rhythm.core.clock import SongClock
from air_rhythm.ui import widgets as ui


class CalibrationScreen:
    """Plays a metronome; you pinch on each click. The median delay between the
    click and your pinch is your offset (camera + processing + audio + reaction
    habits). The game subtracts it from every hit."""

    def __init__(self, app):
        self.app = app
        self.beats = [CALIB_FIRST_MS + i * CALIB_BEAT_MS for i in range(CALIB_COUNT_IN + CALIB_TAPS)]
        self.restart()

    def restart(self):
        self.taps = []
        self.result = None
        self.done = False
        self.clock = SongClock()
        self.clock.start(CALIBRATION_AUDIO, 500)

    def handle(self, events):
        from air_rhythm.ui.screens.menu import MenuScreen  # menu.py imports this file
        for e in events:
            if e.type != pygame.KEYDOWN:
                continue
            if e.key == pygame.K_ESCAPE:
                self.clock.stop()
                self.app.goto(MenuScreen(self.app))
            elif e.key == pygame.K_r:
                self.clock.stop()
                self.restart()
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE) and self.done and self.result is not None:
                self.app.settings["input_offset_ms"] = round(self.result, 1)
                self.app.goto(MenuScreen(self.app))

    def update(self):
        self.clock.update()
        presses = self.app.input.take_presses()
        if self.done:
            return
        for t, _ in presses:
            ms = self.clock.now_ms(t)
            nearest = min(self.beats[CALIB_COUNT_IN:], key=lambda b: abs(ms - b))
            if abs(ms - nearest) <= 250:
                self.taps.append(ms - nearest)
        if self.clock.now_ms() > self.beats[-1] + 800:
            self.done = True
            if len(self.taps) >= 8:
                self.result = statistics.median(self.taps)   # median ignores the odd bad tap

    def draw(self, surf):
        W, H = surf.get_size()
        surf.blit(self.app.background, (0, 0))
        now = self.clock.now_ms()
        ui.text(surf, "Calibration", 64, ui.WHITE, (W // 2, 70))

        past = [b for b in self.beats if b <= now]
        flash = math.exp(-(now - past[-1]) / 120) if past else 0
        counting = len(past) <= CALIB_COUNT_IN
        color = (255, 200, 90) if counting else ui.ACCENT
        pygame.draw.circle(surf, ui.lerp_color((60, 55, 80), color, flash), (W // 2, 300),
                           int(80 + 25 * flash))

        if not self.done:
            if counting:
                left = CALIB_COUNT_IN - len(past)
                msg = "Listen to the clicks..." if not past else f"Get ready... {left}" if left else "Go!"
            else:
                msg = "Pinch on every click (go by sound, not the flash)"
            ui.text(surf, msg, 38, ui.WHITE, (W // 2, 440))
            ui.text(surf, f"Taps: {len(self.taps)} / {CALIB_TAPS}", 30, ui.DIM, (W // 2, 485))
        elif self.result is None:
            ui.text(surf, "Not enough taps were detected. Press R to try again.", 36,
                    (255, 190, 120), (W // 2, 440))
        else:
            spread = statistics.pstdev(self.taps)
            ui.text(surf, f"Your offset: {self.result:+.0f} ms   (spread {spread:.0f} ms)", 44,
                    ui.WHITE, (W // 2, 440))
            ui.text(surf, "Enter: save    R: retry    Esc: cancel", 30, ui.DIM, (W // 2, 490))

        # every tap on a -250..+250 ms timeline
        cx, cy, half = W // 2, 580, 300
        pygame.draw.line(surf, ui.DIM, (cx - half, cy), (cx + half, cy), 2)
        pygame.draw.line(surf, ui.WHITE, (cx, cy - 14), (cx, cy + 14), 2)
        for d in self.taps:
            pygame.draw.circle(surf, ui.ACCENT, (int(cx + d / 250 * half), cy), 6)
        ui.text(surf, "early", 24, ui.DIM, (cx - half - 12, cy), "midright")
        ui.text(surf, "late", 24, ui.DIM, (cx + half + 12, cy), "midleft")
