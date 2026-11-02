"""Menu, results and calibration screens. Buttons can be clicked with the
mouse or by pinching over them."""
import math
import statistics
import time

import pygame

import ui
from audio_gen import CALIB_BEAT_MS, CALIB_COUNT_IN, CALIB_FIRST_MS, CALIB_TAPS
from beatmap import load_beatmap
from clock import SongClock
from map_gen import CALIBRATION_AUDIO, LEVEL_PATHS

LEVELS = list(LEVEL_PATHS)     # menu order: Easy, Normal
from play_screen import COMBO_COLORS, PlayScreen


MOUSE_ACTIVE_S = 2.0     # after the mouse moves, its cursor is shown instead of the hand for this long


class _ButtonScreen:
    """Shared logic: hover with the cursor, press (click or pinch) to activate.
    The mouse works on these screens even in hand mode, so the buttons can
    still be reached when the camera isn't working."""
    buttons = []
    _mouse_moved_at = None

    def handle_mouse(self, events):
        if self.app.input.kind == "mouse":
            return                      # MouseInput already turns clicks into presses
        for e in events:
            if e.type == pygame.MOUSEMOTION:
                self._mouse_moved_at = time.perf_counter()
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self._mouse_moved_at = time.perf_counter()
                for b in self.buttons:
                    if b.contains(e.pos):
                        b.action()
                        return

    def cursor_override(self):
        """Show the mouse instead of the hand while it's being used, or when no hand is seen."""
        if self.app.input.kind == "mouse" or self._mouse_moved_at is None:
            return None
        if (self.app.input.cursor() is None
                or time.perf_counter() - self._mouse_moved_at < MOUSE_ACTIVE_S):
            return self.app.playfield.to_osu(*pygame.mouse.get_pos())
        return None

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
MENU_LEFT, MENU_WIDTH = 96, 460
_menu_bg_cache = {}


def _menu_background(w, h):
    """Dark gradient plus two glow sprites (pink top-right, violet bottom-left). Built once."""
    if (w, h) not in _menu_bg_cache:
        bg = pygame.Surface((w, h))
        for y in range(h):
            pygame.draw.line(bg, ui.lerp_color((16, 13, 30), (6, 6, 12), y / h), (0, y), (w, y))
        glows = [(ui.make_glow(420, (70, 22, 55)), (w - 220, 120), 0.0),
                 (ui.make_glow(380, (36, 24, 80)), (180, h - 80), 2.0)]
        _menu_bg_cache[(w, h)] = bg, glows
    return _menu_bg_cache[(w, h)]


