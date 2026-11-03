"""Small drawing helpers shared by all screens, plus the main menu's widgets."""
import math
import time

import pygame

WHITE = (255, 255, 255)
DIM = (170, 170, 190)
MUTED = (120, 118, 145)
ACCENT = (255, 102, 170)
ACCENT_2 = (140, 92, 255)       # second gradient color (violet)
OK = (110, 230, 160)
WARN = (255, 190, 120)
BG_TOP, BG_BOTTOM = (22, 18, 38), (8, 8, 16)

_fonts = {}
_sans = {}
# Modern UI fonts in order of preference (Windows, macOS, Linux), else pygame's default
_FAMILIES = {
    "regular": "segoeui,helveticaneue,sfprotext,ubuntu,dejavusans",
    "semibold": "segoeuisemibold,helveticaneuemedium,ubuntumedium,dejavusansbold",
    "black": "segoeuiblack,helveticaneueblack,arialblack,ubuntubold,dejavusansbold",
}


def font(size):
    if size not in _fonts:
        _fonts[size] = pygame.font.Font(None, size)
    return _fonts[size]


def sans(size, weight="regular"):
    """A system UI font (Segoe UI on Windows). Falls back to pygame's default font."""
    key = (size, weight)
    if key not in _sans:
        path = pygame.font.match_font(_FAMILIES[weight])
        if path:
            _sans[key] = pygame.font.Font(path, size)
        else:                               # the default font renders smaller, so scale it up
            _sans[key] = pygame.font.Font(None, int(size * 1.35))
            _sans[key].set_bold(weight != "regular")
    return _sans[key]


def text(surf, s, size, color, pos, anchor="center", alpha=255):
    img = font(size).render(s, True, color)
    if alpha < 255:
        img.set_alpha(alpha)
    rect = img.get_rect(**{anchor: pos})
    surf.blit(img, rect)
    return rect


_rendered = {}


def render(s, size, color, weight="regular", spacing=0):
    """Rendered text, cached: the menu draws the same strings every frame."""
    key = (s, size, color, weight, spacing)
    img = _rendered.get(key)
    if img is None:
        if len(_rendered) > 512:
            _rendered.clear()
        f = sans(size, weight)
        if spacing:
            glyphs = [f.render(ch, True, color) for ch in s]
            img = pygame.Surface((sum(g.get_width() for g in glyphs) + spacing * (len(s) - 1),
                                  f.get_height()), pygame.SRCALPHA)
            x = 0
            for g in glyphs:
                img.blit(g, (x, 0))
                x += g.get_width() + spacing
        else:
            img = f.render(s, True, color)
        _rendered[key] = img
    return img


def label(surf, s, size, color, pos, anchor="center", weight="regular", alpha=255, spacing=0):
    """Like text(), with the UI font. `spacing` adds letter spacing in pixels."""
    img = render(s, size, color, weight, spacing)
    if alpha < 255:
        img = img.copy()                    # don't change the cached image
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


# ====================================================================== main menu widgets
_panels = {}


def panel(surf, rect, fill, border=None, radius=14, width=1):
    """Rounded rectangle with see-through fill / border colors (RGBA). Cached per look."""
    key = (rect.size, fill, border, radius, width)
    layer = _panels.get(key)
    if layer is None:
        if len(_panels) > 512:
            _panels.clear()
        layer = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(layer, fill, layer.get_rect(), border_radius=radius)
        if border:
            pygame.draw.rect(layer, border, layer.get_rect(), width, border_radius=radius)
        _panels[key] = layer
    surf.blit(layer, rect)


def ring(surf, color, center, r, width):
    """Antialiased circle outline (plain circle on pygame versions without aacircle)."""
    draw = getattr(pygame.draw, "aacircle", pygame.draw.circle)
    draw(surf, color, (int(center[0]), int(center[1])), int(r), int(width))


def disc(surf, color, center, r):
    draw = getattr(pygame.draw, "aacircle", pygame.draw.circle)
    draw(surf, color, (int(center[0]), int(center[1])), int(r))


