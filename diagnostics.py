"""Logging, startup facts for bug reports, and the error window shown instead of a
silent crash."""
import logging
import logging.handlers
import os
import platform
import subprocess
import sys
import textwrap

import config

log = logging.getLogger("air_rhythm")


def setup_logging():
    """Log to the console and to a rotating file in the data folder (3 x 1 MB).
    If the data folder can't be created, log to the console only."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)
    try:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        file = logging.handlers.RotatingFileHandler(config.LOG_PATH, maxBytes=1_000_000,
                                                    backupCount=2, encoding="utf-8")
        file.setFormatter(fmt)
        root.addHandler(file)
    except OSError as e:
        log.warning("Can't write the log file %s: %s", config.LOG_PATH, e)


def log_startup_info():
    def version(module):
        try:
            return getattr(__import__(module), "__version__", "?")
        except Exception:                   # a broken install must not stop the log line
            return "not installed"
    import pygame
    log.info("Air Rhythm starting | %s %s | Python %s", platform.system(), platform.release(),
             platform.python_version())
    log.info("pygame-ce %s (SDL %s) | mediapipe %s | opencv %s | numpy %s",
             pygame.version.ver, ".".join(map(str, pygame.get_sdl_version())),
             version("mediapipe"), version("cv2"), version("numpy"))
    log.info("Data folder: %s%s", config.DATA_DIR, " (portable)" if config.PORTABLE else "")


def open_folder(path):
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError as e:
        log.warning("Couldn't open %s: %s", path, e)


def show_fatal_error(title, message):
    """Show an error window and wait until it's closed. Falls back to a Windows message
    box, then to the console, if pygame itself can't show anything."""
    try:
        _pygame_error_window(title, message)
    except Exception:
        log.exception("Couldn't show the error window")
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(None, message, f"Air Rhythm: {title}", 0x10)
                return
            except Exception:
                pass
        print(f"\n{title}\n\n{message}", file=sys.stderr)


def _pygame_error_window(title, message):
    import pygame
    pygame.init()
    W, H = 860, 460
    surf = pygame.display.set_mode((W, H))
    pygame.display.set_caption(f"Air Rhythm: {title}")
    pygame.mouse.set_visible(True)
    families = "segoeui,helveticaneue,ubuntu,dejavusans"
    big = pygame.font.SysFont(families, 30, bold=True)
    body = pygame.font.SysFont(families, 19)
    small = pygame.font.SysFont(families, 16)
    lines = []
    for paragraph in message.split("\n"):
        lines += textwrap.wrap(paragraph, 78) or [""]
    can_open_log = os.path.exists(config.LOG_PATH)
    hint = "L: open the log folder     Esc / Enter: close" if can_open_log else "Esc / Enter: close"

    clock = pygame.time.Clock()
    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                return
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    pygame.quit()
                    return
                if e.key == pygame.K_l and can_open_log:
                    open_folder(config.DATA_DIR)
        surf.fill((14, 12, 26))
        pygame.draw.rect(surf, (255, 110, 120), (0, 0, 6, H))
        surf.blit(big.render(title, True, (255, 255, 255)), (40, 36))
        y = 96
        for line in lines[:14]:
            surf.blit(body.render(line, True, (205, 203, 222)), (40, y))
            y += 26
        surf.blit(small.render(hint, True, (140, 138, 165)), (40, H - 44))
        pygame.display.flip()
        clock.tick(30)


def crash_message(exc):
    """Text for an unexpected error: what happened, and where the log is."""
    where = f"A log was saved to:\n{config.LOG_PATH}" if os.path.exists(config.LOG_PATH) \
        else "The console window shows the details."
    return (f"Air Rhythm hit an unexpected error and had to close.\n\n"
            f"{type(exc).__name__}: {exc}\n\n{where}\n\n"
            "If you report this problem, please include the log.")
