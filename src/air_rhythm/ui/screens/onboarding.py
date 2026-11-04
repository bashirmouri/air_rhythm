"""The setup guide, shown on the first start in hand mode (and from Settings any time):
1. camera: a live checklist (camera on, enough light, hand found) next to a large camera view
2. pinch: aim at three circles and pinch, to learn the one move the game needs
3. delay: measure the input delay now (calibration), or later from Settings

It can always be skipped, or left for mouse play. Finishing or skipping marks it done
(settings["setup_done"]), so it isn't shown again."""
import math
import time

import pygame

from air_rhythm.system import config
from air_rhythm.ui import widgets as ui
from air_rhythm.ui.screens.base import ButtonScreen, activate
from air_rhythm.ui.screens.calibration import CalibrationScreen
from air_rhythm.ui.screens.play import COMBO_COLORS, make_circle_sprite

STEPS = ("camera", "pinch", "delay")
TITLES = {"camera": "Set up your camera", "pinch": "Try a pinch", "delay": "Measure your delay"}
LEFT = 96
# practice circles (osu! playfield coordinates), placed clear of the text and buttons
TARGETS = [(256, 200), (430, 110), (110, 300)]
TARGET_R = 58                  # px
HIT_FEEDBACK_S = 0.45
OK, WARN, BAD, WAIT = "ok", "warn", "bad", "wait"
DOT_COLORS = {OK: ui.OK, WARN: ui.WARN, BAD: (255, 110, 120), WAIT: ui.MUTED}


def camera_checklist(stats, kind):
    """[(state, text), ...] for the camera step: camera, light, hand. Pure logic: tested
    without a camera. `stats` comes from the input's camera_stats() (None in mouse mode)."""
    if kind == "mouse" or stats is None:
        return [(WAIT, "Mouse input is on: switch to hand tracking to set up the camera")]
    if stats["error"]:
        return [(BAD, stats["error"])]
    if not stats["ready"]:
        return [(WAIT, "Starting the camera..."), (WAIT, "Light"), (WAIT, "Hand")]
    items = []
    fps = stats["fps"]
    if not stats["warm"]:
        items.append((WAIT, "Camera on, measuring..."))
    elif fps < config.SLOW_CAMERA_FPS:
        items.append((WARN, f"Camera is slow ({fps} fps): more light helps, or close other apps using it"))
    else:
        items.append((OK, f"Camera on ({fps} fps)"))
    b = stats["brightness"]
    if b is None or not stats["warm"]:
        items.append((WAIT, "Checking the light..."))
    elif b < config.DARK_BRIGHTNESS:
        items.append((BAD, "Too dark: turn on a light in front of you"))
    elif b < config.DIM_BRIGHTNESS:
        items.append((WARN, "A bit dark: more light makes tracking steadier"))
    else:
        items.append((OK, "Good light"))
    items.append((OK, "Hand found") if stats["hand"] else
                 (WAIT, "Raise your hand into the white box"))
    return items


