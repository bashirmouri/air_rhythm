"""The gameplay screen: runs the song, sends presses to the rules, draws everything."""
import collections
import math

import pygame

from air_rhythm.core.beatmap import load_beatmap
from air_rhythm.core.clock import SongClock
from air_rhythm.core.gameplay import JUDGE_COLORS, Gameplay
from air_rhythm.system import config
from air_rhythm.ui import widgets as ui

COMBO_COLORS = [(255, 102, 170), (102, 204, 255), (255, 200, 90), (150, 240, 150)]


def make_circle_sprite(r, color, number):
    """Hit circle drawn at 2x size then scaled down (cheap anti-aliasing)."""
    ss = 2
    size = int(r * 2 + 8)
    big_size = size * ss
    c = big_size // 2
    R = r * ss
    big = pygame.Surface((big_size, big_size), pygame.SRCALPHA)
    pygame.draw.circle(big, (0, 0, 0, 110), (c, c + 2 * ss), int(R + 2 * ss))   # shadow
    pygame.draw.circle(big, (255, 255, 255, 255), (c, c), int(R))               # white rim
    inner = R * 0.84
    dark = ui.lerp_color(color, (0, 0, 0), 0.45)
    steps = 14
    for k in range(steps):                                                       # gradient fill
        f = k / (steps - 1)
        pygame.draw.circle(big, ui.lerp_color(dark, color, f) + (255,), (c, c),
                           int(inner * (1 - 0.55 * f)))
    f = ui.font(int(R * 0.95))
    shadow = f.render(str(number), True, (0, 0, 0))
    shadow.set_alpha(120)
    big.blit(shadow, shadow.get_rect(center=(c + 2 * ss, c + 2 * ss)))
    label = f.render(str(number), True, (255, 255, 255))
    big.blit(label, label.get_rect(center=(c, c)))
    return pygame.transform.smoothscale(big, (size, size))


