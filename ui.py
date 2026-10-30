"""Small drawing helpers shared by all screens."""
import pygame

WHITE = (255, 255, 255)
DIM = (170, 170, 190)
ACCENT = (255, 102, 170)
BG_TOP, BG_BOTTOM = (22, 18, 38), (8, 8, 16)

_fonts = {}


def font(size):
    if size not in _fonts:
        _fonts[size] = pygame.font.Font(None, size)
    return _fonts[size]


def text(surf, s, size, color, pos, anchor="center", alpha=255):
    img = font(size).render(s, True, color)
    if alpha < 255:
        img.set_alpha(alpha)
    rect = img.get_rect(**{anchor: pos})
    surf.blit(img, rect)
    return rect


def lerp_color(a, b, f):
    f = min(max(f, 0.0), 1.0)
    return tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))


def make_background(w, h):
    bg = pygame.Surface((w, h))
    for y in range(h):
        pygame.draw.line(bg, lerp_color(BG_TOP, BG_BOTTOM, y / h), (0, y), (w, y))
    return bg


class Button:
    def __init__(self, label, center, size=(420, 62), action=None):
        self.label = label
        self.rect = pygame.Rect(0, 0, *size)
        self.rect.center = center
        self.action = action

    def contains(self, pos):
        return pos is not None and self.rect.collidepoint(pos)

    def draw(self, surf, hovered):
        layer = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        fill = (255, 102, 170, 200) if hovered else (255, 255, 255, 28)
        pygame.draw.rect(layer, fill, layer.get_rect(), border_radius=18)
        pygame.draw.rect(layer, (255, 255, 255, 140 if hovered else 60), layer.get_rect(), 2,
                         border_radius=18)
        surf.blit(layer, self.rect)
        text(surf, self.label, 38, WHITE, self.rect.center)
