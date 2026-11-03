"""Shared logic for screens made of buttons (menu, results)."""
import time

import pygame

MOUSE_ACTIVE_S = 2.0     # after the mouse moves, its cursor is shown instead of the hand for this long


class ButtonScreen:
    """Shared logic: hover with the cursor, press (click or pinch) to activate.
    The mouse works on these screens even in hand mode, so the buttons can
    still be reached when the camera isn't working."""
    buttons = []
    _mouse_moved_at = None

    def handle_mouse(self, events):
        if self.app.input.kind == "mouse":
            return                      # MouseInput already turns clicks into presses
        for e in events:
            if e.type == pygame.MOUSEMOTION:
                self._mouse_moved_at = time.perf_counter()
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self._mouse_moved_at = time.perf_counter()
                for b in self.buttons:
                    if b.contains(e.pos):
                        b.action()
                        return

    def cursor_override(self):
        """Show the mouse instead of the hand while it's being used, or when no hand is seen."""
        if self.app.input.kind == "mouse" or self._mouse_moved_at is None:
            return None
        if (self.app.input.cursor() is None
                or time.perf_counter() - self._mouse_moved_at < MOUSE_ACTIVE_S):
            return self.app.playfield.to_osu(*pygame.mouse.get_pos())
        return None

    def update(self):
        for _, pos in self.app.input.take_presses():
            sp = self.app.to_screen(pos)
            for b in self.buttons:
                if b.contains(sp):
                    b.action()
                    return

    def draw_buttons(self, surf):
        cursor = self.app.cursor_screen()
        for b in self.buttons:
            b.draw(surf, b.contains(cursor))
