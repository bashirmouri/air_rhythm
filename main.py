"""Air Rhythm: an osu!-style rhythm game played by pinching in front of a webcam.

    python main.py              hand mode (webcam)
    python main.py --mouse      mouse + click / Z / X (no camera needed)
    python main.py --autoplay   watch a perfect play
"""
import argparse
import collections
import time

import pygame

import config
import settings as settings_mod
import ui
from audio_gen import make_hitsound
from inputs import HandInput, MouseInput
from map_gen import LEVEL_PATHS, ensure_assets
from playfield import Playfield


class App:
    def __init__(self, args):
        ensure_assets()
        pygame.mixer.pre_init(config.SAMPLE_RATE, -16, 2, config.AUDIO_BUFFER)
        pygame.init()
        pygame.display.set_caption(config.TITLE)
        try:
            self.surface = pygame.display.set_mode((config.WINDOW_W, config.WINDOW_H),
                                                   pygame.SCALED, vsync=1)
        except pygame.error:
            self.surface = pygame.display.set_mode((config.WINDOW_W, config.WINDOW_H), pygame.SCALED)
        pygame.mouse.set_visible(False)

        self.settings = settings_mod.load()
        if args.mouse:
            self.settings["input_mode"] = "mouse"
        self.autoplay = args.autoplay
        if self.settings["level"] not in LEVEL_PATHS:
            self.settings["level"] = settings_mod.DEFAULTS["level"]
        self.map_path = args.map or LEVEL_PATHS[self.settings["level"]]
        self.playfield = Playfield(config.WINDOW_W, config.WINDOW_H)
        self.background = ui.make_background(config.WINDOW_W, config.WINDOW_H)
        self.hitsound = pygame.sndarray.make_sound(make_hitsound())
        self.hitsound.set_volume(0.5)
        self.trail = collections.deque(maxlen=14)
        self.input = None
        self.set_input_mode(self.settings["input_mode"])

        from screens import MenuScreen
        self.screen = None
        self.goto(MenuScreen(self))
        self.running = True

    # ------------------------------------------------------------- helpers
    def set_input_mode(self, mode):
        if self.input:
            self.input.close()
        self.input = HandInput(self.playfield) if mode == "hand" else MouseInput(self.playfield)
        self.settings["input_mode"] = mode

    def set_level(self, level):
        self.settings["level"] = level
        self.map_path = LEVEL_PATHS[level]

    def goto(self, screen):
        if self.input:
            self.input.take_presses()        # don't carry clicks into the next screen
        self.screen = screen

    def quit(self):
        self.running = False

    def to_screen(self, osu_pos):
        return None if osu_pos is None else self.playfield.to_screen(*osu_pos)

    def cursor_screen(self):
        override = getattr(self.screen, "cursor_override", lambda: None)()
        return self.to_screen(override if override is not None else self.input.cursor())

    # ------------------------------------------------------------- drawing on top of every screen
    def draw_cursor(self, surf):
        pos = self.cursor_screen()
        now = time.perf_counter()
        if pos is not None:
            self.trail.append((pos, now))
        for p, t in self.trail:
            age = now - t
            if age < 0.15:
                a = int(120 * (1 - age / 0.15))
                dot = pygame.Surface((14, 14), pygame.SRCALPHA)
                pygame.draw.circle(dot, (255, 255, 255, a), (7, 7), 5)
                surf.blit(dot, (p[0] - 7, p[1] - 7))
        if pos is None:
            return
        down = getattr(self.screen, "cursor_down_override", lambda: None)()
        if down is None:
            down = self.input.is_down()
        x, y = int(pos[0]), int(pos[1])
        if down:
            pygame.draw.circle(surf, (255, 220, 120), (x, y), 12)
            pygame.draw.circle(surf, ui.WHITE, (x, y), 12, 2)
        else:
            pygame.draw.circle(surf, ui.WHITE, (x, y), 15, 3)
            pygame.draw.circle(surf, ui.WHITE, (x, y), 3)

    def draw_camera_preview(self, surf):
        if not self.settings["show_camera"]:
            return
        img = self.input.preview_surface()
        if img is None:
            return
        W, H = surf.get_size()
        rect = img.get_rect(bottomright=(W - 16, H - 16))
        img.set_alpha(200)
        surf.blit(img, rect)
        pygame.draw.rect(surf, (255, 255, 255), rect.inflate(4, 4), 2, border_radius=4)

    # ------------------------------------------------------------- main loop
    def run(self):
        clock = pygame.time.Clock()
        try:
            while self.running:
                events = pygame.event.get()
                for e in events:
                    if e.type == pygame.QUIT:
                        self.running = False
                    elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                        pygame.display.toggle_fullscreen()
                    elif e.type == pygame.KEYDOWN and e.key == pygame.K_v:
                        self.settings["show_camera"] = not self.settings["show_camera"]
                self.input.handle_events(events)
                screen = self.screen
                screen.handle(events)
                if screen is self.screen:        # handle() may have switched screens
                    screen.update()
                self.screen.draw(self.surface)
                self.draw_camera_preview(self.surface)
                self.draw_cursor(self.surface)
                pygame.display.flip()
                clock.tick(config.TARGET_FPS)
        finally:
            self.input.close()
            settings_mod.save(self.settings)
            pygame.quit()


def main():
    parser = argparse.ArgumentParser(description="Air Rhythm")
    parser.add_argument("--mouse", action="store_true", help="play with the mouse instead of the webcam")
    parser.add_argument("--autoplay", action="store_true", help="watch the game play itself")
    parser.add_argument("--map", help="path to a beatmap.json")
    App(parser.parse_args()).run()


if __name__ == "__main__":
    main()