class MenuScreen(_ButtonScreen):
    menu_music = True                       # App fades the menu music in while this screen is shown

    def __init__(self, app):
        self.app = app
        self._load_map_info()
        W, H = app.surface.get_size()
        s = app.settings
        # left column: title, the big Play card, then one row per setting
        x, w = MENU_LEFT, MENU_WIDTH
        self.buttons = [
            ui.PlayCard((x, 248, w, 100), self.play,
                        lambda: f"{self.map_title}  ·  {self.map_version}"),
            ui.OptionRow((x, 366, w, 52), "Level", self.next_level, lambda: (LEVELS, s["level"])),
            ui.OptionRow((x, 426, w, 52), "Input", self.toggle_input,
                         lambda: (["Hand", "Mouse"], "Hand" if app.input.kind == "hand" else "Mouse")),
            ui.OptionRow((x, 486, w, 52), "No-fail", self.toggle_no_fail, lambda: s["no_fail"]),
            ui.OptionRow((x, 546, w, 52), "Calibrate offset", self.calibrate,
                         lambda: f"{s['input_offset_ms']:+.0f} ms"),
            ui.OptionRow((x, 606, w, 52), "Quit", app.quit, danger=True),
        ]
        # right side: a hit circle that keeps getting hit, as a preview of the game
        self.demo = ui.HitCircleDemo((920, 330), 92, COMBO_COLORS)
        self.background, self.glows = _menu_background(W, H)
        self.t0 = time.perf_counter()

    def play(self):
        self.app.goto(PlayScreen(self.app, self.app.map_path, self.app.autoplay))

    def _load_map_info(self):
        bm = load_beatmap(self.app.map_path)
        self.map_title, self.map_version = bm.title, bm.version

    def next_level(self):
        i = LEVELS.index(self.app.settings["level"])
        self.app.set_level(LEVELS[(i + 1) % len(LEVELS)])
        self._load_map_info()

    def calibrate(self):
        self.app.goto(CalibrationScreen(self.app))

    def toggle_music(self):
        self.app.settings["menu_music"] = not self.app.settings["menu_music"]
        self.app.update_menu_music()

    def toggle_input(self):
        self.app.set_input_mode("mouse" if self.app.input.kind == "hand" else "hand")

    def toggle_no_fail(self):
        self.app.settings["no_fail"] = not self.app.settings["no_fail"]

    def handle(self, events):
        keys = {pygame.K_RETURN: self.play, pygame.K_SPACE: self.play, pygame.K_c: self.calibrate,
                pygame.K_l: self.next_level, pygame.K_m: self.toggle_music,
                pygame.K_i: self.toggle_input, pygame.K_n: self.toggle_no_fail,
                pygame.K_ESCAPE: self.app.quit, pygame.K_q: self.app.quit}
        self.handle_mouse(events)
        for e in events:
            if e.type == pygame.KEYDOWN and e.key in keys:
                keys[e.key]()

    def draw(self, surf):
        W, H = surf.get_size()
        t = time.perf_counter() - self.t0
        surf.blit(self.background, (0, 0))
        # two soft lights drifting slowly behind everything
        for glow, (gx, gy), phase in self.glows:
            dx, dy = 40 * math.sin(t * 0.21 + phase), 30 * math.cos(t * 0.17 + phase)
            surf.blit(glow, glow.get_rect(center=(gx + dx, gy + dy)), special_flags=pygame.BLEND_ADD)

        x = MENU_LEFT
        ui.label(surf, "WEBCAM RHYTHM GAME", 15, ui.ACCENT, (x + 2, 96), "midleft", "semibold", spacing=3)
        ui.label(surf, "AIR RHYTHM", 68, ui.WHITE, (x - 3, 148), "midleft", "black")
        ui.label(surf, "Aim with your hand. Pinch on the beat.", 20, ui.DIM, (x, 204), "midleft")
        self.draw_buttons(surf)

        self.demo.draw(surf)
        self._draw_status(surf, (W - 48, 48))

        kx = x
        for key, what in (("Enter", "Play"), ("L", "Level"), ("I", "Input"), ("N", "No-fail"),
                          ("C", "Calibrate"), ("M", "Music"), ("V", "Camera"), ("F11", "Fullscreen"),
                          ("Esc", "Quit")):
            kx = ui.keycap(surf, key, (kx, H - 30))
            kx = ui.label(surf, what, 14, ui.MUTED, (kx + 7, H - 30), "midleft").right + 16

    def _draw_status(self, surf, topright):
        """Pill in the top-right corner: is the camera working?"""
        status = self.app.input.status_text()
        if self.app.input.kind == "mouse":
            msg, dot = "Mouse input", ui.MUTED
        elif status:
            msg, dot = status, ui.WARN
        else:
            msg, dot = "Hand tracking ready", ui.OK
        img = ui.render(msg, 15, ui.WHITE, "semibold")
        pill = pygame.Rect(0, 0, img.get_width() + 46, 34)
        pill.topright = topright
        ui.panel(surf, pill, (255, 255, 255, 14), (255, 255, 255, 36), radius=17)
        ui.disc(surf, dot, (pill.x + 18, pill.centery), 5)
        surf.blit(img, img.get_rect(midleft=(pill.x + 32, pill.centery)))


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
        self.handle_mouse(events)
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
