"""The pause card shown on top of a frozen song: Resume, Retry, Quit to menu.

Not a screen of its own: PlayScreen keeps running underneath (frozen) and passes events,
presses and drawing to this card while the song is paused."""
import pygame

from air_rhythm.ui import widgets as ui
from air_rhythm.ui.screens.base import ButtonScreen

CARD_W, CARD_H = 460, 330
ROW_H, ROW_GAP = 56, 12


class PauseMenu(ButtonScreen):
    def __init__(self, app, resume, retry, quit_to_menu):
        self.app = app
        W, H = app.surface.get_size()
        self.card = pygame.Rect(0, 0, CARD_W, CARD_H)
        self.card.center = (W // 2, H // 2)
        x, w = self.card.x + 28, CARD_W - 56
        y = self.card.y + 116
        self.buttons = [
            ui.OptionRow((x, y, w, ROW_H), "Resume", resume, lambda: "Esc"),
            ui.OptionRow((x, y + ROW_H + ROW_GAP, w, ROW_H), "Retry", retry, lambda: "R"),
            ui.OptionRow((x, y + 2 * (ROW_H + ROW_GAP), w, ROW_H), "Quit to menu", quit_to_menu,
                         lambda: "Q", danger=True),
        ]
        self.keys = {pygame.K_ESCAPE: resume, pygame.K_RETURN: resume, pygame.K_SPACE: resume,
                     pygame.K_r: retry, pygame.K_q: quit_to_menu}
        self._dim = pygame.Surface((W, H), pygame.SRCALPHA)
        self._dim.fill((6, 5, 12, 170))

    def handle(self, events):
        self.handle_mouse(events)
        for e in events:
            if e.type == pygame.KEYDOWN and e.key in self.keys:
                self.keys[e.key]()
                return

    def draw(self, surf, subtitle):
        surf.blit(self._dim, (0, 0))
        ui.panel(surf, self.card, (22, 18, 38, 235), (255, 255, 255, 40), radius=22)
        cx = self.card.centerx
        ui.label(surf, "PAUSED", 15, ui.ACCENT, (cx, self.card.y + 42), "center", "semibold", spacing=3)
        ui.label(surf, subtitle, 22, ui.WHITE, (cx, self.card.y + 78), "center", "semibold")
        self.draw_buttons(surf)
