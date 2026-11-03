"""Results after a song: grade, score, accuracy, judgment counts and timing."""
import pygame

from air_rhythm.core.gameplay import JUDGE_COLORS
from air_rhythm.ui import widgets as ui
from air_rhythm.ui.screens.base import ButtonScreen
from air_rhythm.ui.screens.menu import MenuScreen
from air_rhythm.ui.screens.play import PlayScreen

GRADE_COLORS = {"SS": (255, 230, 120), "S": (255, 210, 90), "A": (130, 230, 130),
                "B": (110, 190, 255), "C": (200, 140, 255), "D": (255, 110, 110), "F": (255, 80, 80)}


class ResultsScreen(ButtonScreen):
    def __init__(self, app, game, map_path, autoplay=False):
        self.app, self.game, self.map_path, self.autoplay = app, game, map_path, autoplay
        W, H = app.surface.get_size()
        self.buttons = [ui.Button("Retry", (W // 2 - 230, H - 80), (400, 62), self.retry),
                        ui.Button("Menu", (W // 2 + 230, H - 80), (400, 62), self.menu)]

    def retry(self):
        self.app.goto(PlayScreen(self.app, self.map_path, self.autoplay))

    def menu(self):
        self.app.goto(MenuScreen(self.app))

    def handle(self, events):
        self.handle_mouse(events)
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r):
                    self.retry()
                elif e.key == pygame.K_ESCAPE:
                    self.menu()

    def draw(self, surf):
        g = self.game
        W, H = surf.get_size()
        surf.blit(self.app.background, (0, 0))
        ui.text(surf, f"{g.bm.title}  [{g.bm.version}]", 48, ui.WHITE, (W // 2, 60))
        if g.failed:
            ui.text(surf, "FAILED", 40, (255, 100, 100), (W // 2, 105))
        grade = g.grade()
        ui.text(surf, grade, 260, GRADE_COLORS[grade], (W * 0.27, H * 0.45))

        x, y = W * 0.52, 160
        rows = [("Score", f"{g.score:,}"), ("Accuracy", f"{g.accuracy * 100:.2f}%"),
                ("Max combo", f"{g.max_combo}x")]
        for label, value in rows:
            ui.text(surf, label, 34, ui.DIM, (x, y), "topleft")
            ui.text(surf, value, 52, ui.WHITE, (x + 230, y - 6), "topleft")
            y += 62
        y += 10
        for j, label in ((300, "300"), (100, "100"), (50, "50"), (0, "Miss")):
            ui.text(surf, label, 36, JUDGE_COLORS[j], (x, y), "topleft")
            ui.text(surf, str(g.counts[j]), 36, ui.WHITE, (x + 120, y), "topleft")
            y += 40
        y += 14
        mean = g.mean_error
        when = "late" if mean > 0 else "early"
        ui.text(surf, f"Average timing: {abs(mean):.0f} ms {when}    Unstable rate: {g.unstable_rate:.0f}",
                28, ui.DIM, (x, y), "topleft")
        if abs(mean) > 25 and not self.autoplay:
            ui.text(surf, "Tip: run Calibrate offset from the menu to fix a constant delay.",
                    24, (255, 190, 120), (x, y + 32), "topleft")
        self.draw_buttons(surf)