def gradient_card(size, left, right, radius):
    """Horizontal gradient with rounded corners."""
    w, h = size
    card = pygame.Surface(size, pygame.SRCALPHA)
    for x in range(w):
        pygame.draw.line(card, lerp_color(left, right, x / max(w - 1, 1)), (x, 0), (x, h))
    mask = pygame.Surface(size, pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
    card.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return card


def make_glow(radius, color):
    """Soft round light, drawn with BLEND_ADD on a dark background."""
    glow = pygame.Surface((radius * 2, radius * 2))
    for r in range(radius, 0, -2):
        f = (1 - r / radius) ** 2.2
        pygame.draw.circle(glow, tuple(int(c * f) for c in color), (radius, radius), r)
    return glow


def keycap(surf, key, pos):
    """A small keyboard key, e.g. [Enter]. Returns its right edge."""
    img = render(key, 14, DIM, "semibold")
    rect = pygame.Rect(0, 0, max(img.get_width() + 14, 26), 24)
    rect.midleft = pos
    panel(surf, rect, (255, 255, 255, 14), (255, 255, 255, 40), radius=6)
    surf.blit(img, img.get_rect(center=rect.center))
    return rect.right


class _Animated:
    """Hover amount that eases 0 -> 1 instead of snapping."""
    hover = 0.0
    _last = None

    def ease(self, hovered):
        now = time.perf_counter()
        dt = 0.0 if self._last is None else now - self._last
        self._last = now
        self.hover += ((1.0 if hovered else 0.0) - self.hover) * min(1.0, dt * 14)
        return self.hover


class PlayCard(_Animated):
    """The big primary button: PLAY, the song and level, and a round play icon."""

    def __init__(self, rect, action, subtitle):
        self.rect, self.action, self.subtitle = pygame.Rect(rect), action, subtitle
        self._card = gradient_card(self.rect.size, ACCENT, ACCENT_2, 18)
        self._glow = make_glow(self.rect.width // 2, (90, 30, 70))

    def contains(self, pos):
        return pos is not None and self.rect.collidepoint(pos)

    def draw(self, surf, hovered):
        h = self.ease(hovered)
        if h > 0.01:
            self._glow.set_alpha(int(255 * h))
            surf.blit(self._glow, self._glow.get_rect(center=self.rect.center),
                      special_flags=pygame.BLEND_ADD)
        rect = self.rect.move(0, -3 * h)
        surf.blit(self._card, rect)
        if h > 0.01:                        # brighten on hover
            panel(surf, rect, (255, 255, 255, int(30 * h)), radius=18)
        label(surf, "PLAY", 40, WHITE, (rect.x + 30, rect.centery - 13), "midleft", "black", spacing=2)
        label(surf, self.subtitle(), 19, (255, 235, 245), (rect.x + 32, rect.centery + 23), "midleft")
        # play icon: white disc with a triangle
        c = (rect.right - 54, rect.centery)
        disc(surf, WHITE, c, 26 + 2 * h)
        s = 10
        pygame.draw.polygon(surf, ACCENT_2, [(c[0] - s * 0.6, c[1] - s), (c[0] - s * 0.6, c[1] + s),
                                             (c[0] + s, c[1])])


class OptionRow(_Animated):
    """A settings row: label on the left, current value on the right. Clicking it
    runs `action`. `value()` returns one of:
      str                    -> plain text (e.g. "+12 ms")
      bool                   -> on/off switch
      (options, selected)    -> segmented control, selected one highlighted"""

    def __init__(self, rect, text_, action, value=None, danger=False):
        self.rect, self.text, self.action, self.value = pygame.Rect(rect), text_, action, value
        self.danger = danger

    def contains(self, pos):
        return pos is not None and self.rect.collidepoint(pos)

    def draw(self, surf, hovered):
        h = self.ease(hovered)
        r = self.rect
        panel(surf, r, (255, 255, 255, int(10 + 16 * h)), (255, 255, 255, int(22 + 40 * h)), radius=14)
        accent = (255, 110, 120) if self.danger else ACCENT
        if h > 0.01:                        # accent bar grows on the left edge
            bar_h = int((r.height - 20) * h)
            pygame.draw.rect(surf, accent, (r.x + 8, r.centery - bar_h // 2, 3, bar_h), border_radius=2)
        color = lerp_color((215, 213, 230), WHITE, h)
        if self.danger:
            color = lerp_color((200, 198, 215), (255, 140, 150), h)
        label(surf, self.text, 20, color, (r.x + 22 + 6 * h, r.centery), "midleft", "semibold")
        if self.value is not None:
            self._draw_value(surf, self.value(), (r.right - 16, r.centery))

    @staticmethod
    def _draw_value(surf, value, right_mid):
        x, y = right_mid
        if isinstance(value, bool):         # on/off switch
            track = pygame.Rect(0, 0, 46, 26)
            track.midright = (x, y)
            pygame.draw.rect(surf, ACCENT if value else (70, 66, 92), track, border_radius=13)
            knob_x = track.right - 13 if value else track.x + 13
            disc(surf, WHITE, (knob_x, y), 9)
        elif isinstance(value, tuple):      # segmented control
            options, selected = value
            imgs = [render(o, 16, WHITE if o == selected else MUTED, "semibold") for o in options]
            widths = [img.get_width() + 24 for img in imgs]
            outer = pygame.Rect(0, 0, sum(widths) + 6, 30)
            outer.midright = (x, y)
            panel(surf, outer, (0, 0, 0, 70), (255, 255, 255, 25), radius=15)
            sx = outer.x + 3
            for o, img, w in zip(options, imgs, widths, strict=True):
                seg = pygame.Rect(sx, outer.y + 3, w, outer.height - 6)
                if o == selected:
                    pygame.draw.rect(surf, ACCENT, seg, border_radius=12)
                surf.blit(img, img.get_rect(center=seg.center))
                sx += w
        else:                               # text with a chevron
            right = label(surf, "›", 26, MUTED, (x, y - 2), "midright")
            label(surf, str(value), 17, DIM, (right.x - 10, y), "midright", "semibold")


class HitCircleDemo:
    """Decorative hit circle that keeps getting 'hit' on a beat: the approach ring
    shrinks onto it, then a burst ring flies out. Combo colors and numbers cycle."""

    def __init__(self, center, radius, colors, period=1.0):
        self.center, self.radius, self.colors, self.period = center, radius, colors, period
        self.t0 = time.perf_counter()

    def draw(self, surf):
        t = (time.perf_counter() - self.t0) / self.period
        beat, f = int(t), t % 1.0
        color = self.colors[beat % len(self.colors)]
        prev = self.colors[(beat - 1) % len(self.colors)]
        cx, cy = self.center
        R = self.radius
        # burst from the previous hit
        if f < 0.35:
            k = f / 0.35
            size = int(R * 3.2)
            layer = pygame.Surface((size, size), pygame.SRCALPHA)
            ring(layer, (*prev, int(200 * (1 - k))), (size / 2, size / 2), R * (1 + 0.45 * k),
                 max(1, 6 * (1 - k)))
            surf.blit(layer, (cx - size / 2, cy - size / 2))
        # the circle: soft shadow, colored body, white border, number
        pop = 1 + 0.06 * math.exp(-f * 12)
        disc(surf, lerp_color(color, (0, 0, 0), 0.82), (cx, cy + 6), R * pop)
        disc(surf, lerp_color(color, (20, 16, 34), 0.35), (cx, cy), R * pop)
        ring(surf, WHITE, (cx, cy), R * pop, 6)
        label(surf, str(beat % 4 + 1), int(R * 0.9), WHITE, (cx, cy + 2), "center", "black")
        # approach ring shrinking toward the circle
        ring(surf, color, (cx, cy), R * (1 + 1.4 * (1 - f)), 4)
