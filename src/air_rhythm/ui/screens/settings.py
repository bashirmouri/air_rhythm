"""Settings: volumes, timing offsets, camera and hand tracking, display.

Every change is used right away (App.apply_settings) and saved when the game closes.
The camera view is drawn large here, so changing the hand area or pinch sensitivity
can be tried on the spot."""
import time

import pygame

from air_rhythm.system import config
from air_rhythm.system.settings import RANGES
from air_rhythm.ui import widgets as ui
from air_rhythm.ui.screens.base import ButtonScreen
from air_rhythm.ui.screens.calibration import CalibrationScreen
from air_rhythm.ui.screens.onboarding import OnboardingScreen

LEFT_X, RIGHT_X, COL_W = 64, 680, 536
TOP = 166                       # first row
ROW_H, STEP = 42, 48            # row height, distance between rows
SECTION_GAP = 40                # extra space before the next group (room for its title)
PREVIEW_SCALE = 4 / 3           # the tracker's 240x180 camera view, shown at 320x240


class SettingsScreen(ButtonScreen):
    menu_music = True           # keep the menu music playing: volume changes can be heard
    draws_camera_preview = True  # App doesn't draw its small camera view on top of this screen

    def __init__(self, app):
        self.app = app
        self.t0 = time.perf_counter()
        self.sections = []      # (title, position)
        left, right = self._left_column(), self._right_column()
        back = ui.OptionRow((1056, 52, 160, 44), "Back", self.back, lambda: "Esc")
        self.buttons = [back, *left, *right]
        self.preview_rect = pygame.Rect(RIGHT_X, self._right_end + 40, 320, 240)

    # ------------------------------------------------------------- layout
    def _rows(self, x, groups):
        """Lays out groups of rows down a column: [(title, [make_row(rect), ...]), ...].
        Returns the rows and where the last one ends."""
        rows, y = [], TOP
        for title, makers in groups:
            self.sections.append((title, (x + 4, y - 18)))
            for make in makers:
                rows.append(make((x, y, COL_W, ROW_H)))
                y += STEP
            y += SECTION_GAP
        return rows, y - SECTION_GAP - STEP + ROW_H

    def _left_column(self):
        s = self.app.settings
        rows, _ = self._rows(LEFT_X, [
            ("AUDIO", [
                lambda r: self._volume(r, "Song", "music_volume"),
                lambda r: self._volume(r, "Hitsounds", "hitsound_volume"),
                lambda r: ui.StepperRow(r, "Menu music", self._menu_music_text,
                                        lambda: self._menu_music(-1), lambda: self._menu_music(+1)),
            ]),
            ("TIMING", [
                lambda r: self._offset(r, "Sound delay", "audio_offset_ms"),
                lambda r: self._offset(r, "Input delay", "input_offset_ms"),
                lambda r: ui.OptionRow(r, "Measure input delay", self.calibrate,
                                       lambda: "C" if self.app.audio_ok else "needs sound"),
            ]),
            ("DISPLAY", [
                lambda r: ui.OptionRow(r, "Fullscreen", lambda: self._toggle("fullscreen"),
                                       lambda: s["fullscreen"]),
                lambda r: ui.OptionRow(r, "Camera view in game", lambda: self._toggle("show_camera"),
                                       lambda: s["show_camera"]),
                lambda r: ui.OptionRow(r, "Show FPS", lambda: self._toggle("show_fps"),
                                       lambda: s["show_fps"]),
            ]),
        ])
        return rows

    def _right_column(self):
        cameras = [str(i + 1) for i in range(config.CAMERA_COUNT)]
        rows, self._right_end = self._rows(RIGHT_X, [
            ("CAMERA & HAND", [
                lambda r: ui.ChoiceRow(r, "Camera", cameras,
                                       lambda: str(self.app.settings["camera_index"] + 1),
                                       lambda c: self._set("camera_index", int(c) - 1)),
                lambda r: self._choice(r, "Hand area", "hand_area", config.HAND_AREAS),
                lambda r: self._choice(r, "Pinch sensitivity", "pinch_sensitivity",
                                       config.PINCH_SENSITIVITY),
                lambda r: self._choice(r, "Cursor smoothing", "cursor_smoothing", config.CURSOR_SMOOTHINGS),
                lambda r: ui.OptionRow(r, "Setup guide", self.setup_guide, lambda: "camera, pinch, delay"),
            ]),
        ])
        return rows

    # ------------------------------------------------------------- row kinds
    def _volume(self, rect, text, key):
        return ui.StepperRow(rect, text, lambda: f"{self.app.settings[key]}%",
                             lambda: self._step(key, -config.VOLUME_STEP),
                             lambda: self._step(key, +config.VOLUME_STEP))

    def _offset(self, rect, text, key):
        return ui.StepperRow(rect, text, lambda: f"{self.app.settings[key]:+.0f} ms",
                             lambda: self._step(key, -config.OFFSET_STEP_MS),
                             lambda: self._step(key, +config.OFFSET_STEP_MS))

    def _choice(self, rect, text, key, options):
        return ui.ChoiceRow(rect, text, list(options), lambda: self.app.settings[key],
                            lambda v: self._set(key, v))

    # ------------------------------------------------------------- changing settings
    def _set(self, key, value):
        self.app.settings[key] = value
        self.app.apply_settings()

    def _step(self, key, delta):
        low, high = RANGES[key]
        value = min(max(self.app.settings[key] + delta, low), high)
        self._set(key, round(value, 1) if isinstance(value, float) else value)

    def _toggle(self, key):
        self._set(key, not self.app.settings[key])

    def _menu_music_text(self):
        s = self.app.settings
        return f"{s['menu_music_volume']}%" if s["menu_music"] and s["menu_music_volume"] else "Off"

    def _menu_music(self, direction):
        """Below the lowest step the menu music turns off; + turns it back on."""
        s = self.app.settings
        on = s["menu_music"] and s["menu_music_volume"] > 0
        if direction < 0 and on and s["menu_music_volume"] <= config.VOLUME_STEP:
            s["menu_music"] = False
        elif direction > 0 and not on:
            s["menu_music"] = True
            s["menu_music_volume"] = max(s["menu_music_volume"], config.VOLUME_STEP)
        elif on:
            self._step("menu_music_volume", direction * config.VOLUME_STEP)
            return
        self.app.apply_settings()

    # ------------------------------------------------------------- navigation
    def back(self):
        from air_rhythm.ui.screens.menu import MenuScreen  # menu.py imports this file
        self.app.goto(MenuScreen(self.app))

    def setup_guide(self):
        self.app.goto(OnboardingScreen(self.app))

    def calibrate(self):
        if self.app.audio_ok:                    # calibration is done by ear: it needs sound
            self.app.goto(CalibrationScreen(self.app, back=lambda: SettingsScreen(self.app)))

    def handle(self, events):
        self.handle_mouse(events)
        for e in events:
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.back()
                return
            if e.type == pygame.KEYDOWN and e.key == pygame.K_c:
                self.calibrate()
                return

    # ------------------------------------------------------------- drawing
    def draw(self, surf):
        ui.draw_menu_background(surf, time.perf_counter() - self.t0)
        ui.label(surf, "AIR RHYTHM", 15, ui.ACCENT, (LEFT_X + 2, 58), "midleft", "semibold", spacing=3)
        ui.label(surf, "Settings", 44, ui.WHITE, (LEFT_X - 2, 94), "midleft", "black")
        for title, pos in self.sections:
            ui.section(surf, title, pos)
        self.draw_buttons(surf)
        self._draw_camera(surf)

    def _draw_camera(self, surf):
        """The camera view, large, with what to look for; or why there is none."""
        r = self.preview_rect
        ui.section(surf, "CAMERA VIEW", (r.x + 4, r.y - 16))
        tips_x = r.right + 24
        inp = self.app.input
        img = inp.preview_surface()
        if img is not None:
            big = pygame.transform.smoothscale(img, r.size)
            surf.blit(big, r)
            pygame.draw.rect(surf, (255, 255, 255, 90), r.inflate(2, 2), 1, border_radius=4)
        else:
            ui.panel(surf, r, (255, 255, 255, 10), (255, 255, 255, 36), radius=10)
            error = getattr(getattr(inp, "tracker", None), "error", None)
            msg = "Off in mouse mode" if inp.kind == "mouse" else error or "Starting camera..."
            lines = ui.wrap(msg, 16, r.width - 40, "semibold")
            for i, line in enumerate(lines):
                y = r.centery + (i - (len(lines) - 1) / 2) * 24
                ui.label(surf, line, 16, ui.WARN if error else ui.DIM, (r.centerx, y), "center", "semibold")
            if error:
                ui.label(surf, "Try another camera above, or switch Input to Mouse in the menu.", 14,
                         ui.DIM, (r.x, r.bottom + 14), "topleft")
        lines = (["Switch Input to Hand", "in the menu to use", "the camera."] if inp.kind == "mouse" else
                 ["Keep your hand inside", "the white box.", "", "The dots turn green",
                  "while you pinch.", "", "Smaller hand area:", "less arm movement."])
        for i, line in enumerate(lines):
            ui.label(surf, line, 15, ui.DIM, (tips_x, r.y + 8 + i * 22), "topleft")
        status = inp.status_text() if inp.kind == "hand" else None
        if status and img is not None:               # e.g. "Show your hand to the camera"
            ui.label(surf, status, 15, ui.WARN, (r.x, r.bottom + 14), "topleft", "semibold")
