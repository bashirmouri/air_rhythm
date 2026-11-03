"""Draws the app icon in the game's own style and saves src/air_rhythm/resources/icon.png (window icon)
and resources/icon.ico (Windows .exe icon, several sizes). Run from the project root:
    python tools/make_icon.py
Needs pygame-ce and Pillow (requirements-dev.txt)."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "src", "air_rhythm", "resources")
PINK, VIOLET, WHITE = (255, 102, 170), (140, 92, 255), (255, 255, 255)


def lerp(a, b, f):
    return tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))


def draw(size=1024):
    """Drawn large, scaled down later for clean edges."""
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    c, R = size // 2, size * 0.30
    # rounded-square background with a pink -> violet diagonal gradient
    bg = pygame.Surface((size, size), pygame.SRCALPHA)
    for y in range(size):
        pygame.draw.line(bg, lerp((40, 22, 70), (14, 10, 30), y / size), (0, y), (size, y))
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=int(size * 0.22))
    bg.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    s.blit(bg, (0, 0))
    # approach ring (outer), hit circle with gradient fill, white rim
    pygame.draw.circle(s, PINK, (c, c), int(R * 1.42), int(size * 0.035))
    for k in range(40):
        f = k / 39
        pygame.draw.circle(s, lerp(VIOLET, PINK, f), (c, c), int(R * (1 - 0.6 * f)))
    pygame.draw.circle(s, WHITE, (c, c), int(R), int(size * 0.05))
    pygame.draw.circle(s, WHITE, (c, c), int(R * 0.18))     # the cursor dot in the middle
    return s


def main():
    pygame.init()
    os.makedirs(OUT_DIR, exist_ok=True)
    big = draw()
    png = os.path.join(OUT_DIR, "icon.png")
    pygame.image.save(pygame.transform.smoothscale(big, (256, 256)), png)
    try:
        from PIL import Image
    except ImportError:
        sys.exit("Pillow is needed for the .ico: pip install -r requirements-dev.txt")
    Image.open(png).save(os.path.join(OUT_DIR, "icon.ico"),
                         sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("Wrote", png, "and icon.ico")


if __name__ == "__main__":
    main()
