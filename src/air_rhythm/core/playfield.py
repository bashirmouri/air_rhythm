"""Converts between osu! playfield coordinates (512 x 384) and window pixels."""
from air_rhythm.system import config


class Playfield:
    def __init__(self, win_w, win_h):
        self.scale = min(win_w * 0.85 / config.PLAYFIELD_W, win_h * 0.78 / config.PLAYFIELD_H)
        self.w = config.PLAYFIELD_W * self.scale
        self.h = config.PLAYFIELD_H * self.scale
        self.ox = (win_w - self.w) / 2
        self.oy = (win_h - self.h) / 2 + win_h * 0.03   # a bit lower, leaves room for the HUD

    def to_screen(self, x, y):
        return self.ox + x * self.scale, self.oy + y * self.scale

    def to_osu(self, sx, sy):
        return (sx - self.ox) / self.scale, (sy - self.oy) / self.scale
