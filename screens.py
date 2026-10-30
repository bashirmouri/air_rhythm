"""Menu, results and calibration screens. Buttons can be clicked with the
mouse or by pinching over them."""
import math
import statistics

import pygame

import ui
from audio_gen import CALIB_BEAT_MS, CALIB_COUNT_IN, CALIB_FIRST_MS, CALIB_TAPS
from beatmap import load_beatmap
from clock import SongClock
from map_gen import CALIBRATION_AUDIO
from play_screen import COMBO_COLORS, PlayScreen


class _ButtonScreen:
    """Shared logic: hover with the cursor, press (click or pinch) to activate."""
    buttons = []

    def update(self):
        for _, pos in self.app.input.take_presses():
            sp = self.app.to_screen(pos)
            for b in self.buttons:
                if b.contains(sp):
                    b.action()
                    return

    def draw_buttons(self, surf):
        cursor = self.app.cursor_screen()
        for b in self.buttons:
            b.draw(surf, b.contains(cursor))


# ======================================================================
class MenuScreen(_ButtonScreen):
    def __init__(self, app):
        self.app = app
        self.map_title = load_beatmap(app.map_path).title
        W, H = app.surface.get_size()
        cx = W // 2
        self.buttons = [
            ui.Button("", (cx, 330), action=self.play),
            ui.Button("Calibrate offset", (cx, 405), action=self.calibrate),
            ui.Button("", (cx, 480), action=self.toggle_input),
            ui.Button("", (cx, 555), action=self.toggle_no_fail),
            ui.Button("Quit", (cx, 630), action=app.quit),
        ]
        self._t = 0

    def play(self):
        self.app.goto(PlayScreen(self.app, self.app.map_path, self.app.autoplay))

    def calibrate(self):
        self.app.goto(CalibrationScreen(self.app))

    def toggle_input(self):
        self.app.set_input_mode("mouse" if self.app.input.kind == "hand" else "hand")

    def toggle_no_fail(self):
        self.app.settings["no_fail"] = not self.app.settings["no_fail"]

    def handle(self, events):
        keys = {pygame.K_RETURN: self.play, pygame.K_SPACE: self.play, pygame.K_c: self.calibrate,
                pygame.K_i: self.toggle_input, pygame.K_n: self.toggle_no_fail,
                pygame.K_ESCAPE: self.app.quit, pygame.K_q: self.app.quit}
        for e in events:
            if e.type == pygame.KEYDOWN and e.key in keys:
                keys[e.key]()

    def draw(self, surf):
        s = self.app.settings
        self.buttons[0].label = f"Play: {self.map_title}"
        self.buttons[2].label = f"Input: {'Hand (webcam)' if self.app.input.kind == 'hand' else 'Mouse'}"
        self.buttons[3].label = f"No-fail: {'on' if s['no_fail'] else 'off'}"

        surf.blit(self.app.background, (0, 0))
        W, H = surf.get_size()
        self._t += 1
        # decorative pulsing circles
        for k, color in enumerate(COMBO_COLORS):
            r = 70 + 12 * math.sin(self._t / 40 + k * 1.6)
            x = W // 2 + (k - 1.5) * 220
            pygame.draw.circle(surf, ui.lerp_color(color, (0, 0, 0), 0.75), (int(x), 150), int(r), 3)
        ui.text(surf, "AIR RHYTHM", 110, ui.WHITE, (W // 2, 150))
        ui.text(surf, "click the beat with your hand", 34, ui.DIM, (W // 2, 225))
        self.draw_buttons(surf)
        ui.text(surf, f"Offset: {s['input_offset_ms']:+.0f} ms     Enter: play   C: calibrate   "
                      f"I: input   N: no-fail   V: camera view   F11: fullscreen",
                22, ui.DIM, (W // 2, H - 22))
        status = self.app.input.status_text()
        if status:
            ui.text(surf, status, 30, (255, 190, 120), (W // 2, 275))


# ======================================================================
GRADE_COLORS = {"SS": (255, 230, 120), "S": (255, 210, 90), "A": (130, 230, 130),
                "B": (110, 190, 255), "C": (200, 140, 255), "D": (255, 110, 110), "F": (255, 80, 80)}


class ResultsScreen(_ButtonScreen):
    def __init__(self, app, game, map_path, autoplay=False):
        self.app, self.game, self.map_path, self.autoplay = app, game, map_path, autoplay
        W, H = app.surface.get_size()
        self.buttons = [ui.Button("Retry", (W // 2 - 230, H - 80), (400, 62), self.retry),
                        ui.Button("Menu", (W // 2 + 230, H - 80), (400, 62), self.menu)]

    def retry(self):
        self.app.goto(PlayScreen(self.app, self.map_path, self.autoplay))

    def menu(self):
        self.app.goto(MenuScreen(self.app))

    def handle(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                    self.retry()
                elif e.key == pygame.K_ESCAPE:
                    self.menu()

    def draw(self, surf):
        g = self.game
        W, H = surf.get_size()
        surf.blit(self.app.background, (0, 0))
        ui.text(surf, f"{g.bm.title}  [{g.bm.version}]", 48, ui.WHITE, (W // 2, 60))
        if g.failed:
            ui.text(surf, "FAILED", 40, (255, 100, 100), (W // 2, 105))
        grade = g.grade()
        ui.text(surf, grade, 260, GRADE_COLORS[grade], (W * 0.27, H * 0.45))

        x, y = W * 0.52, 160
        rows = [("Score", f"{g.score:,}"), ("Accuracy", f"{g.accuracy * 100:.2f}%"),
                ("Max combo", f"{g.max_combo}x")]
        for label, value in rows:
            ui.text(surf, label, 34, ui.DIM, (x, y), "topleft")
            ui.text(surf, value, 52, ui.WHITE, (x + 230, y - 6), "topleft")
            y += 62
        y += 10
        for j, label in ((300, "300"), (100, "100"), (50, "50"), (0, "Miss")):
            from gameplay import JUDGE_COLORS
            ui.text(surf, label, 36, JUDGE_COLORS[j], (x, y), "topleft")
            ui.text(surf, str(g.counts[j]), 36, ui.WHITE, (x + 120, y), "topleft")
            y += 40
        y += 14
        mean = g.mean_error
        when = "late" if mean > 0 else "early"
        ui.text(surf, f"Average timing: {abs(mean):.0f} ms {when}    Unstable rate: {g.unstable_rate:.0f}",
                28, ui.DIM, (x, y), "topleft")
        if abs(mean) > 25 and not self.autoplay:
            ui.text(surf, "Tip: run Calibrate offset from the menu to fix a constant delay.",
                    24, (255, 190, 120), (x, y + 32), "topleft")
        self.draw_buttons(surf)


# ======================================================================
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
