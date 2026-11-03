"""The main menu: Play card, setting rows, animated hit-circle preview, camera status."""
import time

import pygame

from air_rhythm import __version__
from air_rhythm.content.map_gen import LEVEL_PATHS
from air_rhythm.core.beatmap import load_beatmap
from air_rhythm.ui import widgets as ui
from air_rhythm.ui.screens.base import ButtonScreen
from air_rhythm.ui.screens.calibration import CalibrationScreen
from air_rhythm.ui.screens.play import COMBO_COLORS, PlayScreen
from air_rhythm.ui.screens.settings import SettingsScreen

LEVELS = list(LEVEL_PATHS)     # menu order: Easy, Normal


MENU_LEFT, MENU_WIDTH = 96, 460


class MenuScreen(ButtonScreen):
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
            ui.OptionRow((x, 546, w, 52), "Settings", self.open_settings,
                         lambda: "Sound · Timing · Camera"),
            ui.OptionRow((x, 606, w, 52), "Quit", app.quit, danger=True),
        ]
        # right side: a hit circle that keeps getting hit, as a preview of the game
        self.demo = ui.HitCircleDemo((920, 330), 92, COMBO_COLORS)
        ui.menu_background(W, H)             # build it now, not on the first frame
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

    def open_settings(self):
        self.app.goto(SettingsScreen(self.app))

    def calibrate(self):
        if self.app.audio_ok:                # calibration is done by ear: it needs sound
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
                pygame.K_s: self.open_settings,
                pygame.K_l: self.next_level, pygame.K_m: self.toggle_music,
                pygame.K_i: self.toggle_input, pygame.K_n: self.toggle_no_fail,
                pygame.K_ESCAPE: self.app.quit, pygame.K_q: self.app.quit}
        self.handle_mouse(events)
        for e in events:
            if e.type == pygame.KEYDOWN and e.key in keys:
                keys[e.key]()

    def draw(self, surf):
        W, H = surf.get_size()
        ui.draw_menu_background(surf, time.perf_counter() - self.t0)

        x = MENU_LEFT
        ui.label(surf, "WEBCAM RHYTHM GAME", 15, ui.ACCENT, (x + 2, 96), "midleft", "semibold", spacing=3)
        ui.label(surf, "AIR RHYTHM", 68, ui.WHITE, (x - 3, 148), "midleft", "black")
        ui.label(surf, "Aim with your hand. Pinch on the beat.", 20, ui.DIM, (x, 204), "midleft")
        self.draw_buttons(surf)

        self.demo.draw(surf)
        self._draw_status(surf, (W - 48, 48))
        ui.label(surf, f"v{__version__}", 13, ui.MUTED, (W - 50, 98), "topright")

        kx = x
        for key, what in (("Enter", "Play"), ("L", "Level"), ("I", "Input"), ("N", "No-fail"),
                          ("S", "Settings"), ("M", "Music"), ("V", "Camera"), ("F11", "Fullscreen"),
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
        elif self.app.warning:
            msg, dot = self.app.warning, ui.WARN
        else:
            msg, dot = "Hand tracking ready", ui.OK
        img = ui.render(msg, 15, ui.WHITE, "semibold")
        pill = pygame.Rect(0, 0, img.get_width() + 46, 34)
        pill.topright = topright
        ui.panel(surf, pill, (255, 255, 255, 14), (255, 255, 255, 36), radius=17)
        ui.disc(surf, dot, (pill.x + 18, pill.centery), 5)
        surf.blit(img, img.get_rect(midleft=(pill.x + 32, pill.centery)))