class OnboardingScreen(ButtonScreen):
    menu_music = True

    def __init__(self, app, step="camera"):
        self.app = app
        self.t0 = time.perf_counter()
        self.step = step
        self.hits = 0
        self.feedback = None            # ("hit" | "miss", time, screen pos)
        r = TARGET_R
        self.sprites = [make_circle_sprite(r, COMBO_COLORS[i % len(COMBO_COLORS)], i + 1)
                        for i in range(len(TARGETS))]
        self.demo = ui.HitCircleDemo((940, 330), 92, COMBO_COLORS)
        self._build_buttons()

    @property
    def draws_camera_preview(self):     # step 1 draws a big one itself
        return self.step == "camera"

    # ------------------------------------------------------------- buttons per step
    def _build_buttons(self):
        x, w, h = LEFT, 420, 46
        rows = {
            "camera": [("Next", self.next_step, "Enter"), ("Skip setup", self.finish, "Esc"),
                       (self._mode_label(), self.toggle_mode, "M")],
            "pinch": [("Next" if self.hits >= len(TARGETS) else "Skip this step", self.next_step, "Enter"),
                      ("Skip setup", self.finish, "Esc")],
            "delay": ([("Measure now", self.calibrate, "Enter")] if self.app.audio_ok else []) +
                     [("Later" if self.app.audio_ok else "Finish", self.finish, "Esc")],
        }[self.step]
        top = 720 - 56 - (len(rows) - 1) * 54 - h // 2 - 4
        self.buttons = [ui.OptionRow((x, top + i * 54, w, h), text, action, (lambda k=k: k), primary=i == 0)
                        for i, (text, action, k) in enumerate(rows)]

    def _mode_label(self):
        return "Switch to hand tracking" if self.app.input.kind == "mouse" else "Play with the mouse instead"

    # ------------------------------------------------------------- actions
    def next_step(self):
        i = STEPS.index(self.step)
        if i + 1 < len(STEPS):
            self.step = STEPS[i + 1]
            self._build_buttons()
        else:
            self.finish()

    def finish(self):
        from air_rhythm.ui.screens.menu import MenuScreen  # menu.py imports settings, which imports this
        self.app.settings["setup_done"] = True
        self.app.goto(MenuScreen(self.app))

    def toggle_mode(self):
        if self.app.input.kind == "hand":
            self.app.set_input_mode("mouse")
            self.finish()                    # nothing to set up for the mouse
        else:
            self.app.set_input_mode("hand")
            self._build_buttons()

    def calibrate(self):
        from air_rhythm.ui.screens.menu import MenuScreen
        self.app.settings["setup_done"] = True
        self.app.goto(CalibrationScreen(self.app, back=lambda: MenuScreen(self.app)))

    # ------------------------------------------------------------- events
    def handle(self, events):
        self.handle_mouse(events)
        keys = {pygame.K_RETURN: self.buttons[0].action, pygame.K_SPACE: self.buttons[0].action,
                pygame.K_ESCAPE: self.finish if self.step != "delay" else self.buttons[-1].action}
        if self.step == "camera":
            keys[pygame.K_m] = self.toggle_mode
        for e in events:
            if e.type == pygame.KEYDOWN and e.key in keys:
                keys[e.key]()
                return

    def update(self):
        for _, pos in self.app.input.take_presses():
            sp = self.app.to_screen(pos)
            button = next((b for b in self.buttons if b.contains(sp)), None)
            if button:
                activate(button, sp)
                return
            if self.step == "pinch":
                self._practice_press(sp)

    def target_center(self, i):
        return self.app.playfield.to_screen(*TARGETS[i])

    def _practice_press(self, sp):
        if sp is None or self.hits >= len(TARGETS):
            return
        cx, cy = self.target_center(self.hits)
        now = time.perf_counter()
        if math.hypot(sp[0] - cx, sp[1] - cy) <= TARGET_R * 1.15:
            self.feedback = ("hit", now, (cx, cy))
            self.app.hitsound.play()
            self.hits += 1
            if self.hits == len(TARGETS):
                self._build_buttons()        # "Skip this step" becomes "Next"
        else:
            self.feedback = ("miss", now, sp)

    # ------------------------------------------------------------- drawing
    def draw(self, surf):
        ui.draw_menu_background(surf, time.perf_counter() - self.t0)
        i = STEPS.index(self.step)
        ui.label(surf, f"SETUP  ·  STEP {i + 1} OF {len(STEPS)}", 15, ui.ACCENT, (LEFT + 2, 58),
                 "midleft", "semibold", spacing=3)
        ui.label(surf, TITLES[self.step], 44, ui.WHITE, (LEFT - 2, 100), "midleft", "black")
        for k in range(len(STEPS)):            # progress dots
            ui.disc(surf, ui.ACCENT if k <= i else (70, 66, 92), (LEFT + 6 + k * 22, 146), 5)
        getattr(self, f"_draw_{self.step}")(surf)
        self.draw_buttons(surf)

    def _paragraph(self, surf, lines, y, color=ui.DIM, size=19):
        for line in lines:
            ui.label(surf, line, size, color, (LEFT, y), "midleft")
            y += 28
        return y

    def _draw_camera(self, surf):
        y = self._paragraph(surf, ["Sit about an arm's length from the camera, so your",
                                   "raised hand fits inside the white box. Light in front",
                                   "of you (not behind) keeps tracking steady."], 196)
        for state, text in camera_checklist(self.app.input.camera_stats(), self.app.input.kind):
            ui.disc(surf, DOT_COLORS[state], (LEFT + 7, y + 22), 6)
            lines = ui.wrap(text, 19, 420, "semibold")
            for line in lines:
                ui.label(surf, line, 19, ui.WHITE if state != WAIT else ui.DIM, (LEFT + 24, y + 22),
                         "midleft", "semibold")
                y += 26
            y += 10
        view = pygame.Rect(632, 150, 560, 420)
        img = self.app.input.preview_surface()
        if img is None:
            ui.panel(surf, view, (255, 255, 255, 10), (255, 255, 255, 36), radius=12)
            msg = "Camera view appears here" if self.app.input.kind == "hand" else "Camera off (mouse input)"
            ui.label(surf, msg, 18, ui.DIM, view.center, "center", "semibold")
        else:
            surf.blit(pygame.transform.smoothscale(img, view.size), view)
            pygame.draw.rect(surf, (255, 255, 255), view.inflate(2, 2), 1, border_radius=4)
        ui.label(surf, "The dots on your hand turn green while you pinch.", 15, ui.MUTED,
                 (view.x, view.bottom + 18), "midleft")

    def _draw_pinch(self, surf):
        done = self.hits >= len(TARGETS)
        text = (["Nice! That's the only move you need.", "Hit circles like these on the beat."] if done else
                ["Move the cursor into the circle,", "then pinch thumb and index finger."])
        self._paragraph(surf, text, 196)
        ui.label(surf, f"{min(self.hits, len(TARGETS))} / {len(TARGETS)}", 22, ui.WHITE, (LEFT, 270),
                 "midleft", "semibold")
        now = time.perf_counter()
        if not done:
            spr = self.sprites[self.hits]
            cx, cy = self.target_center(self.hits)
            pulse = 0.5 + 0.5 * math.sin((now - self.t0) * 4)
            color = COMBO_COLORS[self.hits % len(COMBO_COLORS)]
            ui.ring(surf, color, (cx, cy), TARGET_R * (1.25 + 0.1 * pulse), 3)     # "pinch here"
            surf.blit(spr, spr.get_rect(center=(cx, cy)))
        if self.feedback and now - self.feedback[1] < HIT_FEEDBACK_S:
            kind, t, pos = self.feedback
            f = (now - t) / HIT_FEEDBACK_S
            if kind == "hit":
                ui.ring(surf, ui.WHITE, pos, TARGET_R * (1 + 0.5 * f), max(1, 5 * (1 - f)))
                ui.label(surf, "300", 30, (110, 200, 255), (pos[0], pos[1] - TARGET_R - 20 - 20 * f),
                         "center", "black", alpha=int(255 * (1 - f)))
            else:                                       # kept on screen wherever the miss was
                W, H = surf.get_size()
                at = (min(max(pos[0], 140), W - 140), min(max(pos[1] - 30, 20), H - 20))
                ui.label(surf, "Get inside the circle first", 18, ui.WARN, at,
                         "center", "semibold", alpha=int(255 * (1 - f)))
        status = self.app.input.status_text()
        if status:
            ui.label(surf, status, 18, ui.WARN, (LEFT, 310), "midleft", "semibold")

    def _draw_delay(self, surf):
        lines = ["Webcams show the game your pinch a little late",
                 "(often 50-150 ms). A 30-second test measures it:",
                 "pinch along with a metronome, by ear.",
                 "",
                 "The game then counts every hit on time."]
        y = self._paragraph(surf, lines, 196)
        extra = (["Using Bluetooth headphones? Set Sound delay in", "Settings first (they play sound late)."]
                 if self.app.audio_ok else
                 ["No sound device found: the test needs sound.", "You can run it later from Settings."])
        self._paragraph(surf, extra, y + 18, ui.MUTED, 17)
        self.demo.draw(surf)
