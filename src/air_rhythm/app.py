"""Startup, the main loop and crash handling: holds the current screen and draws the cursor.

    python -m air_rhythm              hand mode (webcam)
    python -m air_rhythm --mouse      mouse + click / Z / X (no camera needed)
    python -m air_rhythm --autoplay   watch a perfect play
    python -m air_rhythm --portable   keep settings and generated files next to the game
"""
import argparse
import collections
import logging
import os
import time

import pygame

from air_rhythm.content.audio_gen import make_hitsound
from air_rhythm.content.map_gen import LEVEL_PATHS, MENU_MUSIC, StartupError, ensure_assets
from air_rhythm.controls.inputs import HandInput, MouseInput
from air_rhythm.core.beatmap import load_beatmap
from air_rhythm.core.playfield import Playfield
from air_rhythm.system import config, diagnostics
from air_rhythm.system import settings as settings_mod
from air_rhythm.ui import widgets as ui

log = logging.getLogger("air_rhythm")


class _SilentSound:
    """Stands in for a pygame Sound when there is no audio device."""
    def play(self, *args, **kwargs):
        pass

    def set_volume(self, volume):
        pass


class App:
    def __init__(self, args):
        ensure_assets()
        pygame.mixer.pre_init(config.SAMPLE_RATE, -16, 2, config.AUDIO_BUFFER)
        pygame.init()
        pygame.display.set_caption(config.TITLE)
        try:
            pygame.display.set_icon(pygame.image.load(config.ICON_PATH))
        except (pygame.error, FileNotFoundError):
            log.warning("Window icon not found at %s", config.ICON_PATH)
        try:
            self.surface = pygame.display.set_mode((config.WINDOW_W, config.WINDOW_H),
                                                   pygame.SCALED, vsync=1)
        except pygame.error:
            self.surface = pygame.display.set_mode((config.WINDOW_W, config.WINDOW_H), pygame.SCALED)
        pygame.mouse.set_visible(False)
        # No sound device (or it's busy): play silently instead of crashing
        self.audio_ok = pygame.mixer.get_init() is not None
        self.warning = None if self.audio_ok else "No sound device found: playing without sound"

        self.settings = settings_mod.load()
        if args.mouse:
            self.settings["input_mode"] = "mouse"
        self.autoplay = args.autoplay
        if self.settings["level"] not in LEVEL_PATHS:
            self.settings["level"] = settings_mod.DEFAULTS["level"]
        self.map_path = LEVEL_PATHS[self.settings["level"]]
        if args.map:
            if self._map_is_playable(args.map):
                self.map_path = args.map
            else:
                self.warning = f"Couldn't load {os.path.basename(args.map)}: playing First Steps instead"
        self.playfield = Playfield(config.WINDOW_W, config.WINDOW_H)
        self.background = ui.make_background(config.WINDOW_W, config.WINDOW_H)
        self._menu_music_on = False
        if self.audio_ok:
            self.hitsound = pygame.sndarray.make_sound(make_hitsound())
            self.hitsound.set_volume(0.5)
            # Menu music gets its own reserved channel, so hitsounds never cut it off and it can
            # fade out on its own while the song (pygame.mixer.music) loads and starts.
            pygame.mixer.set_reserved(1)
            self.music_channel = pygame.mixer.Channel(0)
            self.menu_music = pygame.mixer.Sound(MENU_MUSIC)
        else:
            self.hitsound = _SilentSound()
        self.trail = collections.deque(maxlen=14)
        self.frame_clock = pygame.time.Clock()
        self._fullscreen = False
        self.input = None
        self.set_input_mode(self.settings["input_mode"])

        from air_rhythm.ui.screens.menu import MenuScreen
        from air_rhythm.ui.screens.onboarding import OnboardingScreen
        self.screen = None
        first_start = not self.settings["setup_done"] and self.input.kind == "hand" and not args.autoplay
        self.goto(OnboardingScreen(self) if first_start else MenuScreen(self))
        self.apply_settings()                # volumes, fullscreen
        self.screen.draw(self.surface)      # warm-up: loads fonts and glyphs before the first shown frame
        self.running = True
        # With vsync, flip() already waits for the monitor, so the frame limiter must not sleep too:
        # it fights vsync (120 fps on a 144 Hz screen = uneven frames) and its sleep sometimes
        # overshoots by a whole frame. Without vsync we cap at TARGET_FPS.
        self.vsync = pygame.display.is_vsync()
        self.refresh = max(pygame.display.get_desktop_refresh_rates() or [60])
        log.info("Display: %s driver, vsync %s, %d Hz | audio: %s", pygame.display.get_driver(),
                 "on" if self.vsync else "off", self.refresh,
                 pygame.mixer.get_init() if self.audio_ok else "none")
        if self.warning:
            log.warning(self.warning)

    @staticmethod
    def _map_is_playable(path):
        try:
            bm = load_beatmap(path)
            if bm.objects and os.path.exists(bm.audio_path):
                return True
            log.warning("Beatmap %s has no circles or its audio file is missing", path)
        except (OSError, ValueError, KeyError, TypeError) as e:
            log.warning("Couldn't load beatmap %s: %s", path, e)
        return False

    # ------------------------------------------------------------- helpers
    def set_input_mode(self, mode):
        if self.input:
            self.input.close()
        if mode == "hand":
            self.input = HandInput(self.playfield, self.settings)
        else:
            self.input = MouseInput(self.playfield)
        self.settings["input_mode"] = mode

    def apply_settings(self):
        """Use the current settings right away (the Settings screen calls this on every change)."""
        s = self.settings
        if not self.input.apply(s):          # another camera: restart hand tracking with it
            self.set_input_mode(self.input.kind)
        if self.audio_ok:
            self.hitsound.set_volume(s["hitsound_volume"] / 100)
            self.menu_music.set_volume(s["menu_music_volume"] / 100)
            pygame.mixer.music.set_volume(s["music_volume"] / 100)
        self.update_menu_music()
        if s["fullscreen"] != self._fullscreen:
            try:
                pygame.display.toggle_fullscreen()
                self._fullscreen = s["fullscreen"]
            except pygame.error as e:          # some drivers can't; stay windowed
                log.warning("Couldn't switch fullscreen: %s", e)
                s["fullscreen"] = self._fullscreen

    def set_level(self, level):
        self.settings["level"] = level
        self.map_path = LEVEL_PATHS[level]

    def goto(self, screen):
        if self.input:
            self.input.take_presses()        # don't carry clicks into the next screen
        self.screen = screen
        self.update_menu_music()

    def update_menu_music(self):
        """Fade the menu music in on screens that want it (the menu), out everywhere else."""
        if not self.audio_ok:
            return
        want = (getattr(self.screen, "menu_music", False) and self.settings["menu_music"]
                and self.settings["menu_music_volume"] > 0)
        if want and not self._menu_music_on:
            self.music_channel.stop()        # in case it is still fading out
            self.music_channel.play(self.menu_music, loops=-1, fade_ms=config.MENU_MUSIC_FADE_IN_MS)
        elif not want and self._menu_music_on:
            self.music_channel.fadeout(config.MENU_MUSIC_FADE_OUT_MS)
        self._menu_music_on = want

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
        if not self.settings["show_camera"] or getattr(self.screen, "draws_camera_preview", False):
            return
        img = self.input.preview_surface()
        if img is None:
            return
        W, H = surf.get_size()
        rect = img.get_rect(bottomright=(W - 16, H - 16))
        img.set_alpha(200)
        surf.blit(img, rect)
        pygame.draw.rect(surf, (255, 255, 255), rect.inflate(4, 4), 2, border_radius=4)

    def draw_fps(self, surf):
        if self.settings["show_fps"]:
            ui.label(surf, f"{self.frame_clock.get_fps():.0f} fps", 13, ui.DIM, (8, 6), "topleft", "semibold")

    # ------------------------------------------------------------- main loop
    def run(self):
        clock = self.frame_clock
        # For automated checks of the packaged game (it has no console to stop it from):
        # AIR_RHYTHM_QUIT_AFTER_S=8 closes it normally after 8 seconds.
        quit_after = float(os.environ.get("AIR_RHYTHM_QUIT_AFTER_S") or 0)
        started = time.perf_counter()
        try:
            while self.running:
                if quit_after and time.perf_counter() - started > quit_after:
                    log.info("Closing after %.0f s (AIR_RHYTHM_QUIT_AFTER_S)", quit_after)
                    self.running = False
                events = pygame.event.get()
                for e in events:
                    if e.type == pygame.QUIT:
                        self.running = False
                    elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                        self.settings["fullscreen"] = not self.settings["fullscreen"]
                        self.apply_settings()
                    elif e.type == pygame.KEYDOWN and e.key == pygame.K_v:
                        self.settings["show_camera"] = not self.settings["show_camera"]
                self.input.handle_events(events)
                screen = self.screen
                screen.handle(events)
                if screen is self.screen:        # handle() may have switched screens
                    screen.update()
                self.screen.draw(self.surface)
                self.draw_camera_preview(self.surface)
                self.draw_fps(self.surface)
                self.draw_cursor(self.surface)
                pygame.display.flip()
                if self.vsync:
                    clock.tick()                     # just measures; flip() did the waiting
                    if clock.get_fps() > 1.5 * self.refresh:
                        self.vsync = False           # the driver ignores vsync: cap it ourselves
                else:
                    clock.tick(config.TARGET_FPS)
        finally:
            self.input.close()
            settings_mod.save(self.settings)
            pygame.quit()
            log.info("Air Rhythm closed")


def main():
    parser = argparse.ArgumentParser(prog="air-rhythm", description="Air Rhythm")
    parser.add_argument("--mouse", action="store_true", help="play with the mouse instead of the webcam")
    parser.add_argument("--autoplay", action="store_true", help="watch the game play itself")
    parser.add_argument("--map", help="path to a beatmap.json")
    parser.add_argument("--portable", action="store_true",
                        help="keep settings and generated files next to the game (see config.py)")
    args = parser.parse_args()

    diagnostics.setup_logging()
    diagnostics.log_startup_info()
    settings_mod.migrate_legacy_files()
    try:
        App(args).run()
    except StartupError as e:                # the player can fix this one: say how
        log.error("Startup failed: %s", e)
        diagnostics.show_fatal_error("Air Rhythm can't start", str(e))
    except Exception as e:                   # anything else: log it and explain, don't just vanish
        log.exception("Unexpected error")
        diagnostics.show_fatal_error("Something went wrong", diagnostics.crash_message(e))


if __name__ == "__main__":
    main()