class PlayScreen:
    def __init__(self, app, map_path, autoplay=False):
        self.app = app
        self.map_path = map_path
        self.autoplay = autoplay
        self.bm = load_beatmap(map_path)
        self.game = Gameplay(self.bm, no_fail=app.settings["no_fail"] or autoplay)
        self.r_px = self.bm.radius * app.playfield.scale
        self._sprites = {}
        for o in self.bm.objects:            # build every circle image now, not mid-song (no hitches)
            self.sprite(o.color, o.number)
        self.overlay = pygame.Surface(app.surface.get_size(), pygame.SRCALPHA)
        self.anims = []                                   # (object index, judgment, start ms)
        self.recent_errors = collections.deque(maxlen=24)
        self.popups = {j: ui.font(46).render(label, True, JUDGE_COLORS[j])
                       for j, label in ((300, "300"), (100, "100"), (50, "50"), (0, "miss"))}
        self._auto_pos = None
        self._auto_down_until = -1
        self.clock = SongClock()
        self.clock.start(self.bm.audio_path, self.bm.lead_in_ms)

    def sprite(self, color, number):
        key = (color % len(COMBO_COLORS), number)
        if key not in self._sprites:
            self._sprites[key] = make_circle_sprite(self.r_px, COMBO_COLORS[key[0]], number)
        return self._sprites[key]

    # ------------------------------------------------------------- cursor overrides (autoplay)
    def cursor_override(self):
        return self._auto_pos if self.autoplay else None

    def cursor_down_override(self):
        return self.clock.now_ms() < self._auto_down_until if self.autoplay else None

    # ------------------------------------------------------------- events / update
    def handle(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.clock.stop()
                from air_rhythm.ui.screens.menu import MenuScreen
                self.app.goto(MenuScreen(self.app))

    def update(self):
        self.clock.update()
        now = self.clock.now_ms()
        offset = self.app.settings["input_offset_ms"]
        for t, pos in self.app.input.take_presses():
            if pos is not None and not self.autoplay:
                # subtract the calibrated delay so a pinch seen late still counts on time
                self.game.press(self.clock.now_ms(t) - offset, pos)
        if self.autoplay:
            self._autoplay(now)
        self.game.update(now)

        for i, j, _ms, err in self.game.drain_events():
            self.anims.append((i, j, now))
            if j:
                self.app.hitsound.play()
                self.recent_errors.append((err, now))

        if self.game.failed or self.game.finished(now):
            self.clock.stop(fade_ms=1200)
            from air_rhythm.ui.screens.results import ResultsScreen
            self.app.goto(ResultsScreen(self.app, self.game, self.map_path, self.autoplay))

    def _autoplay(self, now):
        objs, g = self.bm.objects, self.game
        i = g.first_unjudged
        while i < len(objs) and objs[i].time <= now:
            if g.results[i] is None:
                g.press(objs[i].time, (objs[i].x, objs[i].y))
                self._auto_down_until = now + 70
            i += 1
        # glide the cursor smoothly from one circle to the next
        idx = min(g.first_unjudged, len(objs) - 1)
        nxt = objs[idx]
        prev = objs[idx - 1] if idx > 0 else None
        if prev is None or nxt.time == prev.time:
            self._auto_pos = (nxt.x, nxt.y)
        else:
            f = min(max((now - prev.time) / (nxt.time - prev.time), 0), 1)
            f = 0.5 - 0.5 * math.cos(math.pi * f)
            self._auto_pos = (prev.x + (nxt.x - prev.x) * f, prev.y + (nxt.y - prev.y) * f)

    # ------------------------------------------------------------- drawing
    def draw(self, surf, now=None):
        if now is None:
            now = self.clock.now_ms()
        surf.blit(self.app.background, (0, 0))
        self._draw_beat_pulse(surf, now)
        self.overlay.fill((0, 0, 0, 0))       # approach circles: drawn here, blended on top below
        self._draw_circles(surf, self.overlay, now)
        self._draw_hit_animations(surf, now)
        surf.blit(self.overlay, (0, 0))
        self._draw_judgments(surf, now)
        self._draw_hud(surf, now)

    def _draw_beat_pulse(self, surf, now):
        """The background brightens briefly on every beat while the song plays."""
        if 0 <= now <= self.bm.objects[-1].time:
            beat_ms = 60000 / self.bm.bpm
            pulse = math.exp(-(now % beat_ms) / 140)
            v = int(10 * pulse)
            if v:
                surf.fill((v, v // 2, v), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_circles(self, surf, ov, now):
        """Circles that are on screen and not judged yet, with their approach circles (on ov)."""
        pf, bm, g = self.app.playfield, self.bm, self.game
        objs = bm.objects
        visible = []
        for i in range(g.first_unjudged, len(objs)):
            if objs[i].time - bm.preempt > now:
                break
            if g.results[i] is None:
                visible.append(i)

        for i in reversed(visible):          # later circles go underneath earlier ones
            o = objs[i]
            sx, sy = pf.to_screen(o.x, o.y)
            alpha = min(max((now - (o.time - bm.preempt)) / bm.fade_in, 0), 1)
            spr = self.sprite(o.color, o.number)
            spr.set_alpha(int(255 * alpha))
            surf.blit(spr, spr.get_rect(center=(sx, sy)))
            # approach circle: shrinks from 3.2x to 1x the radius, closing exactly on time
            f = min(max((o.time - now) / bm.preempt, 0), 1)
            color = COMBO_COLORS[o.color % len(COMBO_COLORS)]
            pygame.draw.circle(ov, color + (int(230 * alpha),), (int(sx), int(sy)),
                               int(self.r_px * (1 + 2.2 * f)), max(2, int(self.r_px * 0.08)))

    def _draw_hit_animations(self, surf, now):
        """Hit circles grow and fade, missed ones fade; drops animations that have finished."""
        pf, objs = self.app.playfield, self.bm.objects
        keep = []
        for i, j, start in self.anims:
            age = now - start
            if age < 0:
                keep.append((i, j, start))
                continue
            o = objs[i]
            sx, sy = pf.to_screen(o.x, o.y)
            spr = self.sprite(o.color, o.number)
            if j and age < config.HIT_ANIM_MS:
                f = age / config.HIT_ANIM_MS
                size = int(spr.get_width() * (1 + 0.45 * f))
                img = pygame.transform.smoothscale(spr, (size, size))
                img.set_alpha(int(255 * (1 - f)))
                surf.blit(img, img.get_rect(center=(sx, sy)))
            elif not j and age < config.MISS_ANIM_MS:
                spr.set_alpha(int(150 * (1 - age / config.MISS_ANIM_MS)))
                surf.blit(spr, spr.get_rect(center=(sx, sy)))
            if age < config.JUDGE_POPUP_MS:
                keep.append((i, j, start))
        self.anims = keep

    def _draw_judgments(self, surf, now):
        """Judgment numbers (300 / 100 / 50 / miss) float up and fade."""
        pf, objs = self.app.playfield, self.bm.objects
        for i, j, start in self.anims:
            f = (now - start) / config.JUDGE_POPUP_MS
            if f < 0:
                continue
            o = objs[i]
            sx, sy = pf.to_screen(o.x, o.y)
            img = self.popups[j]
            img.set_alpha(int((120 if j == 300 else 255) * (1 - f * f)))
            surf.blit(img, img.get_rect(center=(sx, sy - self.r_px * 0.2 - 24 * f)))

    def _draw_hud(self, surf, now):
        W, H = surf.get_size()
        g, objs = self.game, self.bm.objects

        # song progress (thin line at the very top)
        first, last = objs[0].time, objs[-1].time
        p = min(max((now - first) / max(last - first, 1), 0), 1)
        pygame.draw.rect(surf, (255, 255, 255), (0, 0, int(W * p), 4))

        # health bar
        bar = pygame.Rect(24, 22, 360, 12)
        pygame.draw.rect(surf, (45, 42, 62), bar, border_radius=6)
        fill = bar.copy()
        fill.width = max(0, int(bar.width * g.health))
        pygame.draw.rect(surf, ui.lerp_color((235, 70, 80), (110, 230, 150), g.health), fill,
                         border_radius=6)

        ui.text(surf, f"{g.score:08d}", 60, ui.WHITE, (W - 24, 14), "topright")
        ui.text(surf, f"{g.accuracy * 100:.2f}%", 36, (215, 215, 230), (W - 24, 64), "topright")
        if g.combo:
            ui.text(surf, f"{g.combo}x", 84, ui.WHITE, (24, H - 14), "bottomleft")

        self._draw_error_meter(surf, now)

        if now < objs[0].time - self.bm.preempt:
            ui.text(surf, "Get ready!", 64, ui.WHITE, (W // 2, H // 2 - 30))
            ui.text(surf, "Pinch when the outer ring touches the circle", 30, ui.DIM,
                    (W // 2, H // 2 + 20))
        if self.autoplay:
            ui.text(surf, "AUTOPLAY", 30, (180, 180, 255), (W // 2, 26))
        else:
            status = self.app.input.status_text()
            if status:
                ui.text(surf, status, 34, (255, 190, 120), (W // 2, 30))

    def _draw_error_meter(self, surf, now):
        """Timing bar at the bottom: each tick is one hit. Left = early, right = late."""
        W, H = surf.get_size()
        g = self.game
        half = 170
        s = half / g.w50
        cx, cy = W // 2, H - 30
        for w, color in ((g.w50, (255, 210, 100)), (g.w100, (130, 230, 130)), (g.w300, (110, 200, 255))):
            pygame.draw.rect(surf, ui.lerp_color(color, (0, 0, 0), 0.4),
                             (cx - w * s, cy - 3, 2 * w * s, 6))
        pygame.draw.rect(surf, ui.WHITE, (cx - 1, cy - 12, 2, 24))
        layer = pygame.Surface((2 * half + 8, 32), pygame.SRCALPHA)
        for err, t in self.recent_errors:
            a = int(255 * min(1.0, max(0.0, 1 - (now - t) / 4000)))
            if a:
                x = int(half + 4 + max(-half, min(half, err * s)))
                pygame.draw.rect(layer, (255, 255, 255, a), (x - 1, 4, 3, 24))
        surf.blit(layer, (cx - half - 4, cy - 16))
        if self.recent_errors:
            mean = sum(e for e, _ in self.recent_errors) / len(self.recent_errors)
            mx = cx + max(-half, min(half, mean * s))
            pygame.draw.polygon(surf, ui.ACCENT, [(mx, cy - 14), (mx - 7, cy - 24), (mx + 7, cy - 24)])
        ui.text(surf, "early", 22, ui.DIM, (cx - half - 10, cy), "midright")
        ui.text(surf, "late", 22, ui.DIM, (cx + half + 10, cy), "midleft")
